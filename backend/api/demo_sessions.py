"""Bounded, in-memory visitor isolation for the public mock-tool demo.

A session cookie is an opaque capability. This module does not authenticate a
real person; it only keeps separate visitors from sharing tasks and approvals.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Callable, Dict, Generic, Optional, Tuple, TypeVar

T = TypeVar("T")


class SessionCapacityError(RuntimeError):
    pass


@dataclass
class _Session(Generic[T]):
    value: T
    last_seen: float


class DemoSessionStore(Generic[T]):
    """Issue opaque session IDs and cap idle runtime memory use."""

    def __init__(
        self,
        factory: Callable[[], T],
        *,
        idle_seconds: int = 3600,
        max_sessions: int = 64,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._factory = factory
        self._idle_seconds = idle_seconds
        self._max_sessions = max_sessions
        self._clock = clock
        self._sessions: Dict[str, _Session[T]] = {}
        self._lock = RLock()

    def get_or_create(self, session_id: Optional[str]) -> Tuple[str, T, bool]:
        with self._lock:
            now = self._clock()
            self._sessions = {
                key: item
                for key, item in self._sessions.items()
                if now - item.last_seen < self._idle_seconds
            }
            if session_id is not None and session_id in self._sessions:
                item = self._sessions[session_id]
                item.last_seen = now
                return session_id, item.value, False
            if len(self._sessions) >= self._max_sessions:
                raise SessionCapacityError("demo visitor limit reached")
            new_id = secrets.token_urlsafe(32)
            value = self._factory()
            self._sessions[new_id] = _Session(value, now)
            return new_id, value, True

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
