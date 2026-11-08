"""Tests for the made-up test events.

Save this file as: tests/test_fake_events.py
Run from the backend folder with:  python -m pytest
"""

import sys
from datetime import date, datetime

import pytest

from app import event_store, taxonomy
from app.schemas.event import Event
from scripts import add_fake_events as fake


def test_every_fake_event_is_valid_with_real_tags():
    events = fake.fake_events()
    assert len(events) == len(fake.FAKE) > 20
    assert len({e.id for e in events}) == len(events)
    assert all(e.id.startswith("fake_") and e.interest_tags for e in events)
    assert all(t in taxonomy.LABELS for e in events for t in e.interest_tags)


def test_they_cover_every_day_of_the_week_and_many_different_times():
    events = fake.fake_events(date(2026, 11, 9))
    assert {e.start.date().weekday() for e in events} == set(range(7))
    assert len({(e.start.hour, e.start.minute) for e in events}) >= 20
    assert all(date(2026, 11, 9) <= e.start.date() <= date(2026, 11, 15) for e in events)


def test_about_a_third_are_computing_and_some_are_limited_to_a_college():
    events = fake.fake_events()
    computing = [e for e in events if any(t.startswith("technology-coding") for t in e.interest_tags)]
    assert 9 <= len(computing) <= 13
    assert {c for e in events for c in e.relevant_colleges} == {"computing", "terry"}


def test_events_can_be_moved_to_another_week_but_only_to_a_monday():
    moved = fake.fake_events(date(2026, 11, 16))
    assert min(e.start for e in moved).date() == date(2026, 11, 16)
    with pytest.raises(ValueError, match="not a Monday"):
        fake.fake_events(date(2026, 11, 17))


def test_the_demo_file_is_separate_and_removable(tmp_path, monkeypatch):
    real_path, demo_path = tmp_path / "events.json", tmp_path / "demo_events.json"
    real = Event(id="flyer_001", title="Real", start=datetime.fromisoformat("2026-11-10T18:00:00-05:00"))
    event_store.save_events([real], path=real_path)
    monkeypatch.setattr(event_store, "EVENTS_PATH", real_path)
    monkeypatch.setattr(event_store, "DEMO_EVENTS_PATH", demo_path)
    monkeypatch.delenv("INCLUDE_DEMO_EVENTS", raising=False)
    monkeypatch.setattr(sys, "argv", ["add_fake_events"])

    fake.main()
    assert demo_path.is_file()
    assert [e.id for e in event_store.load_events(real_path)] == ["flyer_001"]  # real file untouched
    assert len(event_store.load_events()) == 1  # and the demo is off by default

    fake.main()  # running twice just rewrites the same file
    assert len(event_store.load_demo_events()) == len(fake.FAKE)

    monkeypatch.setattr(sys, "argv", ["add_fake_events", "--remove"])
    fake.main()
    assert not demo_path.exists() and event_store.load_demo_events() == []
    fake.main()  # removing again is harmless
    assert not demo_path.exists()