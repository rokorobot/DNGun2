from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "dngun.sqlite3"


class Base(DeclarativeBase):
    pass


def get_database_path() -> Path:
    return Path(os.environ.get("DNGUN_DB_PATH", DEFAULT_DB_PATH))


def database_url_for(path: Path | None = None) -> str:
    db_path = path or get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(db_path: Path | None = None) -> sessionmaker[Session]:
    engine = create_engine(
        database_url_for(db_path),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    
    # Dynamically resolve and run migrate_db migrations
    try:
        from scripts.migrate_db import migrate as run_migrations
        run_migrations(db_path)
    except ImportError:
        try:
            from backend.scripts.migrate_db import migrate as run_migrations
            run_migrations(db_path)
        except ImportError:
            import sys
            backend_dir = Path(__file__).resolve().parents[1]
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))
            from scripts.migrate_db import migrate as run_migrations
            run_migrations(db_path)

    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
