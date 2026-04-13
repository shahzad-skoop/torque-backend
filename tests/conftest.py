from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
db_path = Path("test.db").absolute()
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["AUTH_MOCK_MODE"] = "true"
os.environ["API_REQUIRE_AUTH"] = "false"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"


@pytest.fixture(scope="session", autouse=True)
def configure_test_env():
    yield
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def client():
    from app.db.base import Base
    from app.db.session import engine
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c
