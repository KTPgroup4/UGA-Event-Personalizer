"""Tests for the whole per-student pipeline.

Save this file as: tests/test_pipeline.py
Run from the backend folder with:  python -m pytest
"""

from datetime import datetime, timedelta

from app.matching.pipeline import recommend, week_window
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

MONDAY = datetime.fromisoformat("2026-11-09T00:00:00-05:00")
NOW = datetime.fromisoformat("2026-11-08T12:00:00-05:00")  # Sunday, the day before the week


def student(interests=("music",), majors=("undecided",), busy=()):
    return UserProfile(week_start="2026-11-09", majors=list(majors), interests=list(interests), busy=list(busy))


def event(event_id, hours_after_monday, tags=("music",), colleges=()):
    return Event(id=event_id, title=event_id, start=MONDAY + timedelta(hours=hours_after_monday),
                 interest_tags=list(tags), relevant_colleges=list(colleges))


def deck_ids(rec):
    return [c.scored.event.id for c in rec.deck]


def test_the_planning_week_runs_monday_to_monday_on_campus_time():
    start, end = week_window(student())
    assert (start.isoformat(), end.isoformat()) == ("2026-11-09T00:00:00-05:00", "2026-11-16T00:00:00-05:00")


def test_events_outside_the_week_are_dropped():
    events = [event("last-week", -5), event("in-week", 10), event("next-week", 24 * 7 + 1)]
    rec = recommend(student(), events, NOW)
    assert deck_ids(rec) == ["in-week"]
    assert [e.id for e in rec.out_of_week] == ["last-week", "next-week"]


def test_events_that_already_started_are_dropped_but_later_ones_stay():
    rec = recommend(student(), [event("began", 10), event("later", 30)], now=MONDAY + timedelta(hours=11))
    assert deck_ids(rec) == ["later"]
    assert [e.id for e in rec.already_started] == ["began"]


def test_events_during_busy_blocks_are_dropped():
    busy = [{"day": "mon", "start": "09:00", "end": "10:00"}]
    rec = recommend(student(busy=busy), [event("class-time", 9), event("after", 10)], NOW)
    assert deck_ids(rec) == ["after"]
    assert [e.id for e in rec.busy] == ["class-time"]


def test_events_for_other_colleges_are_dropped():
    cs = student(majors=["computer-science"])
    rec = recommend(cs, [event("terry", 10, colleges=["terry"]), event("open", 11)], NOW)
    assert deck_ids(rec) == ["open"]
    assert [e.id for e in rec.other_college] == ["terry"]


def test_the_deck_is_scored_and_the_best_event_comes_first():
    rec = recommend(student(["music"]), [event("food", 10, ["food-cooking"]), event("band", 20, ["music"])], NOW)
    assert deck_ids(rec)[0] == "band"
    assert rec.deck[0].scored.reason == "Matches your interest in Music"


def test_nothing_in_nothing_out():
    rec = recommend(student(), [], NOW)
    assert rec.deck == [] and rec.not_chosen == 0


def test_the_counts_add_up():
    events = [event(f"e{i}", 10 + 3 * i) for i in range(20)]
    rec = recommend(student(), events, NOW, deck_size=5)
    assert len(rec.deck) == 5 and rec.not_chosen == 15