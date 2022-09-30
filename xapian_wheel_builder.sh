#!/bin/sh

uname_sysname="$(uname -s)"
case "${uname_sysname}" in
    Linux)
        ;;
    Darwin)
        ;;
    FreeBSD)
        ;;
    *)
        echo "Platform ${uname_sysname} is not supported"
        exit 1
esac

PYTHON=$(command -v python3)
# shellcheck disable=SC2046
set -- $(getopt p: "$@")
for opt; do
    case "$opt" in
        -p)
            PYTHON="$2"; shift 2 ;;
        --)
            shift ; break ;;
    esac
done

usage() {
    echo "usage: $0 [-p <path-to-python3>] version_number" 1>&2
}

version_at_least() {
    test "$(printf "%s\\n%s" "${VERSION}" "${1}" | sort -V | head -n1)" = "${1}"
    return $?
}

VERSION=${1-${XAPIAN_VERSION}}
if [ -z "${VERSION}" ]; then
    usage
    exit 1
fi

if [ -z "${PYTHON}" ] || [ ! -x "${PYTHON}" ]; then
    usage
    echo "error: could not find python3, please specify with -p" 1>&2
    exit 1
fi

exittrap() { :; }
sigtrap() {
    # Whether or not exittrap runs on EXIT due to a signal is not defined.
    # We use it for cleanup, and cleaning up twice is not a problem,
    # so let's do that.
    exittrap
    exit $(($1 + 128))
}
for sig in 1 2 13 15; do
    # shellcheck disable=SC2064
    trap "sigtrap $sig" $sig
done
trap 'exittrap' EXIT

WHL_DEST=$(pwd)
TMPDIR=$(mktemp -d -t "xapian-builder-XXXXXX") || die "Unable to mktemp"
exittrap() { rm -rf "${TMPDIR}"; }

set -e

echo "Building in ${TMPDIR}."
cd "${TMPDIR}"

echo "Preparing build virtualenv..."
VE="${TMPDIR}/ve"
"${PYTHON}" -m venv "${VE}"
"${VE}/bin/python" -m pip install --upgrade pip wheel setuptools

# xapian before 1.4.12 had issues building with sphinx>=2
if version_at_least "1.4.12"; then
    "${VE}/bin/pip" install sphinx
else
    "${VE}/bin/pip" install "sphinx<2"
fi

BASE_URI="https://oligarchy.co.uk/xapian/"
CORE="xapian-core-${VERSION}"
BINDINGS="xapian-bindings-${VERSION}"
CORE_URI="${BASE_URI}${VERSION}/${CORE}.tar.xz"
BINDINGS_URI="${BASE_URI}${VERSION}/${BINDINGS}.tar.xz"

echo "Downloading source..."
curl -O "${CORE_URI}"
curl -O "${BINDINGS_URI}"

echo "Extracting source..."
mkdir src
tar -C src -xf "${CORE}.tar.xz"
tar -C src -xf "${BINDINGS}.tar.xz"

# building xapian-core
mkdir target

