"""Saves the week's events to a file, and loads them back.

The weekly job (python -m scripts.build_events) writes data/events.json.
The API reads it on every request, so a student request never calls the AI.

Demo events (python -m scripts.add_fake_events) live in their own file,
data/demo_events.json, and are only mixed in when .env says INCLUDE_DEMO_EVENTS=true.
So real data stays pure, and the demo events survive a rebuild of events.json.

Save this file as: app/event_store.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.schemas.event import Event

load_dotenv()  # the API process may not have read .env yet

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # the backend folder
EVENTS_PATH = PROJECT_ROOT / "data" / "events.json"
DEMO_EVENTS_PATH = PROJECT_ROOT / "data" / "demo_events.json"


class NoEventsYet(Exception):
    """data/events.json doesn't exist, so the weekly job has not run."""


def save_events(events: list[Event], needs_review: list[dict] | None = None, path: Path | None = None) -> Path:
    """Write the events (and the list of flyers that need review) to a JSON file."""
    path = path or EVENTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "events": [event.model_dump(mode="json") for event in events],
        "needs_review": needs_review or [],
    }
    temp = path.with_suffix(".tmp")  # write a temp file first so a crash can't leave a half-written file
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return path


def demo_events_enabled() -> bool:
    """True when .env has INCLUDE_DEMO_EVENTS=true (also accepts 1, yes, on)."""
    return os.getenv("INCLUDE_DEMO_EVENTS", "").strip().lower() in {"1", "true", "yes", "on"}


def _read_events(path: Path) -> list[Event]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Event.model_validate(item) for item in data["events"]]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} is damaged ({exc}). Run: python -m scripts.build_events") from exc


def load_demo_events() -> list[Event]:
    """The demo events, or an empty list if there is no demo file."""
    path = DEMO_EVENTS_PATH
    return _read_events(path) if path.is_file() else []


def load_events(path: Path | None = None, include_demo: bool | None = None) -> list[Event]:
    """Read the events back. Raises NoEventsYet if there are none to show.

    With no `path` (the normal case) the demo events are mixed in when .env asks for
    it. Pass include_demo=True/False to decide explicitly.
    """
    if include_demo is None:
        include_demo = path is None and demo_events_enabled()
    path = path or EVENTS_PATH
    if path.is_file():
        events = _read_events(path)
    elif include_demo and load_demo_events():
        events = []  # demo events alone are enough to try the app
    else:
        raise NoEventsYet("No events yet. Run: python -m scripts.build_events")
    if include_demo:
        events = sorted(events + load_demo_events(), key=lambda e: (e.start.timestamp(), e.id))
    return events