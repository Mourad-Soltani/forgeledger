"""Database session — Mourad.Soltani."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DB_PATH = os.environ.get("FORGELEDGER_DB", os.path.join(os.path.dirname(__file__), "..", "forgeledger.db"))
DATABASE_URL = f"sqlite:///{os.path.abspath(DB_PATH)}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()


def ensure_schema() -> None:
    """Lightweight SQLite column adds for soft-archive — Mourad.Soltani."""
    from sqlalchemy import text, inspect
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, col in (("clients", "archived"), ("invoices", "archived")):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} BOOLEAN DEFAULT 0"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
