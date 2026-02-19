from __future__ import annotations

import threading
from typing import Any

from .models import DropHandleResult, HandleInfo


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

    def count(self) -> int:
        with self._lock:
            return len(self._items)


def _drop_handle_sync(handle_id: str) -> DropHandleResult:
    normalized = handle_id.strip()
    if not normalized:
        raise ValueError("handle_id cannot be empty.")

    existed = _HANDLE_STORE.drop(normalized)
    # Idempotent delete semantics: desired post-state is "handle absent".
    return DropHandleResult(
        handle_id=normalized,
        dropped=True,
        existed=existed,
        remaining_handles=_HANDLE_STORE.count(),
    )


_HANDLE_STORE = _HandleStore()
