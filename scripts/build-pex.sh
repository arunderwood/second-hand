#!/bin/bash
# Build a multi-Python pex executable for second-hand
#
# Bundles wheels for every CPython the supported distros ship as python3:
# 3.11 (Debian 12), 3.12 (Ubuntu 24.04), 3.13 (Debian 13), 3.14 (Ubuntu 26.04)
# and 3.15. Built per-architecture (amd64/arm64) in CI.
#
# Requires uv on PATH. Dependencies are installed from a PEP 751 export of
# uv.lock, which pins every artifact by sha256: pex refuses any wheel whose
# hash differs, so a release ships exactly the files CI tested. pex itself is
# pinned in uv.lock too.
set -euo pipefail

if ! command -v uv > /dev/null; then
    echo "uv is required to build the pex: https://docs.astral.sh/uv/" >&2
    exit 1
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

# The whole lock, the project included as a non-editable directory entry: pex
# installs every package in the lock and cannot add one from outside it.
uv export --frozen --no-dev --no-editable --format pylock.toml \
    --output-file dist/pylock.toml > /dev/null

# pip's --platform only walks the compatibility ladder for the legacy
# manylinux2014/2010 prefixes, not PEP 600 manylinux_x_y. manylinux2014 is the
# one request every dependency matches; a PEP 600 request hides pydantic-core
# and silently falls back to building it from source.
MANYLINUX="manylinux2014"

# Every version is listed, whichever python3 the build host has;
# --resolve-local-platforms swaps in the local interpreter for its own one.
PLATFORMS=()
for version in 311 312 313 314 315; do
    PLATFORMS+=(--platform "${MANYLINUX}_${ARCH_SUFFIX}-cp-${version}-cp${version}")
done

# The interpreter constraint stops at the newest bundled version: on a newer
# python3 the pex must refuse to start rather than fail importing a compiled
# dependency it has no wheel for. debian/control carries the same upper bound
# on python3 so apt refuses the install instead; change both together.
#
# pex runs under the system python3 so --resolve-local-platforms finds it, in a
# venv of its own so the build never disturbs a developer's .venv. It builds
# that pip venv with `python3 -m venv`, which on Debian is the separate
# python3-venv package (Build-Depends).
UV_PROJECT_ENVIRONMENT=dist/build-venv \
    uv run --frozen --only-group build --python /usr/bin/python3 \
    pex \
    --pylock dist/pylock.toml \
    --python-shebang=/usr/bin/python3 \
    --interpreter-constraint='>=3.11,<3.16' \
    --pip-version=latest-compatible \
    --resolve-local-platforms \
    "${PLATFORMS[@]}" \
    -o dist/second-hand.pex \
    -c second-hand

# debian/copyright relies on two facts about the finished pex: every bundled
# distribution carries its own license file, and the pex runtime vendors
# exactly the packages it names. Fail here rather than ship a pex where
# either has stopped being true.
python3 - dist/second-hand.pex <<'EOF'
import re
import sys
import zipfile

# Top-level packages of the pex runtime's vendored copies, as named in the
# .bootstrap paragraph of debian/copyright.
EXPECTED_VENDORED = {"attr", "colors", "packaging", "pyparsing"}

names = zipfile.ZipFile(sys.argv[1]).namelist()
dist_infos = {m.group(1) for n in names if (m := re.match(r"(\.deps/[^/]+/[^/]+\.dist-info)/", n))}
unlicensed = sorted(
    d for d in dist_infos
    if not any(n.startswith(d + "/") and re.search(r"LICEN[CS]E|COPYING", n.rsplit("/", 1)[-1], re.I) for n in names)
)
vendored = {m.group(1) for n in names if (m := re.match(r"\.bootstrap/pex/vendor/_vendored/[^/]+/([^/.]+)/", n))}

errors = [f"no license file in {d}" for d in unlicensed]
if vendored != EXPECTED_VENDORED:
    errors.append(
        f"pex now vendors {sorted(vendored)}, not {sorted(EXPECTED_VENDORED)}: "
        "update the .bootstrap list in debian/copyright and in this check"
    )
for error in errors:
    print(f"build-pex.sh: {error}", file=sys.stderr)
sys.exit(1 if errors else 0)
EOF

echo "Built: dist/second-hand.pex"
echo "Supported: Python 3.11-3.15 on ${ARCH_SUFFIX}"
