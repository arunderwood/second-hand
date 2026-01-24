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

mkdir -p dist dist/pychrony-wheels

# Detect architecture for platform string
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  ARCH_SUFFIX="x86_64" ;;
    aarch64) ARCH_SUFFIX="aarch64" ;;
    arm64)   ARCH_SUFFIX="aarch64" ;;
    *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "Building for architecture: $ARCH_SUFFIX"

# Download pychrony wheels from Test PyPI for ALL target Python versions
# pip download only grabs wheels for the current Python, so we need to
# explicitly download for each target version
for pyver in 3.11 3.12 3.13; do
    echo "Downloading pychrony for Python $pyver..."
    pip3 download --dest dist/pychrony-wheels \
        --index-url https://test.pypi.org/simple/ \
        --extra-index-url https://pypi.org/simple/ \
        --no-deps \
        --python-version "$pyver" \
        --only-binary=:all: \
        --platform "manylinux_2_17_${ARCH_SUFFIX}" \
        pychrony || echo "Warning: No wheel for Python $pyver"
done

echo "Downloaded pychrony wheels:"
ls -la dist/pychrony-wheels/

# Build multi-Python pex for current architecture
# --resolve-local-platforms: Resolve for local Python (3.11 on Debian 12)
# --platform: Add wheels for Python 3.12 and 3.13
# Uses manylinux_2_17 for broad compatibility (works on glibc 2.17+)
python3 -m pex . \
    --python-shebang='/usr/bin/env python3' \
    --find-links=dist/pychrony-wheels \
    --interpreter-constraint='>=3.11,<4' \
    --pip-version=24.2 \
    --resolve-local-platforms \
    --platform "manylinux_2_17_${ARCH_SUFFIX}-cp-312-cp312" \
    --platform "manylinux_2_17_${ARCH_SUFFIX}-cp-313-cp313" \
    -o dist/second-hand.pex \
    -c second-hand

echo "Built: dist/second-hand.pex"
echo "Supported: Python 3.11-3.13 on ${ARCH_SUFFIX}"
