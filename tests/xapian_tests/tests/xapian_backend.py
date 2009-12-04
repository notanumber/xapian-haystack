# Copyright (C) 2009 David Sauve, Trapeze.  All rights reserved.
# Based on original code by Daniel Lindsley as part of the Haystack test suite.

import cPickle as pickle
import datetime
import os
import shutil
import xapian

from django.conf import settings
from django.db import models
from django.test import TestCase

from haystack import indexes, sites, backends
from haystack.backends.xapian_backend import SearchBackend, SearchQuery, _marshal_value
from haystack.exceptions import HaystackError
from haystack.query import SearchQuerySet, SQ
from haystack.sites import SearchSite

from core.models import MockTag, MockModel, AnotherMockModel


class XapianMockModel(models.Model):
    """
    Same as tests.core.MockModel with a few extra fields for testing various
    sorting and ordering criteria.
    """
    author = models.CharField(max_length=255)
    foo = models.CharField(max_length=255, blank=True)
    pub_date = models.DateTimeField(default=datetime.datetime.now)
    tag = models.ForeignKey(MockTag)

    value = models.IntegerField(default=0)
    flag = models.BooleanField(default=True)
    slug = models.SlugField()
    popularity = models.FloatField(default=0.0)

    def __unicode__(self):
        return self.author
    
    def hello(self):
        return 'World!'


class XapianMockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(
        document=True, use_template=True, 
        template_name='search/indexes/core/mockmodel_text.txt'
    )
    name = indexes.CharField(model_attr='author')
    pub_date = indexes.DateField(model_attr='pub_date')
    value = indexes.IntegerField(model_attr='value')
    flag = indexes.BooleanField(model_attr='flag')
    slug = indexes.CharField(indexed=False, model_attr='slug')
    popularity = indexes.FloatField(model_attr='popularity')
    sites = indexes.MultiValueField()

    def prepare_sites(self, obj):
        return ['%d' % (i * obj.id) for i in xrange(1, 4)]


