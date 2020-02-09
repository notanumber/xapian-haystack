#!/usr/bin/env bash
# first argument of the script is Xapian version (e.g. 1.2.19)

VERSION=$1
VIRTUAL_ENV=`realpath $VIRTUAL_ENV`

if [ -z "$VERSION" ]; then
    echo "usage: $0 version_number" 1>&2
    exit 1
fi

# funcions
vercomp () {
    if [[ $1 == $2 ]]
    then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    # fill empty fields in ver1 with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++))
    do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++))
    do
        if [[ -z ${ver2[i]} ]]
        then
            # fill empty fields in ver2 with zeros
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]}))
        then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]}))
        then
            return 2
        fi
    done
    return 0
}

# prepare
mkdir -p $VIRTUAL_ENV/packages

CORE=xapian-core-$VERSION
BINDINGS=xapian-bindings-$VERSION

# download
echo "Downloading source..."
(cd $VIRTUAL_ENV/packages && curl -L -O -C - https://oligarchy.co.uk/xapian/$VERSION/${CORE}.tar.xz)
(cd $VIRTUAL_ENV/packages && curl -L -O -C - https://oligarchy.co.uk/xapian/$VERSION/${BINDINGS}.tar.xz)

# extract
echo "Extracting source..."
(cd $VIRTUAL_ENV/packages && tar Jxf $VIRTUAL_ENV/packages/${CORE}.tar.xz)
(cd $VIRTUAL_ENV/packages && tar Jxf $VIRTUAL_ENV/packages/${BINDINGS}.tar.xz)

# install
echo "Installing Xapian-core..."
(cd $VIRTUAL_ENV/packages/${CORE} \
    && ./configure --prefix=$VIRTUAL_ENV \
    && make \
    && make install)

PYV=`python -c "import sys;t='{v[0]}'.format(v=list(sys.version_info[:1]));sys.stdout.write(t)";`

if [ $PYV = "2" ]; then
    PYTHON_FLAG=--with-python
else
    PYTHON_FLAG=--with-python3
fi

if [ $VERSION = "1.3.3" ]; then
    XAPIAN_CONFIG=$VIRTUAL_ENV/bin/xapian-config-1.3
else
    XAPIAN_CONFIG=
fi

# The bindings for Python require python-sphinx
vercomp $VERSION "1.4.11"
case $? in
    0) SPHINX_VERSION="<1.7.0";; # =
    1) SPHINX_VERSION=">=2.0,<3.0";; # >
    2) SPHINX_VERSION="<1.7.0";; # <
esac

echo "Installing Python-Sphinx..."
pip install -U "Sphinx${SPHINX_VERSION}"

echo "Installing Xapian-bindings..."
(cd $VIRTUAL_ENV/packages/${BINDINGS} \
    && ./configure --prefix=$VIRTUAL_ENV $PYTHON_FLAG XAPIAN_CONFIG=$XAPIAN_CONFIG \
    && make \
    && make install)

# clean
cd $VIRTUAL_ENV
rm -rf $VIRTUAL_ENV/packages

# test
echo "Testing Xapian..."
python -c "import xapian" && echo "OK"
