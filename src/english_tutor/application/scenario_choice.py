"""The scenario picked for the running session, shared by the session and the tutor model."""

from __future__ import annotations

from ..domain.scenarios import FREE, KEYS


class ScenarioChoice:
    """Holds the current scenario key; an unknown key means the free conversation."""

    def __init__(self) -> None:
        self._key = FREE

    @property
    def key(self) -> str:
        """The scenario now in use (``free`` for an ordinary conversation)."""
        return self._key

    def set(self, key: str) -> str:
        """Choose ``key`` (unknown keys become ``free``) and return what was stored."""
        self._key = key if key in KEYS else FREE
        return self._key
