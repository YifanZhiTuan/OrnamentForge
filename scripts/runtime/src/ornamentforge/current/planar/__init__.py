"""Planar-master construction and relief layouts."""

from .contract import PlanarMasterV1

__all__ = ["build", "retrieve", "retrieve_reference", "PlanarMasterV1"]


def __getattr__(name):
    # The contract/database path must not require optional raster dependencies.
    if name in ("build", "retrieve", "retrieve_reference"):
        from . import master
        return getattr(master, name)
    raise AttributeError(name)
