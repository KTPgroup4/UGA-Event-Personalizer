"""The one place that talks to an AI model.

Everything else in the backend calls  client.complete_json(prompt, schema)  and
gets text back. To switch AI services, change LLM_PROVIDER and LLM_MODEL in .env.
Nothing else needs to change.

Supported services:
  gemini  Google's Gemini API (free tier, needs an API key from Google AI Studio). The default.
  ollama  a model running on your own computer (free and private, but a small model
          tagged our test flyers poorly). Kept only as an offline fallback.

Settings (put them in your .env file; change LLM_PROVIDER and LLM_MODEL together):

    LLM_PROVIDER=gemini           gemini or ollama
    LLM_MODEL=gemini-3.8-flash    gemini: use a stable (not preview) model
                                  ollama: run `ollama list` to see yours
    LLM_TIMEOUT_SEC=90            give up on one request after this long (default: 90 for gemini, 600 for ollama)

    GEMINI_API_KEY=your-key-here          (gemini only, never commit it)
    OLLAMA_URL=http://localhost:11434     (ollama only)

Save this file as: app/ai/llm_client.py
"""

import logging
import os
import time
from typing import Protocol

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "gemini"
DEFAULT_MODELS = {"ollama": "qwen2.5:3b", "gemini": "gemini-3.8-flash"}
DEFAULT_OLLAMA_URL = "http://localhost:11434"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TIMEOUT_SEC = 600  # Ollama on a laptop can be slow
GEMINI_TIMEOUT_SEC = 90  # a normal Gemini answer takes seconds; a longer wait means it is stuck
GEMINI_MAX_TIMEOUTS_IN_A_ROW = 2  # then stop the run instead of waiting on every remaining request
DEFAULT_TIMEOUTS = {"ollama": DEFAULT_TIMEOUT_SEC, "gemini": GEMINI_TIMEOUT_SEC}
CONTEXT_TOKENS = 4096  # Ollama's default window is small, so we set it ourselves


class LLMError(Exception):
    """The model could not give an answer (timeout, server error, bad response)."""


class LLMUnavailable(LLMError):
    """The model service can't be used right now. Retrying every item won't help."""


class LLMRateLimited(LLMUnavailable):
    """The service said we have asked too much (free-tier limit). Wait, then run again."""


class LLMClient(Protocol):
    model: str

    def complete_json(self, prompt: str, schema: dict) -> str:
        """Send the prompt and return the model's answer as JSON text.

        `schema` is a JSON Schema describing the shape the answer must have.
        """
        ...


class OllamaClient:
    def __init__(self, model: str, url: str = DEFAULT_OLLAMA_URL, timeout: int = DEFAULT_TIMEOUT_SEC):
        self.model = model
        self.url = url.rstrip("/")
        self.timeout = timeout

    def complete_json(self, prompt: str, schema: dict) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,  # Ollama forces the answer to match this shape
            "options": {"temperature": 0, "num_ctx": CONTEXT_TOKENS},
        }
        try:
            response = requests.post(f"{self.url}/api/chat", json=payload, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise LLMUnavailable(
                f"Can't reach Ollama at {self.url}. Is it running? "
                "(Open the Ollama app, or run `ollama serve` in another window.)"
            ) from exc
        except requests.Timeout as exc:
            raise LLMError(f"Ollama took longer than {self.timeout} seconds to answer.") from exc

        if response.status_code != 200:
            raise LLMError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        try:
            return response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("Ollama's reply was not in the expected format.") from exc


class GeminiClient:
    def __init__(self, model: str, api_key: str, timeout: int = GEMINI_TIMEOUT_SEC):
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._timeouts_in_a_row = 0

    def complete_json(self, prompt: str, schema: dict) -> str:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                # Gemini forces the answer to match this shape, like Ollama's "format".
                "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": schema}},
            },
        }
        # The key goes in a header, never in the URL, so it can't end up in logs or error messages.
        headers = {"x-goog-api-key": self.api_key}
        logger.info("Asking Gemini (gives up after %d seconds)...", self.timeout)
        started = time.time()
        try:
            response = requests.post(
                f"{GEMINI_URL}/{self.model}:generateContent",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.ConnectionError as exc:
            raise LLMUnavailable("Can't reach Google's Gemini API. Check your internet connection.") from exc
        except requests.Timeout as exc:
            self._timeouts_in_a_row += 1
            if self._timeouts_in_a_row >= GEMINI_MAX_TIMEOUTS_IN_A_ROW:
                raise LLMUnavailable(
                    f"Gemini did not answer {self._timeouts_in_a_row} requests in a row (each waited {self.timeout} seconds). "
                    "Progress is saved: wait a few minutes and run again, or try a faster model "
                    "(LLM_MODEL=gemini-3.5-flash-lite in your .env)."
                ) from exc
            raise LLMError(f"Gemini took longer than {self.timeout} seconds to answer.") from exc
        self._timeouts_in_a_row = 0
        logger.info("Gemini answered in %.0f seconds.", time.time() - started)

        if response.status_code == 429:
            raise LLMRateLimited(
                "Gemini's free-tier limit was reached. Progress is saved: wait a few minutes "
                "(or until tomorrow if it was the daily limit) and run again."
            )
        if response.status_code != 200:
            hint = " Check GEMINI_API_KEY and LLM_MODEL in your .env." if response.status_code in (400, 401, 403, 404) else ""
            raise LLMError(f"Gemini returned HTTP {response.status_code}: {response.text[:200]}{hint}")
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini's reply was not in the expected format (it may have been blocked).") from exc


def get_client() -> LLMClient:
    """Build the client chosen in .env."""
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"LLM_PROVIDER '{provider}' is not supported (use 'ollama' or 'gemini').")
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS[provider]
    timeout = int(os.getenv("LLM_TIMEOUT_SEC", DEFAULT_TIMEOUTS[provider]))

    if provider == "ollama":
        return OllamaClient(model, os.getenv("OLLAMA_URL", DEFAULT_OLLAMA_URL), timeout)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")
    return GeminiClient(model, api_key, timeout)