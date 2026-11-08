from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import get_db, make_engine
from app.main import app, get_now

# segunda-feira, 09:00
FIXED_NOW = datetime(2026, 3, 2, 9, 0)


@pytest.fixture()
def client():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def prof(client):
    r = client.post("/professionals", json={"name": "Dra. Helena Prado", "specialty": "Dermatologia"})
    assert r.status_code == 201
    return r.json()


@pytest.fixture()
def patient(client):
    r = client.post("/patients", json={"name": "Marcos Teixeira", "cpf": "529.982.247-25"})
    assert r.status_code == 201
    return r.json()
