from __future__ import unicode_literals

import datetime

from django.conf import settings
from django.test import TestCase

from haystack import connections, reset_search_queries
from haystack.models import SearchResult
from haystack.query import SearchQuerySet, SQ

from ...mocks import MockSearchResult

from ..models import MockModel, AnotherMockModel, AFourthMockModel
from ..search_indexes import MockQueryIndex, MockSearchIndex, BoostMockSearchIndex
from ..tests.test_backend import HaystackBackendTestCase


class XapianSearchQueryTestCase(HaystackBackendTestCase, TestCase):
    """
    Tests the XapianSearchQuery, the class that converts SearchQuerySet queries
    using the `__` notation to XapianQueries.
    """

    fixtures = ["base_data.json"]

    def get_index(self):
        return MockQueryIndex()

    def setUp(self):
        super(XapianSearchQueryTestCase, self).setUp()
        self.sq = connections["default"].get_query()

    def test_all(self):
        self.assertExpectedQuery(self.sq.build_query(), "<alldocuments>")

    def test_single_word(self):
        self.sq.add_filter(SQ(content="hello"))
        self.assertExpectedQuery(self.sq.build_query(), "(Zhello OR hello)")

    def test_single_word_not(self):
        self.sq.add_filter(~SQ(content="hello"))
        self.assertExpectedQuery(self.sq.build_query(), "(<alldocuments> AND_NOT (Zhello OR hello))")

    def test_single_word_field_exact(self):
        self.sq.add_filter(SQ(foo__exact="hello"))
        self.assertExpectedQuery(self.sq.build_query(), "(XFOO^ PHRASE 3 XFOOhello PHRASE 3 XFOO$)")

    def test_single_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo="hello"))
        self.assertExpectedQuery(
            self.sq.build_query(), "(<alldocuments> AND_NOT " "(XFOO^ PHRASE 3 XFOOhello PHRASE 3 XFOO$))",
        )

    def test_boolean(self):
        self.sq.add_filter(SQ(content=True))
        self.assertExpectedQuery(self.sq.build_query(), "(Ztrue OR true)")

    def test_date(self):
        self.sq.add_filter(SQ(content=datetime.date(2009, 5, 8)))
        self.assertExpectedQuery(self.sq.build_query(), "(Z2009-05-08 OR 2009-05-08)")

    def test_date_not(self):
        self.sq.add_filter(~SQ(content=datetime.date(2009, 5, 8)))
        self.assertExpectedQuery(
            self.sq.build_query(), "(<alldocuments> AND_NOT " "(Z2009-05-08 OR 2009-05-08))",
        )

    def test_datetime(self):
        self.sq.add_filter(SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Z2009-05-08 OR 2009-05-08) OR" " (Z11:28:00 OR 11:28:00))",
            xapian12string="(Z2009-05-08 OR 2009-05-08 OR" " Z11:28:00 OR 11:28:00)",
        )

    def test_datetime_not(self):
        self.sq.add_filter(~SQ(content=datetime.datetime(2009, 5, 8, 11, 28)))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "(<alldocuments> AND_NOT ((Z2009-05-08 OR 2009-05-08) OR (Z11:28:00 OR 11:28:00)))",
            xapian12string="(<alldocuments> AND_NOT (Z2009-05-08 OR 2009-05-08 OR Z11:28:00 OR 11:28:00))",
        )

    def test_float(self):
        self.sq.add_filter(SQ(content=25.52))
        self.assertExpectedQuery(self.sq.build_query(), "(Z25.52 OR 25.52)")

    def test_multiple_words_and(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_filter(SQ(content="world"))
        self.assertExpectedQuery(self.sq.build_query(), "((Zhello OR hello) AND (Zworld OR world))")

    def test_multiple_words_not(self):
        self.sq.add_filter(~SQ(content="hello"))
        self.sq.add_filter(~SQ(content="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((<alldocuments> AND_NOT (Zhello OR hello)) AND" " (<alldocuments> AND_NOT (Zworld OR world)))",
        )

    def test_multiple_words_or(self):
        self.sq.add_filter(SQ(content="hello") | SQ(content="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zhello OR hello) OR (Zworld OR world))",
            xapian12string="(Zhello OR hello OR Zworld OR world)",
        )

    def test_multiple_words_or_not(self):
        self.sq.add_filter(~SQ(content="hello") | ~SQ(content="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((<alldocuments> AND_NOT (Zhello OR hello)) OR" " (<alldocuments> AND_NOT (Zworld OR world)))",
        )

    def test_multiple_words_mixed(self):
        self.sq.add_filter(SQ(content="why") | SQ(content="hello"))
        self.sq.add_filter(~SQ(content="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "(((Zwhi OR why) OR (Zhello OR hello)) AND " "(<alldocuments> AND_NOT (Zworld OR world)))",
            xapian12string="((Zwhi OR why OR Zhello OR hello) AND" " (<alldocuments> AND_NOT (Zworld OR world)))",
        )

    def test_multiple_word_field_exact(self):
        self.sq.add_filter(SQ(foo="hello"))
        self.sq.add_filter(SQ(title="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((XFOO^ PHRASE 3 XFOOhello PHRASE 3 XFOO$) AND" " (XTITLE^ PHRASE 3 XTITLEworld PHRASE 3 XTITLE$))",
        )

    def test_multiple_word_field_exact_not(self):
        self.sq.add_filter(~SQ(foo="hello"))
        self.sq.add_filter(~SQ(title="world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((<alldocuments> AND_NOT (XFOO^ PHRASE 3 XFOOhello PHRASE 3 XFOO$)) AND"
            " (<alldocuments> AND_NOT (XTITLE^ PHRASE 3 XTITLEworld PHRASE 3 XTITLE$)))",
        )

    def test_or(self):
        self.sq.add_filter(SQ(content="hello world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zhello OR hello) OR (Zworld OR world))",
            xapian12string="(Zhello OR hello OR Zworld OR world)",
        )

    def test_not_or(self):
        self.sq.add_filter(~SQ(content="hello world"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "(<alldocuments> AND_NOT ((Zhello OR hello) OR (Zworld OR world)))",
            xapian12string="(<alldocuments> AND_NOT (Zhello OR hello OR Zworld OR world))",
        )

    def test_boost(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_boost("world", 5)
        self.assertExpectedQuery(
            self.sq.build_query(), "((Zhello OR hello) AND_MAYBE" " 5 * (Zworld OR world))",
        )

    def test_not_in_filter_single_words(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(~SQ(title__in=["Dune", "Jaws"]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zwhi OR why) AND "
            "(<alldocuments> AND_NOT ("
            "(XTITLE^ PHRASE 3 XTITLEdune PHRASE 3 XTITLE$) OR "
            "(XTITLE^ PHRASE 3 XTITLEjaws PHRASE 3 XTITLE$))))",
        )

    def test_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zwhi OR why) AND ((XTITLE^ PHRASE 5 XTITLEa PHRASE 5 "
            "XTITLEfamous PHRASE 5 XTITLEpaper PHRASE 5 XTITLE$) OR "
            "(XTITLE^ PHRASE 5 XTITLEan PHRASE 5 XTITLEinfamous PHRASE 5 "
            "XTITLEarticle PHRASE 5 XTITLE$)))",
        )

    def test_in_filter_multiple_words_with_punctuation(self):
        self.sq.add_filter(SQ(title__in=["A Famous Paper", "An Infamous Article", "My Store Inc."]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((XTITLE^ PHRASE 5 XTITLEa PHRASE 5 XTITLEfamous PHRASE 5"
            " XTITLEpaper PHRASE 5 XTITLE$) OR "
            "(XTITLE^ PHRASE 5 XTITLEan PHRASE 5 XTITLEinfamous PHRASE 5"
            " XTITLEarticle PHRASE 5 XTITLE$) OR "
            "(XTITLE^ PHRASE 5 XTITLEmy PHRASE 5 XTITLEstore PHRASE 5"
            " XTITLEinc. PHRASE 5 XTITLE$))",
        )

    def test_not_in_filter_multiple_words(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(~SQ(title__in=["A Famous Paper", "An Infamous Article"]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zwhi OR why) AND (<alldocuments> AND_NOT "
            "((XTITLE^ PHRASE 5 XTITLEa PHRASE 5 XTITLEfamous PHRASE 5 "
            "XTITLEpaper PHRASE 5 XTITLE$) OR (XTITLE^ PHRASE 5 "
            "XTITLEan PHRASE 5 XTITLEinfamous PHRASE 5 "
            "XTITLEarticle PHRASE 5 XTITLE$))))",
        )

    def test_in_filter_datetime(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(pub_date__in=[datetime.datetime(2009, 7, 6, 1, 56, 21)]))
        self.assertExpectedQuery(
            self.sq.build_query(), "((Zwhi OR why) AND " "(XPUB_DATE2009-07-06 AND_MAYBE XPUB_DATE01:56:21))",
        )

    def test_clean(self):
        self.assertEqual(self.sq.clean("hello world"), "hello world")
        self.assertEqual(self.sq.clean("hello AND world"), "hello AND world")
        self.assertEqual(
            self.sq.clean('hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \\ world'),
            'hello AND OR NOT TO + - && || ! ( ) { } [ ] ^ " ~ * ? : \\ world',
        )
        self.assertEqual(
            self.sq.clean("so please NOTe i am in a bAND and bORed"), "so please NOTe i am in a bAND and bORed"
        )

    def test_with_models(self):
        self.sq.add_filter(SQ(content="hello"))
        self.sq.add_model(MockModel)
        self.assertExpectedQuery(
            self.sq.build_query(), "((Zhello OR hello) AND 0 * CONTENTTYPEcore.mockmodel)",
        )

        self.sq.add_model(AnotherMockModel)

        self.assertExpectedQuery(
            self.sq.build_query(),
            [
                "((Zhello OR hello) AND "
                "(0 * CONTENTTYPEcore.mockmodel OR"
                " 0 * CONTENTTYPEcore.anothermockmodel))",
                "((Zhello OR hello) AND "
                "(0 * CONTENTTYPEcore.anothermockmodel OR"
                " 0 * CONTENTTYPEcore.mockmodel))",
            ],
        )

    def test_with_punctuation(self):
        self.sq.add_filter(SQ(content="http://www.example.com"))
        self.assertExpectedQuery(
            self.sq.build_query(), "(Zhttp://www.example.com OR" " http://www.example.com)",
        )

    def test_in_filter_values_list(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(title__in=MockModel.objects.values_list("id", flat=True)))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zwhi OR why) AND ("
            "(XTITLE^ PHRASE 3 XTITLE1 PHRASE 3 XTITLE$) OR "
            "(XTITLE^ PHRASE 3 XTITLE2 PHRASE 3 XTITLE$) OR "
            "(XTITLE^ PHRASE 3 XTITLE3 PHRASE 3 XTITLE$)))",
        )

    def test_content_type(self):
        self.sq.add_filter(SQ(django_ct="time"))
        self.assertExpectedQuery(self.sq.build_query(), "CONTENTTYPEtime")


class SearchQueryTestCase(HaystackBackendTestCase, TestCase):
    """
    Tests expected behavior of
    SearchQuery.
    """

    fixtures = ["base_data.json"]

    def get_index(self):
        return MockSearchIndex()

    def setUp(self):
        super(SearchQueryTestCase, self).setUp()

        self.backend.update(self.index, MockModel.objects.all())

        self.sq = connections["default"].get_query()

    def test_get_spelling(self):
        self.sq.add_filter(SQ(content="indxd"))
        self.assertEqual(self.sq.get_spelling_suggestion(), "indexed")
        self.assertEqual(self.sq.get_spelling_suggestion("indxd"), "indexed")

    def test_contains(self):
        self.sq.add_filter(SQ(content="circular"))
        self.sq.add_filter(SQ(title__contains="haystack"))
        self.assertExpectedQuery(
            self.sq.build_query(), "((Zcircular OR circular) AND " "(ZXTITLEhaystack OR XTITLEhaystack))",
        )

    def test_startswith(self):
        self.sq.add_filter(SQ(name__startswith="da"))
        self.assertEqual([result.pk for result in self.sq.get_results()], [1, 2, 3])

    def test_endswith(self):
        with self.assertRaises(NotImplementedError):
            self.sq.add_filter(SQ(name__endswith="el2"))
            self.sq.get_results()

    def test_gt(self):
        self.sq.add_filter(SQ(name__gt="m"))
        self.assertExpectedQuery(self.sq.build_query(), "(<alldocuments> AND_NOT VALUE_RANGE 3 a m)")

    def test_gte(self):
        self.sq.add_filter(SQ(name__gte="m"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "VALUE_RANGE 3 m zzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        )

    def test_lt(self):
        self.sq.add_filter(SQ(name__lt="m"))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "(<alldocuments> AND_NOT VALUE_RANGE 3 m "
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzz)",
        )

    def test_lte(self):
        self.sq.add_filter(SQ(name__lte="m"))
        self.assertExpectedQuery(self.sq.build_query(), "VALUE_RANGE 3 a m")

    def test_range(self):
        self.sq.add_filter(SQ(django_id__range=[2, 4]))
        self.assertExpectedQuery(self.sq.build_query(), "VALUE_RANGE 1 000000000002 000000000004")
        self.sq.add_filter(~SQ(django_id__range=[0, 2]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "(VALUE_RANGE 1 000000000002 000000000004 AND "
            "(<alldocuments> AND_NOT VALUE_RANGE 1 000000000000 000000000002))",
        )
        self.assertEqual([result.pk for result in self.sq.get_results()], [3])

    def test_multiple_filter_types(self):
        self.sq.add_filter(SQ(content="why"))
        self.sq.add_filter(SQ(pub_date__lte=datetime.datetime(2009, 2, 10, 1, 59, 0)))
        self.sq.add_filter(SQ(name__gt="david"))
        self.sq.add_filter(SQ(title__gte="B"))
        self.sq.add_filter(SQ(django_id__in=[1, 2, 3]))
        self.assertExpectedQuery(
            self.sq.build_query(),
            "((Zwhi OR why) AND"
            " VALUE_RANGE 5 00010101000000 20090210015900 AND"
            " (<alldocuments> AND_NOT VALUE_RANGE 3 a david)"
            " AND VALUE_RANGE 7 b zzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzzzzzzzzzzzzzzzzzzzzzzz AND"
            " (QQ000000000001 OR QQ000000000002 OR QQ000000000003))",
        )

    def test_log_query(self):
        reset_search_queries()
        self.assertEqual(len(connections["default"].queries), 0)

        # Stow.
        old_debug = settings.DEBUG
        settings.DEBUG = False

        len(self.sq.get_results())
        self.assertEqual(len(connections["default"].queries), 0)

        settings.DEBUG = True
        # Redefine it to clear out the cached results.
        self.sq = connections["default"].get_query()
        self.sq.add_filter(SQ(name="bar"))
        len(self.sq.get_results())
        self.assertEqual(len(connections["default"].queries), 1)
        self.assertExpectedQuery(
            connections["default"].queries[0]["query_string"], "(XNAME^ PHRASE 3 XNAMEbar PHRASE 3 XNAME$)",
        )

        # And again, for good measure.
        self.sq = connections["default"].get_query()
        self.sq.add_filter(SQ(name="bar"))
        self.sq.add_filter(SQ(text="moof"))
        len(self.sq.get_results())
        self.assertEqual(len(connections["default"].queries), 2)
        self.assertExpectedQuery(
            connections["default"].queries[0]["query_string"], "(XNAME^ PHRASE 3 XNAMEbar PHRASE 3 XNAME$)",
        )
        self.assertExpectedQuery(
            connections["default"].queries[1]["query_string"],
            "((XNAME^ PHRASE 3 XNAMEbar PHRASE 3 XNAME$) AND" " (XTEXT^ PHRASE 3 XTEXTmoof PHRASE 3 XTEXT$))",
        )

        # Restore.
        settings.DEBUG = old_debug


class LiveSearchQuerySetTestCase(HaystackBackendTestCase, TestCase):
    """
    SearchQuerySet specific tests
    """

    fixtures = ["base_data.json"]

    def get_index(self):
        return MockSearchIndex()

    def setUp(self):
        super(LiveSearchQuerySetTestCase, self).setUp()

        self.backend.update(self.index, MockModel.objects.all())
        self.sq = connections["default"].get_query()
        self.sqs = SearchQuerySet()

    def test_result_class(self):
        # Assert that we"re defaulting to ``SearchResult``.
        sqs = self.sqs.all()
        self.assertTrue(isinstance(sqs[0], SearchResult))

        # Custom class.
        sqs = self.sqs.result_class(MockSearchResult).all()
        self.assertTrue(isinstance(sqs[0], MockSearchResult))

        # Reset to default.
        sqs = self.sqs.result_class(None).all()
        self.assertTrue(isinstance(sqs[0], SearchResult))

    def test_facet(self):
        self.assertEqual(len(self.sqs.facet("name").facet_counts()["fields"]["name"]), 3)


class BoostFieldTestCase(HaystackBackendTestCase, TestCase):
    """
    Tests boosted fields.
    """

    def get_index(self):
        return BoostMockSearchIndex()

    def setUp(self):
        super(BoostFieldTestCase, self).setUp()

        self.sample_objs = []
        for i in range(1, 5):
            mock = AFourthMockModel()
            mock.id = i
            if i % 2:
                mock.author = "daniel"
                mock.editor = "david"
            else:
                mock.author = "david"
                mock.editor = "daniel"
            mock.pub_date = datetime.date(2009, 2, 25) - datetime.timedelta(days=i)
            self.sample_objs.append(mock)

        self.backend.update(self.index, self.sample_objs)

    def test_boost(self):
        sqs = SearchQuerySet()

        self.assertEqual(len(sqs.all()), 4)

        results = sqs.filter(SQ(author="daniel") | SQ(editor="daniel"))

        self.assertEqual(
            [result.id for result in results],
            [
                "core.afourthmockmodel.1",
                "core.afourthmockmodel.3",
                "core.afourthmockmodel.2",
                "core.afourthmockmodel.4",
            ],
        )
