"""Database engine, session, and migration helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = "sqlite:///data/opportunity_engine.db"


def _prepare_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return
    database = url.database
    if not database or database == ":memory:":
        return
    Path(database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str = DEFAULT_DATABASE_URL) -> Engine:
    """Create an engine with SQLite foreign-key enforcement enabled."""
    _prepare_sqlite_parent(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, connect_args=connect_args)

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a transaction-safe SQLAlchemy session factory."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield one session and commit or roll back atomically."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def build_alembic_config(
    database_url: str,
    *,
    config_path: str | Path = "alembic.ini",
) -> Config:
    """Build an Alembic config with an explicit runtime database URL."""
    config = Config(str(config_path))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database(
    database_url: str = DEFAULT_DATABASE_URL,
    *,
    revision: str = "head",
    config_path: str | Path = "alembic.ini",
) -> None:
    """Apply Alembic migrations to the requested revision."""
    _prepare_sqlite_parent(database_url)
    command.upgrade(build_alembic_config(database_url, config_path=config_path), revision)
