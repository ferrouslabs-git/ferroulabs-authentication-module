"""Transitional DB compatibility layer for auth module.

Do not create DB runtime objects here. Host app owns engine/session/Base/get_db.
"""

from app.database import Base, SessionLocal, get_db, engine

__all__ = ["engine", "SessionLocal", "Base", "get_db"]
