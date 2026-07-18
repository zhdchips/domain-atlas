from __future__ import annotations

from fastapi.testclient import TestClient

from domain_atlas.core.db import initialize_database
from domain_atlas.core.settings import Settings
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.web import app as web_app
from domain_atlas.web.app import create_app


def test_public_demo_renders_catalog_without_creating_or_reading_runtime_data(tmp_path):
    private_data_dir = tmp_path / "private-data"
    initialize_database(private_data_dir / "domain_atlas.sqlite3")
    DomainProjectRepository(private_data_dir / "domain_atlas.sqlite3").create(
        CreateDomainProject(name="Private Local Project")
    )
    app = create_app(Settings(data_dir=private_data_dir, public_demo_mode=True))
    client = TestClient(app)

    overview = client.get("/demo")
    wiki = client.get("/demo/wiki")
    learning_path = client.get("/demo/path")
    qa = client.get("/demo/qa")

    assert overview.status_code == 200
    assert "Agent Harness Engineering" in overview.text
    assert "Private Local Project" not in overview.text
    assert "OpenAI Agents SDK documentation" in overview.text
    assert wiki.status_code == 200
    assert "Harness Map" in wiki.text
    assert 'href="/demo/wiki/concepts/agent-loop"' in wiki.text
    assert learning_path.status_code == 200
    assert "从主干到支线逐步推进" in learning_path.text
    assert 'href="/demo/wiki/concepts/agent-loop"' in learning_path.text
    assert qa.status_code == 200
    assert "为什么 Agent Harness 不等于一个更长的 prompt？" in qa.text
    assert "<form" not in qa.text
    assert client.get("/domains/1").status_code == 404


def test_public_demo_does_not_create_database_for_missing_data_dir(tmp_path):
    data_dir = tmp_path / "does-not-exist"
    client = TestClient(create_app(Settings(data_dir=data_dir, public_demo_mode=True)))

    assert client.get("/demo").status_code == 200
    assert not data_dir.exists()


def test_public_demo_blocks_mutation_routes_before_provider_construction(tmp_path, monkeypatch):
    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("Public demo must not construct external providers.")

    monkeypatch.setattr(web_app, "ExaSearchProvider", fail_if_constructed)
    monkeypatch.setattr(web_app, "OpenAICompatibleChatProvider", fail_if_constructed)
    monkeypatch.setattr(web_app, "OpenAICompatibleEmbeddingProvider", fail_if_constructed)
    monkeypatch.setattr(web_app, "IngestionService", fail_if_constructed)
    client = TestClient(create_app(Settings(data_dir=tmp_path / "demo", public_demo_mode=True)))

    paths = [
        "/domains",
        "/domains/1/intake",
        "/domains/1/discover",
        "/domains/1/candidates/1/confirm",
        "/domains/1/sources/url",
        "/domains/1/sources/file",
        "/domains/1/sources/1/ingest",
        "/domains/1/build",
        "/domains/1/autopilot",
        "/domains/1/qa",
        "/demo",
    ]

    for path in paths:
        assert client.post(path, follow_redirects=False).status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_public_demo_contains_no_mutable_forms_or_submit_buttons(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, public_demo_mode=True)))

    for path in ("/demo", "/demo/wiki", "/demo/path", "/demo/qa"):
        page = client.get(path)
        assert page.status_code == 200
        assert "<form" not in page.text
        assert 'type="submit"' not in page.text


def test_default_local_mode_retains_project_creation_and_hides_demo(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))

    created = client.post("/domains", data={"name": "Local Project"}, follow_redirects=False)

    assert created.status_code == 303
    assert created.headers["location"] == "/domains/1"
    assert client.get("/domains/1").status_code == 200
    assert client.get("/demo").status_code == 404
