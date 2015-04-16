Xapian backend for Django-Haystack
==================================

.. _Travis: https://travis-ci.org/notanumber/xapian-haystack

.. image:: https://travis-ci.org/notanumber/xapian-haystack.svg?branch=master
   :target: https://travis-ci.org/notanumber/xapian-haystack

Xapian-haystack is a backend of `Django-Haystack <http://haystacksearch.org/>`_
for the `Xapian <http://xapian.org>`_ search engine.
Thanks for checking it out.

You can find more information about Xapian `here <http://getting-started-with-xapian.readthedocs.org>`_.


Features
--------

Xapian-Haystack provides all the standard features of Haystack:

- Weighting
- Faceted search (date, query, etc.)
- Sorting
- Spelling suggestions
- EdgeNGram and Ngram (for autocomplete)


Requirements
------------

- Python 2.4+ (Python 3.3 not support `yet <http://trac.xapian.org/ticket/346>`_).
- Django 1.6+
- Django-Haystack 2.0.X
- Xapian 1.0.13+

In particular, we build this backend on `Travis`_ using:

- Python 2.7.6
- Django 1.6, 1.7 and 1.8
- Django-Haystack (master)
- Xapian 1.2.8 (libxapian22)


Installation
------------

First you need to install Xapian in your machine.
We recommend installing it on the virtual environment using
`this gist <https://gist.github.com/jleclanche/ea0bc333b20ef6aa749c>`_:
activate the virtual environment and run the script.

You can test if the installation was successful by running::

    python -c "import xapian"

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
  can be found `here <http://xapian.org/docs/apidoc/html/classXapian_1_1Stem.html>`_.

- ``HAYSTACK_XAPIAN_WEIGHTING_SCHEME``: a tuple with parameters to be passed to the weighting scheme
  `BM25 <https://en.wikipedia.org/wiki/Okapi_BM25>`_.
  By default, it uses the same parameters as Xapian recommends; this setting allows you to change them.

- ``HAYSTACK_XAPIAN_FLAGS``: the options used to parse `AutoQueries`;
  the default is ``FLAG_PHRASE | FLAG_BOOLEAN | FLAG_LOVEHATE | FLAG_WILDCARD | FLAG_PURE_NOT``
  See `here <http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html>`_ for more information
  on what they mean.

- ``HAYSTACK_XAPIAN_STEMMING_STRATEGY``: This option lets you chose the stemming strategy used by Xapian. Possible
  values are ``STEM_NONE``, ``STEM_SOME``, ``STEM_ALL``, ``STEM_ALL_Z``, where ``STEM_SOME`` is the default.
  See `here <http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html#ac7dc3b55b6083bd3ff98fc8b2726c8fd>`_ for
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

Xapian-Haystack is maintained by Jorge C. Leitão;
`David Sauve <mailto:david.sauve@bag-of-holding.com>`_ was the main contributor of Xapian-Haystack and
Xapian-Haystack was originally funded by `Trapeze <http://www.trapeze.com>`_.
`ANtlord <https://github.com/ANtlord>`_ implemented support for EdgeNgram and Ngram.


License
-------

Xapian-haystack is free software licenced under GNU General Public Licence v2 and
Copyright (c) 2009, 2010, 2011, 2012 David Sauve, 2009, 2010 Trapeze, 2014 Jorge C. Leitão.
It may be redistributed under the terms specified in the LICENSE file.


Questions, Comments, Concerns:
------------------------------

Feel free to open an issue `here <http://github.com/notanumber/xapian-haystack/issues>`_
or pull request your work.

You can ask questions on the django-haystack `mailing list <http://groups.google.com/group/django-haystack/>`_
or in the irc ``#haystack``.
