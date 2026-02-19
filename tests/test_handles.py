from __future__ import annotations

from artifactory_mcp.handles import _HANDLE_STORE, _drop_handle_sync


def test_drop_handle_is_idempotent_and_reports_existence() -> None:
    handle_id = _HANDLE_STORE.put(object())

    first = _drop_handle_sync(handle_id)
    second = _drop_handle_sync(handle_id)

    assert first["dropped"] is True
    assert first["existed"] is True
    assert isinstance(first["remaining_handles"], int)

    assert second["dropped"] is True
    assert second["existed"] is False
    assert isinstance(second["remaining_handles"], int)


def test_drop_handle_rejects_empty_id() -> None:
    try:
        _drop_handle_sync("   ")
    except ValueError as exc:
        assert "handle_id cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty handle_id.")
