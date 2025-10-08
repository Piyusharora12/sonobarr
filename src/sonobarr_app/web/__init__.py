from __future__ import annotations

from .auth import bp as auth_bp
from .main import bp as main_bp
from .admin import bp as admin_bp

__all__ = ["auth_bp", "main_bp", "admin_bp"]
