from __future__ import unicode_literals

import datetime
import sys
import xapian
import subprocess
import os

from django.db import models
from django.test import TestCase
from django.db.models.loading import get_model

from haystack import connections
from haystack import indexes
from haystack.backends.xapian_backend import InvalidIndexError, _term_to_xapian_value
from haystack.models import SearchResult
from haystack.utils.loading import UnifiedIndex

from ...core.models import AnotherMockModel, MockTag


class XapianMockSearchResult(SearchResult):
    def __init__(self, app_label, model_name, pk, score, **kwargs):
        super(XapianMockSearchResult, self).__init__(app_label, model_name, pk, score, **kwargs)
        self._model = get_model('xapian_tests', model_name)


def get_terms(backend, *args):
    result = subprocess.check_output(['delve'] + list(args) + [backend.path],
                                     env=os.environ.copy()).decode('utf-8')
    result = result.split(": ")[1].strip()
    return result.split(" ")


def pks(results):
    return [result.pk for result in results]


class XapianMockModel(models.Model):
    """
    Same as tests.core.MockModel with a few extra fields for testing various
    sorting and ordering criteria.
    """
    author = models.CharField(max_length=255)
    foo = models.CharField(max_length=255, blank=True)
    pub_date = models.DateTimeField(default=datetime.datetime.now)
    exp_date = models.DateTimeField(default=datetime.datetime.now)
    tag = models.ForeignKey(MockTag)

    value = models.IntegerField(default=0)
    flag = models.BooleanField(default=True)
    slug = models.SlugField()
    popularity = models.FloatField(default=0.0)
    url = models.URLField()

    def __unicode__(self):
        return self.author


class XapianMockSearchIndex(indexes.SearchIndex):
    text = indexes.CharField(
        document=True, use_template=True,
        template_name='search/indexes/core/mockmodel_text.txt'
    )
    name = indexes.CharField(model_attr='author', faceted=True)
    pub_date = indexes.DateField(model_attr='pub_date')
    exp_date = indexes.DateField(model_attr='exp_date')
    value = indexes.IntegerField(model_attr='value')
    flag = indexes.BooleanField(model_attr='flag')
    slug = indexes.CharField(indexed=False, model_attr='slug')
    popularity = indexes.FloatField(model_attr='popularity')
    month = indexes.CharField(indexed=False)
    url = indexes.CharField(model_attr='url')
    empty = indexes.CharField()

    # Various MultiValueFields
    sites = indexes.MultiValueField()
    tags = indexes.MultiValueField()
    keys = indexes.MultiValueField()
    titles = indexes.MultiValueField()

    def get_model(self):
        return XapianMockModel

    def prepare_sites(self, obj):
        return ['%d' % (i * obj.id) for i in range(1, 4)]

    def prepare_tags(self, obj):
        if obj.id == 1:
            return ['a', 'b', 'c']
        elif obj.id == 2:
            return ['ab', 'bc', 'cd']
        else:
            return ['an', 'to', 'or']

    def prepare_keys(self, obj):
        return [i * obj.id for i in range(1, 4)]

    def prepare_titles(self, obj):
        if obj.id == 1:
            return ['object one title one', 'object one title two']
        elif obj.id == 2:
            return ['object two title one', 'object two title two']
        else:
            return ['object three title one', 'object three title two']

    def prepare_month(self, obj):
        return '%02d' % obj.pub_date.month

    def prepare_empty(self, obj):
        return ''


class XapianSimpleMockIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True)
    author = indexes.CharField(model_attr='author')
    url = indexes.CharField()
    non_anscii = indexes.CharField()
    funny_text = indexes.CharField()

    datetime = indexes.DateTimeField(model_attr='pub_date')
    date = indexes.DateField()

    number = indexes.IntegerField()
    float_number = indexes.FloatField()
    decimal_number = indexes.DecimalField()

    multi_value = indexes.MultiValueField()

    def get_model(self):
        return XapianMockModel

    def prepare_text(self, obj):
        return 'this_is_a_word inside a big text'

    def prepare_author(self, obj):
        return 'david holland'

    def prepare_url(self, obj):
        return 'http://example.com/1/'

    def prepare_non_anscii(self, obj):
        return 'thsi sdas das corrup\xe7\xe3o das'

    def prepare_funny_text(self, obj):
        return 'this-text has funny.words!!'

    def prepare_datetime(self, obj):
        return datetime.datetime(2009, 2, 25, 1, 1, 1)

    def prepare_date(self, obj):
        return datetime.date(2008, 8, 8)

    def prepare_number(self, obj):
        return 123456789

    def prepare_float_number(self, obj):
        return 123.123456789

    def prepare_decimal_number(self, obj):
        return '22.34'

    def prepare_multi_value(self, obj):
        return ['tag', 'tag-tag', 'tag-tag-tag']


class XapianNGramIndex(indexes.SearchIndex):
    text = indexes.CharField(model_attr='author', document=True)
    ngram = indexes.NgramField(model_attr='author')

    def get_model(self):
        return XapianMockModel


class XapianEdgeNGramIndex(indexes.SearchIndex):
    text = indexes.CharField(model_attr='author', document=True)
    edge_ngram = indexes.EdgeNgramField(model_attr='author')

    def get_model(self):
        return XapianMockModel


class HaystackBackendTestCase(object):
    """
    Abstract TestCase that implements an hack to ensure `connections`
    has the right index

    It has a method get_index() that returns a SearchIndex
    that must be overwritten.
    """
    def get_index(self):
        raise NotImplementedError

    def get_objects(self):
        raise NotImplementedError

    def setUp(self):
        self.old_ui = connections['default'].get_unified_index()
        self.ui = UnifiedIndex()
        self.index = self.get_index()
        self.ui.build(indexes=[self.index])
        self.backend = connections['default'].get_backend()
        connections['default']._index = self.ui

    def tearDown(self):
        self.backend.clear()
        connections['default']._index = self.old_ui


