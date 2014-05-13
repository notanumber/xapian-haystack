Xapian backend for Django-Haystack
==================================

.. image:: https://travis-ci.org/notanumber/xapian-haystack.svg?branch=master
   :target: https://travis-ci.org/notanumber/xapian-haystack

.. _Django-Haystack: http://haystacksearch.org/

.. _Xapian: http://xapian.org

Xapian-haystack is a backend of Django-Haystack_ for the Xapian_ search engine.
Thanks for checking it out.

.. _here: http://getting-started-with-xapian.readthedocs.org/en/latest/index.html

Haystack is an API for searching in Django websites. xapian-haystack is
a bridge from Haystack, the API, to Xapian, a search engine.

Xapian is a powerful search engine written in C++ that uses probabilistic measures
to efficient search on text. More useful information can be found here_ (read the docs).

Requirements
------------

.. _yet: http://trac.xapian.org/ticket/346

- Python 2.4+ (Python 3.3 not support yet_).
- Django 1.5+
- Django-Haystack 2.0.X
- Xapian 1.0.13+

.. _Travis:

In particular, the backend is built on Travis_ using:

- Python 2.7.6
- Django 1.6.4
- Django-Haystack (latest)
- Xapian 1.2.8 (libxapian22)

Features
--------

Xapian-Haystack provides all the standard features of Haystack:

- Weighting
- Faceted search (date, query, etc.)
- Sorting
- Spelling suggestions

.. _stemmer: https://en.wikipedia.org/wiki/Stemming

Additionally, Xapian also uses a stemmer_ to create its index,
with support to different languages.

Installation
------------

.. _`this gist`: https://gist.github.com/jleclanche/ea0bc333b20ef6aa749c

First, you need to install Xapian in your machine.
We recommend installing it on the virtual environment using `this gist`_.
First you activate the virtual environment, and them run the script.

You can test the installation was successful by running::

    python -c "import xapian"

Finally, install Xapian-haystack by running::

    pip install git+https://github.com/jorgecarleitao/xapian-haystack.git

Configuration
-------------

Xapian is configured as other backends of Haystack.
You have to define the connection to the database, which is done to a path to a directory, e.g::

    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'haystack.backends.xapian_backend.XapianEngine',
            'PATH': os.path.join(os.path.dirname(__file__), 'xapian_index')
        },
    }

   .. _languages: http://xapian.org/docs/apidoc/html/classXapian_1_1Stem.html

The backend includes the following settings:

- `HAYSTACK_XAPIAN_LANGUAGE`: the stemming language.  By default is english, the list of available languages
  can be found `here <languages>`_.

- `HAYSTACK_XAPIAN_WEIGHTING_SCHEME` - sets the weighting scheme used during search.
  See the default scheme in the source code or see `Xapian::BM25Weight::BM25Weight in the Xapian documentation <http://xapian.org/docs/apidoc/html/classXapian_1_1BM25Weight.html>`_
  for further information.

- `HAYSTACK_XAPIAN_FLAGS`: used to further configure how indexes are stored and manipulated.
  By default, this value is set to `FLAG_PHRASE | FLAG_BOOLEAN | FLAG_LOVEHATE | FLAG_WILDCARD | FLAG_PURE_NOT`.
  See the `Xapian::QueryParser::feature_flag in the Xapian documentation <http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html>`_
  for further explanation of the available Xapian.QueryParser flags.

Testing
-------

Xapian-Haystack has a test suite in continuous deployment in Travis_. The script `.travis.yml` contains
all the steps to run the test suite on your machine.

Source
------

.. _github: http://github.com/notanumber/xapian-haystack/

The source code can be found in github_.

Credits
-------

This fork of xapian-haystack is maintained by Jorge C. Leitão but
`David Sauve <mailto:david.sauve@bag-of-holding.com>`_ was the main contributor of Xapian-Haystack;
Xapian-haystack was originally funded by `Trapeze <http://www.trapeze.com>`_.

License
-------

Xapian-haystack is Copyright (c) 2009, 2010, 2011, 2012 David Sauve, 2009, 2010 Trapeze and 2014 by Jorge C. Leitão.
It is free software, and may be redistributed under the terms specified in the LICENSE file.

Questions, Comments, Concerns:
------------------------------

Feel free to open an issue here: `github.com/notanumber/xapian-haystack/issues <http://github.com/notanumber/xapian-haystack/issues>`_
or pull request your work.

You can ask questions on the django-haystack `mailing list <http://groups.google.com/group/django-haystack/>`_
or in the `irc channel <irc://irc.freenode.net/haystack>`_.
