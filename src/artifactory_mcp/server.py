from __future__ import annotations

import base64
import codecs
import fnmatch
import importlib.metadata
import inspect
import logging
import os
import pathlib
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal, TypedDict, cast
from urllib.parse import urlparse

import anyio
from artifactory import ArtifactoryException, ArtifactoryPath, ArtifactorySaaSPath
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def _parse_bool(value: str | None, *, default: bool, name: str) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value!r}. Use one of: true/false, 1/0, yes/no.")


def _parse_int(
    value: str | None,
    *,
    default: int,
    minimum: int,
    maximum: int,
    name: str,
) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer value for {name}: {value!r}.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"Invalid value for {name}: {parsed}. Expected range is {minimum}..{maximum}.")
    return parsed


def _parse_csv(value: str | None) -> list[str]:
    if value is None or value.strip() == "":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_base_url(value: str, *, name: str) -> str:
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid {name}: {value!r}. Expected an absolute HTTP/HTTPS URL.")
    return candidate


def _validate_repository(repository: str) -> str:
    repo = repository.strip()
    if not repo:
        raise ValueError("Repository cannot be empty.")
    if not _REPO_PATTERN.fullmatch(repo):
        raise ValueError(f"Invalid repository {repository!r}. Use letters, numbers, '.', '_' or '-'.")
    return repo


def _validate_path(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    if cleaned in {"", ".", "/"}:
        return ""
    parts = [segment for segment in cleaned.split("/") if segment and segment != "."]
    if any(segment == ".." for segment in parts):
        raise ValueError("Path cannot contain '..' segments.")
    return "/".join(parts)


def _validate_auth_inputs(
    username: str | None,
    password: str | None,
    api_key: str | None,
    token: str | None,
) -> None:
    if (username and not password) or (password and not username):
        raise ValueError("Set both ARTIFACTORY_USERNAME and ARTIFACTORY_PASSWORD, or neither.")

    auth_methods = int(bool(token)) + int(bool(api_key)) + int(bool(username and password))
    if auth_methods > 1:
        raise ValueError("Configure only one authentication method: token, api key, or username/password.")


def _validate_encoding(encoding: str) -> str:
    candidate = encoding.strip()
    if not candidate:
        raise ValueError("encoding cannot be empty.")
    try:
        codecs.lookup(candidate)
    except LookupError as exc:
        raise ValueError(f"Unsupported encoding: {encoding!r}.") from exc
    return candidate


@dataclass(frozen=True)
class ServerSettings:
    artifactory_base_url: str | None
    artifactory_username: str | None
    artifactory_password: str | None
    artifactory_api_key: str | None
    artifactory_token: str | None
    artifactory_verify_ssl: bool
    artifactory_timeout_seconds: int
    artifactory_use_saas_path: bool
    mcp_transport: Literal["stdio", "streamable-http"]
    mcp_host: str
    mcp_port: int
    mcp_streamable_http_path: str
    mcp_stateless_http: bool
    mcp_json_response: bool
    mcp_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    mcp_enable_dns_rebinding_protection: bool
    mcp_allowed_hosts: list[str]
    mcp_allowed_origins: list[str]
    mcp_default_max_items: int

    @classmethod
    def from_env(cls) -> ServerSettings:
        transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError(f"Invalid MCP_TRANSPORT {transport!r}. Supported values: stdio, streamable-http.")
        mcp_transport: Literal["stdio", "streamable-http"] = cast(Literal["stdio", "streamable-http"], transport)

        log_level = os.getenv("MCP_LOG_LEVEL", "INFO").strip().upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"Invalid MCP_LOG_LEVEL {log_level!r}. Use one of: {', '.join(sorted(_VALID_LOG_LEVELS))}."
            )
        mcp_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = cast(
            Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], log_level
        )

        base_url = os.getenv("ARTIFACTORY_BASE_URL")
        validated_base_url = (
            _validate_base_url(base_url, name="ARTIFACTORY_BASE_URL") if base_url and base_url.strip() else None
        )

        username = os.getenv("ARTIFACTORY_USERNAME")
        password = os.getenv("ARTIFACTORY_PASSWORD")
        api_key = os.getenv("ARTIFACTORY_API_KEY")
        token = os.getenv("ARTIFACTORY_TOKEN")
        _validate_auth_inputs(username, password, api_key, token)

        streamable_http_path = os.getenv("MCP_STREAMABLE_HTTP_PATH", "/mcp").strip()
        if not streamable_http_path.startswith("/"):
            raise ValueError("MCP_STREAMABLE_HTTP_PATH must start with '/'.")

        return cls(
            artifactory_base_url=validated_base_url,
            artifactory_username=username,
            artifactory_password=password,
            artifactory_api_key=api_key,
            artifactory_token=token,
            artifactory_verify_ssl=_parse_bool(
                os.getenv("ARTIFACTORY_VERIFY_SSL"),
                default=True,
                name="ARTIFACTORY_VERIFY_SSL",
            ),
            artifactory_timeout_seconds=_parse_int(
                os.getenv("ARTIFACTORY_TIMEOUT_SECONDS"),
                default=30,
                minimum=1,
                maximum=600,
                name="ARTIFACTORY_TIMEOUT_SECONDS",
            ),
            artifactory_use_saas_path=_parse_bool(
                os.getenv("ARTIFACTORY_USE_SAAS_PATH"),
                default=False,
                name="ARTIFACTORY_USE_SAAS_PATH",
            ),
            mcp_transport=mcp_transport,
            mcp_host=os.getenv("MCP_HOST", "127.0.0.1"),
            mcp_port=_parse_int(
                os.getenv("MCP_PORT"),
                default=8000,
                minimum=1,
                maximum=65535,
                name="MCP_PORT",
            ),
            mcp_streamable_http_path=streamable_http_path,
            mcp_stateless_http=_parse_bool(
                os.getenv("MCP_STATELESS_HTTP"),
                default=False,
                name="MCP_STATELESS_HTTP",
            ),
            mcp_json_response=_parse_bool(
                os.getenv("MCP_JSON_RESPONSE"),
                default=False,
                name="MCP_JSON_RESPONSE",
            ),
            mcp_log_level=mcp_log_level,
            mcp_enable_dns_rebinding_protection=_parse_bool(
                os.getenv("MCP_ENABLE_DNS_REBINDING_PROTECTION"),
                default=False,
                name="MCP_ENABLE_DNS_REBINDING_PROTECTION",
            ),
            mcp_allowed_hosts=_parse_csv(os.getenv("MCP_ALLOWED_HOSTS")),
            mcp_allowed_origins=_parse_csv(os.getenv("MCP_ALLOWED_ORIGINS")),
            mcp_default_max_items=_parse_int(
                os.getenv("MCP_DEFAULT_MAX_ITEMS"),
                default=200,
                minimum=10,
                maximum=5000,
                name="MCP_DEFAULT_MAX_ITEMS",
            ),
        )


