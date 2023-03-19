from distutils.core import setup
from pathlib import Path


def read(fname):
    return (Path(__file__).parent / fname).read_text(encoding='utf-8')


setup(
    name='xapian-haystack',
    version='3.1.0',
    description='A Xapian backend for Haystack',
    long_description=read('README.rst'),
    long_description_content_type='text/x-rst',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Framework :: Django',
        'Programming Language :: Python :: 3 :: Only',
    ],
    author='Jorge C. Leitão',
    author_email='jorgecarleitao@gmail.com',
    url='https://github.com/notanumber/xapian-haystack',
    license='GPL2',
    py_modules=['xapian_backend'],
    install_requires=[
        'django>=3.2',
        'django-haystack>=2.8.0',
        'filelock>=3.4',
    ]
)
