from __future__ import annotations

from typing import Any

from artifactory import ArtifactoryPath, ArtifactorySaaSPath

from .models import ArtifactStat
from .settings import SETTINGS, _validate_base_url, _validate_path, _validate_repository


def _resolve_base_url(base_url: str | None) -> str:
    if base_url and base_url.strip():
        return _validate_base_url(base_url, name="base_url")
    if SETTINGS.artifactory_base_url:
        return SETTINGS.artifactory_base_url
    raise ValueError("Missing Artifactory base URL. Set ARTIFACTORY_BASE_URL or pass base_url in the tool call.")


def _auth_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "verify": SETTINGS.artifactory_verify_ssl,
        "timeout": SETTINGS.artifactory_timeout_seconds,
    }
    if SETTINGS.artifactory_token:
        kwargs["token"] = SETTINGS.artifactory_token
    elif SETTINGS.artifactory_api_key:
        kwargs["apikey"] = SETTINGS.artifactory_api_key
    elif SETTINGS.artifactory_username and SETTINGS.artifactory_password:
        kwargs["auth"] = (SETTINGS.artifactory_username, SETTINGS.artifactory_password)
    return kwargs


def _create_root(base_url: str) -> ArtifactoryPath | ArtifactorySaaSPath:
    path_cls = ArtifactorySaaSPath if SETTINGS.artifactory_use_saas_path else ArtifactoryPath
    return path_cls(base_url, **_auth_kwargs())


def _create_path(
    base_url: str,
    repository: str,
    item_path: str,
) -> ArtifactoryPath | ArtifactorySaaSPath:
    repo = _validate_repository(repository)
    relative_path = _validate_path(item_path)
    artifact_url = f"{base_url}/{repo}"
    if relative_path:
        artifact_url = f"{artifact_url}/{relative_path}"
    path_cls = ArtifactorySaaSPath if SETTINGS.artifactory_use_saas_path else ArtifactoryPath
    return path_cls(artifact_url, **_auth_kwargs())


def _path_in_repo(path: ArtifactoryPath | ArtifactorySaaSPath) -> str:
    return str(path.path_in_repo).lstrip("/")


def _to_artifact_stat(raw_stat: Any) -> ArtifactStat:
    children = getattr(raw_stat, "children", None)
    return ArtifactStat(
        created=getattr(raw_stat, "created", None),
        last_modified=getattr(raw_stat, "last_modified", None),
        last_updated=getattr(raw_stat, "last_updated", None),
        created_by=getattr(raw_stat, "created_by", None),
        modified_by=getattr(raw_stat, "modified_by", None),
        mime_type=getattr(raw_stat, "mime_type", None),
        size=getattr(raw_stat, "size", None),
        sha1=getattr(raw_stat, "sha1", None),
        sha256=getattr(raw_stat, "sha256", None),
        md5=getattr(raw_stat, "md5", None),
        is_dir=bool(getattr(raw_stat, "is_dir", False)),
        children=list(children) if children is not None else None,
    )