class BackendIndexationTestCase(HaystackBackendTestCase, TestCase):
    """
    Tests indexation behavior.

    Tests related to how the backend indexes terms,
    values, and others go here.
    """

    def get_index(self):
        return XapianSimpleMockIndex()

    def setUp(self):
        super(BackendIndexationTestCase, self).setUp()
        mock = XapianMockModel()
        mock.id = 1
        mock.author = u'david'
        self.backend.update(self.index, [mock])

    def test_app_is_not_split(self):
        """
        Tests that the app path is not split
        and added as independent terms.
        """
        terms = get_terms(self.backend, '-a')

        self.assertFalse('tests' in terms)
        self.assertFalse('Ztest' in terms)

    def test_app_is_not_indexed(self):
        """
        Tests that the app path is not indexed.
        """
        terms = get_terms(self.backend, '-a')

        self.assertFalse('tests.xapianmockmodel.1' in terms)
        self.assertFalse('xapianmockmodel' in terms)
        self.assertFalse('tests' in terms)

    def test_fields_exist(self):
        """
        Tests that all fields are in the database
        """
        terms = get_terms(self.backend, '-a')
        for field in ['author', 'datetime', 'text', 'url']:
            is_inside = False
            for term in terms:
                if term.startswith("X%s" % field.upper()):
                    is_inside = True
                    break
            self.assertTrue(is_inside, field)

    def test_text_field(self):
        terms = get_terms(self.backend, '-a')
        self.assertTrue('this_is_a_word' in terms)
        self.assertTrue('Zthis_is_a_word' in terms)
        self.assertTrue('ZXTEXTthis_is_a_word' in terms)
        self.assertTrue('XTEXTthis_is_a_word' in terms)

        self.assertFalse('^this_is_a_word inside a big text$' in terms)

    def test_text_posting(self):
        """
        Tests that text is correctly positioned in the document
        """
        expected_order = ['^', 'this_is_a_word', 'inside', 'a', 'big', 'text', '$']

        def get_positions(term):
            """
            Uses delve to get
            the positions of the term in the first document.
            """
            return sorted([int(pos) for pos in get_terms(self.backend, '-r1', '-tXTEXT%s' % term)])

        # confirms expected_order
        previous_position = get_positions(expected_order[0])
        for term in expected_order[1:]:
            pos = get_positions(term)
            # only two positions per term
            # (one from term_generator, one from literal text)
            self.assertEqual(len(pos), 2)

            self.assertEqual(pos[0] - 1, previous_position[0])
            self.assertEqual(pos[1] - 1, previous_position[1])
            previous_position[0] += 1
            previous_position[1] += 1

    def test_author_field(self):
        terms = get_terms(self.backend, '-a')

        self.assertTrue('XAUTHORdavid' in terms)
        self.assertTrue('ZXAUTHORdavid' in terms)
        self.assertTrue('Zdavid' in terms)
        self.assertTrue('david' in terms)

    def test_funny_text_field(self):
        terms = get_terms(self.backend, '-r1')
        self.assertTrue('this-text' in terms)

    def test_datetime_field(self):
        terms = get_terms(self.backend, '-a')

        self.assertFalse('XDATETIME20090225000000' in terms)
        self.assertFalse('ZXDATETIME20090225000000' in terms)
        self.assertFalse('20090225000000' in terms)

        self.assertTrue('XDATETIME2009-02-25' in terms)
        self.assertTrue('2009-02-25' in terms)
        self.assertTrue('01:01:01' in terms)
        self.assertTrue('XDATETIME01:01:01' in terms)

    def test_date_field(self):
        terms = get_terms(self.backend, '-a')

        self.assertTrue('XDATE2008-08-08' in terms)
        self.assertTrue('2008-08-08' in terms)
        self.assertFalse('XDATE00:00:00' in terms)
        self.assertFalse('00:00:00' in terms)

    def test_url_field(self):
        terms = get_terms(self.backend, '-a')
        self.assertTrue('http://example.com/1/' in terms)

    def test_integer_field(self):
        terms = get_terms(self.backend, '-a')
        self.assertTrue('123456789' in terms)
        self.assertTrue('XNUMBER123456789' in terms)
        self.assertFalse('ZXNUMBER123456789' in terms)

    def test_float_field(self):
        terms = get_terms(self.backend, '-a')
        self.assertTrue('123.123456789' in terms)
        self.assertTrue('XFLOAT_NUMBER123.123456789' in terms)
        self.assertFalse('ZXFLOAT_NUMBER123.123456789' in terms)

    def test_decimal_field(self):
        terms = get_terms(self.backend, '-a')
        self.assertTrue('22.34' in terms)
        self.assertTrue('XDECIMAL_NUMBER22.34' in terms)
        self.assertFalse('ZXDECIMAL_NUMBER22.34' in terms)

    def test_multivalue_field(self):
        """
        Regression test for #103
        """
        terms = get_terms(self.backend, '-a')
        self.assertTrue('tag' in terms)
        self.assertTrue('tag-tag' in terms)
        self.assertTrue('tag-tag-tag' in terms)

        self.assertTrue('XMULTI_VALUEtag' in terms)
        self.assertTrue('XMULTI_VALUEtag-tag' in terms)
        self.assertTrue('XMULTI_VALUEtag-tag-tag' in terms)

    def test_non_ascii_chars(self):
        terms = get_terms(self.backend, '-a')
        self.assertIn('corrup\xe7\xe3o', terms)


