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

    assert {".env", ".env.*", "data/", "uploads/", "reports/", "tests/", "*.sqlite", "*.sqlite3"} <= patterns
