from __future__ import annotations

from typing import Any, TypedDict


class ArtifactEntry(TypedDict):
    uri: str
    name: str
    path: str
    is_dir: bool
    size: int | None
    last_modified: str | None


class ArtifactStat(TypedDict):
    created: str | None
    last_modified: str | None
    last_updated: str | None
    created_by: str | None
    modified_by: str | None
    mime_type: str | None
    size: int | None
    sha1: str | None
    sha256: str | None
    md5: str | None
    is_dir: bool
    children: list[str] | None


class ListArtifactsResult(TypedDict):
    base_url: str
    repository: str
    path: str
    count: int
    truncated: bool
    items: list[ArtifactEntry]


class ArtifactDetailsResult(TypedDict):
    base_url: str
    repository: str
    path: str
    uri: str
    is_dir: bool
    stat: ArtifactStat
    properties: dict[str, Any]
    download_stats: dict[str, Any] | None


class ReadArtifactTextResult(TypedDict):
    base_url: str
    repository: str
    path: str
    uri: str
    encoding: str
    size: int
    content: str


class WriteArtifactTextResult(TypedDict):
    base_url: str
    repository: str
    path: str
    uri: str
    bytes_written: int
    overwritten: bool


class HandleInfo(TypedDict):
    handle_id: str
    class_name: str
    summary: str


class DropHandleResult(TypedDict):
    handle_id: str
    dropped: bool


class MethodDescriptor(TypedDict):
    name: str
    signature: str


class CapabilitiesResult(TypedDict):
    package: str
    package_version: str
    path_method_count: int
    path_methods: list[MethodDescriptor]
    handle_workflow: list[str]
    argument_encodings: dict[str, str]


class GenericMethodResult(TypedDict):
    target: str
    method: str
    result_type: str
    result: Any
