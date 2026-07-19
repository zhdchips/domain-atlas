from __future__ import annotations

from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_is_a_single_read_only_docker_service() -> None:
    blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text())

    assert set(blueprint) == {"services"}
    assert len(blueprint["services"]) == 1
    service = blueprint["services"][0]
    assert service == {
        "type": "web",
        "name": "domain-atlas-demo",
        "runtime": "docker",
        "plan": "free",
        "region": "singapore",
        "dockerfilePath": "./Dockerfile",
        "healthCheckPath": "/health",
        "autoDeployTrigger": "checksPass",
        "renderSubdomainPolicy": "enabled",
        "envVars": [{"key": "PUBLIC_DEMO_MODE", "value": "true"}],
    }


def test_private_render_blueprint_is_paid_single_owner_with_persistent_disk() -> None:
    blueprint = yaml.safe_load((PROJECT_ROOT / "render.private.yaml").read_text())

    assert set(blueprint) == {"services"}
    assert len(blueprint["services"]) == 1
    service = blueprint["services"][0]
    assert service["type"] == "web"
    assert service["runtime"] == "docker"
    assert service["plan"] == "starter"
    assert service["region"] == "singapore"
    assert service["numInstances"] == 1
    assert service["healthCheckPath"] == "/health"
    assert service["disk"] == {
        "name": "domain-atlas-data",
        "mountPath": "/app/data",
        "sizeGB": 1,
    }
    env = {item["key"]: item for item in service["envVars"]}
    assert env["DEPLOYMENT_MODE"]["value"] == "private_owner"
    assert env["DATA_DIR"]["value"] == "/app/data"
    assert env["PERSISTENT_DATA_ACKNOWLEDGED"]["value"] == "true"
    assert env["SESSION_SECRET"] == {"key": "SESSION_SECRET", "generateValue": True}
    for key in {
        "GITHUB_OAUTH_CLIENT_ID",
        "GITHUB_OAUTH_CLIENT_SECRET",
        "GITHUB_OAUTH_CALLBACK_URL",
        "OWNER_GITHUB_USER_ID",
        "EXA_API_KEY",
        "LLM_API_KEY",
        "EMBEDDING_API_KEY",
    }:
        assert env[key] == {"key": key, "sync": False}
    serialized = (PROJECT_ROOT / "render.private.yaml").read_text()
    assert "client-secret" not in serialized
    assert "sk-" not in serialized


def test_docker_delivery_uses_runtime_port_and_non_root_user() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()

    assert "PORT=8000" in dockerfile
    assert "--host 0.0.0.0" in dockerfile
    assert '--port \\"$PORT\\"' in dockerfile
    assert dockerfile.index("USER domainatlas") < dockerfile.index("CMD [")


def test_docker_context_excludes_private_and_runtime_content() -> None:
    patterns = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        "data/",
        "uploads/",
        "reports/",
        "backups/",
        "domain-atlas-*.tar.gz",
        "tests/",
        "*.sqlite",
        "*.sqlite3",
    } <= patterns
