from __future__ import annotations

import base64
import codecs
import json
import os
import re
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlparse, urlunparse

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
    if parsed.path in {"", "/"}:
        return urlunparse(parsed._replace(path="/artifactory"))
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


def _looks_like_jwt_header_only(token: str) -> bool:
    if "." in token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
        parsed = json.loads(decoded)
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    header_keys = {"alg", "kid", "typ"}
    return header_keys.issubset(parsed.keys())


def _validate_token_value(token: str) -> None:
    candidate = token.strip()
    if not candidate:
        raise ValueError("ARTIFACTORY_TOKEN cannot be empty.")
    if _looks_like_jwt_header_only(candidate):
        raise ValueError(
            "ARTIFACTORY_TOKEN appears to be only a JWT header segment, not a full access token. "
            "Use the complete token string."
        )


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

    if token:
        _validate_token_value(token)


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
