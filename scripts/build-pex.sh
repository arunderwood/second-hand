#!/bin/bash
# Build a multi-Python pex executable for second-hand
#
# Creates a pex that works with Python 3.11, 3.12, and 3.13.
# Built per-architecture (amd64/arm64) in CI.
set -e

# Upgrade pip first to fix TOML parsing bug with --platform
pip3 install --break-system-packages --upgrade pip || pip3 install --upgrade pip

# Install pex if not available
# Use --break-system-packages for Debian 12+ (PEP 668) in build containers
if ! python3 -m pex --version &> /dev/null; then
    pip3 install --break-system-packages pex || pip3 install pex
fi

mkdir -p dist

# Detect architecture for platform string
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  ARCH_SUFFIX="x86_64" ;;
    aarch64) ARCH_SUFFIX="aarch64" ;;
    arm64)   ARCH_SUFFIX="aarch64" ;;
    *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "Building for architecture: $ARCH_SUFFIX"

# pip's --platform only walks the compatibility ladder for the legacy
# manylinux2014/2010 prefixes, not PEP 600 manylinux_x_y. manylinux2014 is the
# one request every dependency matches; a PEP 600 request hides pydantic-core
# and silently falls back to building it from source.
MANYLINUX="manylinux2014"

# Build multi-Python pex for current architecture
# --resolve-local-platforms: Resolve for local Python (3.11 on Debian 12)
# --platform: Add wheels for Python 3.12 and 3.13
python3 -m pex . \
    --python-shebang='/usr/bin/env python3' \
    --interpreter-constraint='>=3.11,<4' \
    --pip-version=24.2 \
    --resolve-local-platforms \
    --platform "${MANYLINUX}_${ARCH_SUFFIX}-cp-312-cp312" \
    --platform "${MANYLINUX}_${ARCH_SUFFIX}-cp-313-cp313" \
    -o dist/second-hand.pex \
    -c second-hand

echo "Built: dist/second-hand.pex"
echo "Supported: Python 3.11-3.13 on ${ARCH_SUFFIX}"
