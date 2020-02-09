# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
from distutils.core import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="xapian-haystack",
    version="3.0.0",
    description="A Xapian backend for Haystack",
    long_description=read("README.rst"),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Framework :: Django",
    ],
    author="Jorge C. Leitão",
    author_email="jorgecarleitao@gmail.com",
    url="http://github.com/notanumber/xapian-haystack",
    download_url="https://github.com/notanumber/xapian-haystack/archive/3.0.0.tar.gz",
    license="GPL2",
    py_modules=["xapian_backend"],
    install_requires=["django>=2.0", "django-haystack>=2.5.1", "six"],
)
