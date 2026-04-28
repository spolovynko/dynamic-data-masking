from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ddm_engine.config import Settings, get_settings
from ddm_engine.storage.models import Base


def create_metadata_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    database_url = settings.resolved_database_url
    connect_args = {}

    if database_url.startswith("sqlite"):
        database_path = _sqlite_path_from_url(database_url)
        if database_path is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["check_same_thread"] = False

    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def create_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_metadata_engine(settings),
        autoflush=False,
        expire_on_commit=False,
    )


def init_database(settings: Settings | None = None) -> None:
    engine = create_metadata_engine(settings)
    Base.metadata.create_all(bind=engine)


def session_scope(settings: Settings | None = None) -> Generator[Session]:
    session_factory = create_session_factory(settings)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _sqlite_path_from_url(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None

    path = database_url.removeprefix(prefix)
    if path == ":memory:":
        return None
    return Path(path)
