"""Tests for the Ollama client and the .env settings. No real Ollama is needed.

Save this file as: tests/test_llm_client.py
Run from the backend folder with:  python -m pytest
"""

import pytest
import requests

from app.ai import llm_client
from app.ai.llm_client import (
    GeminiClient,
    LLMError,
    LLMRateLimited,
    LLMUnavailable,
    OllamaClient,
    get_client,
)

SCHEMA = {"type": "object", "properties": {"results": {"type": "array"}}}


class FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code, self._body, self.text = status_code, body, text

    def json(self):
        if self._body is None:
            raise ValueError("no JSON")
        return self._body


def patch_post(monkeypatch, response=None, error=None):
    seen = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        seen.update(url=url, json=json, timeout=timeout, headers=headers)
        if error:
            raise error
        return response

    monkeypatch.setattr(llm_client.requests, "post", fake_post)
    return seen


def test_a_good_reply_returns_the_text(monkeypatch):
    seen = patch_post(monkeypatch, FakeResponse(body={"message": {"content": '{"results": []}'}}))
    text = OllamaClient("qwen2.5:3b", "http://localhost:11434", 99).complete_json("Hello", SCHEMA)
    assert text == '{"results": []}'
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["timeout"] == 99


def test_the_request_asks_for_a_fixed_shape_and_no_creativity(monkeypatch):
    seen = patch_post(monkeypatch, FakeResponse(body={"message": {"content": "{}"}}))
    OllamaClient("qwen2.5:3b").complete_json("Hello", SCHEMA)
    payload = seen["json"]
    assert payload["model"] == "qwen2.5:3b"
    assert payload["messages"] == [{"role": "user", "content": "Hello"}]
    assert payload["format"] == SCHEMA
    assert payload["stream"] is False
    assert payload["options"] == {"temperature": 0, "num_ctx": llm_client.CONTEXT_TOKENS}


def test_a_trailing_slash_in_the_url_is_fine(monkeypatch):
    seen = patch_post(monkeypatch, FakeResponse(body={"message": {"content": "{}"}}))
    OllamaClient("m", "http://localhost:11434/").complete_json("x", SCHEMA)
    assert seen["url"] == "http://localhost:11434/api/chat"


def test_ollama_not_running_gives_a_helpful_message(monkeypatch):
    patch_post(monkeypatch, error=requests.ConnectionError("refused"))
    with pytest.raises(LLMUnavailable, match="Is it running"):
        OllamaClient("m").complete_json("x", SCHEMA)


def test_a_timeout_is_an_error_but_not_unavailable(monkeypatch):
    patch_post(monkeypatch, error=requests.Timeout("slow"))
    with pytest.raises(LLMError, match="longer than") as caught:
        OllamaClient("m", timeout=5).complete_json("x", SCHEMA)
    assert not isinstance(caught.value, LLMUnavailable)


def test_an_http_error_is_reported_with_its_code(monkeypatch):
    patch_post(monkeypatch, FakeResponse(status_code=500, text="model not found"))
    with pytest.raises(LLMError, match="500"):
        OllamaClient("m").complete_json("x", SCHEMA)


def test_a_reply_in_the_wrong_format_is_an_error(monkeypatch):
    patch_post(monkeypatch, FakeResponse(body={"unexpected": 1}))
    with pytest.raises(LLMError, match="expected format"):
        OllamaClient("m").complete_json("x", SCHEMA)
    patch_post(monkeypatch, FakeResponse(body=None))
    with pytest.raises(LLMError, match="expected format"):
        OllamaClient("m").complete_json("x", SCHEMA)


# ---- Gemini ----


def gemini_reply(text='{"results": []}'):
    return FakeResponse(body={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_gemini_good_reply_returns_the_text(monkeypatch):
    seen = patch_post(monkeypatch, gemini_reply('{"results": [1]}'))
    assert GeminiClient("gemini-3.8-flash", "SECRET").complete_json("Hi", SCHEMA) == '{"results": [1]}'
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"


def test_gemini_request_has_the_documented_shape(monkeypatch):
    seen = patch_post(monkeypatch, gemini_reply())
    GeminiClient("gemini-3.8-flash", "SECRET", timeout=42).complete_json("Hi", SCHEMA)
    body = seen["json"]
    assert body["contents"] == [{"parts": [{"text": "Hi"}]}]
    config = body["generationConfig"]
    assert config["temperature"] == 0
    assert config["responseFormat"] == {"text": {"mimeType": "APPLICATION_JSON", "schema": SCHEMA}}
    assert seen["timeout"] == 42


def test_the_gemini_key_goes_in_a_header_never_the_url(monkeypatch):
    seen = patch_post(monkeypatch, gemini_reply())
    GeminiClient("gemini-3.8-flash", "SECRET").complete_json("Hi", SCHEMA)
    assert seen["headers"] == {"x-goog-api-key": "SECRET"}
    assert "SECRET" not in seen["url"]


def test_gemini_free_tier_limit_stops_the_run_with_a_clear_message(monkeypatch):
    patch_post(monkeypatch, FakeResponse(status_code=429, text="quota"))
    with pytest.raises(LLMRateLimited, match="run again") as caught:
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)
    assert isinstance(caught.value, LLMUnavailable)  # so the tagger stops instead of retrying


def test_gemini_bad_key_or_model_points_at_the_env_file(monkeypatch):
    patch_post(monkeypatch, FakeResponse(status_code=400, text="API key not valid"))
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)


