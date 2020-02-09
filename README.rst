Xapian backend for Django-Haystack
==================================

.. _Travis: https://travis-ci.org/notanumber/xapian-haystack

.. image:: https://travis-ci.org/notanumber/xapian-haystack.svg?branch=master
   :target: https://travis-ci.org/notanumber/xapian-haystack
.. image:: https://coveralls.io/repos/notanumber/xapian-haystack/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/notanumber/xapian-haystack?branch=master

Xapian-haystack is a backend of `Django-Haystack <http://haystacksearch.org/>`__
for the `Xapian <http://xapian.org>`__ search engine.
Thanks for checking it out.

You can find more information about Xapian `here <http://getting-started-with-xapian.readthedocs.org>`__.


Features
--------

Xapian-Haystack provides all the standard features of Haystack:

- Weighting
- Faceted search (date, query, etc.)
- Sorting
- Spelling suggestions
- EdgeNGram and Ngram (for autocomplete)

Limitations
-----------

The `endswith` search operation is not supported by Xapian-Haystack.


Requirements
------------

- Python 3.5+
- Django 2.0+
- Django-Haystack 2.5.1
- Xapian 1.4.0+

In particular, we build-test this backend in `Travis`_ using:

- Python 3.5+
- Django 2.0+ and 3.0+
- Django-Haystack (master)
- Xapian 1.4.9 and 1.4.14


Installation
------------

First, install Xapian in your machine e.g. with the script provided,
`install_xapian.sh`. Call it after activating the virtual environment to install::

    source <path>/bin/activate
    ./install_xapian.sh <version>

`<version>` must be >=1.3.0 for Python 3 envs. This takes around 10 minutes.

Finally, install Xapian-Haystack by running::

    pip install git+https://github.com/notanumber/xapian-haystack.git


Configuration
-------------

Xapian is configured as other backends of Haystack.
You have to define the connection to the database,
which is done to a path to a directory, e.g::

    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'xapian_backend.XapianEngine',
            'PATH': os.path.join(os.path.dirname(__file__), 'xapian_index')
        },
    }

The backend has the following optional settings:

- ``HAYSTACK_XAPIAN_LANGUAGE``: the stemming language; the default is `english` and the list of available languages
  can be found `here <http://xapian.org/docs/apidoc/html/classXapian_1_1Stem.html>`__.

- ``HAYSTACK_XAPIAN_WEIGHTING_SCHEME``: a tuple with parameters to be passed to the weighting scheme
  `BM25 <https://en.wikipedia.org/wiki/Okapi_BM25>`__.
  By default, it uses the same parameters as Xapian recommends; this setting allows you to change them.

- ``HAYSTACK_XAPIAN_FLAGS``: the options used to parse `AutoQueries`;
  the default is ``FLAG_PHRASE | FLAG_BOOLEAN | FLAG_LOVEHATE | FLAG_WILDCARD | FLAG_PURE_NOT``
  See `here <http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html>`__ for more information
  on what they mean.

- ``HAYSTACK_XAPIAN_STEMMING_STRATEGY``: This option lets you chose the stemming strategy used by Xapian. Possible
  values are ``STEM_NONE``, ``STEM_SOME``, ``STEM_ALL``, ``STEM_ALL_Z``, where ``STEM_SOME`` is the default.
  See `here <http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html#ac7dc3b55b6083bd3ff98fc8b2726c8fd>`__ for
  more information about the different strategies.


Testing
-------

Xapian-Haystack has a test suite in continuous deployment in `Travis`_. The script
``.travis.yml`` contains the steps required to run the test suite.


Source
------

The source code can be found in `github <http://github.com/notanumber/xapian-haystack/>`_.


Credits
-------

Xapian-Haystack is maintained by `Jorge C. Leitão <http://jorgecarleitao.net>`__;
`David Sauve <mailto:david.sauve@bag-of-holding.com>`__ was the main contributor of Xapian-Haystack and
Xapian-Haystack was originally funded by `Trapeze <http://www.trapeze.com>`__.
`Claudep <http://www.2xlibre.net>`__ is a frequent contributor.
`ANtlord <https://github.com/ANtlord>`__ implemented support for EdgeNgram and Ngram.


License
-------

Xapian-haystack is free software licenced under GNU General Public Licence v2 and
Copyright (c) 2009, 2010, 2011, 2012 David Sauve, 2009, 2010 Trapeze, 2014 Jorge C. Leitão.
It may be redistributed under the terms specified in the LICENSE file.


Questions, Comments, Concerns:
------------------------------

Feel free to open an issue `here <http://github.com/notanumber/xapian-haystack/issues>`__
or pull request your work.

You can ask questions on the django-haystack `mailing list <http://groups.google.com/group/django-haystack/>`_:
or in the irc ``#haystack``.
