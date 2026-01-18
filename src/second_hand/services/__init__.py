"""Service layer for second-hand."""

from .chrony import ChronyData, fetch_chrony_data

__all__ = ["ChronyData", "fetch_chrony_data"]
