from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path):
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test.db"
    os.environ["REGISTRY_ROOT_PATH"] = str(tmp_path / "models")
    os.environ["REGISTRY_ACTOR"] = "tester"

    (tmp_path / "models").mkdir(parents=True, exist_ok=True)

    # import after env vars
    import app.config
    import app.database
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.database)
    importlib.reload(app.main)

    with TestClient(app.main.app) as c:
        yield c


def test_create_model_and_version_and_get(client: TestClient, tmp_path: Path):
    r = client.post("/models", json={"name": "my_model", "description": "baseline"})
    assert r.status_code == 201, r.text

    (tmp_path / "models" / "mlds_1").mkdir()
    (tmp_path / "models" / "mlds_1" / "my_model_v1").mkdir()

    r = client.post(
        "/models/my_model/versions",
        json={
            "version": "1",
            "artifact_path": "mlds_1/my_model_v1",
            "stage": "development",
            "metadata": {"metric": {"auc": 0.9}},
            "tags": {"team": "mlds_1"},
        },
    )
    assert r.status_code == 201, r.text

    r = client.get("/models/my_model/versions/1")
    assert r.status_code == 200
    assert r.json()["model_name"] == "my_model"

    r = client.get("/models/my_model/versions/1/artifact")
    assert r.status_code == 200
    assert r.json()["exists"] is True


def test_duplicate_version_conflict(client: TestClient):
    r = client.post(
        "/models/dup/versions",
        json={"version": "1", "artifact_path": "x", "stage": "development", "metadata": {}, "tags": {}},
    )
    assert r.status_code == 201

    r = client.post(
        "/models/dup/versions",
        json={"version": "1", "artifact_path": "y", "stage": "development", "metadata": {}, "tags": {}},
    )
    assert r.status_code == 409


def test_filter_by_stage_and_tag(client: TestClient):
    client.post("/models/m1/versions", json={"version": "1", "artifact_path": "x", "stage": "production", "metadata": {}, "tags": {"team": "a"}})
    client.post("/models/m2/versions", json={"version": "1", "artifact_path": "y", "stage": "development", "metadata": {}, "tags": {"team": "b"}})

    r = client.get("/models", params={"stage": "production"})
    assert r.status_code == 200
    names = {m["name"] for m in r.json()}
    assert "m1" in names
    assert "m2" not in names

    r = client.get("/models", params={"tag": "team:a"})
    assert r.status_code == 200
    names = {m["name"] for m in r.json()}
    assert names == {"m1"}

