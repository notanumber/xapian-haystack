# Copyright (C) 2009, 2010, 2011 David Sauve
# Copyright (C) 2009, 2010 Trapeze

import os
from settings import *

INSTALLED_APPS += [
    'xapian_tests',
]

HAYSTACK_SEARCH_ENGINE = 'xapian'
HAYSTACK_XAPIAN_PATH = os.path.join('tmp', 'test_xapian_query')
HAYSTACK_INCLUDE_SPELLING = True
