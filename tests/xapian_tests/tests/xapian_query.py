# Copyright (C) 2009, 2010, 2011 David Sauve
# Copyright (C) 2009, 2010 Trapeze

import datetime
import os
import shutil

from django.conf import settings
from django.test import TestCase

from haystack.backends.xapian_backend import SearchBackend, SearchQuery
from haystack.query import SQ

from core.models import MockModel, AnotherMockModel


class XapianSearchQueryTestCase(TestCase):
    def setUp(self):
        super(XapianSearchQueryTestCase, self).setUp()
        self.sq = SearchQuery(backend=SearchBackend())
    
    def tearDown(self):
        if os.path.exists(settings.HAYSTACK_XAPIAN_PATH):
            shutil.rmtree(settings.HAYSTACK_XAPIAN_PATH)
        
        super(XapianSearchQueryTestCase, self).tearDown()
    
    def test_build_query_all(self):
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(<alldocuments>)')
    
    def test_build_query_single_word(self):
        self.sq.add_filter(SQ(content='hello'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Zhello OR hello))')
    
    def test_build_query_single_word_not(self):
        self.sq.add_filter(~SQ(content='hello'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((<alldocuments> AND_NOT (Zhello OR hello)))')
    
    def test_build_query_single_word_field_exact(self):
        self.sq.add_filter(SQ(foo='hello'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((ZXFOOhello OR XFOOhello))')
    
    def test_build_query_single_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo='hello'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((<alldocuments> AND_NOT (ZXFOOhello OR XFOOhello)))')
    
    def test_build_query_boolean(self):
        self.sq.add_filter(SQ(content=True))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Ztrue OR true))')
    
    def test_build_query_date(self):
        self.sq.add_filter(SQ(content=datetime.date(2009, 5, 8)))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Z20090508000000 OR 20090508000000))')
    
    def test_build_query_date_not(self):
        self.sq.add_filter(~SQ(content=datetime.date(2009, 5, 8)))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((<alldocuments> AND_NOT (Z20090508000000 OR 20090508000000)))')

    def test_build_query_datetime(self):
        self.sq.add_filter(SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Z20090508112800 OR 20090508112800))')
    
    def test_build_query_datetime_not(self):
        self.sq.add_filter(~SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((<alldocuments> AND_NOT (Z20090508112800 OR 20090508112800)))')

    def test_build_query_float(self):
        self.sq.add_filter(SQ(content=25.52))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Z25.52 OR 25.52))')
    
    def test_build_query_multiple_words_and(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_filter(SQ(content='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zhello OR hello) AND (Zworld OR world)))')
    
    def test_build_query_multiple_words_not(self):
        self.sq.add_filter(~SQ(content='hello'))
        self.sq.add_filter(~SQ(content='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((<alldocuments> AND_NOT (Zhello OR hello)) AND (<alldocuments> AND_NOT (Zworld OR world))))')
    
    def test_build_query_multiple_words_or(self):
        self.sq.add_filter(SQ(content='hello') | SQ(content='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Zhello OR hello OR Zworld OR world))')
    
    def test_build_query_multiple_words_or_not(self):
        self.sq.add_filter(~SQ(content='hello') | ~SQ(content='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((<alldocuments> AND_NOT (Zhello OR hello)) OR (<alldocuments> AND_NOT (Zworld OR world))))')
    
    def test_build_query_multiple_words_mixed(self):
        self.sq.add_filter(SQ(content='why') | SQ(content='hello'))
        self.sq.add_filter(~SQ(content='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why OR Zhello OR hello) AND (<alldocuments> AND_NOT (Zworld OR world))))')
    
    def test_build_query_multiple_word_field_exact(self):
        self.sq.add_filter(SQ(foo='hello'))
        self.sq.add_filter(SQ(bar='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((ZXFOOhello OR XFOOhello) AND (ZXBARworld OR XBARworld)))')
    
    def test_build_query_multiple_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo='hello'))
        self.sq.add_filter(~SQ(bar='world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((<alldocuments> AND_NOT (ZXFOOhello OR XFOOhello)) AND (<alldocuments> AND_NOT (ZXBARworld OR XBARworld))))')
    
    def test_build_query_phrase(self):
        self.sq.add_filter(SQ(content='hello world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((hello PHRASE 2 world))')
    
    def test_build_query_phrase_not(self):
        self.sq.add_filter(~SQ(content='hello world'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((<alldocuments> AND_NOT (hello PHRASE 2 world)))')
    
    def test_build_query_boost(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_boost('world', 5)
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zhello OR hello) AND_MAYBE 5 * (Zworld OR world)))')
    
    def test_build_query_in_filter_single_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(title__in=["Dune", "Jaws"]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND (ZXTITLEdune OR XTITLEdune OR ZXTITLEjaw OR XTITLEjaws)))')
    
    def test_build_query_not_in_filter_single_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(~SQ(title__in=["Dune", "Jaws"]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND (<alldocuments> AND_NOT (ZXTITLEdune OR XTITLEdune OR ZXTITLEjaw OR XTITLEjaws))))')
    
    def test_build_query_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND ((XTITLEa PHRASE 3 XTITLEfamous PHRASE 3 XTITLEpaper) OR (XTITLEan PHRASE 3 XTITLEinfamous PHRASE 3 XTITLEarticle))))')
    
    def test_build_query_in_filter_multiple_words_with_punctuation(self):
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article", "My Store Inc."]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((XTITLEa PHRASE 3 XTITLEfamous PHRASE 3 XTITLEpaper) OR (XTITLEan PHRASE 3 XTITLEinfamous PHRASE 3 XTITLEarticle) OR (XTITLEmy PHRASE 3 XTITLEstore PHRASE 3 XTITLEinc.)))')

    def test_build_query_not_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(~SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND (<alldocuments> AND_NOT ((XTITLEa PHRASE 3 XTITLEfamous PHRASE 3 XTITLEpaper) OR (XTITLEan PHRASE 3 XTITLEinfamous PHRASE 3 XTITLEarticle)))))')
    
    def test_build_query_in_filter_datetime(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(pub_date__in=[datetime.datetime(2009, 7, 6, 1, 56, 21)]))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND (ZXPUB_DATE20090706015621 OR XPUB_DATE20090706015621)))')
    
    def test_clean(self):
        self.assertEqual(self.sq.clean('hello world'), 'hello world')
        self.assertEqual(self.sq.clean('hello AND world'), 'hello AND world')
        self.assertEqual(self.sq.clean('hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \ world'), 'hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \ world')
        self.assertEqual(self.sq.clean('so please NOTe i am in a bAND and bORed'), 'so please NOTe i am in a bAND and bORed')
    
    def test_build_query_with_models(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_model(MockModel)
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zhello OR hello) AND 0 * XCONTENTTYPEcore.mockmodel))')
        
        self.sq.add_model(AnotherMockModel)
        self.assertTrue(str(self.sq.build_query()) in u'Xapian::Query(((Zhello OR hello) AND (0 * XCONTENTTYPEcore.anothermockmodel OR 0 * XCONTENTTYPEcore.mockmodel)))' or u'Xapian::Query(((Zhello OR hello) AND (0 * XCONTENTTYPEcore.mockmodel OR 0 * XCONTENTTYPEcore.anothermockmodel)))')

    def test_build_query_with_punctuation(self):
        self.sq.add_filter(SQ(content='http://www.example.com'))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query((Zhttp://www.example.com OR http://www.example.com))')
    
    def test_in_filter_values_list(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(title__in=MockModel.objects.values_list('id', flat=True)))
        self.assertEqual(str(self.sq.build_query()), u'Xapian::Query(((Zwhi OR why) AND (ZXTITLE1 OR XTITLE1 OR ZXTITLE2 OR XTITLE2 OR ZXTITLE3 OR XTITLE3)))')
