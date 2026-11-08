"""Tests for saving and loading the week's events.

Save this file as: tests/test_event_store.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import datetime

import pytest

from app import event_store
from app.schemas.event import Event


def make_event(event_id="e1", **extra):
    fields = dict(id=event_id, title="AI Club Kickoff", start=datetime.fromisoformat("2026-11-12T18:00:00-05:00"),
                  end=datetime.fromisoformat("2026-11-12T19:30:00-05:00"), location="Boyd 328",
                  interest_tags=["technology-coding:ai"], relevant_colleges=["computing"])
    fields.update(extra)
    return Event(**fields)


def test_events_survive_a_save_and_load(tmp_path):
    path = tmp_path / "events.json"
    original = [make_event("e1"), make_event("e2", end=None, url="https://example.com/x")]
    event_store.save_events(original, path=path)
    loaded = event_store.load_events(path)
    assert loaded == original
    assert loaded[0].start.utcoffset().total_seconds() == -5 * 3600  # the clock offset is kept


def test_the_file_also_records_flyers_that_need_review(tmp_path):
    path = tmp_path / "events.json"
    event_store.save_events([make_event()], needs_review=[{"flyer_id": "f9", "reason": "no date"}], path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["needs_review"] == [{"flyer_id": "f9", "reason": "no date"}]
    assert "built_at" in data


def test_saving_makes_the_folder_and_leaves_no_temp_file(tmp_path):
    path = tmp_path / "new" / "folder" / "events.json"
    event_store.save_events([], path=path)
    assert path.is_file() and list(path.parent.glob("*.tmp")) == []
    assert event_store.load_events(path) == []


def test_loading_before_the_weekly_job_has_run_says_what_to_do(tmp_path):
    with pytest.raises(event_store.NoEventsYet, match="scripts.build_events"):
        event_store.load_events(tmp_path / "missing.json")


def test_a_damaged_file_gives_a_clear_error(tmp_path):
    path = tmp_path / "events.json"
    path.write_text("{oops", encoding="utf-8")
    with pytest.raises(ValueError, match="damaged"):
        event_store.load_events(path)
    path.write_text(json.dumps({"events": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="damaged"):
        event_store.load_events(path)


# ---- demo events ----


def setup_demo(tmp_path, monkeypatch, real=True):
    real_path, demo_path = tmp_path / "events.json", tmp_path / "demo_events.json"
    if real:
        event_store.save_events([make_event("real", start=datetime.fromisoformat("2026-11-12T18:00:00-05:00"))], path=real_path)
    event_store.save_events([make_event("fake_01", start=datetime.fromisoformat("2026-11-09T10:00:00-05:00"))], path=demo_path)
    monkeypatch.setattr(event_store, "EVENTS_PATH", real_path)
    monkeypatch.setattr(event_store, "DEMO_EVENTS_PATH", demo_path)
    monkeypatch.delenv("INCLUDE_DEMO_EVENTS", raising=False)


def test_demo_events_are_left_out_unless_switched_on(tmp_path, monkeypatch):
    setup_demo(tmp_path, monkeypatch)
    assert [e.id for e in event_store.load_events()] == ["real"]
    for value in ("true", "TRUE", " 1 ", "yes", "on"):
        monkeypatch.setenv("INCLUDE_DEMO_EVENTS", value)
        assert [e.id for e in event_store.load_events()] == ["fake_01", "real"]  # mixed in, in time order
    for value in ("false", "0", "", "no"):
        monkeypatch.setenv("INCLUDE_DEMO_EVENTS", value)
        assert [e.id for e in event_store.load_events()] == ["real"]


def test_an_explicit_choice_beats_the_env_setting(tmp_path, monkeypatch):
    setup_demo(tmp_path, monkeypatch)
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "true")
    assert [e.id for e in event_store.load_events(include_demo=False)] == ["real"]
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "false")
    assert [e.id for e in event_store.load_events(include_demo=True)] == ["fake_01", "real"]


def test_loading_a_specific_file_never_mixes_in_demo_events(tmp_path, monkeypatch):
    setup_demo(tmp_path, monkeypatch)
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "true")
    assert [e.id for e in event_store.load_events(tmp_path / "events.json")] == ["real"]


def test_demo_events_alone_are_enough_to_try_the_app(tmp_path, monkeypatch):
    setup_demo(tmp_path, monkeypatch, real=False)
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "true")
    assert [e.id for e in event_store.load_events()] == ["fake_01"]
    monkeypatch.setenv("INCLUDE_DEMO_EVENTS", "false")
    with pytest.raises(event_store.NoEventsYet):
        event_store.load_events()