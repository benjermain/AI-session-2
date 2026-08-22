"""
Vellora Bio Web Platform Package.

Forwarding standard library platform module attributes to prevent standard library
shadowing when third-party libraries (attrs, jsonschema, uvicorn) import platform.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_stdlib_platform_path = os.path.join(os.path.dirname(os.__file__), "platform.py")
if os.path.exists(_stdlib_platform_path):
    _spec = importlib.util.spec_from_file_location("_stdlib_platform", _stdlib_platform_path)
    if _spec and _spec.loader:
        _stdlib = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_stdlib)
        for _attr in dir(_stdlib):
            if not _attr.startswith("__") or _attr in {"__version__"}:
                globals()[_attr] = getattr(_stdlib, _attr)
