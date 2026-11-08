"""Tests for the Event schema.

Save this file as: tests/test_event.py
Run from the backend folder with:  python -m pytest
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.schemas.event import DEFAULT_EVENT_MINUTES, Event

START = "2026-11-12T18:00:00-05:00"


def make(**changes):
    data = {"id": "e1", "title": "AI Club Kickoff", "start": START}
    data.update(changes)
    return Event(**data)


def test_a_minimal_event_is_valid():
    e = make()
    assert e.id == "e1" and e.title == "AI Club Kickoff"
    assert e.end is None and e.end_is_estimated
    assert e.interest_tags == [] and e.relevant_colleges == [] and e.event_type == "other"


def test_a_full_event_is_valid():
    e = make(
        end="2026-11-12T19:30:00-05:00",
        description="Pizza and demos",
        location="Boyd 328",
        organizer="AI Club",
        url="https://example.com/ai",
        flyer_id="flyer-101",
        interest_tags=["technology-coding:ai"],
        relevant_colleges=["computing"],
        event_type="talk",
    )
    assert not e.end_is_estimated
    assert e.event_type == "talk" and e.flyer_id == "flyer-101"


def test_blank_id_or_title_is_rejected():
    for field in ("id", "title"):
        with pytest.raises(ValidationError, match="must not be blank"):
            make(**{field: "   "})


def test_times_without_a_timezone_are_rejected():
    with pytest.raises(ValidationError, match="must include a timezone"):
        make(start="2026-11-12T18:00:00")
    with pytest.raises(ValidationError, match="must include a timezone"):
        make(end="2026-11-12T19:00:00")


def test_end_must_be_after_start():
    for end in (START, "2026-11-12T17:00:00-05:00"):
        with pytest.raises(ValidationError, match="end must be after start"):
            make(end=end)


def test_end_is_compared_as_a_real_moment_not_a_clock_time():
    # 23:00Z is 18:00 in New York, the same moment as the start, so this is not "after".
    with pytest.raises(ValidationError, match="end must be after start"):
        make(end="2026-11-12T23:00:00+00:00")
    assert make(end="2026-11-12T23:30:00+00:00").end is not None


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        make(attendees=84)


def test_made_up_tags_are_dropped_and_real_ones_tidied():
    e = make(interest_tags=["Technology-Coding:AI ", "music:kazoo-solo", "music", "music", 5])
    assert e.interest_tags == ["technology-coding:ai", "music"]
    assert make(relevant_colleges=["Computing", "not-a-college", "computing"]).relevant_colleges == ["computing"]


def test_an_unknown_event_type_becomes_other():
    assert make(event_type="Workshop-ish").event_type == "other"
    assert make(event_type=" Talk ").event_type == "talk"
    assert make(event_type=None).event_type == "other"


def test_tags_that_are_not_a_list_are_rejected():
    with pytest.raises(ValidationError):
        make(interest_tags="music")


def test_a_bad_url_is_rejected():
    with pytest.raises(ValidationError):
        make(url="not a url")


def test_effective_end_uses_the_default_length_when_there_is_no_end():
    e = make()
    assert e.effective_end() - e.start == timedelta(minutes=DEFAULT_EVENT_MINUTES)


def test_effective_end_returns_the_real_end_when_there_is_one():
    e = make(end="2026-11-12T20:15:00-05:00")
    assert e.effective_end() == e.end


def test_effective_end_counts_real_time_across_the_clock_change():
    # 1:30 daylight time on Nov 1, 2026 + 1 real hour = 1:30 standard time (the hour repeats).
    ny = ZoneInfo("America/New_York")
    e = make(start=datetime(2026, 11, 1, 1, 30, tzinfo=ny))
    elapsed = e.effective_end().astimezone(timezone.utc) - e.start.astimezone(timezone.utc)
    assert elapsed == timedelta(minutes=DEFAULT_EVENT_MINUTES)
    assert e.effective_end().utcoffset() == timedelta(hours=-5)


def test_an_event_survives_a_json_round_trip():
    e = make(end="2026-11-12T19:00:00-05:00", interest_tags=["music"], url="https://example.com/x")
    again = Event.model_validate_json(e.model_dump_json())
    assert again == e