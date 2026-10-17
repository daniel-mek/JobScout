from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import Settings


class Base(DeclarativeBase):
    pass


def make_database(config: Settings):
    if config.database_url.startswith("sqlite:///"):
        from pathlib import Path

        name = config.database_url.removeprefix("sqlite:///")
        if name != ":memory:":
            Path(name).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        config.database_url,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if config.database_url.startswith("sqlite") else {},
    )
    if config.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(engine, expire_on_commit=False)
