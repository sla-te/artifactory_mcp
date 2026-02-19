from __future__ import annotations

from functools import partial
from typing import Any, cast

import anyio

from .artifact_ops import (
    _get_artifact_details_sync,
    _list_artifacts_sync,
    _read_artifact_text_sync,
    _write_artifact_text_sync,
)
from .artifactory_client import _create_path, _create_root, _resolve_base_url
from .bridge import _invoke_method_sync, _list_capabilities_sync
from .errors import _format_error
from .handles import _HANDLE_STORE, _drop_handle_sync
from .models import (
    ArtifactDetailsResult,
    CapabilitiesResult,
    DropHandleResult,
    GenericMethodResult,
    HandleInfo,
    ListArtifactsResult,
    ReadArtifactTextResult,
    WriteArtifactTextResult,
)
from .runtime import logger, mcp
from .settings import SETTINGS


@mcp.tool(structured_output=True)
async def list_artifacts(
    repository: str,
    path: str = "",
    recursive: bool = False,
    pattern: str = "*",
    include_directories: bool = True,
    include_stats: bool = False,
    max_items: int = 200,
    base_url: str | None = None,
) -> ListArtifactsResult:
    """List artifacts under a repository path with optional filtering and recursion."""
    try:
        return cast(
            ListArtifactsResult,
            await anyio.to_thread.run_sync(
                _list_artifacts_sync,
                repository,
                path,
                recursive,
                pattern,
                include_directories,
                include_stats,
                max_items,
                base_url,
            ),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("list_artifacts", exc)) from None


@mcp.tool(structured_output=True)
async def get_artifact_details(
    repository: str,
    path: str,
    include_properties: bool = True,
    include_download_stats: bool = False,
    base_url: str | None = None,
) -> ArtifactDetailsResult:
    """Fetch metadata for an artifact or folder, including optional properties and download stats."""
    try:
        return cast(
            ArtifactDetailsResult,
            await anyio.to_thread.run_sync(
                _get_artifact_details_sync,
                repository,
                path,
                include_properties,
                include_download_stats,
                base_url,
            ),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("get_artifact_details", exc)) from None


@mcp.tool(structured_output=True)
async def read_artifact_text(
    repository: str,
    path: str,
    encoding: str = "utf-8",
    max_bytes: int = 200_000,
    base_url: str | None = None,
) -> ReadArtifactTextResult:
    """Read a text artifact when its size is below max_bytes."""
    try:
        return cast(
            ReadArtifactTextResult,
            await anyio.to_thread.run_sync(
                _read_artifact_text_sync,
                repository,
                path,
                encoding,
                max_bytes,
                base_url,
            ),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("read_artifact_text", exc)) from None


@mcp.tool(structured_output=True)
async def write_artifact_text(
    repository: str,
    path: str,
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = False,
    create_parents: bool = True,
    base_url: str | None = None,
) -> WriteArtifactTextResult:
    """Upload text content as an artifact, with optional parent directory creation."""
    try:
        return cast(
            WriteArtifactTextResult,
            await anyio.to_thread.run_sync(
                _write_artifact_text_sync,
                repository,
                path,
                content,
                encoding,
                overwrite,
                create_parents,
                base_url,
            ),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("write_artifact_text", exc)) from None


@mcp.tool(structured_output=True)
async def list_artifactory_capabilities() -> CapabilitiesResult:
    """List the available method surface from the underlying dohq-artifactory client and bridge argument conventions."""
    try:
        return cast(CapabilitiesResult, await anyio.to_thread.run_sync(_list_capabilities_sync))
    except Exception as exc:
        raise RuntimeError(_format_error("list_artifactory_capabilities", exc)) from None


@mcp.tool(structured_output=True)
async def invoke_artifactory_root_method(
    method: str,
    positional_args: list[Any] | None = None,
    keyword_args: dict[str, Any] | None = None,
    base_url: str | None = None,
    max_items: int | None = None,
) -> GenericMethodResult:
    """Invoke any public method on a root ArtifactoryPath object to access full admin/build/query functionality."""
    try:
        root = _create_root(_resolve_base_url(base_url))
        invoke_call = partial(
            _invoke_method_sync,
            target=root,
            target_label=f"root:{root}",
            method=method,
            positional_args=positional_args or [],
            keyword_args=keyword_args or {},
            max_items=max_items,
        )
        return cast(
            GenericMethodResult,
            await anyio.to_thread.run_sync(invoke_call),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("invoke_artifactory_root_method", exc)) from None


@mcp.tool(structured_output=True)
async def invoke_artifactory_path_method(
    repository: str,
    method: str,
    path: str = "",
    positional_args: list[Any] | None = None,
    keyword_args: dict[str, Any] | None = None,
    base_url: str | None = None,
    max_items: int | None = None,
) -> GenericMethodResult:
    """Invoke any public method on an ArtifactoryPath object for broad path-level package coverage."""
    try:
        target = _create_path(_resolve_base_url(base_url), repository, path)
        invoke_call = partial(
            _invoke_method_sync,
            target=target,
            target_label=f"path:{target}",
            method=method,
            positional_args=positional_args or [],
            keyword_args=keyword_args or {},
            max_items=max_items,
        )
        return cast(
            GenericMethodResult,
            await anyio.to_thread.run_sync(invoke_call),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("invoke_artifactory_path_method", exc)) from None


@mcp.tool(structured_output=True)
async def invoke_artifactory_handle_method(
    handle_id: str,
    method: str,
    positional_args: list[Any] | None = None,
    keyword_args: dict[str, Any] | None = None,
    max_items: int | None = None,
) -> GenericMethodResult:
    """Invoke a method on an object previously returned as a handle from bridge tools."""
    try:
        handle = _HANDLE_STORE.get(handle_id)
        invoke_call = partial(
            _invoke_method_sync,
            target=handle,
            target_label=f"handle:{handle_id}:{type(handle).__name__}",
            method=method,
            positional_args=positional_args or [],
            keyword_args=keyword_args or {},
            max_items=max_items,
        )
        return cast(
            GenericMethodResult,
            await anyio.to_thread.run_sync(invoke_call),
        )
    except Exception as exc:
        raise RuntimeError(_format_error("invoke_artifactory_handle_method", exc)) from None


@mcp.tool(structured_output=True)
async def list_artifactory_handles() -> list[HandleInfo]:
    """List active object handles produced by generic invocation tools."""
    return cast(list[HandleInfo], await anyio.to_thread.run_sync(_HANDLE_STORE.list))


@mcp.tool(structured_output=True)
async def drop_artifactory_handle(handle_id: str) -> DropHandleResult:
    """Idempotently remove a stored handle and report whether it existed."""
    return cast(DropHandleResult, await anyio.to_thread.run_sync(_drop_handle_sync, handle_id))


def main() -> None:
    logger.info("Starting artifactory-mcp with transport=%s", SETTINGS.mcp_transport)
    mcp.run(transport=SETTINGS.mcp_transport)
