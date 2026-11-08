"""Tests for the JSON that POST /api/schedules returns.

Save this file as: tests/test_schedules_service.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import datetime

from app.schedules_service import TARGET_PICKS, build_response
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

NOW = datetime.fromisoformat("2026-11-08T09:00:00-05:00")
KEYS = {"id", "title", "description", "start", "end", "end_is_estimated", "location", "organizer", "url",
        "interest_tags", "match_kind", "reason", "conflicts_with"}


def student(interests=("music",)):
    return UserProfile(week_start="2026-11-09", majors=["undecided"], interests=list(interests))


def event(event_id, start, end=None, tags=("music",), **extra):
    return Event(id=event_id, title=f"Event {event_id}", start=datetime.fromisoformat(start),
                 end=datetime.fromisoformat(end) if end else None, interest_tags=list(tags), **extra)


def test_the_response_matches_the_contract():
    events = [event("a", "2026-11-12T18:00:00-05:00", "2026-11-12T19:30:00-05:00", location="Boyd 328", organizer="Club")]
    body = build_response(student(), events, now=NOW)
    assert set(body) == {"week_start", "target_picks", "events"}
    assert body["week_start"] == "2026-11-09" and body["target_picks"] == TARGET_PICKS
    card = body["events"][0]
    assert set(card) == KEYS
    assert card["id"] == "a" and card["location"] == "Boyd 328" and card["organizer"] == "Club"
    assert card["start"] == "2026-11-12T18:00:00-05:00" and card["end"] == "2026-11-12T19:30:00-05:00"
    assert card["end_is_estimated"] is False and card["url"] is None
    assert (card["match_kind"], card["reason"]) == ("interest", "Matches your interest in Music")
    assert card["conflicts_with"] == []


def test_a_missing_end_time_is_filled_in_and_flagged():
    body = build_response(student(), [event("a", "2026-11-12T18:00:00-05:00")], now=NOW)
    card = body["events"][0]
    assert card["end"] == "2026-11-12T19:00:00-05:00" and card["end_is_estimated"] is True


def test_every_time_has_a_utc_offset_and_the_whole_body_is_plain_json():
    events = [event("a", "2026-11-12T18:00:00-05:00", url="https://example.com/a")]
    body = build_response(student(), events, now=NOW)
    for card in body["events"]:
        assert datetime.fromisoformat(card["start"]).utcoffset() is not None
        assert datetime.fromisoformat(card["end"]).utcoffset() is not None
    assert json.loads(json.dumps(body)) == body
    assert body["events"][0]["url"] == "https://example.com/a"


def test_clashing_cards_name_each_other():
    events = [event("a", "2026-11-12T18:00:00-05:00", "2026-11-12T19:00:00-05:00"),
              event("b", "2026-11-12T18:30:00-05:00", "2026-11-12T19:30:00-05:00")]
    cards = {c["id"]: c for c in build_response(student(), events, now=NOW)["events"]}
    assert cards["a"]["conflicts_with"] == ["b"] and cards["b"]["conflicts_with"] == ["a"]


def test_no_events_gives_an_empty_deck_not_an_error():
    body = build_response(student(), [], now=NOW)
    assert body["events"] == [] and body["target_picks"] == TARGET_PICKS