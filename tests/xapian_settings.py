# Copyright (C) 2009, 2010, 2011, 2012 David Sauve
# Copyright (C) 2009, 2010 Trapeze

import os
from settings import *

INSTALLED_APPS += [
    'xapian_tests',
]

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.xapian_backend.XapianEngine',
        'PATH': os.path.join('tmp', 'test_xapian_query'),
        'INCLUDE_SPELLING': True,
    }
}
