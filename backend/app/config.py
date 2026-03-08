"""Compatibility shim for legacy imports.

Preferred import location:
    app.auth_usermanagement.config
"""
from app.auth_usermanagement.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
