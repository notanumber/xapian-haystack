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
HAYSTACK_INCLUDE_SPELLING = True
