import os
from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='xapian-haystack',
    version='1.0.1beta',
    description="A Xapian backend for Haystack",
    long_description=read('README'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Framework :: Django',
    ],
    author='David Sauve',
    author_email='david.sauve@bag-of-holding.com',
    url='http://github.com/notanumber/xapian-haystack',
    license='GPL2',
    py_modules=['xapian_backend'],
)
