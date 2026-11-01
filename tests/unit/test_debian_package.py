"""Consistency checks between the .deb's metadata and the pex build."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_python_upper_bound_matches_the_pex() -> None:
    """apt must refuse a python3 the pex would refuse to start on."""
    control = (ROOT / "debian" / "control").read_text()
    build = (ROOT / "scripts" / "build-pex.sh").read_text()

    deb_bound = re.search(r"python3 \(<< ([0-9.]+)\)", control)
    pex_bound = re.search(r"--interpreter-constraint='[^']*,<([0-9.]+)'", build)
    assert deb_bound and pex_bound
    assert deb_bound.group(1) == pex_bound.group(1)
