#!/usr/bin/env bash
# first argument of the script is Xapian version (e.g. 1.2.19)

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "usage: $0 version_number" 1>&2
    exit 1
fi

# prepare
mkdir -p $VIRTUAL_ENV/packages && cd $VIRTUAL_ENV/packages

CORE=xapian-core-$VERSION
BINDINGS=xapian-bindings-$VERSION

# download
echo "Downloading source..."
curl -O https://oligarchy.co.uk/xapian/$VERSION/${CORE}.tar.xz
curl -O https://oligarchy.co.uk/xapian/$VERSION/${BINDINGS}.tar.xz

# extract
echo "Extracting source..."
tar xf ${CORE}.tar.xz
tar xf ${BINDINGS}.tar.xz

# install
echo "Installing Xapian-core..."
cd $VIRTUAL_ENV/packages/${CORE}
./configure --prefix=$VIRTUAL_ENV && make && make install

PYTHON_FLAG=--with-python3

if [ $VERSION = "1.3.3" ]; then
    XAPIAN_CONFIG=$VIRTUAL_ENV/bin/xapian-config-1.3
else
    XAPIAN_CONFIG=
fi

# The bindings for Python require python-sphinx
echo "Installing Python-Sphinx..."
SPHINX2_FIXED_VERSION=1.4.12
if [ $(printf "${VERSION}\n${SPHINX2_FIXED_VERSION}" | sort -V | head -n1) = "${SPHINX2_FIXED_VERSION}" ]; then
    pip install sphinx
else
    pip install "sphinx<2"
fi

echo "Installing Xapian-bindings..."
cd $VIRTUAL_ENV/packages/${BINDINGS}
./configure --prefix=$VIRTUAL_ENV $PYTHON_FLAG XAPIAN_CONFIG=$XAPIAN_CONFIG && make && make install

# clean
cd $VIRTUAL_ENV
rm -rf $VIRTUAL_ENV/packages

# test
echo "Testing Xapian..."
python -c "import xapian"