class XapianSearchBackendTestCase(TestCase):
    def setUp(self):
        super(XapianSearchBackendTestCase, self).setUp()
        
        self.site = SearchSite()
        self.backend = SearchBackend(site=self.site)
        self.index = XapianMockSearchIndex(XapianMockModel, backend=self.backend)
        self.site.register(XapianMockModel, XapianMockSearchIndex)
        
        self.sample_objs = []
        
        for i in xrange(1, 4):
            mock = XapianMockModel()
            mock.id = i
            mock.author = 'david%s' % i
            mock.pub_date = datetime.date(2009, 2, 25) - datetime.timedelta(days=i)
            mock.value = i * 5
            mock.flag = bool(i % 2)
            mock.slug = 'http://example.com/%d' % i
            self.sample_objs.append(mock)
            
        self.sample_objs[0].popularity = 834.0
        self.sample_objs[1].popularity = 35.5
        self.sample_objs[2].popularity = 972.0
    
    def tearDown(self):
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            shutil.rmtree(settings.HAYSTACK_XAPIAN_PATH)

        super(XapianSearchBackendTestCase, self).tearDown()
    
    def xapian_search(self, query_string):
        database = xapian.Database(settings.HAYSTACK_XAPIAN_PATH)
        if query_string:
            qp = xapian.QueryParser()
            qp.set_database(database)
            query = qp.parse_query(query_string, xapian.QueryParser.FLAG_WILDCARD)
        else:
            query = xapian.Query(query_string) # Empty query matches all
        enquire = xapian.Enquire(database)
        enquire.set_query(query)
        matches = enquire.get_mset(0, database.get_doccount())
        
        document_list = []
        
        for match in matches:
            document = match.get_document()
            app_label, module_name, pk, model_data = pickle.loads(document.get_data())
            for key, value in model_data.iteritems():
                model_data[key] = _marshal_value(value)
            model_data['id'] = u'%s.%s.%d' % (app_label, module_name, pk)
            document_list.append(model_data)

        return document_list
    
    def silly_test(self):
        
        self.backend.update(self.index, self.sample_objs)
        
        self.assertEqual(len(self.xapian_search('indexed')), 3)
        self.assertEqual(len(self.xapian_search('Indexed')), 3)
    
    def test_update(self):
        self.backend.update(self.index, self.sample_objs)
        
        self.assertEqual(len(self.xapian_search('')), 3)
        self.assertEqual([dict(doc) for doc in self.xapian_search('')], [
            {'flag': u't', 'name': u'david1', 'text': u'indexed!\n1', 'sites': u"['1', '2', '3']", 'pub_date': u'20090224000000', 'value': u'000000000005', 'id': u'tests.xapianmockmodel.1', 'slug': u'http://example.com/1', 'popularity': '\xca\x84', 'django_id': u'1', 'django_ct': u'tests.xapianmockmodel'},
            {'flag': u'f', 'name': u'david2', 'text': u'indexed!\n2', 'sites': u"['2', '4', '6']", 'pub_date': u'20090223000000', 'value': u'000000000010', 'id': u'tests.xapianmockmodel.2', 'slug': u'http://example.com/2', 'popularity': '\xb4p', 'django_id': u'2', 'django_ct': u'tests.xapianmockmodel'},
            {'flag': u't', 'name': u'david3', 'text': u'indexed!\n3', 'sites': u"['3', '6', '9']", 'pub_date': u'20090222000000', 'value': u'000000000015', 'id': u'tests.xapianmockmodel.3', 'slug': u'http://example.com/3', 'popularity': '\xcb\x98', 'django_id': u'3', 'django_ct': u'tests.xapianmockmodel'}
        ])

    def test_duplicate_update(self):
        self.backend.update(self.index, self.sample_objs)
        self.backend.update(self.index, self.sample_objs) # Duplicates should be updated, not appended -- http://github.com/notanumber/xapian-haystack/issues/#issue/6
        
        self.assertEqual(len(self.xapian_search('')), 3)

    def test_remove(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.backend.remove(self.sample_objs[0])
        self.assertEqual(len(self.xapian_search('')), 2)
        self.assertEqual([dict(doc) for doc in self.xapian_search('')], [
            {'flag': u'f', 'name': u'david2', 'text': u'indexed!\n2', 'sites': u"['2', '4', '6']", 'pub_date': u'20090223000000', 'value': u'000000000010', 'id': u'tests.xapianmockmodel.2', 'slug': u'http://example.com/2', 'popularity': '\xb4p', 'django_id': u'2', 'django_ct': u'tests.xapianmockmodel'},
            {'flag': u't', 'name': u'david3', 'text': u'indexed!\n3', 'sites': u"['3', '6', '9']", 'pub_date': u'20090222000000', 'value': u'000000000015', 'id': u'tests.xapianmockmodel.3', 'slug': u'http://example.com/3', 'popularity': '\xcb\x98', 'django_id': u'3', 'django_ct': u'tests.xapianmockmodel'}
        ])
    
    def test_clear(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.backend.clear()
        self.assertEqual(len(self.xapian_search('')), 0)
        
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.backend.clear([AnotherMockModel])
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.backend.clear([XapianMockModel])
        self.assertEqual(len(self.xapian_search('')), 0)
        
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.backend.clear([AnotherMockModel, XapianMockModel])
        self.assertEqual(len(self.xapian_search('')), 0)
    
    def test_search(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.backend.search(xapian.Query()), {'hits': 0, 'results': []})
        self.assertEqual(self.backend.search(xapian.Query(''))['hits'], 3)
        self.assertEqual([result.pk for result in self.backend.search(xapian.Query(''))['results']], [1, 2, 3])
        self.assertEqual(self.backend.search(xapian.Query('indexed'))['hits'], 3)
        self.assertEqual([result.pk for result in self.backend.search(xapian.Query(''))['results']], [1, 2, 3])
        
    def test_field_facets(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.backend.search(xapian.Query(), facets=['name']), {'hits': 0, 'results': []})
        results = self.backend.search(xapian.Query('indexed'), facets=['name'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['name'], [('david1', 1), ('david2', 1), ('david3', 1)])
    
        results = self.backend.search(xapian.Query('indexed'), facets=['flag'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['flag'], [(False, 1), (True, 2)])
        
        results = self.backend.search(xapian.Query('indexed'), facets=['sites'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['sites'], [('1', 1), ('3', 2), ('2', 2), ('4', 1), ('6', 2), ('9', 1)])
            
    def test_date_facets(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
    
        self.assertEqual(self.backend.search(xapian.Query(), date_facets={'pub_date': {'start_date': datetime.datetime(2008, 10, 26), 'end_date': datetime.datetime(2009, 3, 26), 'gap_by': 'month'}}), {'hits': 0, 'results': []})
        results = self.backend.search(xapian.Query('indexed'), date_facets={'pub_date': {'start_date': datetime.datetime(2008, 10, 26), 'end_date': datetime.datetime(2009, 3, 26), 'gap_by': 'month'}})
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['dates']['pub_date'], [
            ('2009-02-26T00:00:00', 0),
            ('2009-01-26T00:00:00', 3),
            ('2008-12-26T00:00:00', 0),
            ('2008-11-26T00:00:00', 0),
            ('2008-10-26T00:00:00', 0),
        ])
    
        results = self.backend.search(xapian.Query('indexed'), date_facets={'pub_date': {'start_date': datetime.datetime(2009, 02, 01), 'end_date': datetime.datetime(2009, 3, 15), 'gap_by': 'day', 'gap_amount': 15}})
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['dates']['pub_date'], [
            ('2009-03-03T00:00:00', 0),
            ('2009-02-16T00:00:00', 3),
            ('2009-02-01T00:00:00', 0)
        ])

    # def test_query_facets(self):
    #     self.backend.update(self.index, self.sample_objs)
    #     self.assertEqual(len(self.xapian_search('')), 3)
    # 
    #     self.assertEqual(self.backend.search(xapian.Query(), query_facets={'name': 'da*', {'hits': 0, 'results': []})
    #     results = self.backend.search(xapian.Query('index'), query_facets={'name': 'da*'})
    #     self.assertEqual(results['hits'], 3)
    #     self.assertEqual(results['facets']['queries']['name'], ('da*', 3))
    
    def test_narrow_queries(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.backend.search(xapian.Query(), narrow_queries=set([xapian.Query('XNAMEdavid1')])), {'hits': 0, 'results': []})
        results = self.backend.search(xapian.Query('indexed'), narrow_queries=set([xapian.Query('XNAMEdavid1')]))
        self.assertEqual(results['hits'], 1)
    
    def test_highlight(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.backend.search(xapian.Query(), highlight=True), {'hits': 0, 'results': []})
        self.assertEqual(self.backend.search(xapian.Query('indexed'), highlight=True)['hits'], 3)
        self.assertEqual([result.highlighted['text'] for result in self.backend.search(xapian.Query('indexed'), highlight=True)['results']], ['<em>indexed</em>!\n1', '<em>indexed</em>!\n2', '<em>indexed</em>!\n3'])
    
    def test_spelling_suggestion(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.backend.search(xapian.Query('indxe'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('indxe'))['spelling_suggestion'], 'indexed')
        
        self.assertEqual(self.backend.search(xapian.Query('indxed'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('indxed'))['spelling_suggestion'], 'indexed')
        
        self.assertEqual(self.backend.search(xapian.Query('foo'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('foo'), spelling_query='indexy')['spelling_suggestion'], 'indexed')

        self.assertEqual(self.backend.search(xapian.Query('XNAMEdavid'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('XNAMEdavid'))['spelling_suggestion'], 'david1')

    def test_more_like_this(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        results = self.backend.more_like_this(self.sample_objs[0])
        self.assertEqual(results['hits'], 2)
        self.assertEqual([result.pk for result in results['results']], [3, 2])
    
        results = self.backend.more_like_this(self.sample_objs[0], additional_query=xapian.Query('david3'))
        self.assertEqual(results['hits'], 1)
        self.assertEqual([result.pk for result in results['results']], [3])

        results = self.backend.more_like_this(self.sample_objs[0], limit_to_registered_models=True)
        self.assertEqual(results['hits'], 2)
        self.assertEqual([result.pk for result in results['results']], [3, 2])

    def test_order_by(self):
        self.backend.update(self.index, self.sample_objs)
        
        results = self.backend.search(xapian.Query(''), sort_by=['pub_date'])
        self.assertEqual([result.pk for result in results['results']], [3, 2, 1])
        
        results = self.backend.search(xapian.Query(''), sort_by=['-pub_date'])
        self.assertEqual([result.pk for result in results['results']], [1, 2, 3])
    
        results = self.backend.search(xapian.Query(''), sort_by=['id'])
        self.assertEqual([result.pk for result in results['results']], [1, 2, 3])
    
        results = self.backend.search(xapian.Query(''), sort_by=['-id'])
        self.assertEqual([result.pk for result in results['results']], [3, 2, 1])
    
        results = self.backend.search(xapian.Query(''), sort_by=['value'])
        self.assertEqual([result.pk for result in results['results']], [1, 2, 3])
    
        results = self.backend.search(xapian.Query(''), sort_by=['-value'])
        self.assertEqual([result.pk for result in results['results']], [3, 2, 1])
    
        results = self.backend.search(xapian.Query(''), sort_by=['popularity'])
        self.assertEqual([result.pk for result in results['results']], [2, 1, 3])
    
        results = self.backend.search(xapian.Query(''), sort_by=['-popularity'])
        self.assertEqual([result.pk for result in results['results']], [3, 1, 2])
    
        results = self.backend.search(xapian.Query(''), sort_by=['flag', 'id'])
        self.assertEqual([result.pk for result in results['results']], [2, 1, 3])
    
        results = self.backend.search(xapian.Query(''), sort_by=['flag', '-id'])
        self.assertEqual([result.pk for result in results['results']], [2, 3, 1])

    def test__marshal_value(self):
        self.assertEqual(_marshal_value('abc'), u'abc')
        self.assertEqual(_marshal_value(1), '000000000001')
        self.assertEqual(_marshal_value(2653), '000000002653')
        self.assertEqual(_marshal_value(25.5), '\xb2`')
        self.assertEqual(_marshal_value([1, 2, 3]), u'[1, 2, 3]')
        self.assertEqual(_marshal_value((1, 2, 3)), u'(1, 2, 3)')
        self.assertEqual(_marshal_value({'a': 1, 'c': 3, 'b': 2}), u"{'a': 1, 'c': 3, 'b': 2}")
        self.assertEqual(_marshal_value(datetime.datetime(2009, 5, 9, 16, 14)), u'20090509161400')
        self.assertEqual(_marshal_value(datetime.datetime(2009, 5, 9, 0, 0)), u'20090509000000')
        self.assertEqual(_marshal_value(datetime.datetime(1899, 5, 18, 0, 0)), u'18990518000000')
        self.assertEqual(_marshal_value(datetime.datetime(2009, 5, 18, 1, 16, 30, 250)), u'20090518011630000250')

    def test_build_schema(self):
        (content_field_name, fields) = self.backend.build_schema(self.site.all_searchfields())
        self.assertEqual(content_field_name, 'text')
        self.assertEqual(len(fields), 7)
        self.assertEqual(fields, [
            {'column': 0, 'field_name': 'name', 'type': 'text', 'multi_valued': 'false'},
            {'column': 1, 'field_name': 'text', 'type': 'text', 'multi_valued': 'false'},
            {'column': 2, 'field_name': 'popularity', 'type': 'float', 'multi_valued': 'false'},
            {'column': 3, 'field_name': 'sites', 'type': 'text', 'multi_valued': 'true'},
            {'column': 4, 'field_name': 'value', 'type': 'long', 'multi_valued': 'false'},
            {'column': 5, 'field_name': 'flag', 'type': 'boolean', 'multi_valued': 'false'},
            {'column': 6, 'field_name': 'pub_date', 'type': 'date', 'multi_valued': 'false'},
        ])

    def test_parse_query(self):
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(self.backend.parse_query('indexed').get_description(), 'Xapian::Query((indexed:(pos=1) OR Zindex:(pos=1)))')
        self.assertEqual(self.backend.parse_query('name:david').get_description(), 'Xapian::Query((XNAMEdavid1:(pos=1) OR XNAMEdavid2:(pos=1) OR XNAMEdavid3:(pos=1) OR ZXNAMEdavid:(pos=1)))')
        self.assertEqual(self.backend.parse_query('name:david1..david2').get_description(), 'Xapian::Query(VALUE_RANGE 0 david1 david2)')
        self.assertEqual(self.backend.parse_query('value:0..10').get_description(), 'Xapian::Query(VALUE_RANGE 4 000000000000 000000000010)')
        self.assertEqual(self.backend.parse_query('value:..10').get_description(), 'Xapian::Query(VALUE_RANGE 4 -02147483648 000000000010)')
        self.assertEqual(self.backend.parse_query('value:10..*').get_description(), 'Xapian::Query(VALUE_RANGE 4 000000000010 002147483647)')
        self.assertEqual(self.backend.parse_query('popularity:25.5..100.0').get_description(), 'Xapian::Query(VALUE_RANGE 2 \xb2` \xba@)')


class LiveXapianMockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr='author')
    pub_date = indexes.DateField(model_attr='pub_date')


class LiveXapianSearchQueryTestCase(TestCase):
    """
    SearchQuery specific tests
    """
    fixtures = ['initial_data.json']

    def setUp(self):
        super(LiveXapianSearchQueryTestCase, self).setUp()

        site = SearchSite()
        backend = SearchBackend(site=site)
        index = LiveXapianMockSearchIndex(MockModel, backend=backend)
        site.register(MockModel, LiveXapianMockSearchIndex)
        backend.update(index, MockModel.objects.all())

        self.sq = SearchQuery(backend=backend)

    def test_get_spelling(self):
        self.sq.add_filter(SQ(content='indxd'))
        self.assertEqual(self.sq.get_spelling_suggestion(), u'indexed')
        self.assertEqual(self.sq.get_spelling_suggestion('indxd'), u'indexed')

    def test_startswith(self):
        self.sq.add_filter(SQ(name__startswith='da*'))
        self.assertEqual([result.pk for result in self.sq.get_results()], [1, 2, 3])

        self.sq = SearchQuery(backend=SearchBackend())
        self.sq.add_filter(SQ(name__startswith='daniel1'))
        self.assertEqual([result.pk for result in self.sq.get_results()], [1])

    def test_build_query_gt(self):
        self.sq.add_filter(SQ(name__gt='a'))
        self.assertEqual(self.sq.build_query().get_description(), u'Xapian::Query(VALUE_RANGE 2 a zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz)')

    def test_build_query_lt(self):
        self.sq.add_filter(SQ(name__lt='m'))
        self.assertEqual(self.sq.build_query().get_description(), u'Xapian::Query(VALUE_RANGE 2 a m)')

    def test_build_query_multiple_filter_types(self):
        self.sq.add_filter(SQ(content='why'))
    #     self.sq.add_filter(SQ(pub_date__lte='2009-02-10 01:59:00'))
        self.sq.add_filter(SQ(name__gt='david'))
    #     self.sq.add_filter(SQ(created__lt='2009-02-12 12:13:00'))
    #     self.sq.add_filter(SQ(title__gte='B'))
        self.sq.add_filter(SQ(id__in=[1, 2, 3]))
        self.assertEqual(self.sq.build_query().get_description(), u'Xapian::Query((why AND VALUE_RANGE 2 david zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz AND (XID1 OR XID2 OR XID3)))')

    def test_log_query(self):
        backends.reset_search_queries()
        self.assertEqual(len(backends.queries), 0)
    
        # Stow.
        old_debug = settings.DEBUG
        settings.DEBUG = False
    
        len(self.sq.get_results())
        self.assertEqual(len(backends.queries), 0)
    
        settings.DEBUG = True
        # Redefine it to clear out the cached results.
        self.sq = SearchQuery(backend=SearchBackend())
        self.sq.add_filter(SQ(name='bar'))
        len(self.sq.get_results())
        self.assertEqual(len(backends.queries), 1)
        self.assertEqual(backends.queries[0]['query_string'].get_description(), 'Xapian::Query(XNAMEbar)')
    
        # And again, for good measure.
        self.sq = SearchQuery(backend=SearchBackend())
        self.sq.add_filter(SQ(name='bar'))
        self.sq.add_filter(SQ(text='moof'))
        len(self.sq.get_results())
        self.assertEqual(len(backends.queries), 2)
        self.assertEqual(backends.queries[0]['query_string'].get_description(), u'Xapian::Query(XNAMEbar)')
        self.assertEqual(backends.queries[1]['query_string'].get_description(), u'Xapian::Query((XNAMEbar AND XTEXTmoof))')
    
        # Restore.
        settings.DEBUG = old_debug