SETTINGS = ServerSettings.from_env()

logging.basicConfig(
    level=getattr(logging, SETTINGS.mcp_log_level),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("artifactory_mcp")


def _build_transport_security_settings() -> TransportSecuritySettings:
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=SETTINGS.mcp_enable_dns_rebinding_protection,
        allowed_hosts=SETTINGS.mcp_allowed_hosts,
        allowed_origins=SETTINGS.mcp_allowed_origins,
    )


mcp = FastMCP(
    name="artifactory-mcp",
    instructions=(
        "MCP server for JFrog Artifactory using dohq-artifactory. "
        "Supports convenience artifact tools plus generic root/path/handle method invocation "
        "to cover full underlying client functionality."
    ),
    host=SETTINGS.mcp_host,
    port=SETTINGS.mcp_port,
    streamable_http_path=SETTINGS.mcp_streamable_http_path,
    stateless_http=SETTINGS.mcp_stateless_http,
    json_response=SETTINGS.mcp_json_response,
    transport_security=_build_transport_security_settings(),
    log_level=SETTINGS.mcp_log_level,
)


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


class _HandleStore:
    def __init__(self) -> None:
        self._items: dict[str, Any] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def put(self, obj: Any) -> str:
        with self._lock:
            self._counter += 1
            handle_id = f"h{self._counter}"
            self._items[handle_id] = obj
            return handle_id

    def get(self, handle_id: str) -> Any:
        with self._lock:
            if handle_id not in self._items:
                raise ValueError(f"Unknown handle_id {handle_id!r}.")
            return self._items[handle_id]

    def drop(self, handle_id: str) -> bool:
        with self._lock:
            return self._items.pop(handle_id, None) is not None

    def list(self) -> list[HandleInfo]:
        with self._lock:
            output: list[HandleInfo] = []
            for handle_id, obj in self._items.items():
                output.append(
                    HandleInfo(
                        handle_id=handle_id,
                        class_name=type(obj).__name__,
                        summary=repr(obj),
                    )
                )
            return output


