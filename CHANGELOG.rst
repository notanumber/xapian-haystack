=========================
xapian-haystack Changelog
=========================

v3.0.0 (2021-10-28)
-------------------

- Dropped Python 2 support.
- Supported Django versions: 2.2, 3.0, 3.1, 3.2
- Dropped support for xapian < 1.4
- Added new ``xapian_wheel_builder.sh`` script.
- Fixed ``os.path.exists`` race situation.
- Fixed setup.py on non-UTF-8 systems.

A special thanks to Alejandro R. Sedeño who made this release
possible with great contributions.

v2.1.1 (2017-05-18)
-------------------

- Django 1.8 as minimal version, added support for Django 1.9/1.10.
- Adapted default Haystack query from ``contains`` to ``content``.
- Raise ``NotImplementedError`` for endswith queries.
- Supported range search filter (#161).
- Configure ``limit_to_registered_models`` according to haystack docs.
