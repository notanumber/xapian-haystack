#!/bin/bash

uname_sysname="$(uname -s)"
case "${uname_sysname}" in
    Linux)
        ;;
    Darwin)
        ;;
    *)
        echo "Platform ${uname_sysname} is not supported"
        exit 1
esac

VERSION=${1-${XAPIAN_VERSION}}
if [ -z "$VERSION" ]; then
    echo "usage: $0 version_number" 1>&2
    exit 1
fi

exittrap() { :; }
for sig in 1 2 13 15; do trap "exit $(($sig + 128))" $sig; done
trap 'exittrap' EXIT

WHL_DEST=$(pwd)
if [ "x${WORKSPACE}" = "x" ]; then
    WORKSPACE=$(mktemp -d -t "xapian-builder-XXXXXX") || die "Unable to mktemp"
    exittrap() { rm -rf "${WORKSPACE}"; }
fi
echo "Building in ${WORKSPACE}."
pushd ${WORKSPACE}

echo "Preparing build virtualenv..."
VE="${WORKSPACE}/ve"
python3 -m venv ${VE}
${VE}/bin/pip install --upgrade pip wheel setuptools

# xapian before 1.4.12 had issues building with sphinx>=2
SPHINX2_FIXED_VERSION=1.4.12
if [ $(printf "${VERSION}\n${SPHINX2_FIXED_VERSION}" | sort -V | head -n1) = "${SPHINX2_FIXED_VERSION}" ]; then
    ${VE}/bin/pip install sphinx
else
    ${VE}/bin/pip install "sphinx<2"
fi

CORE="xapian-core-${VERSION}"
BINDINGS="xapian-bindings-${VERSION}"

echo "Downloading source..."
curl -O https://oligarchy.co.uk/xapian/${VERSION}/${CORE}.tar.xz
curl -O https://oligarchy.co.uk/xapian/${VERSION}/${BINDINGS}.tar.xz

echo "Extracting source..."
mkdir src
tar -C src -xf "${CORE}.tar.xz"
tar -C src -xf "${BINDINGS}.tar.xz"

# building xapian-core
mkdir target

prefix=${WORKSPACE}/target
pprefix=${prefix}
case "${uname_sysname}" in
    Linux)
    while [ ${#pprefix} -lt 7 ]; do
        # add padding as needed
        pprefix=${pprefix}/.
    done
    ;;
esac

echo "Building xapian core..."
(
    cd src/${CORE}
    ./configure --prefix=${pprefix}
    make
    make install
)

XAPIAN_CONFIG=${prefix}/bin/xapian-config*

echo "Building xapian python3 bindings..."
(
    cd src/${BINDINGS}
    # We're building python3 bindings here, and we need to contort things to make it work.
    # We want the xapian-config we just built.
    # We want the sphinx we just put in a virtualenv because the xapian bindings insist on making their docs.
    # We use the python3 from that same virtualenv, because the xapian bindings don't use the shebang line of sphinx-build.
    # We override PYTHON3_LIB because if we don't then the bindings will be installed in the virutalenv, despite what we set prefix to.
    ./configure --prefix=$prefix --with-python3 XAPIAN_CONFIG=${XAPIAN_CONFIG} SPHINX_BUILD=${VE}/bin/sphinx-build PYTHON3=${VE}/bin/python3 PYTHON3_LIB=${prefix}
    make
    make install
)

echo "preparing xapian wheel..."
for file in $(find ${prefix}/xapian -name '*.so'); do
    case "${uname_sysname}" in
        Linux)
            # Binary patch rpath to be '$ORIGIN' as needed.
            rpath_offset=$(strings -t d ${file} | grep "${pprefix}/lib" | awk '{ printf $1; }')
            printf "\$ORIGIN\x00" | dd of=${file} obs=1 seek=${rpath_offset} conv=notrunc 2>/dev/null
            # Verify
            readelf -d ${file} | grep RPATH | grep -q ORIGIN
            libxapian_name=$(ldd $file | grep libxapian | awk '{ printf $1; }')
            ;;
        Darwin)
            libxapian_name=$(otool -L $file | grep -o libxapian.* | awk '{ printf $1; }')
            install_name_tool -change "${prefix}/lib/${libxapian_name}" "@loader_path/${libxapian_name}" "${file}"
            ;;
    esac
done

# Copy libxapian into place alongside the python bindings.
cp "${prefix}/lib/${libxapian_name}" "${prefix}/xapian"
case "${uname_sysname}" in
    Darwin)
        install_name_tool -id "@loader_path/${libxapian_name}" "${prefix}/xapian/${libxapian_name}"
        ;;
esac

# Prepare the scaffolding for the wheel
cat > $prefix/setup.py <<EOF
from setuptools import setup

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            _bdist_wheel.finalize_options(self)
            # Really, this is not pure python
            self.root_is_pure = False
except ImportError:
    bdist_wheel = None

setup(name='xapian',
      version='${VERSION}',
      description='Xapian Bindings for Python3',
      packages=['xapian'],
      cmdclass={'bdist_wheel': bdist_wheel},
      include_package_data=True,
      zip_safe=False)
EOF

cat >$prefix/MANIFEST.in <<EOF
include xapian/*
EOF

(
    cd target
    ${VE}/bin/python setup.py bdist_wheel
    cp dist/*.whl ${WHL_DEST}
)
popd
rm -rf "${WORKSPACE}"
exittrap() { :; }