_HANDLE_STORE = _HandleStore()


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


def _format_error(action: str, exc: Exception) -> str:
    if isinstance(exc, (ValueError, FileNotFoundError, FileExistsError, TypeError)):
        return str(exc)
    if isinstance(exc, ArtifactoryException):
        return f"Artifactory error during {action}: {exc}"
    return f"Unexpected error during {action}: {type(exc).__name__}: {exc}"


def _normalize_max_items(max_items: int | None) -> int:
    if max_items is None:
        return SETTINGS.mcp_default_max_items
    if max_items < 1 or max_items > 10_000:
        raise ValueError("max_items must be between 1 and 10000.")
    return max_items


def _iter_with_limit(values: Iterator[Any], *, max_items: int) -> tuple[list[Any], bool]:
    output: list[Any] = []
    truncated = False
    for item in values:
        if len(output) >= max_items:
            truncated = True
            break
        output.append(item)
    return output, truncated


def _serialize_value(value: Any, *, max_items: int, create_handles: bool = True) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, bytes):
        return {
            "type": "bytes",
            "size": len(value),
            "base64": base64.b64encode(value).decode("ascii"),
        }

    if isinstance(value, pathlib.Path):
        return str(value)

    if isinstance(value, (ArtifactoryPath, ArtifactorySaaSPath)):
        return {
            "type": "artifactory_path",
            "uri": str(value),
            "repository": value.repo,
            "path": _path_in_repo(value),
        }

    if isinstance(value, dict):
        output_dict: dict[str, Any] = {}
        for key, item in value.items():
            output_dict[str(key)] = _serialize_value(item, max_items=max_items, create_handles=create_handles)
        return output_dict

    if isinstance(value, (list, tuple, set)):
        output_list: list[Any] = []
        for item in list(value)[:max_items]:
            output_list.append(_serialize_value(item, max_items=max_items, create_handles=create_handles))
        if len(value) > max_items:
            return {
                "type": "truncated_list",
                "items": output_list,
                "total": len(value),
                "returned": max_items,
            }
        return output_list

    if isinstance(value, Iterator):
        consumed, truncated = _iter_with_limit(value, max_items=max_items)
        return {
            "type": "iterator",
            "items": [_serialize_value(item, max_items=max_items, create_handles=create_handles) for item in consumed],
            "truncated": truncated,
            "returned": len(consumed),
        }

    if isinstance(value, Exception):
        return {"type": "exception", "class": type(value).__name__, "message": str(value)}

    if create_handles:
        handle_id = _HANDLE_STORE.put(value)
        return {
            "type": "handle",
            "handle_id": handle_id,
            "class_name": type(value).__name__,
            "summary": repr(value),
        }

    return {"type": "repr", "value": repr(value)}


def _decode_special_argument(mapping: dict[str, Any]) -> Any:
    if "__handle_id__" in mapping and len(mapping) == 1:
        handle_id = mapping["__handle_id__"]
        if not isinstance(handle_id, str):
            raise ValueError("__handle_id__ must be a string.")
        return _HANDLE_STORE.get(handle_id)

    if "__bytes_base64__" in mapping and len(mapping) == 1:
        encoded = mapping["__bytes_base64__"]
        if not isinstance(encoded, str):
            raise ValueError("__bytes_base64__ must be a string.")
        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("Invalid __bytes_base64__ payload.") from exc

    if "__path__" in mapping and len(mapping) == 1:
        path_ref = mapping["__path__"]
        if not isinstance(path_ref, dict):
            raise ValueError("__path__ must be an object.")

        ref_repository = path_ref.get("repository")
        ref_path = path_ref.get("path", "")
        ref_base_url = path_ref.get("base_url")

        if not isinstance(ref_repository, str):
            raise ValueError("__path__.repository must be a string.")
        if not isinstance(ref_path, str):
            raise ValueError("__path__.path must be a string.")
        if ref_base_url is not None and not isinstance(ref_base_url, str):
            raise ValueError("__path__.base_url must be a string if provided.")

        resolved = _resolve_base_url(ref_base_url)
        return _create_path(resolved, ref_repository, ref_path)

    decoded: dict[str, Any] = {}
    for key, value in mapping.items():
        decoded[key] = _decode_json_argument(value)
    return decoded


