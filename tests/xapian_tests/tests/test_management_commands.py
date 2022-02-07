import random
from unittest import TestCase

from django.core.management import call_command

from ..models import BlogEntry
from ..search_indexes import BlogSearchIndex
from .test_backend import BackendFeaturesTestCase, HaystackBackendTestCase


class ManagementCommandTestCase(HaystackBackendTestCase, TestCase):

    NUM_BLOG_ENTRIES = 20

    def get_index(self):
        return BlogSearchIndex()

    def setUp(self):
        super().setUp()

        self.sample_objs = []

        for i in range(1, self.NUM_BLOG_ENTRIES + 1):
            entry = BackendFeaturesTestCase.get_entry(i)
            entry.float_number = random.uniform(0.0, 1000.0)
            self.sample_objs.append(entry)
            entry.save()

        self.backend.update(self.index, BlogEntry.objects.all())

    def verify_indexed_document_count(self, expected):
        count = self.backend.document_count()
        self.assertEqual(count, expected)

    def verify_indexed_documents(self):
        """Confirm that the documents in the search index match the database"""

        count = self.backend.document_count()
        self.assertEqual(count, self.NUM_BLOG_ENTRIES)

        pks = set(BlogEntry.objects.values_list("pk", flat=True))
        doc_ids = set()
        database = self.backend._database()
        for pk in pks:
            xapian_doc = database.get_document(pk)
            doc_id = xapian_doc.get_docid()
            doc_ids.add(doc_id)
        database.close()

        self.assertSetEqual(pks, doc_ids)

    def test_basic_commands(self):
        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("rebuild_index", interactive=False, verbosity=0)
        self.verify_indexed_documents()

    def test_remove(self):
        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

        # Remove several instances.
        BlogEntry.objects.get(pk=1).delete()
        BlogEntry.objects.get(pk=2).delete()
        BlogEntry.objects.get(pk=8).delete()
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # Plain ``update_index`` doesn't fix it.
        call_command("update_index", verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # … but remove does:
        call_command("update_index", remove=True, verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES - 3)
