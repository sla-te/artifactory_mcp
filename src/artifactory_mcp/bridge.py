from __future__ import annotations

import base64
import importlib.metadata
import inspect
import pathlib
from collections.abc import Iterator
from dataclasses import asdict, is_dataclass
from difflib import get_close_matches
from typing import Any, cast

from artifactory import ArtifactoryPath, ArtifactorySaaSPath

from .artifactory_client import _create_path, _path_in_repo, _resolve_base_url
from .handles import _HANDLE_STORE
from .models import CapabilitiesResult, GenericMethodResult, MethodDescriptor
from .settings import SETTINGS


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


def _coerce_object_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    if hasattr(value, "_asdict"):
        as_dict = value._asdict()
        if isinstance(as_dict, dict):
            return as_dict

    if is_dataclass(value) and not isinstance(value, type):
        data = asdict(cast(Any, value))
        if isinstance(data, dict):
            return data

    if hasattr(value, "__dict__"):
        return {str(key): item for key, item in vars(value).items() if not str(key).startswith("_")}

    raise TypeError(f"Cannot convert value of type {type(value).__name__} to a dictionary.")


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


def _public_method_names_for_target(target: Any) -> list[str]:
    names = {name for name, member in inspect.getmembers(type(target), predicate=callable) if not name.startswith("_")}
    return sorted(names)


def _render_method_suggestions(name: str, candidates: list[str]) -> str:
    if not candidates:
        return ""
    matches = get_close_matches(name, candidates, n=3, cutoff=0.5)
    if not matches:
        return ""
    if len(matches) == 1:
        return f" Did you mean {matches[0]!r}?"
    return f" Did you mean one of: {', '.join(repr(item) for item in matches)}?"


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

    if name.startswith("_"):
        raise ValueError(
            f"Method {name!r} is private/special and cannot be invoked. "
            "Use public callables only (discover via list_artifactory_capabilities)."
        )

    public_method_names = _public_method_names_for_target(target)

    if not hasattr(target, name):
        suggestion = _render_method_suggestions(name, public_method_names)
        raise ValueError(
            f"Method {name!r} not found on target type {type(target).__name__}. "
            "Call list_artifactory_capabilities for discoverability."
            f"{suggestion}"
        )

    member = getattr(target, name)
    if not callable(member):
        raise ValueError(
            f"Attribute {name!r} exists on target type {type(target).__name__} but is not callable. "
            "This bridge only supports method invocation."
        )

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
