import os
import tempfile

# Configure before the app (and its engine) is imported.
_tmp = tempfile.mkdtemp(prefix="chalkback-test-")
os.environ.update(
    DATABASE_URL="sqlite://",
    DATA_DIR=_tmp,
    ANTHROPIC_API_KEY="",
    SCHEDULER_ENABLED="false",
    SEED_DEMO="true",
    PUBLIC_BASE_URL="http://testserver",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


def auth(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def teacher(client):
    return auth(client, "teacher@demo.chalkback", "demo-password")
