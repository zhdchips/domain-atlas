from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke_public_demo_remote.py"
SPEC = importlib.util.spec_from_file_location("smoke_public_demo_remote", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
normalize_base_url = MODULE.normalize_base_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("https://domain-atlas.onrender.com/", "https://domain-atlas.onrender.com"),
    ],
)
def test_normalize_base_url_accepts_an_origin(value: str, expected: str) -> None:
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "domain-atlas.onrender.com",
        "ftp://domain-atlas.onrender.com",
        "https://user:password@domain-atlas.onrender.com",
        "https://domain-atlas.onrender.com/demo",
        "https://domain-atlas.onrender.com?mode=demo",
        "https://domain-atlas.onrender.com#demo",
    ],
)
def test_normalize_base_url_rejects_non_origin_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_base_url(value)
