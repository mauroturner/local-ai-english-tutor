"""OllamaTutorModel against a fake requests.Session."""

from __future__ import annotations

import json

import pytest
import requests

from english_tutor.adapters.ollama_chat import OllamaTutorModel
from english_tutor.domain.models import ChatMessage, Turn
from english_tutor.domain.prompts import (
    REPORT_SCHEMA,
    REPORT_SYSTEM_PROMPT,
    TURN_SCHEMA,
    TURN_SYSTEM_PROMPT,
)
from english_tutor.ports import LlmUnavailable


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, post=None, get=None, error=None):
        self._post, self._get, self._error = post, get, error
        self.posts, self.gets = [], []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        if self._error:
            raise self._error
        return self._post

    def get(self, url, timeout=None):
        self.gets.append({"url": url, "timeout": timeout})
        if self._error:
            raise self._error
        return self._get


def model(session):
    return OllamaTutorModel("http://x:11434/", "m:1", 90, 0.5, session=session)


def answer(content):
    return FakeResponse({"message": {"role": "assistant", "content": content}})


def test_reply_payload_and_message_order():
    content = json.dumps({"reply": "Hello! How are you?", "errors": []})
    session = FakeSession(post=answer(content))
    history = [ChatMessage("user", "hi"), ChatMessage("assistant", "hello")]
    result = model(session).reply(history, "Could you hear me?")

    call = session.posts[0]
    assert call["url"] == "http://x:11434/api/chat"
    assert call["timeout"] == (5, 90)
    payload = call["json"]
    assert payload["model"] == "m:1"
    assert payload["stream"] is False
    assert payload["format"] == TURN_SCHEMA
    assert payload["options"] == {"temperature": 0.5, "num_ctx": 4096}
    assert payload["keep_alive"] == "10m"
    assert payload["messages"] == [
        {"role": "system", "content": TURN_SYSTEM_PROMPT},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "Could you hear me?"},
    ]
    assert result.reply == "Hello! How are you?"


def test_feedback_uses_report_schema_and_prompt():
    content = json.dumps({"summary": "Good.", "strengths": [], "focus_areas": []})
    session = FakeSession(post=answer(content))
    turns = [Turn(1, "I go home", "ok", (), None)]
    result = model(session).feedback(turns)
    payload = session.posts[0]["json"]
    assert payload["format"] == REPORT_SCHEMA
    assert payload["messages"][0] == {"role": "system", "content": REPORT_SYSTEM_PROMPT}
    assert "1. I go home" in payload["messages"][1]["content"]
    assert result.summary == "Good."


def test_check_ok_with_exact_and_latest_tag():
    tags = FakeResponse({"models": [{"name": "m:1"}]})
    session = FakeSession(get=tags)
    model(session).check()
    assert session.gets[0]["url"] == "http://x:11434/api/tags"
    assert session.gets[0]["timeout"] == 3

    latest = FakeSession(get=FakeResponse({"models": [{"name": "english:latest"}]}))
    OllamaTutorModel("http://x", "english", 10, 0.1, session=latest).check()


def test_check_model_missing_message():
    session = FakeSession(get=FakeResponse({"models": [{"name": "other:1"}]}))
    with pytest.raises(LlmUnavailable, match=r"Model m:1 not found: run `ollama pull m:1`"):
        model(session).check()


def test_check_unreachable_message():
    session = FakeSession(error=requests.ConnectionError("refused"))
    with pytest.raises(
        LlmUnavailable, match=r"Ollama not reachable at http://x:11434: run `ollama serve`"
    ):
        model(session).check()


def test_chat_connection_error_becomes_llm_unavailable():
    with pytest.raises(LlmUnavailable, match="not reachable"):
        model(FakeSession(error=requests.ConnectionError("refused"))).reply([], "hi")


def test_chat_timeout_and_http_error_become_llm_unavailable():
    with pytest.raises(LlmUnavailable, match="timed out"):
        model(FakeSession(error=requests.ReadTimeout("slow"))).reply([], "hi")
    with pytest.raises(LlmUnavailable, match="request failed"):
        model(FakeSession(post=FakeResponse({}, status=500))).reply([], "hi")
    with pytest.raises(LlmUnavailable, match="request failed"):
        model(FakeSession(post=FakeResponse({"unexpected": 1}))).reply([], "hi")


def test_check_still_requires_the_exact_name_or_latest_tag():
    # The connection test shares the matching rule: no prefix matching, "name" means "name:latest".
    session = FakeSession(get=FakeResponse({"models": [{"name": "m:2"}, {"name": "mm:latest"}]}))
    with pytest.raises(LlmUnavailable, match="Model m not found"):
        OllamaTutorModel("http://x", "m", 10, 0.1, session=session).check()
