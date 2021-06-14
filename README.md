# Fork of Xapian backend for Django-Haystack maintained by somebody...

[![image](https://travis-ci.org/notanumber/xapian-haystack.svg?branch=master)](https://travis-ci.org/notanumber/xapian-haystack)

[![image](https://coveralls.io/repos/notanumber/xapian-haystack/badge.svg?branch=master&service=github)](https://coveralls.io/github/notanumber/xapian-haystack?branch=master)

Xapian-haystack is a backend of
[Django-Haystack](http://haystacksearch.org/) for the
[Xapian](http://xapian.org) search engine. Thanks for checking it out.

You can find more information about Xapian
[here](http://getting-started-with-xapian.readthedocs.org).

## Features

Xapian-Haystack provides all the standard features of Haystack:

-   Weighting
-   Faceted search (date, query, etc.)
-   Sorting
-   Spelling suggestions
-   EdgeNGram and Ngram (for autocomplete)

## Limitations

The [endswith]{.title-ref} search operation is not supported by
Xapian-Haystack.

# Initial package requirements:

## Ubuntu 18.04/20.04 and probably future versions:

```bash
sudo apt install curl gcc g++ python3-dev make libxapian30
```

After that you need to install Xapian cloned outside of project repository using:
`./install_xapian __libxapian30_version__`

You will find version of libxapian30 just using `apt search`.

## macOS with Intel/AMD chip:

To be continued... I remember there is some clang/gcc quirk.

## macOS with M1:

You need to use python3.6 using `pythonM1` hack described here:
https://youtrack.jetbrains.com/issue/PY-46290

Or just use my implementation made out of ...:
```
#!/usr/bin/env zsh
mydir=${0:a:h}
/usr/bin/arch -x86_64 $mydir/python3.6 $*
```

Also use `runx86` implementation from here:
https://github.com/HoshiYamazaki/apple-arm-utils

Use it ALWAYS when you run python commands, especially when installing pip packages,
because when you will not use it, it will try to use ARM packages.

## Tested on:

* r5 3600 based-Hackintosh
* Mac Mini 2020 with M1 cpu

## Requirements

-   Python 2.7 or 3+
-   Django 1.8+
-   Django-Haystack 2.5.1
-   Xapian 1.2.19+

In particular, we build-test this backend in
[Travis](https://travis-ci.org/notanumber/xapian-haystack) using:

-   Python 2.7 and 3.4
-   Django 1.8, 1.9 and 1.10
-   Django-Haystack (master)
-   Xapian 1.2.19 (Python 2 only), 1.3.3 (both), and 1.4.1 (both)

## Installation

First, install Xapian in your machine e.g. with the script provided,
[install_xapian.sh]{.title-ref}. Call it after activating the virtual
environment to install:

    source <path>/bin/activate
    ./install_xapian.sh <version>

[\<version>]{.title-ref} must be \>=1.3.0 for Python 3 envs. This takes
around 10 minutes.

Finally, install Xapian-Haystack by running:

    pip install git+https://github.com/notanumber/xapian-haystack.git

## Configuration

Xapian is configured as other backends of Haystack. You have to define
the connection to the database, which is done to a path to a directory,
e.g:

    HAYSTACK_CONNECTIONS = {
        'default': {
            'ENGINE': 'xapian_backend.XapianEngine',
            'PATH': os.path.join(os.path.dirname(__file__), 'xapian_index')
        },
    }

The backend has the following optional settings:

-   `HAYSTACK_XAPIAN_LANGUAGE`: the stemming language; the default is
    [english]{.title-ref} and the list of available languages can be
    found
    [here](http://xapian.org/docs/apidoc/html/classXapian_1_1Stem.html).
-   `HAYSTACK_XAPIAN_WEIGHTING_SCHEME`: a tuple with parameters to be
    passed to the weighting scheme
    [BM25](https://en.wikipedia.org/wiki/Okapi_BM25). By default, it
    uses the same parameters as Xapian recommends; this setting allows
    you to change them.
-   `HAYSTACK_XAPIAN_FLAGS`: the options used to parse
    [AutoQueries]{.title-ref}; the default is
    `FLAG_PHRASE | FLAG_BOOLEAN | FLAG_LOVEHATE | FLAG_WILDCARD | FLAG_PURE_NOT`
    See
    [here](http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html)
    for more information on what they mean.
-   `HAYSTACK_XAPIAN_STEMMING_STRATEGY`: This option lets you chose the
    stemming strategy used by Xapian. Possible values are `STEM_NONE`,
    `STEM_SOME`, `STEM_ALL`, `STEM_ALL_Z`, where `STEM_SOME` is the
    default. See
    [here](http://xapian.org/docs/apidoc/html/classXapian_1_1QueryParser.html#ac7dc3b55b6083bd3ff98fc8b2726c8fd)
    for more information about the different strategies.

## Testing

Xapian-Haystack has a test suite in continuous deployment in
[Travis](https://travis-ci.org/notanumber/xapian-haystack). The script
`.travis.yml` contains the steps required to run the test suite.

## Source

The source code can be found in
[github](http://github.com/notanumber/xapian-haystack/).

## Credits

Xapian-Haystack is maintained by [Jorge C.
Leitão](http://jorgecarleitao.net); [David
Sauve](mailto:david.sauve@bag-of-holding.com) was the main contributor
of Xapian-Haystack and Xapian-Haystack was originally funded by
[Trapeze](http://www.trapeze.com). [Claudep](http://www.2xlibre.net) is
a frequent contributor. [ANtlord](https://github.com/ANtlord)
implemented support for EdgeNgram and Ngram.

## License

Xapian-haystack is free software licenced under GNU General Public
Licence v2 and Copyright (c) 2009, 2010, 2011, 2012 David Sauve, 2009,
2010 Trapeze, 2014 Jorge C. Leitão. It may be redistributed under the
terms specified in the LICENSE file.

## Questions, Comments, Concerns:

Feel free to open an issue
[here](http://github.com/notanumber/xapian-haystack/issues) or pull
request your work.

You can ask questions on the django-haystack [mailing
list](http://groups.google.com/group/django-haystack/): or in the irc
`#haystack`.