class BackendFeaturesTestCase(HaystackBackendTestCase, TestCase):
    """
    Tests supported features on the backend side.

    Tests to features implemented on the backend
    go here.
    """

    def get_index(self):
        return XapianMockSearchIndex()

    def setUp(self):
        super(BackendFeaturesTestCase, self).setUp()

        self.sample_objs = []

        for i in range(1, 4):
            mock = XapianMockModel()
            mock.id = i
            mock.author = 'david%s' % i
            mock.pub_date = datetime.date(2009, 2, 25) - datetime.timedelta(days=i)
            mock.exp_date = datetime.date(2009, 2, 23) + datetime.timedelta(days=i)
            mock.value = i * 5
            mock.flag = bool(i % 2)
            mock.slug = 'http://example.com/%d/' % i
            mock.url = 'http://example.com/%d/' % i
            self.sample_objs.append(mock)

        self.sample_objs[0].popularity = 834.0
        self.sample_objs[1].popularity = 35.5
        self.sample_objs[2].popularity = 972.0

        self.backend.update(self.index, self.sample_objs)

    def test_update(self):
        self.assertEqual(pks(self.backend.search(xapian.Query(''))['results']),
                         [1, 2, 3])

    def test_duplicate_update(self):
        """
        Regression test for #6.
        """
        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(self.backend.document_count(), 3)

    def test_remove(self):
        self.backend.remove(self.sample_objs[0])
        self.assertEqual(pks(self.backend.search(xapian.Query(''))['results']),
                         [2, 3])

    def test_clear(self):
        self.backend.clear()
        self.assertEqual(self.backend.document_count(), 0)

        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(self.backend.document_count(), 3)

        self.backend.clear([AnotherMockModel])
        self.assertEqual(self.backend.document_count(), 3)

        self.backend.clear([XapianMockModel])
        self.assertEqual(self.backend.document_count(), 0)

        self.backend.update(self.index, self.sample_objs)
        self.assertEqual(self.backend.document_count(), 3)

        self.backend.clear([AnotherMockModel, XapianMockModel])
        self.assertEqual(self.backend.document_count(), 0)

    def test_search(self):
        # no match query
        self.assertEqual(self.backend.search(xapian.Query()), {'hits': 0, 'results': []})
        # all match query
        self.assertEqual(pks(self.backend.search(xapian.Query(''))['results']),
                         [1, 2, 3])

        # Other `result_class`
        self.assertTrue(
            isinstance(self.backend.search(xapian.Query('indexed'), result_class=XapianMockSearchResult)['results'][0],
                       XapianMockSearchResult))

    def test_search_field_with_punctuation(self):
        self.assertEqual(pks(self.backend.search(xapian.Query('http://example.com/1/'))['results']),
                         [1])

    def test_search_by_mvf(self):
        self.assertEqual(self.backend.search(xapian.Query('ab'))['hits'], 1)
        self.assertEqual(self.backend.search(xapian.Query('b'))['hits'], 1)
        self.assertEqual(self.backend.search(xapian.Query('to'))['hits'], 1)
        self.assertEqual(self.backend.search(xapian.Query('one'))['hits'], 3)

    def test_field_facets(self):
        self.assertEqual(self.backend.search(xapian.Query(), facets=['name']),
                         {'hits': 0, 'results': []})

        results = self.backend.search(xapian.Query('indexed'), facets=['name'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['name'],
                         [('david1', 1), ('david2', 1), ('david3', 1)])

        results = self.backend.search(xapian.Query('indexed'), facets=['flag'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['flag'],
                         [(False, 1), (True, 2)])

        results = self.backend.search(xapian.Query('indexed'), facets=['sites'])
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['fields']['sites'],
                         [('1', 1), ('3', 2), ('2', 2), ('4', 1), ('6', 2), ('9', 1)])

    def test_raise_index_error_on_wrong_field(self):
        """
        Regression test for #109.
        """
        self.assertRaises(InvalidIndexError, self.backend.search, xapian.Query(''), facets=['dsdas'])

    def test_date_facets(self):
        facets = {'pub_date': {'start_date': datetime.datetime(2008, 10, 26),
                               'end_date': datetime.datetime(2009, 3, 26),
                               'gap_by': 'month'}}

        self.assertEqual(self.backend.search(xapian.Query(), date_facets=facets),
                         {'hits': 0, 'results': []})

        results = self.backend.search(xapian.Query('indexed'), date_facets=facets)
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['dates']['pub_date'], [
            ('2009-02-26T00:00:00', 0),
            ('2009-01-26T00:00:00', 3),
            ('2008-12-26T00:00:00', 0),
            ('2008-11-26T00:00:00', 0),
            ('2008-10-26T00:00:00', 0),
        ])

        facets = {'pub_date': {'start_date': datetime.datetime(2009, 2, 1),
                               'end_date': datetime.datetime(2009, 3, 15),
                               'gap_by': 'day',
                               'gap_amount': 15}}
        results = self.backend.search(xapian.Query('indexed'), date_facets=facets)
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['dates']['pub_date'], [
            ('2009-03-03T00:00:00', 0),
            ('2009-02-16T00:00:00', 3),
            ('2009-02-01T00:00:00', 0)
        ])

    def test_query_facets(self):
        self.assertEqual(self.backend.search(xapian.Query(), query_facets={'name': 'da*'}),
                         {'hits': 0, 'results': []})

        results = self.backend.search(xapian.Query('indexed'), query_facets={'name': 'da*'})
        self.assertEqual(results['hits'], 3)
        self.assertEqual(results['facets']['queries']['name'], ('da*', 3))

    def test_narrow_queries(self):
        self.assertEqual(self.backend.search(xapian.Query(), narrow_queries={'name:david1'}),
                         {'hits': 0, 'results': []})
        results = self.backend.search(xapian.Query('indexed'), narrow_queries={'name:david1'})
        self.assertEqual(results['hits'], 1)

    def test_highlight(self):
        self.assertEqual(self.backend.search(xapian.Query(), highlight=True),
                         {'hits': 0, 'results': []})
        self.assertEqual(self.backend.search(xapian.Query('indexed'), highlight=True)['hits'], 3)

        results = self.backend.search(xapian.Query('indexed'), highlight=True)['results']
        self.assertEqual([result.highlighted['text'] for result in results],
                         ['<em>indexed</em>!\n1', '<em>indexed</em>!\n2', '<em>indexed</em>!\n3'])

    def test_spelling_suggestion(self):
        self.assertEqual(self.backend.search(xapian.Query('indxe'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('indxe'))['spelling_suggestion'],
                         'indexed')

        self.assertEqual(self.backend.search(xapian.Query('indxed'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('indxed'))['spelling_suggestion'],
                         'indexed')

        self.assertEqual(self.backend.search(xapian.Query('foo'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('foo'), spelling_query='indexy')['spelling_suggestion'],
                         'indexed')

        self.assertEqual(self.backend.search(xapian.Query('XNAMEdavid'))['hits'], 0)
        self.assertEqual(self.backend.search(xapian.Query('XNAMEdavid'))['spelling_suggestion'],
                         'david1')

    def test_more_like_this(self):
        results = self.backend.more_like_this(self.sample_objs[0])

        self.assertEqual(pks(results['results']), [3, 2])

        results = self.backend.more_like_this(self.sample_objs[0],
                                              additional_query=xapian.Query('david3'))

        self.assertEqual(pks(results['results']), [3])

        results = self.backend.more_like_this(self.sample_objs[0],
                                              limit_to_registered_models=True)

        self.assertEqual(pks(results['results']), [3, 2])

        # Other `result_class`
        result = self.backend.more_like_this(self.sample_objs[0],
                                             result_class=XapianMockSearchResult)
        self.assertTrue(isinstance(result['results'][0], XapianMockSearchResult))

    def test_order_by(self):
        results = self.backend.search(xapian.Query(''), sort_by=['pub_date'])
        self.assertEqual(pks(results['results']), [3, 2, 1])

        results = self.backend.search(xapian.Query(''), sort_by=['-pub_date'])
        self.assertEqual(pks(results['results']), [1, 2, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['exp_date'])
        self.assertEqual(pks(results['results']), [1, 2, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['-exp_date'])
        self.assertEqual(pks(results['results']), [3, 2, 1])

        results = self.backend.search(xapian.Query(''), sort_by=['id'])
        self.assertEqual(pks(results['results']), [1, 2, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['-id'])
        self.assertEqual(pks(results['results']), [3, 2, 1])

        results = self.backend.search(xapian.Query(''), sort_by=['value'])
        self.assertEqual(pks(results['results']), [1, 2, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['-value'])
        self.assertEqual(pks(results['results']), [3, 2, 1])

        results = self.backend.search(xapian.Query(''), sort_by=['popularity'])
        self.assertEqual(pks(results['results']), [2, 1, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['-popularity'])
        self.assertEqual(pks(results['results']), [3, 1, 2])

        results = self.backend.search(xapian.Query(''), sort_by=['flag', 'id'])
        self.assertEqual(pks(results['results']), [2, 1, 3])

        results = self.backend.search(xapian.Query(''), sort_by=['flag', '-id'])
        self.assertEqual(pks(results['results']), [2, 3, 1])

    def test_verify_type(self):
        self.assertEqual([result.month for result in self.backend.search(xapian.Query(''))['results']],
                         ['02', '02', '02'])

    def test_term_to_xapian_value(self):
        self.assertEqual(_term_to_xapian_value('abc', 'text'), 'abc')
        self.assertEqual(_term_to_xapian_value(1, 'integer'), '000000000001')
        self.assertEqual(_term_to_xapian_value(2653, 'integer'), '000000002653')
        self.assertEqual(_term_to_xapian_value(25.5, 'float'), b'\xb2`')
        self.assertEqual(_term_to_xapian_value([1, 2, 3], 'text'), '[1, 2, 3]')
        self.assertEqual(_term_to_xapian_value((1, 2, 3), 'text'), '(1, 2, 3)')
        self.assertEqual(_term_to_xapian_value({'a': 1, 'c': 3, 'b': 2}, 'text'),
                         "{u'a': 1, u'c': 3, u'b': 2}")
        self.assertEqual(_term_to_xapian_value(datetime.datetime(2009, 5, 9, 16, 14), 'datetime'),
                         '20090509161400')
        self.assertEqual(_term_to_xapian_value(datetime.datetime(2009, 5, 9, 0, 0), 'date'),
                         '20090509000000')
        self.assertEqual(_term_to_xapian_value(datetime.datetime(1899, 5, 18, 0, 0), 'date'),
                         '18990518000000')

    def test_build_schema(self):
        search_fields = connections['default'].get_unified_index().all_searchfields()
        (content_field_name, fields) = self.backend.build_schema(search_fields)

        self.assertEqual(content_field_name, 'text')
        self.assertEqual(len(fields), 14 + 3)
        self.assertEqual(fields, [
            {'column': 0, 'type': 'text', 'field_name': 'id', 'multi_valued': 'false'},
            {'column': 1, 'type': 'integer', 'field_name': 'django_id', 'multi_valued': 'false'},
            {'column': 2, 'type': 'text', 'field_name': 'django_ct', 'multi_valued': 'false'},
            {'column': 3, 'type': 'text', 'field_name': 'empty', 'multi_valued': 'false'},
            {'column': 4, 'type': 'date', 'field_name': 'exp_date', 'multi_valued': 'false'},
            {'column': 5, 'type': 'boolean', 'field_name': 'flag', 'multi_valued': 'false'},
            {'column': 6, 'type': 'text', 'field_name': 'keys', 'multi_valued': 'true'},
            {'column': 7, 'type': 'text', 'field_name': 'name', 'multi_valued': 'false'},
            {'column': 8, 'type': 'text', 'field_name': 'name_exact', 'multi_valued': 'false'},
            {'column': 9, 'type': 'float', 'field_name': 'popularity', 'multi_valued': 'false'},
            {'column': 10, 'type': 'date', 'field_name': 'pub_date', 'multi_valued': 'false'},
            {'column': 11, 'type': 'text', 'field_name': 'sites', 'multi_valued': 'true'},
            {'column': 12, 'type': 'text', 'field_name': 'tags', 'multi_valued': 'true'},
            {'column': 13, 'type': 'text', 'field_name': 'text', 'multi_valued': 'false'},
            {'column': 14, 'type': 'text', 'field_name': 'titles', 'multi_valued': 'true'},
            {'column': 15, 'type': 'text', 'field_name': 'url', 'multi_valued': 'false'},
            {'column': 16, 'type': 'integer', 'field_name': 'value', 'multi_valued': 'false'}
        ])

    def test_parse_query(self):
        self.assertEqual(str(self.backend.parse_query('indexed')),
                         'Xapian::Query(Zindex:(pos=1))')
        self.assertEqual(str(self.backend.parse_query('name:david')),
                         'Xapian::Query(ZXNAMEdavid:(pos=1))')

        if xapian.minor_version() >= 2:
            self.assertEqual(str(self.backend.parse_query('name:da*')),
                             'Xapian::Query(('
                             'XNAMEdavid1:(pos=1) SYNONYM '
                             'XNAMEdavid2:(pos=1) SYNONYM '
                             'XNAMEdavid3:(pos=1)))')
        else:
            self.assertEqual(str(self.backend.parse_query('name:da*')),
                             'Xapian::Query(('
                             'XNAMEdavid1:(pos=1) OR '
                             'XNAMEdavid2:(pos=1) OR '
                             'XNAMEdavid3:(pos=1)))')

        self.assertEqual(str(self.backend.parse_query('name:david1..david2')),
                         'Xapian::Query(VALUE_RANGE 7 david1 david2)')
        self.assertEqual(str(self.backend.parse_query('value:0..10')),
                         'Xapian::Query(VALUE_RANGE 16 000000000000 000000000010)')
        self.assertEqual(str(self.backend.parse_query('value:..10')),
                         'Xapian::Query(VALUE_RANGE 16 %012d 000000000010)' % (-sys.maxsize - 1))
        self.assertEqual(str(self.backend.parse_query('value:10..*')),
                         'Xapian::Query(VALUE_RANGE 16 000000000010 %012d)' % sys.maxsize)
        self.assertEqual(str(self.backend.parse_query('popularity:25.5..100.0')),
                         b'Xapian::Query(VALUE_RANGE 9 \xb2` \xba@)')

    def test_order_by_django_id(self):
        """
        We need this test because ordering on more than
        10 entries was not correct at some point.
        """
        self.sample_objs = []
        number_list = list(range(1, 101))
        for i in number_list:
            mock = XapianMockModel()
            mock.id = i
            mock.author = 'david%s' % i
            mock.pub_date = datetime.date(2009, 2, 25) - datetime.timedelta(days=i)
            mock.exp_date = datetime.date(2009, 2, 23) + datetime.timedelta(days=i)
            mock.value = i * 5
            mock.flag = bool(i % 2)
            mock.slug = 'http://example.com/%d/' % i
            mock.url = 'http://example.com/%d/' % i
            mock.popularity = i*2
            self.sample_objs.append(mock)

        self.backend.clear()
        self.backend.update(self.index, self.sample_objs)

        results = self.backend.search(xapian.Query(''), sort_by=['-django_id'])
        self.assertEqual(pks(results['results']), list(reversed(number_list)))

    def test_more_like_this_with_unindexed_model(self):
        """
        Tests that more_like_this raises an error when it is called
         with an unindexed model and if silently_fail is True.
         Also tests the other way around.
        """
        mock = XapianMockModel()
        mock.id = 10
        mock.author = 'david10'

        try:
            self.assertEqual(self.backend.more_like_this(mock)['results'], [])
        except InvalidIndexError:
            self.fail("InvalidIndexError raised when silently_fail is True")

        self.backend.silently_fail = False
        self.assertRaises(InvalidIndexError, self.backend.more_like_this, mock)


class IndexationNGramTestCase(HaystackBackendTestCase, TestCase):
    def get_index(self):
        return XapianNGramIndex()

    def setUp(self):
        super(IndexationNGramTestCase, self).setUp()
        mock = XapianMockModel()
        mock.id = 1
        mock.author = u'david'

        mock1 = XapianMockModel()
        mock1.id = 2
        mock1.author = u'da1id'

        self.backend.update(self.index, [mock, mock1])

    def test_field(self):
        terms = get_terms(self.backend, '-a')

        self.assertTrue('da' in terms)
        self.assertTrue('XNGRAMda' in terms)
        self.assertTrue('dav' in terms)
        self.assertTrue('XNGRAMdav' in terms)
        self.assertTrue('davi' in terms)
        self.assertTrue('XNGRAMdavi' in terms)
        self.assertTrue('david' in terms)
        self.assertTrue('XNGRAMdavid' in terms)

        self.assertTrue('vid' in terms)
        self.assertTrue('XNGRAMvid' in terms)
        self.assertTrue('id' in terms)
        self.assertTrue('XNGRAMid' in terms)
        self.assertTrue('av' in terms)
        self.assertTrue('XNGRAMav' in terms)

    def test_search(self):
        """Tests edge ngram search with different parts of words"""
        # Minimun length of query string must be equal to EDGE_NGRAM_MIN_LENGTH.
        self.assertEqual(pks(self.backend.search(xapian.Query('da'))['results']),
                [1, 2])
        self.assertEqual(pks(self.backend.search(xapian.Query('dav'))['results']),
                [1])
        self.assertEqual(pks(self.backend.search(xapian.Query('da1'))['results']),
                [2])


class IndexationEdgeNGramTestCase(HaystackBackendTestCase, TestCase):
    def get_index(self):
        return XapianEdgeNGramIndex()

    def setUp(self):
        super(IndexationEdgeNGramTestCase, self).setUp()
        mock = XapianMockModel()
        mock.id = 1
        mock.author = u'david'

        mock1 = XapianMockModel()
        mock1.id = 2
        mock1.author = u'da1id'

        self.backend.update(self.index, [mock, mock1])

    def test_field(self):
        terms = get_terms(self.backend, '-a')

        self.assertTrue('da' in terms)
        self.assertTrue('XEDGE_NGRAMda' in terms)
        self.assertTrue('dav' in terms)
        self.assertTrue('XEDGE_NGRAMdav' in terms)
        self.assertTrue('davi' in terms)
        self.assertTrue('XEDGE_NGRAMdavi' in terms)
        self.assertTrue('david' in terms)
        self.assertTrue('XEDGE_NGRAMdavid' in terms)

        self.assertTrue('vid' not in terms)
        self.assertTrue('XEDGE_NGRAMvid' not in terms)
        self.assertTrue('id' not in terms)
        self.assertTrue('XEDGE_NGRAMid' not in terms)
        self.assertTrue('av' not in terms)
        self.assertTrue('XEDGE_NGRAMav' not in terms)

    def test_search(self):
        """Tests edge ngram search with different parts of words"""
        # Minimun length of query string must be equal to NGRAM_MIN_LENGTH.
        self.assertEqual(pks(self.backend.search(xapian.Query('da'))['results']),
                [1, 2])
        self.assertEqual(pks(self.backend.search(xapian.Query('dav'))['results']),
                [1])
        self.assertEqual(pks(self.backend.search(xapian.Query('da1'))['results']),
                [2])
