import os
from django.conf import settings

DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = 'xapian_tests.db'

INSTALLED_APPS = (
    'haystack',
    'xapian_haystack.tests',
)

ROOT_URLCONF = 'tests.urls'

HAYSTACK_SEARCH_ENGINE = 'xapian'
HAYSTACK_XAPIAN_PATH = os.path.join('tmp', 'test_xapian_query')
