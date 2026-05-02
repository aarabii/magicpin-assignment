"""
Version-controlled in-memory context store.

Rules:
  - Same version re-push → rejected (stale_version)
  - Higher version → atomic replace
  - Lower version → rejected (stale_version)
"""

from __future__ import annotations
import threading
from datetime import datetime, timezone
from typing import Any, Optional


class VersionedContext:
    __slots__ = ("data", "version", "stored_at")

    def __init__(self, data: dict[str, Any], version: int):
        self.data = data
        self.version = version
        self.stored_at = datetime.now(timezone.utc).isoformat()


class ContextStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._stores: dict[str, dict[str, VersionedContext]] = {
            "category": {},
            "merchant": {},
            "customer": {},
            "trigger": {},
        }

    # ── upsert ──────────────────────────────────────────────────────────

    def upsert(
        self, scope: str, context_id: str, version: int, payload: dict[str, Any]
    ) -> tuple[bool, str, Optional[str], Optional[int]]:
        """
        Returns (accepted, ack_id, stored_at | None, current_version | None).
        """
        store = self._stores.get(scope)
        if store is None:
            return False, "", None, None

        with self._lock:
            existing = store.get(context_id)
            if existing and existing.version >= version:
                return False, "", None, existing.version

            vc = VersionedContext(payload, version)
            store[context_id] = vc
            ack_id = f"ack_{context_id}_v{version}"
            return True, ack_id, vc.stored_at, None

    # ── reads ───────────────────────────────────────────────────────────

    def get(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        store = self._stores.get(scope, {})
        vc = store.get(context_id)
        return vc.data if vc else None

    def get_all(self, scope: str) -> dict[str, dict[str, Any]]:
        store = self._stores.get(scope, {})
        return {cid: vc.data for cid, vc in store.items()}

    def counts(self) -> dict[str, int]:
        return {scope: len(s) for scope, s in self._stores.items()}

    # ── bulk load (for dataset pre-load) ────────────────────────────────

    def bulk_load(self, scope: str, items: dict[str, dict[str, Any]], version: int = 0):
        """Load many items at once (startup only, version=0 so judge can override)."""
        store = self._stores.get(scope)
        if store is None:
            return
        with self._lock:
            for cid, data in items.items():
                if cid not in store:
                    store[cid] = VersionedContext(data, version)
