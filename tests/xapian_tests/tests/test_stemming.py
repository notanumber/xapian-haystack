# -*- coding: utf-8 -*-
import datetime
from django.test import TestCase

from haystack.query import SearchQuerySet
from haystack import indexes, connections

from xapian_tests.models import Document
from xapian_tests.tests.test_backend import pks


class DocumentIndex(indexes.SearchIndex):
    text = indexes.CharField(document=True)
    word = indexes.CharField(model_attr='name')

    def get_model(self):
        return Document


class StemmingTestCase(TestCase):

    def setUp(self):
        super(StemmingTestCase, self).setUp()
        # Words (especialy nouns) start with an upper case letter in some languages (German, ...)
        words = ['Connection', 'connection']

        for i in range(1, 3):
            doc = Document()
            doc.number = i
            doc.date = datetime.date.today()
            doc.name = words[i - 1]
            doc.text = words[i - 1]
            doc.save()

        self.index = DocumentIndex()
        self.ui = connections['default'].get_unified_index()
        self.ui.build(indexes=[self.index])

        self.backend = connections['default'].get_backend()
        self.backend.update(self.index, Document.objects.all())

        self.queryset = SearchQuerySet()

    def tearDown(self):
        Document.objects.all().delete()
        super(StemmingTestCase, self).tearDown()

    def test_stemmeing(self):
        object_ids = set(pks(Document.objects.all()))
        # Searches for the exact term sould return both documents
        self.assertEqual(set(pks(self.queryset.auto_query("Connection"))), object_ids)
        self.assertEqual(set(pks(self.queryset.auto_query("connection"))), object_ids)
        # Same should apply for the stemmed values
        self.assertEqual(set(pks(self.queryset.auto_query("connect"))), object_ids)
        self.assertEqual(set(pks(self.queryset.auto_query("Connect"))), object_ids)
