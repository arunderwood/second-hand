#!/bin/bash
# Build a self-contained pex executable for second-hand
#
# This creates a cross-Python-version executable that works with
# Python 3.11+ without needing a virtualenv at install time.
set -e

# Install pex if not available
if ! command -v pex &> /dev/null; then
    pip3 install pex
fi

# Create output directory
mkdir -p dist

# Download pychrony from Test PyPI to a local directory
# This avoids conflicts with malicious packages on Test PyPI
mkdir -p dist/pychrony-wheels
pip3 download --dest dist/pychrony-wheels \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    --no-deps pychrony

# Build pex for current architecture
# --python-shebang: Use env to find python3, works across distros
# --find-links: Use local pychrony wheel
# --interpreter-constraint: Support Python 3.11-3.14
# -c: Entry point console script
pex . \
    --python-shebang='/usr/bin/env python3' \
    --find-links=dist/pychrony-wheels \
    --interpreter-constraint='>=3.11,<4' \
    -o dist/second-hand.pex \
    -c second-hand

echo "Built: dist/second-hand.pex"
