"""Ollama /api/chat adapter implementing the TutorModel port."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

import requests

from ..domain.learner import LearnerProfile, explanation_rule, with_profile
from ..domain.scenarios import FREE, with_scenario
from ..domain.models import (
    ChatMessage,
    MistakeRecord,
    PracticeReply,
    SessionFeedback,
    Turn,
    TutorReply,
)
from ..domain.prompts import (
    REPORT_SCHEMA,
    REPORT_SYSTEM_PROMPT,
    TURN_SCHEMA,
    TURN_SYSTEM_PROMPT,
    build_report_user_message,
)
from ..domain.practice_prompts import PRACTICE_SCHEMA, build_practice_system_prompt
from ..ports import LlmUnavailable
from .ollama_check import model_installed
from .ollama_parsing import parse_feedback, parse_practice_reply, parse_tutor_reply

logger = logging.getLogger(__name__)

_CHECK_TIMEOUT_S = 3
_CONNECT_TIMEOUT_S = 5
_NUM_CTX = 4096


class OllamaTutorModel:
    """Talks to a local Ollama server using structured (JSON schema) outputs."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        temperature: float,
        session: requests.Session | None = None,
        profile: Callable[[], LearnerProfile] = LearnerProfile,
        scenario: Callable[[], str] = lambda: FREE,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._http = session if session is not None else requests.Session()
        self._profile = profile  # read on every call, so a saved change applies at once
        self._scenario = scenario  # same for the scenario picked in the main window

    def check(self) -> None:
        """Raise LlmUnavailable if Ollama is down or the model is not pulled."""
        unreachable = LlmUnavailable(
            f"Ollama not reachable at {self._base_url}: run `ollama serve`"
        )
        try:
            response = self._http.get(f"{self._base_url}/api/tags", timeout=_CHECK_TIMEOUT_S)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise unreachable from exc
        try:
            names = {m.get("name", "") for m in payload.get("models") or []}
        except (AttributeError, TypeError) as exc:
            raise LlmUnavailable(
                f"Unexpected response from Ollama at {self._base_url}/api/tags"
            ) from exc
        if not model_installed(names, self._model):
            raise LlmUnavailable(
                f"Model {self._model} not found: run `ollama pull {self._model}`"
            )

    def _turn_prompt(self) -> str:
        profile = self._profile()
        prompt = with_scenario(with_profile(TURN_SYSTEM_PROMPT, profile), self._scenario())
        rule = explanation_rule(profile)
        return f"{prompt}\n\n{rule}" if rule else prompt

    def reply(self, history: Sequence[ChatMessage], user_text: str) -> TutorReply:
        """Send system prompt + history + the raw learner text."""
        messages = [
            ChatMessage("system", self._turn_prompt()),
            *history,
            ChatMessage("user", user_text),
        ]
        return parse_tutor_reply(self._chat(messages, TURN_SCHEMA))

    def feedback(self, turns: Sequence[Turn]) -> SessionFeedback:
        """Ask for the overall session feedback."""
        messages = [
            ChatMessage("system", with_profile(REPORT_SYSTEM_PROMPT, self._profile())),
            ChatMessage("user", build_report_user_message(turns)),
        ]
        return parse_feedback(self._chat(messages, REPORT_SCHEMA))

    def practice(
        self, target: MistakeRecord, history: Sequence[ChatMessage], learner_text: str
    ) -> PracticeReply:
        """Judge one practice answer about ``target`` and ask the next question."""
        messages = [
            ChatMessage("system", build_practice_system_prompt(target, self._profile())),
            *history,
            ChatMessage("user", learner_text),
        ]
        return parse_practice_reply(self._chat(messages, PRACTICE_SCHEMA))

    def _chat(self, messages: Sequence[ChatMessage], schema: dict[str, Any]) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "format": schema,
            "options": {"temperature": self._temperature, "num_ctx": _NUM_CTX},
            "keep_alive": "10m",
        }
        try:
            response = self._http.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=(_CONNECT_TIMEOUT_S, self._timeout_s),
            )
            response.raise_for_status()
            return str(response.json()["message"]["content"])
        except requests.ConnectionError as exc:
            raise LlmUnavailable(
                f"Ollama not reachable at {self._base_url}: run `ollama serve`"
            ) from exc
        except requests.Timeout as exc:
            raise LlmUnavailable(f"Ollama timed out after {self._timeout_s:.0f}s") from exc
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise LlmUnavailable(f"Ollama request failed: {exc}") from exc
