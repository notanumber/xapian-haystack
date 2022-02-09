import sys
from io import StringIO
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
            self.sample_objs.append(entry)
            entry.save()

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

    def test_clear(self):
        self.backend.update(self.index, BlogEntry.objects.all())
        self.verify_indexed_documents()

        call_command("clear_index", interactive=False, verbosity=0)
        self.verify_indexed_document_count(0)

    def test_update(self):
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

    def test_rebuild(self):
        self.verify_indexed_document_count(0)

        call_command("rebuild_index", interactive=False, verbosity=0)
        self.verify_indexed_documents()

    def test_remove(self):
        self.verify_indexed_document_count(0)

        call_command("update_index", verbosity=0)
        self.verify_indexed_documents()

        # Remove three instances.
        three_pks = BlogEntry.objects.all()[:3].values_list("pk", flat=True)
        BlogEntry.objects.filter(pk__in=three_pks).delete()
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # Plain ``update_index`` doesn't fix it.
        call_command("update_index", verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES)

        # … but remove does:
        call_command("update_index", remove=True, verbosity=0)
        self.verify_indexed_document_count(self.NUM_BLOG_ENTRIES - 3)

    def test_multiprocessing(self):
        self.verify_indexed_document_count(0)

        old_stderr = sys.stderr
        sys.stderr = StringIO()
        call_command(
            "update_index",
            verbosity=2,
            workers=10,
            batchsize=2,
        )
        err = sys.stderr.getvalue()
        sys.stderr = old_stderr
        print(err)
        self.assertNotIn("xapian.DatabaseLockError", err)
        self.verify_indexed_documents()
