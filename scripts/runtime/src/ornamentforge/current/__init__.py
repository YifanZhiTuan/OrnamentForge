"""Single maintained OrnamentForge capability line.

Versioned package names are historical evidence only.  New code imports from
this namespace or from the stable foundational modules at ``ornamentforge.*``.
"""

from .input.router import IntentMode, ObjectFamily, classify_intent, infer_object_family

__all__ = ["IntentMode", "ObjectFamily", "classify_intent", "infer_object_family"]
