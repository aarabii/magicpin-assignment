"""
Suppression registry — prevents duplicate sends and tracks ended conversations.
"""

from __future__ import annotations
import threading
from datetime import datetime, timezone


class SuppressionRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._sent: dict[str, str] = {}          # suppression_key → iso timestamp
        self._ended: set[str] = set()             # conversation_ids that are ended
        self._sent_bodies: dict[str, set[str]] = {}  # conversation_id → set of body hashes

    # ── suppression keys ──

    def is_suppressed(self, key: str) -> bool:
        with self._lock:
            return key in self._sent

    def mark_sent(self, key: str):
        with self._lock:
            self._sent[key] = datetime.now(timezone.utc).isoformat()

    # ── ended conversations ──

    def is_ended(self, conversation_id: str) -> bool:
        with self._lock:
            return conversation_id in self._ended

    def mark_ended(self, conversation_id: str):
        with self._lock:
            self._ended.add(conversation_id)

    # ── anti-repetition ──

    def is_body_repeated(self, conversation_id: str, body: str) -> bool:
        h = str(hash(body.strip().lower()))
        with self._lock:
            bodies = self._sent_bodies.get(conversation_id, set())
            return h in bodies

    def record_body(self, conversation_id: str, body: str):
        h = str(hash(body.strip().lower()))
        with self._lock:
            self._sent_bodies.setdefault(conversation_id, set()).add(h)
