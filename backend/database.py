"""
database.py — SQLAlchemy engine, session factory, and FastAPI dependency.

No tables are created here; that is deferred to a later task.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# pool_pre_ping=True makes SQLAlchemy test the connection before each use,
# so stale connections are automatically replaced.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# autocommit=False  → we commit explicitly inside each request
# autoflush=False   → prevents surprise flushes before we are ready
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)

# ---------------------------------------------------------------------------
# Declarative base — future models will inherit from this
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a single request.

    Usage in a route:
        from fastapi import Depends
        from backend.database import get_db

        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
