from __future__ import annotations

import fnmatch
import pathlib
from typing import Any, cast

from .artifactory_client import _create_path, _path_in_repo, _resolve_base_url, _to_artifact_stat
from .bridge import _coerce_object_to_dict, _serialize_value
from .models import (
    ArtifactDetailsResult,
    ArtifactEntry,
    ListArtifactsResult,
    ReadArtifactTextResult,
    WriteArtifactTextResult,
)
from .settings import SETTINGS, _validate_encoding, _validate_path, _validate_repository


def _list_artifacts_sync(
    repository: str,
    path: str,
    recursive: bool,
    pattern: str,
    include_directories: bool,
    include_stats: bool,
    max_items: int,
    base_url: str | None,
) -> ListArtifactsResult:
    if max_items < 1 or max_items > 1000:
        raise ValueError("max_items must be between 1 and 1000.")
    if not pattern.strip():
        raise ValueError("pattern cannot be empty.")

    resolved_base_url = _resolve_base_url(base_url)
    root = _create_path(resolved_base_url, repository, path)

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Path is not a directory: {root}")

    root_in_repo = _path_in_repo(root)
    if recursive:
        recursive_pattern = pattern
        if recursive_pattern == "*":
            recursive_pattern = "**/*"
        iterator = root.glob(recursive_pattern)
    else:
        all_children = list(root.iterdir())
        if pattern == "*":
            iterator = iter(all_children)
        else:
            iterator = (child for child in all_children if fnmatch.fnmatch(child.name, pattern))

    items: list[ArtifactEntry] = []
    truncated = False
    for child in iterator:
        if len(items) >= max_items:
            truncated = True
            break

        is_dir = child.is_dir()
        if is_dir and not include_directories:
            continue

        child_path = _path_in_repo(child)
        relative_path = str(pathlib.PurePosixPath(child_path).relative_to(root_in_repo)) if root_in_repo else child_path

        size: int | None = None
        last_modified: str | None = None
        if include_stats:
            stat = child.stat()
            size = None if is_dir else int(getattr(stat, "size", 0) or 0)
            raw_last_modified = getattr(stat, "last_modified", None)
            last_modified = str(raw_last_modified) if raw_last_modified is not None else None

        items.append(
            ArtifactEntry(
                uri=str(child),
                name=child.name,
                path=relative_path,
                is_dir=is_dir,
                size=size,
                last_modified=last_modified,
            )
        )

    return ListArtifactsResult(
        base_url=resolved_base_url,
        repository=_validate_repository(repository),
        path=_validate_path(path),
        count=len(items),
        truncated=truncated,
        items=items,
    )


def _get_artifact_details_sync(
    repository: str,
    path: str,
    include_properties: bool,
    include_download_stats: bool,
    base_url: str | None,
) -> ArtifactDetailsResult:
    resolved_base_url = _resolve_base_url(base_url)
    target = _create_path(resolved_base_url, repository, path)
    if not target.exists():
        raise FileNotFoundError(f"Artifact not found: {target}")

    stat = target.stat()
    is_dir = bool(getattr(stat, "is_dir", False))
    download_stats: dict[str, Any] | None = None
    if include_download_stats and not is_dir:
        raw_download = _coerce_object_to_dict(target.download_stats())
        download_stats = cast(dict[str, Any], _serialize_value(raw_download, max_items=SETTINGS.mcp_default_max_items))

    properties: dict[str, Any] = {}
    if include_properties:
        raw_properties = _coerce_object_to_dict(target.properties)
        properties = cast(
            dict[str, Any],
            _serialize_value(raw_properties, max_items=SETTINGS.mcp_default_max_items),
        )

    return ArtifactDetailsResult(
        base_url=resolved_base_url,
        repository=_validate_repository(repository),
        path=_validate_path(path),
        uri=str(target),
        is_dir=is_dir,
        stat=_to_artifact_stat(stat),
        properties=properties,
        download_stats=download_stats,
    )


def _read_artifact_text_sync(
    repository: str,
    path: str,
    encoding: str,
    max_bytes: int,
    base_url: str | None,
) -> ReadArtifactTextResult:
    if max_bytes < 1 or max_bytes > 5_000_000:
        raise ValueError("max_bytes must be between 1 and 5000000.")
    normalized_encoding = _validate_encoding(encoding)

    resolved_base_url = _resolve_base_url(base_url)
    clean_path = _validate_path(path)
    if not clean_path:
        raise ValueError("path must reference a file in the repository.")

    target = _create_path(resolved_base_url, repository, clean_path)
    if not target.exists():
        raise FileNotFoundError(f"Artifact not found: {target}")
    if target.is_dir():
        raise ValueError(f"Artifact is a directory: {target}")

    stat = target.stat()
    size = int(getattr(stat, "size", 0) or 0)
    if size > max_bytes:
        raise ValueError(f"Artifact size {size} exceeds max_bytes {max_bytes}. Increase max_bytes to continue.")

    content = target.read_text(encoding=normalized_encoding)
    return ReadArtifactTextResult(
        base_url=resolved_base_url,
        repository=_validate_repository(repository),
        path=clean_path,
        uri=str(target),
        encoding=normalized_encoding,
        size=size,
        content=content,
    )


def _write_artifact_text_sync(
    repository: str,
    path: str,
    content: str,
    encoding: str,
    overwrite: bool,
    create_parents: bool,
    base_url: str | None,
) -> WriteArtifactTextResult:
    normalized_encoding = _validate_encoding(encoding)
    if len(content.encode(normalized_encoding)) > 5_000_000:
        raise ValueError("content is too large. Maximum supported payload is 5 MB.")

    resolved_base_url = _resolve_base_url(base_url)
    clean_path = _validate_path(path)
    if not clean_path:
        raise ValueError("path must reference a file in the repository.")

    target = _create_path(resolved_base_url, repository, clean_path)
    exists_before = target.exists()
    if exists_before and not overwrite:
        raise FileExistsError(f"Artifact already exists at {target}. Set overwrite=true to replace it.")

    if create_parents:
        target.parent.mkdir(parents=True, exist_ok=True)

    bytes_written = int(target.write_text(content, encoding=normalized_encoding))
    return WriteArtifactTextResult(
        base_url=resolved_base_url,
        repository=_validate_repository(repository),
        path=clean_path,
        uri=str(target),
        bytes_written=bytes_written,
        overwritten=exists_before,
    )
