from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from artifactory_mcp.artifactory_client import _to_artifact_stat


def test_to_artifact_stat_serializes_datetime_values() -> None:
    raw = SimpleNamespace(
        created=datetime(2026, 2, 18, 10, 11, 12, tzinfo=UTC),
        last_modified=datetime(2026, 2, 18, 10, 12, 13, tzinfo=UTC),
        last_updated=datetime(2026, 2, 18, 10, 13, 14, tzinfo=UTC),
        created_by="admin",
        modified_by="deployer",
        mime_type="application/octet-stream",
        size="42",
        sha1=123,
        sha256="abc",
        md5="def",
        is_dir=False,
        children=[1, "child2"],
    )

    stat = _to_artifact_stat(raw)

    assert stat["created"] == "2026-02-18T10:11:12+00:00"
    assert stat["last_modified"] == "2026-02-18T10:12:13+00:00"
    assert stat["last_updated"] == "2026-02-18T10:13:14+00:00"
    assert stat["size"] == 42
    assert stat["sha1"] == "123"
    assert stat["children"] == ["1", "child2"]
