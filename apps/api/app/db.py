import os
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import DATABASE_URL, ROOT

if os.getenv("REQUIRE_POSTGRES") == "true" and make_url(DATABASE_URL).get_backend_name() != "postgresql":
    raise RuntimeError("Docker requires a PostgreSQL DATABASE_URL; SQLite fallback is disabled.")

(ROOT / "data").mkdir(exist_ok=True)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **({"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}),
)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def sqlite_integrity(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session
