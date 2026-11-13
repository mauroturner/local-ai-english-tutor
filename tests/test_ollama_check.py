"""check_connection classifies the answer of an Ollama server without raising."""

from __future__ import annotations

import pytest
import requests

from english_tutor.adapters.ollama_check import check_connection, model_installed
from english_tutor.ports import ConnectionStatus as S


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self._response, self._error = response, error
        self.gets = []

    def get(self, url, timeout=None):
        self.gets.append({"url": url, "timeout": timeout})
        if self._error:
            raise self._error
        return self._response


def tags(*names):
    return FakeResponse({"models": [{"name": n} for n in names]})


def test_ok_when_the_model_is_installed():
    session = FakeSession(tags("llama3:8b", "other:1"))
    result = check_connection("http://localhost:11434/", "llama3:8b", session)
    assert result.status is S.OK
    assert session.gets == [{"url": "http://localhost:11434/api/tags", "timeout": 3.0}]


def test_a_model_without_a_tag_matches_latest():
    session = FakeSession(tags("english:latest"))
    assert check_connection("http://x", "english", session).status is S.OK


def test_model_missing_when_it_is_not_in_the_list():
    result = check_connection("http://x", "llama3:8b", FakeSession(tags("other:1")))
    assert result.status is S.MODEL_MISSING


def test_model_missing_with_an_empty_list():
    empty = FakeResponse({"models": []})
    assert check_connection("http://x", "m", FakeSession(empty)).status is S.MODEL_MISSING
    nothing = FakeResponse({})
    assert check_connection("http://x", "m", FakeSession(nothing)).status is S.MODEL_MISSING


def test_connection_refused_is_unreachable():
    session = FakeSession(error=requests.ConnectionError("refused"))
    assert check_connection("http://x", "m", session).status is S.UNREACHABLE


def test_a_timeout_is_reported_as_such_even_for_connect_timeouts():
    for error in (requests.ReadTimeout("slow"), requests.ConnectTimeout("slow")):
        assert check_connection("http://x", "m", FakeSession(error=error)).status is S.TIMEOUT


@pytest.mark.parametrize(
    "response",
    [FakeResponse({}, status=500), FakeResponse(ValueError("not json")), FakeResponse(["x"])],
)
def test_a_bad_answer_is_unreachable_with_a_detail(response):
    result = check_connection("http://x", "m", FakeSession(response))
    assert result.status is S.UNREACHABLE
    assert result.detail


@pytest.mark.parametrize(
    "url", ["", "   ", "localhost:11434", "ftp://x", "http://", "http://x?a=1"]
)
def test_a_bad_url_never_touches_the_network(url):
    session = FakeSession(tags("m"))
    result = check_connection(url, "m", session)
    assert result.status is S.BAD_URL
    assert result.detail
    assert session.gets == []


def test_an_empty_model_name_counts_as_missing():
    assert check_connection("http://x", "  ", FakeSession(tags("m"))).status is S.MODEL_MISSING


def test_model_installed_rules():
    assert model_installed({"m:1"}, "m:1")
    assert model_installed({"english:latest"}, "english")
    assert not model_installed({"llama3:8b"}, "llama3")  # no prefix matching
    assert not model_installed(set(), "m")
