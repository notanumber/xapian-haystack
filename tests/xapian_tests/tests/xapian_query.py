# Copyright (C) 2009 David Sauve
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
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(<alldocuments>)')
    
    def test_build_query_single_word(self):
        self.sq.add_filter(SQ(content='hello'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(hello)')
    
    def test_build_query_single_word_not(self):
        self.sq.add_filter(~SQ(content='hello'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((<alldocuments> AND_NOT hello))')

    def test_build_query_single_word_field_exact(self):
        self.sq.add_filter(SQ(foo='hello'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(XFOOhello)')

    def test_build_query_single_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo='hello'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((<alldocuments> AND_NOT XFOOhello))')

    def test_build_query_boolean(self):
        self.sq.add_filter(SQ(content=True))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(true)')
    
    def test_build_query_datetime(self):
        self.sq.add_filter(SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(20090508T112800Z)')
    
    def test_build_query_multiple_words_and(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_filter(SQ(content='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello AND world))')
    
    def test_build_query_multiple_words_not(self):
        self.sq.add_filter(~SQ(content='hello'))
        self.sq.add_filter(~SQ(content='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(((<alldocuments> AND_NOT hello) AND (<alldocuments> AND_NOT world)))')
    
    def test_build_query_multiple_words_or(self):
        self.sq.add_filter(SQ(content='hello') | SQ(content='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello OR world))')
    
    def test_build_query_multiple_words_or_not(self):
        self.sq.add_filter(~SQ(content='hello') | ~SQ(content='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(((<alldocuments> AND_NOT hello) OR (<alldocuments> AND_NOT world)))')

    def test_build_query_multiple_words_mixed(self):
        self.sq.add_filter(SQ(content='why') | SQ(content='hello'))
        self.sq.add_filter(~SQ(content='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(((why OR hello) AND (<alldocuments> AND_NOT world)))')
    
    def test_build_query_multiple_word_field_exact(self):
        self.sq.add_filter(SQ(foo='hello'))
        self.sq.add_filter(SQ(bar='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((XFOOhello AND XBARworld))')

    def test_build_query_multiple_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo='hello'))
        self.sq.add_filter(~SQ(bar='world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(((<alldocuments> AND_NOT XFOOhello) AND (<alldocuments> AND_NOT XBARworld)))')

    def test_build_query_phrase(self):
        self.sq.add_filter(SQ(content='hello world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello PHRASE 2 world))')
    
    def test_build_query_phrase_not(self):
        self.sq.add_filter(~SQ(content='hello world'))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((<alldocuments> AND_NOT (hello PHRASE 2 world)))')

    def test_build_query_boost(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_boost('world', 5)
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello OR 5 * world))')
    
    # def test_build_query_multiple_filter_types(self):
    #     self.sq.add_filter(SQ(content='why'))
    #     self.sq.add_filter(SQ(pub_date__lte='2009-02-10 01:59:00'))
    #     self.sq.add_filter(SQ(author__gt='daniel'))
    #     self.sq.add_filter(SQ(created__lt='2009-02-12 12:13:00'))
    #     self.sq.add_filter(SQ(title__gte='B'))
    #     self.sq.add_filter(SQ(id__in=[1, 2, 3]))
    #     self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query(why AND pub_date:[* TO "2009-02-10 01:59:00"] AND author:{daniel TO *} AND created:{* TO "2009-02-12 12:13:00"} AND title:[B TO *] AND (id:"1" OR id:"2" OR id:"3"))')
    
    def test_build_query_in_filter_single_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(title__in=["Dune", "Jaws"]))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((why AND (XTITLEdune OR XTITLEjaws)))')

    def test_build_query_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content='why'))
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((why AND ((XTITLEa PHRASE 3 XTITLEfamous PHRASE 3 XTITLEpaper) OR (XTITLEan PHRASE 3 XTITLEinfamous PHRASE 3 XTITLEarticle))))')
    
    # def test_build_query_not_in_filter_multiple_words(self):
    #     self.sq.add_filter(SQ(content='why'))
    #     self.sq.add_filter(~SQ(title__in=["A Famous Paper", "An Infamous Article"]))
    #     self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((why AND_NOT (XTITLEa famous paper OR XTITLEan infamous article)))')
    # 
    # def test_build_query_in_filter_datetime(self):
    #     self.sq.add_filter(SQ(content='why'))
    #     self.sq.add_filter(SQ(pub_date__in=[datetime.datetime(2009, 7, 6, 1, 56, 21)]))
    #     self.assertEqual(self.sq.build_query(), u'(why AND (pub_date:"2009-07-06T01:56:21Z"))')
    # 
    # def test_build_query_wildcard_filter_types(self):
    #     self.sq.add_filter(SQ(content='why'))
    #     self.sq.add_filter(SQ(title__startswith='haystack'))
    #     self.assertEqual(self.sq.build_query(), u'(why AND title:haystack*)')

    def test_clean(self):
        self.assertEqual(self.sq.clean('hello world'), 'hello world')
        self.assertEqual(self.sq.clean('hello AND world'), 'hello AND world')
        self.assertEqual(self.sq.clean('hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \ world'), 'hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \ world')
        self.assertEqual(self.sq.clean('so please NOTe i am in a bAND and bORed'), 'so please NOTe i am in a bAND and bORed')
    
    def test_build_query_with_models(self):
        self.sq.add_filter(SQ(content='hello'))
        self.sq.add_model(MockModel)
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello AND 0 * XCONTENTTYPEcore.mockmodel))')
    
        self.sq.add_model(AnotherMockModel)
        self.assertEqual(self.sq.build_query().get_description(), 'Xapian::Query((hello AND (0 * XCONTENTTYPEcore.anothermockmodel OR 0 * XCONTENTTYPEcore.mockmodel)))')
