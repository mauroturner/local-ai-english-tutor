"""Bounded conversation memory sent to the language model."""

from __future__ import annotations

from collections import deque

from ..domain.models import ChatMessage


class ChatHistory:
    """Keeps the last ``max_exchanges`` user/assistant pairs.

    The assistant side stores only the reply text, never the JSON envelope.
    """

    def __init__(self, max_exchanges: int) -> None:
        self._messages: deque[ChatMessage] = deque(maxlen=2 * max(max_exchanges, 1))

    def add_exchange(self, user: str, assistant: str) -> None:
        """Append one user message and the tutor's reply."""
        self._messages.append(ChatMessage("user", user))
        self._messages.append(ChatMessage("assistant", assistant))

    def messages(self) -> list[ChatMessage]:
        """Return a copy of the remembered messages, oldest first."""
        return list(self._messages)

    def clear(self) -> None:
        """Forget everything."""
        self._messages.clear()
