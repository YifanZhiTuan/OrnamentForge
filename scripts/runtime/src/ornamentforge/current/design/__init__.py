"""Offline records of externally completed design; no image generation clients."""
from .handoff import DesignHandoff, HandoffError

__all__ = ["DesignHandoff", "HandoffError"]
