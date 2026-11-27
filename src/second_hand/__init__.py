"""second-hand: Chrony time statistics dashboard."""

from importlib.metadata import PackageNotFoundError, version

# Installed metadata, not a generated _version.py: pex builds this project's
# sdist once per target platform in parallel, and a build hook rewriting a file
# in the source tree lets one build tar it mid-write.
try:
    __version__ = version("second-hand")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"
