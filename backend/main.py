"""
main.py — FastAPI application entry point.

Exposes:
  GET /health    → basic liveness check
  GET /db-health → verifies the PostgreSQL connection via SQLAlchemy

On startup, creates any missing database tables using SQLAlchemy's
Base.metadata.create_all(). This is intentional for the hackathon;
Alembic migrations will be introduced in a later task.
"""

from fastapi import Depends, FastAPI
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

# Import all models BEFORE create_all so metadata is fully populated.
import backend.models  # noqa: F401 — side-effect import registers all tables

from backend.database import Base, engine, get_db

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Customer Support Resolution Agent",
    description="Backend API for the AI Customer Support Resolution Agent hackathon project.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Startup — create tables if they don't already exist
# ---------------------------------------------------------------------------


@app.on_event("startup")
def create_tables() -> None:
    """
    Create all tables defined in Base.metadata that don't exist yet.
    Existing tables and their data are left untouched (checkfirst=True is
    the default behaviour of create_all).
    """
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health_check():
    """Basic liveness check — confirms the API is running."""
    return {"status": "ok"}


@app.get("/db-health", tags=["Health"])
def db_health_check(db: Session = Depends(get_db)):
    """
    Verifies the PostgreSQL connection by executing SELECT 1.

    Returns {"database": "connected"} on success.
    Raises an HTTP 500 error automatically if the query fails.
    """
    db.execute(text("SELECT 1"))
    return {"database": "connected"}


@app.get("/db-tables", tags=["Health"])
def db_tables_check():
    """
    Returns the list of tables currently present in the public schema.
    Useful for verifying that create_all() ran successfully.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names(schema="public")
    return {"tables": tables}