def _decode_json_argument(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return [_decode_json_argument(item) for item in value]

    if isinstance(value, dict):
        return _decode_special_argument(value)

    return value


def _public_method_descriptors() -> list[MethodDescriptor]:
    methods: list[MethodDescriptor] = []
    for name, member in inspect.getmembers(ArtifactoryPath, predicate=callable):
        if name.startswith("_"):
            continue
        try:
            signature = str(inspect.signature(member))
        except (TypeError, ValueError):
            signature = "(...)"
        methods.append(MethodDescriptor(name=name, signature=signature))
    methods.sort(key=lambda item: item["name"])
    return methods


def _list_capabilities_sync() -> CapabilitiesResult:
    try:
        package_version = importlib.metadata.version("dohq-artifactory")
    except importlib.metadata.PackageNotFoundError:
        package_version = "unknown"

    method_descriptors = _public_method_descriptors()

    return CapabilitiesResult(
        package="dohq-artifactory",
        package_version=package_version,
        path_method_count=len(method_descriptors),
        path_methods=method_descriptors,
        handle_workflow=[
            "Use invoke_artifactory_root_method or invoke_artifactory_path_method.",
            "If result includes a handle_id, pass {'__handle_id__': '<id>'} in later calls "
            "or use invoke_artifactory_handle_method.",
            "Use drop_artifactory_handle to release handles.",
        ],
        argument_encodings={
            "handle_ref": "{'__handle_id__': 'h1'}",
            "path_ref": "{'__path__': {'repository': 'libs-release-local', 'path': 'com/example/app.jar', 'base_url': 'https://host/artifactory'}}",
            "bytes": "{'__bytes_base64__': '<base64-bytes>'}",
        },
    )


def _invoke_method_sync(
    *,
    target: Any,
    target_label: str,
    method: str,
    positional_args: list[Any],
    keyword_args: dict[str, Any],
    max_items: int | None,
) -> GenericMethodResult:
    resolved_max_items = _normalize_max_items(max_items)

    name = method.strip()
    if not name:
        raise ValueError("method cannot be empty.")

    if not hasattr(target, name):
        raise ValueError(
            f"Method {name!r} not found on target type {type(target).__name__}. "
            "Call list_artifactory_capabilities for discoverability."
        )

    member = getattr(target, name)
    if not callable(member):
        raise ValueError(f"Attribute {name!r} exists but is not callable.")

    decoded_args = [_decode_json_argument(item) for item in positional_args]
    decoded_kwargs = {key: _decode_json_argument(value) for key, value in keyword_args.items()}

    result = member(*decoded_args, **decoded_kwargs)
    if inspect.isawaitable(result):
        raise ValueError(f"Method {name!r} returned an awaitable, which is not supported by this bridge.")

    serialized = _serialize_value(result, max_items=resolved_max_items)
    return GenericMethodResult(
        target=target_label,
        method=name,
        result_type=type(result).__name__,
        result=serialized,
    )


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
        raw_download = dict(target.download_stats())
        download_stats = cast(dict[str, Any], _serialize_value(raw_download, max_items=SETTINGS.mcp_default_max_items))

    properties: dict[str, Any] = {}
    if include_properties:
        raw_properties = dict(target.properties)
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
    """Drop a stored handle when it is no longer needed."""
    dropped = await anyio.to_thread.run_sync(_HANDLE_STORE.drop, handle_id)
    return DropHandleResult(handle_id=handle_id, dropped=dropped)


def main() -> None:
    logger.info("Starting artifactory-mcp with transport=%s", SETTINGS.mcp_transport)
    mcp.run(transport=SETTINGS.mcp_transport)


if __name__ == "__main__":
    main()
