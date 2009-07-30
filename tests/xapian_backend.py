# Copyright (C) 2007 David Sauve
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import cPickle as pickle
import datetime
import os
import xapian

from django.conf import settings
from django.utils.encoding import force_unicode
from django.test import TestCase

from haystack import indexes, sites
from haystack.backends.xapian_backend import SearchBackend

from xapian_haystack.tests.models import MockModel, AnotherMockModel
from xapian_haystack.xapian_backend import DEFAULT_MAX_RESULTS


class XapianMockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True, use_template=True)
    name = indexes.CharField(model_attr='author')
    pub_date = indexes.DateField(model_attr='pub_date')
    value = indexes.IntegerField(model_attr='value')
    flag = indexes.BooleanField(model_attr='flag')


class XapianSearchSite(sites.SearchSite):
    pass


class XapianSearchBackendTestCase(TestCase):
    def setUp(self):
        super(XapianSearchBackendTestCase, self).setUp()
        
        temp_path = os.path.join('tmp', 'test_xapian_query')
        self.old_xapian_path = getattr(settings, 'HAYSTACK_XAPIAN_PATH', temp_path)
        settings.HAYSTACK_XAPIAN_PATH = temp_path
        
        self.site = XapianSearchSite()
        self.sb = SearchBackend(site=self.site)
        self.msi = XapianMockSearchIndex(MockModel, backend=self.sb)
        self.site.register(MockModel, XapianMockSearchIndex)
        
        self.sample_objs = []
        
        for i in xrange(1, 4):
            mock = MockModel()
            mock.id = i
            mock.author = 'david%s' % i
            mock.pub_date = datetime.date(2009, 2, 25) - datetime.timedelta(days=i)
            mock.value = i * 5
            mock.flag = bool(i % 2)
            self.sample_objs.append(mock)
    
    def tearDown(self):
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            index_files = os.listdir(settings.HAYSTACK_XAPIAN_PATH)
            
            for index_file in index_files:
                os.remove(os.path.join(settings.HAYSTACK_XAPIAN_PATH, index_file))
            
            os.removedirs(settings.HAYSTACK_XAPIAN_PATH)
        
        settings.HAYSTACK_XAPIAN_PATH = self.old_xapian_path
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
        matches = enquire.get_mset(0, DEFAULT_MAX_RESULTS)
        
        document_list = []
        
        for match in matches:
            document = match.get_document()
            object_data = pickle.loads(document.get_data())
            for key, value in object_data.iteritems():
                object_data[key] = self.sb._from_python(value)
            object_data['id'] = force_unicode(document.get_value(0))
            document_list.append(object_data)
        
        return document_list
    
    def test_update(self):
        self.sb.update(self.msi, self.sample_objs)
        self.sb.update(self.msi, self.sample_objs) # Duplicates should be updated, not appended -- http://github.com/notanumber/xapian-haystack/issues/#issue/6
        
        self.assertEqual(len(self.xapian_search('')), 3)
        self.assertEqual([dict(doc) for doc in self.xapian_search('')], [{'flag': u't', 'name': u'david1', 'text': u'Indexed!\n1', 'pub_date': u'20090224000000', 'value': u'5', 'id': u'tests.mockmodel.1'}, {'flag': u'f', 'name': u'david2', 'text': u'Indexed!\n2', 'pub_date': u'20090223000000', 'value': u'10', 'id': u'tests.mockmodel.2'}, {'flag': u't', 'name': u'david3', 'text': u'Indexed!\n3', 'pub_date': u'20090222000000', 'value': u'15', 'id': u'tests.mockmodel.3'}])
    
    def test_remove(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.sb.remove(self.sample_objs[0])
        self.assertEqual(len(self.xapian_search('')), 2)
        self.assertEqual([dict(doc) for doc in self.xapian_search('')], [{'flag': u'f', 'name': u'david2', 'text': u'Indexed!\n2', 'pub_date': u'20090223000000', 'value': u'10', 'id': u'tests.mockmodel.2'}, {'flag': u't', 'name': u'david3', 'text': u'Indexed!\n3', 'pub_date': u'20090222000000', 'value': u'15', 'id': u'tests.mockmodel.3'}])
    
    def test_clear(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.sb.clear()
        self.assertEqual(len(self.xapian_search('')), 0)
        
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.sb.clear([AnotherMockModel])
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.sb.clear([MockModel])
        self.assertEqual(len(self.xapian_search('')), 0)
        
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.sb.clear([AnotherMockModel, MockModel])
        self.assertEqual(len(self.xapian_search('')), 0)
    
    def test_search(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        # Empty query
        self.assertEqual(self.sb.search(''), {'hits': 0, 'results': []})
        
        # Wildcard -- All
        self.assertEqual(self.sb.search('*')['hits'], 3)
        self.assertEqual([result.pk for result in self.sb.search('*')['results']], [u'1', u'2', u'3'])
        
        # NOT operator
        self.assertEqual([result.pk for result in self.sb.search('NOT author:david1')['results']], [u'1', u'2', u'3'])
    
    def test_field_facets(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.sb.search('', facets=['name']), {'hits': 0, 'results': []})
        results = self.sb.search('index', facets=['name'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['name'], [('david1', 1), ('david2', 1), ('david3', 1)])
    
    #     self.assertEqual(self.sb.search('', date_facets={'pub_date': {'start_date': datetime.date(2008, 2, 26), 'end_date': datetime.date(2008, 2, 26), 'gap': '/MONTH'}}), [])
    #     results = self.sb.search('Index*', date_facets={'pub_date': {'start_date': datetime.date(2008, 2, 26), 'end_date': datetime.date(2008, 2, 26), 'gap': '/MONTH'}})
    #     self.assertEqual(results['hits'], 3)
    #     self.assertEqual(results['facets'], {})
    #
    #     self.assertEqual(self.sb.search('', query_facets={'name': '[* TO e]'}), [])
    #     results = self.sb.search('Index*', query_facets={'name': '[* TO e]'})
    #     self.assertEqual(results['hits'], 3)
    #     self.assertEqual(results['facets'], {})
    
    def test_narrow_queries(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.sb.search('', narrow_queries=['name:david1']), {'hits': 0, 'results': []})
        results = self.sb.search('index', narrow_queries=['name:david1'])
        self.assertEqual(results['hits'], 1)
    
    def test_highlight(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.sb.search('', highlight=True), {'hits': 0, 'results': []})
        self.assertEqual(self.sb.search('Index', highlight=True)['hits'], 3)
        self.assertEqual([result.highlighted['text'] for result in self.sb.search('Index', highlight=True)['results']], ['<em>Index</em>ed!\n1', '<em>Index</em>ed!\n2', '<em>Index</em>ed!\n3'])
    
    def test_spelling_suggestion(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        self.assertEqual(self.sb.search('indxe')['hits'], 0)
        self.assertEqual(self.sb.search('indxe')['spelling_suggestion'], 'indexed')
        
        self.assertEqual(self.sb.search('indxed')['hits'], 0)
        self.assertEqual(self.sb.search('indxed')['spelling_suggestion'], 'indexed')
    
    def test_stemming(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        results = self.sb.search('index')
        self.assertEqual(results['hits'], 3)
        
        results = self.sb.search('indexing')
        self.assertEqual(results['hits'], 3)
    
    def test_more_like_this(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(len(self.xapian_search('')), 3)
        
        results = self.sb.more_like_this(self.sample_objs[0])
        self.assertEqual(results['hits'], 2)
        self.assertEqual([result.pk for result in results['results']], [u'3', u'2'])
    
    def test_document_count(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assertEqual(self.sb.document_count(), 3)
    
    def test_delete_index(self):
        self.sb.update(self.msi, self.sample_objs)
        self.assert_(self.sb.document_count() > 0)
        
        self.sb.delete_index()
        self.assertEqual(self.sb.document_count(), 0)
    
    def test_order_by(self):
        self.sb.update(self.msi, self.sample_objs)
        
        results = self.sb.search('*', sort_by=['pub_date'])
        self.assertEqual([result.pk for result in results['results']], [u'1', u'2', u'3'])
        
        results = self.sb.search('*', sort_by=['-pub_date'])
        self.assertEqual([result.pk for result in results['results']], [u'3', u'2', u'1'])
        
        results = self.sb.search('*', sort_by=['id'])
        self.assertEqual([result.pk for result in results['results']], [u'3', u'2', u'1'])
        
        results = self.sb.search('*', sort_by=['-id'])
        self.assertEqual([result.pk for result in results['results']], [u'1', u'2', u'3'])
        
        results = self.sb.search('*', sort_by=['value'])
        self.assertEqual([result.pk for result in results['results']], [u'3', u'2', u'1'])
        
        results = self.sb.search('*', sort_by=['-value'])
        self.assertEqual([result.pk for result in results['results']], [u'1', u'2', u'3'])
        
        results = self.sb.search('*', sort_by=['flag', 'id'])
        self.assertEqual([result.pk for result in results['results']], [u'3', u'1', u'2'])
        
        results = self.sb.search('*', sort_by=['flag', '-id'])
        self.assertEqual([result.pk for result in results['results']], [u'1', u'3', u'2'])
    
    def test__from_python(self):
        self.assertEqual(self.sb._from_python('abc'), u'abc')
        self.assertEqual(self.sb._from_python(1), u'1')
        self.assertEqual(self.sb._from_python(2653), u'2653')
        self.assertEqual(self.sb._from_python(25.5), u'25.5')
        self.assertEqual(self.sb._from_python([1, 2, 3]), u'[1, 2, 3]')
        self.assertEqual(self.sb._from_python((1, 2, 3)), u'(1, 2, 3)')
        self.assertEqual(self.sb._from_python({'a': 1, 'c': 3, 'b': 2}), u"{'a': 1, 'c': 3, 'b': 2}")
        self.assertEqual(self.sb._from_python(datetime.datetime(2009, 5, 9, 16, 14)), u'20090509161400')
        self.assertEqual(self.sb._from_python(datetime.datetime(2009, 5, 9, 0, 0)), u'20090509000000')
        self.assertEqual(self.sb._from_python(datetime.datetime(1899, 5, 18, 0, 0)), u'18990518000000')
        self.assertEqual(self.sb._from_python(datetime.datetime(2009, 5, 18, 1, 16, 30, 250)), u'20090518011630000250')
