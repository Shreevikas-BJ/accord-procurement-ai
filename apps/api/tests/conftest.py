import shutil
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.db import Base, get_db
from app.main import app
from app import seed as seed_module
from app import providers


@pytest.fixture(scope="session")
def seeded_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("seed") / "base.db"
    original_storage = providers.STORAGE_PATH
    providers.STORAGE_PATH = path.parent / "uploads"
    engine = create_engine("sqlite:///" + str(path))
    Base.metadata.create_all(engine)
    original = seed_module.SessionLocal
    seed_module.SessionLocal = sessionmaker(engine, expire_on_commit=False)
    seed_module.seed()
    seed_module.SessionLocal = original
    engine.dispose()
    yield path
    providers.STORAGE_PATH = original_storage


@pytest.fixture
def db_factory(seeded_file, tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    shutil.copyfile(seeded_file, path)
    engine = create_engine("sqlite:///" + str(path), connect_args={"check_same_thread": False})
    factory = sessionmaker(engine, expire_on_commit=False)

    def override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr("app.pipeline.SessionLocal", factory)
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def db(db_factory):
    with db_factory() as session:
        yield session


@pytest.fixture
def client(db_factory):
    with TestClient(app, headers={"X-Procurement-Client": "workspace"}) as client:
        yield client


@pytest.fixture
def buyer(client):
    assert (
        client.post("/auth/login", json={"email": "buyer@apex.example", "password": "Demo2026!accord"}).status_code
        == 200
    )
    return client
