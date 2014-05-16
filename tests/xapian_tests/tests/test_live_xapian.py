import datetime
from django.test import TestCase

from haystack import connections
from haystack.inputs import AutoQuery
from haystack.query import SearchQuerySet

from xapian_tests.models import Document
from xapian_tests.search_indexes import DocumentIndex


def pks(results):
    return [result.pk for result in results]


class LiveXapianTestCase(TestCase):

    def setUp(self):

        types_names = ['book', 'magazine', 'article']
        texts = ['This is a huge text',
                 'This is a medium text',
                 'This is a small text']
        dates = [datetime.date(year=2010, month=1, day=1),
                 datetime.date(year=2010, month=2, day=1),
                 datetime.date(year=2010, month=3, day=1)]

        summaries = ['This is a huge summary',
                     'This is a medium summary',
                     'This is a small summary']

        for i in range(1, 13):
            doc = Document()
            doc.type_name = types_names[i % 3]
            doc.text = texts[i % 3]
            doc.date = dates[i % 3]
            doc.summary = summaries[i % 3]
            doc.number = i * 2
            doc.save()

        self.index = DocumentIndex()
        self.ui = connections['default'].get_unified_index()
        self.ui.build(indexes=[self.index])

        self.backend = connections['default'].get_backend()
        self.backend.update(self.index, Document.objects.all())

        self.queryset = SearchQuerySet()

    def tearDown(self):
        Document.objects.all().delete()
        self.backend.clear()

    def test_count(self):
        self.assertEqual(self.queryset.count(), Document.objects.count())

    def test_content_search(self):
        result = self.queryset.filter(content='medium this')
        self.assertEqual(sorted(pks(result)),
                         pks(Document.objects.all()))

        # documents with "medium" AND "this" have higher score
        self.assertEqual(pks(result)[:4], [1, 4, 7, 10])

    def test_field_search(self):
        self.assertEqual(pks(self.queryset.filter(name='8')), [4])
        self.assertEqual(pks(self.queryset.filter(type_name='book')),
                         pks(Document.objects.filter(type_name='book')))

        self.assertEqual(pks(self.queryset.filter(text='text huge')),
                         pks(Document.objects.filter(text__contains='text huge')))

    def test_field_contains(self):
        self.assertEqual(pks(self.queryset.filter(summary='huge')),
                         pks(Document.objects.filter(summary__contains='huge')))

        result = self.queryset.filter(summary='huge summary')
        self.assertEqual(sorted(pks(result)),
                         pks(Document.objects.all()))

        # documents with "huge" AND "summary" have higher score
        self.assertEqual(pks(result)[:4], [3, 6, 9, 12])

    def test_field_exact(self):
        self.assertEqual(pks(self.queryset.filter(name__exact='8')), [])
        self.assertEqual(pks(self.queryset.filter(name__exact='magazine 2')), [1])

    def test_content_exact(self):
        self.assertEqual(pks(self.queryset.filter(content__exact='huge')), [])

    def test_content_and(self):
        self.assertEqual(pks(self.queryset.filter(content='huge').filter(summary='medium')), [])

        self.assertEqual(len(self.queryset.filter(content='huge this')), 12)
        self.assertEqual(len(self.queryset.filter(content='huge this').filter(summary='huge')), 4)

    def test_content_or(self):
        self.assertEqual(len(self.queryset.filter(content='huge medium')), 8)
        self.assertEqual(len(self.queryset.filter(content='huge medium small')), 12)

    def test_field_and(self):
        self.assertEqual(pks(self.queryset.filter(name='8').filter(name='4')), [])

    def test_field_or(self):
        self.assertEqual(pks(self.queryset.filter(name='8 4')), [2, 4])

    def test_field_in(self):
        self.assertEqual(pks(self.queryset.filter(name__in=['magazine 2', 'article 4'])), [1, 2])

        self.assertEqual(pks(self.queryset.filter(number__in=[4])),
                         pks(Document.objects.filter(number__in=[4])))

        self.assertEqual(pks(self.queryset.filter(number__in=[4, 8])),
                         pks(Document.objects.filter(number__in=[4, 8])))

    def test_private_fields(self):
        self.assertEqual(pks(self.queryset.filter(django_id=4)),
                         pks(Document.objects.filter(id__in=[4])))
        self.assertEqual(pks(self.queryset.filter(django_id__in=[2, 4])),
                         pks(Document.objects.filter(id__in=[2, 4])))

        self.assertEqual(pks(self.queryset.models(Document)),
                         pks(Document.objects.all()))

    def test_field_startswith(self):
        self.assertEqual(len(self.queryset.filter(name__startswith='magaz')), 4)
        self.assertEqual(len(self.queryset.filter(text__startswith='This is')), 12)

    def test_auto_query(self):
        self.assertEqual(len(self.queryset.auto_query("huge OR medium")), 8)
        self.assertEqual(len(self.queryset.auto_query("huge AND medium")), 0)
        self.assertEqual(len(self.queryset.auto_query("huge -this")), 0)
        self.assertEqual(len(self.queryset.filter(name=AutoQuery("8 OR 4"))), 2)
        self.assertEqual(len(self.queryset.filter(name=AutoQuery("8 AND 4"))), 0)

    def test_value_range(self):
        self.assertEqual(pks(self.queryset.filter(number__lt=3)),
                         pks(Document.objects.filter(number__lt=3)))

        self.assertEqual(pks(self.queryset.filter(django_id__gte=6)),
                         pks(Document.objects.filter(id__gte=6)))

    def test_date_range(self):
        date = datetime.date(year=2010, month=2, day=1)
        self.assertEqual(pks(self.queryset.filter(date__gte=date)),
                         pks(Document.objects.filter(date__gte=date)))

        date = datetime.date(year=2010, month=3, day=1)
        self.assertEqual(pks(self.queryset.filter(date__lte=date)),
                         pks(Document.objects.filter(date__lte=date)))

    def test_order_by(self):
        # private order
        self.assertEqual(pks(self.queryset.order_by("-django_id")),
                         pks(Document.objects.order_by("-id")))

        # value order
        self.assertEqual(pks(self.queryset.order_by("number")),
                         pks(Document.objects.order_by("number")))

        # text order
        self.assertEqual(pks(self.queryset.order_by("summary")),
                         pks(Document.objects.order_by("summary")))

        # date order
        self.assertEqual(pks(self.queryset.order_by("-date")),
                         pks(Document.objects.order_by("-date")))