def test_gemini_server_error_is_a_plain_error(monkeypatch):
    patch_post(monkeypatch, FakeResponse(status_code=503, text="overloaded"))
    with pytest.raises(LLMError, match="503") as caught:
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)
    assert not isinstance(caught.value, LLMUnavailable)


def test_gemini_no_internet_is_unavailable_and_timeout_is_not(monkeypatch):
    patch_post(monkeypatch, error=requests.ConnectionError("offline"))
    with pytest.raises(LLMUnavailable, match="internet"):
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)
    patch_post(monkeypatch, error=requests.Timeout("slow"))
    with pytest.raises(LLMError, match="longer than") as caught:
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)
    assert not isinstance(caught.value, LLMUnavailable)


def test_a_gemini_reply_with_no_candidates_is_an_error(monkeypatch):
    patch_post(monkeypatch, FakeResponse(body={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(LLMError, match="blocked"):
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)
    patch_post(monkeypatch, FakeResponse(body={"candidates": []}))
    with pytest.raises(LLMError, match="blocked"):
        GeminiClient("m", "k").complete_json("Hi", SCHEMA)


# ---- settings from .env ----


def clear_settings(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL", "OLLAMA_URL", "LLM_TIMEOUT_SEC", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_the_default_provider_is_gemini(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    client = get_client()
    assert isinstance(client, GeminiClient)
    assert client.model == "gemini-3.8-flash"


def test_ollama_still_works_when_chosen(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    client = get_client()
    assert isinstance(client, OllamaClient)
    assert client.model == "qwen2.5:3b"
    assert client.url == "http://localhost:11434"


def test_ollama_settings_can_be_changed_in_env(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OLLAMA_URL", "http://example:1234")
    monkeypatch.setenv("LLM_TIMEOUT_SEC", "30")
    client = get_client()
    assert (client.model, client.url, client.timeout) == ("llama3.2:3b", "http://example:1234", 30)


def test_an_unsupported_provider_is_rejected(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "some-other-ai")
    with pytest.raises(ValueError, match="not supported"):
        get_client()


def test_gemini_is_chosen_in_env_with_its_own_default_model(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "Gemini")
    monkeypatch.setenv("GEMINI_API_KEY", " abc ")
    client = get_client()
    assert isinstance(client, GeminiClient)
    assert client.model == "gemini-3.8-flash" and client.api_key == "abc"


def test_the_gemini_model_can_be_changed_in_env(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash-lite")
    assert get_client().model == "gemini-3.5-flash-lite"


def test_gemini_without_a_key_says_how_to_fix_it(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY is not set"):
        get_client()


# ---- not waiting forever on a stuck Gemini ----


def test_gemini_gives_up_after_90_seconds_by_default_and_ollama_after_600(monkeypatch):
    clear_settings(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "abc")
    assert get_client().timeout == 90
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert get_client().timeout == 600
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_TIMEOUT_SEC", "45")
    assert get_client().timeout == 45


def test_two_gemini_timeouts_in_a_row_stop_the_run(monkeypatch):
    patch_post(monkeypatch, error=requests.Timeout("slow"))
    client = GeminiClient("m", "k", timeout=5)
    with pytest.raises(LLMError, match="longer than") as first:
        client.complete_json("x", SCHEMA)
    assert not isinstance(first.value, LLMUnavailable)
    with pytest.raises(LLMUnavailable, match="2 requests in a row"):
        client.complete_json("x", SCHEMA)


def test_a_good_answer_resets_the_timeout_count(monkeypatch):
    client = GeminiClient("m", "k", timeout=5)
    patch_post(monkeypatch, error=requests.Timeout("slow"))
    with pytest.raises(LLMError):
        client.complete_json("x", SCHEMA)
    patch_post(monkeypatch, gemini_reply())
    client.complete_json("x", SCHEMA)
    patch_post(monkeypatch, error=requests.Timeout("slow"))
    with pytest.raises(LLMError) as again:
        client.complete_json("x", SCHEMA)
    assert not isinstance(again.value, LLMUnavailable)