prefix=${TMPDIR}/target
pprefix=${prefix}
case "${uname_sysname}" in
    Linux|FreeBSD)
    while [ ${#pprefix} -lt 7 ]; do
        # add padding as needed
        pprefix=${pprefix}/.
    done
    ;;
esac

JFLAG=1
if [ "$2" = "--use-all-cores" ]; then
  JFLAG=$(($(getconf _NPROCESSORS_ONLN) + 1))
fi

echo "Building xapian core..."
(
    cd "src/${CORE}"
    ./configure --prefix="${pprefix}"
    make -j$JFLAG
    make install
)

XAPIAN_CONFIG="${prefix}/bin/xapian-config*"

echo "Building xapian python3 bindings..."
(
    cd "src/${BINDINGS}"
    # We're building python3 bindings here, and we need to contort things to make it work.
    # We want the xapian-config we just built.
    # We want the sphinx we just put in a virtualenv because the xapian bindings insist on making their docs.
    # We use the python3 from that same virtualenv, because the xapian bindings don't use the shebang line of sphinx-build.
    # We override PYTHON3_LIB because if we don't then the bindings will be installed in the virutalenv, despite what we set prefix to.
    case "${uname_sysname}" in
        FreeBSD)
            sed -i '' -e 's|-lstdc++||' configure
            ;;
    esac
    ./configure --prefix="$prefix" --with-python3 XAPIAN_CONFIG="${XAPIAN_CONFIG}" SPHINX_BUILD="${VE}/bin/sphinx-build" PYTHON3="${VE}/bin/python3" PYTHON3_LIB="${prefix}"
    make
    make install
)

binary_patch_rpath() {
    file="${1}"
    case "${uname_sysname}" in
        Linux|FreeBSD)
            # Binary patch rpath to be '$ORIGIN' as needed.
            rpath_offset=$(strings -t d "${file}" | grep "${pprefix}/lib" | awk '{ printf $1; }')
            printf "\$ORIGIN\\000" | dd of="${file}" obs=1 seek="${rpath_offset}" conv=notrunc 2>/dev/null
            # Verify
            readelf -d "${file}" | grep RUNPATH | grep -q ORIGIN
            libxapian_name=$(ldd "${file}" | grep libxapian | awk '{ printf $1; }')
            ;;
        Darwin)
            libxapian_name=$(otool -L "${file}" | grep -o 'libxapian.*' | awk '{ printf $1; }')
            install_name_tool -change "${prefix}/lib/${libxapian_name}" "@loader_path/${libxapian_name}" "${file}"
            ;;
    esac
}

echo "preparing xapian wheel..."
for file in "${prefix}"/xapian/*.so; do
    binary_patch_rpath "${file}"
done

# Copy libxapian into place alongside the python bindings.
cp "${prefix}/lib/${libxapian_name}" "${prefix}/xapian"
case "${uname_sysname}" in
    Darwin)
        install_name_tool -id "@loader_path/${libxapian_name}" "${prefix}/xapian/${libxapian_name}"
        ;;
esac

for file in "${prefix}"/bin/xapian-delve*; do
    binary_patch_rpath "${file}"
    cp "${file}" "${prefix}/xapian"
done

# Prepare the scaffolding for the wheel
cat > "${prefix}/setup.py" <<EOF
from pathlib import Path
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

cwd = Path(__file__).parent
readme = (cwd / 'README').read_text()

setup(name='xapian',
      version='${VERSION}',
      description='Xapian Library and Bindings for Python as packaged for local use by xapian-haystack',
      long_description=readme,
      long_description_content_type='text/plain',
      license='GPL2',
      classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Programming Language :: Python :: 3 :: Only',
      ],
      packages=['xapian'],
      cmdclass={'bdist_wheel': bdist_wheel},
      include_package_data=True,
      zip_safe=False)
EOF

cat > "${prefix}/MANIFEST.in" <<EOF
include xapian/*
EOF
cat > "${prefix}/README" <<EOF
This wheel contains the xapian library and python bindings.
It was built using \`xapian_wheel_builder.sh\` from the Xapian Haystack project.

Xapian Haystack is a Xapian backend for Django-Haystack.
https://github.com/notanumber/xapian-haystack

The Xapian version used in this wheel is: ${VERSION}
The sources were downloaded from the xapian upstream:
- ${CORE_URI}
- ${BINDINGS_URI}

Xapian's homepage can be found at https://xapian.org/

You can find the script used to build this specific wheel inside of itself.
EOF

(cd "${WHL_DEST}"; cp "$0" "${prefix}/xapian/xapian_wheel_builder.sh")

cp "src/${CORE}/COPYING" "${prefix}/LICENSE.txt"

(
    cd target
    "${VE}/bin/python" setup.py bdist_wheel
    cp dist/*.whl "${WHL_DEST}"
)
cd "${WHL_DEST}"
rm -rf "${TMPDIR}"
exittrap() { :; }
