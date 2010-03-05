# Copyright (C) 2009-2010 David Sauve, Trapeze.  All rights reserved.

import os
from settings import *

INSTALLED_APPS += [
    'xapian_tests',
]

HAYSTACK_SEARCH_ENGINE = 'xapian'
HAYSTACK_XAPIAN_PATH = os.path.join('tmp', 'test_xapian_query')
HAYSTACK_INCLUDE_SPELLING = True
