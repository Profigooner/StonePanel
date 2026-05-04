import pytest
from fastapi.testclient import TestClient

from stonepanel.config import Settings
from stonepanel.main import create_app


@pytest.fixture()
def file_root(tmp_path):
    root = tmp_path / "files"
    root.mkdir()
    (root / "test.txt").write_text("hello world")
    sub = root / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested content")
    return root


@pytest.fixture()
def settings(tmp_path, file_root):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return Settings(
        data_dir=data_dir,
        secret_key="test-secret-key-for-testing",
        file_root=str(file_root),
        dev_mode=True,
    )


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_token(client):
    resp = client.post("/api/auth/setup", json={"password": "testpassword123"})
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
