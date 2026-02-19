from __future__ import annotations

import pytest

from artifactory_mcp.bridge import _invoke_method_sync


class _DummyTarget:
    non_callable = "x"

    def get_repositories(self) -> list[str]:
        return ["libs-release-local"]


def test_invoke_method_sync_rejects_private_special_names() -> None:
    target = _DummyTarget()

    with pytest.raises(ValueError, match="private/special"):
        _invoke_method_sync(
            target=target,
            target_label="dummy",
            method="__dict__",
            positional_args=[],
            keyword_args={},
            max_items=10,
        )


def test_invoke_method_sync_suggests_close_method_names() -> None:
    target = _DummyTarget()

    with pytest.raises(ValueError, match=r"Did you mean 'get_repositories'\?"):
        _invoke_method_sync(
            target=target,
            target_label="dummy",
            method="get_repo",
            positional_args=[],
            keyword_args={},
            max_items=10,
        )


def test_invoke_method_sync_rejects_non_callable_attribute() -> None:
    target = _DummyTarget()

    with pytest.raises(ValueError, match="not callable"):
        _invoke_method_sync(
            target=target,
            target_label="dummy",
            method="non_callable",
            positional_args=[],
            keyword_args={},
            max_items=10,
        )
