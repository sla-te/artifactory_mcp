from __future__ import annotations

from artifactory_mcp.settings import _validate_base_url


def test_validate_base_url_appends_artifactory_for_host_only_urls() -> None:
    assert _validate_base_url("https://artifactory.local", name="base_url") == "https://artifactory.local/artifactory"
    assert _validate_base_url("https://artifactory.local/", name="base_url") == "https://artifactory.local/artifactory"


def test_validate_base_url_keeps_existing_path() -> None:
    assert _validate_base_url("https://artifactory.local/artifactory", name="base_url") == (
        "https://artifactory.local/artifactory"
    )
    assert _validate_base_url("https://artifactory.local/custom-path", name="base_url") == (
        "https://artifactory.local/custom-path"
    )
