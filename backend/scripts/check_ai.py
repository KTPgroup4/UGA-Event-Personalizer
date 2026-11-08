"""Check that the AI chosen in your .env is reachable and answers correctly.

Run from the backend folder:

    python -m scripts.check_ai

It sends one tiny question to the model named in your .env and prints the reply
and how long it took. With Ollama the first call can be slow because the model
has to load into memory. This replaces scripts/check_ollama.py.

Save this file as: scripts/check_ai.py
"""

import json
import sys
import time

from app.ai.llm_client import GeminiClient, LLMError, LLMUnavailable, OllamaClient, get_client

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


def main() -> None:
    try:
        client = get_client()
    except (RuntimeError, ValueError) as exc:  # a missing key or an unsupported provider
        print(f"\nSETTINGS PROBLEM: {exc}")
        sys.exit(1)

    kind = type(client).__name__.replace("Client", "")
    print(f"Asking {kind} model '{client.model}' ...")
    start = time.time()
    try:
        reply = client.complete_json('Reply with exactly this JSON: {"ok": true}', SCHEMA)
    except LLMUnavailable as exc:
        print(f"\nNOT AVAILABLE: {exc}")
        sys.exit(1)
    except LLMError as exc:
        print(f"\nREACHED THE SERVICE, BUT THE MODEL FAILED: {exc}")
        if isinstance(client, OllamaClient):
            print(f"If it says the model was not found, run:  ollama pull {client.model}")
        if isinstance(client, GeminiClient):
            print("Check the model name against the list in Google AI Studio.")
        sys.exit(1)

    seconds = time.time() - start
    try:
        ok = json.loads(reply).get("ok") is True
    except (json.JSONDecodeError, AttributeError):
        ok = False
    print(f"\nReply: {reply.strip()}")
    print(f"Took {seconds:.1f} seconds.")
    if ok:
        print("WORKING: connected and answering correctly.")
    else:
        print("CONNECTED, but the reply was not the JSON we asked for. The tagger will not work well with this model.")
        sys.exit(1)


if __name__ == "__main__":
    main()