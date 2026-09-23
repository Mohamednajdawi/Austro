"""Check preparation artifacts, not unimplemented domain acceptance controls."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "name",
    [
        "IMPLEMENTATION_BRIEF.md",
        "BACKLOG.md",
        "ACCEPTANCE.md",
        "READINESS.md",
        "CLARIFICATION_REQUEST.md",
        "SOURCES.md",
    ],
)
def test_required_documents_exist_and_have_content(name):
    assert len((ROOT / "docs" / name).read_text(encoding="utf-8")) > 200


def test_all_acceptance_ids_are_unique_and_present():
    text = (ROOT / "docs" / "ACCEPTANCE.md").read_text(encoding="utf-8")
    ids = re.findall(r"^\| (A\d{2}) \|", text, re.MULTILINE)
    assert ids == [f"A{i:02}" for i in range(1, 32)]


def test_document_links_resolve():
    for document in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]:
        for target in re.findall(
            r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")
        ):
            if "://" not in target and not target.startswith("#"):
                assert (document.parent / target.split("#")[0]).is_file(), target


def test_example_configuration_is_safe_and_has_no_credentials():
    config = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert config["APP_MODE"] == "synthetic-demo"
    assert config["MODEL_PROVIDER"] == "fake"
    assert config["HOST"] == "127.0.0.1"
    for key in [
        "ALLOW_EXTERNAL_INFERENCE",
        "ALLOW_PRODUCTION_WRITES",
        "ENABLE_TELEMETRY",
    ]:
        assert config[key] == "false"
    for key in [
        "WO_INSTANCE",
        "WO_API_KEY",
        "MODEL_BASE_URL",
        "MODEL_API_KEY",
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
    ]:
        assert config[key] == ""


def test_installed_versions_match_snapshot():
    from importlib.metadata import distributions

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {
        package["name"].replace("_", "-").lower(): package["version"]
        for package in lock["package"]
    }
    for package in distributions():
        name = package.metadata["Name"].replace("_", "-").lower()
        if name not in {"pip", "setuptools"}:
            assert versions[name] == package.version
