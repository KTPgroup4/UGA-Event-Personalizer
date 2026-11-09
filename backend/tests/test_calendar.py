"""Tests for the saved calendar rules (app/schemas/calendar.py).

Save this file as: tests/test_calendar.py
"""

import pytest
from pydantic import ValidationError

from app.schemas.calendar import MAX_PERSONAL_EVENTS, MAX_SAVED_EVENTS, PersonalEvent, SavedCalendar, SavedEvent

EVENT = {"id": "e1", "title": "Guitar Circle", "start": "2026-11-12T18:00:00-05:00"}
PERSONAL = {"id": "p1", "title": "Study group", "date": "2026-11-11", "time": "15:30"}


def test_a_saved_event_only_needs_an_id_a_title_and_a_start():
    event = SavedEvent(**EVENT)
    assert event.end is None and event.description is None and event.interest_tags == []


def test_extra_card_fields_are_ignored_but_a_missing_start_is_not_ok():
    SavedEvent(**EVENT, reason="Matches", match_kind="interest", conflicts_with=["x"])
    with pytest.raises(ValidationError):
        SavedEvent(id="e1", title="No start")
    with pytest.raises(ValidationError):
        SavedEvent(**{**EVENT, "start": "tomorrow-ish"})


def test_a_personal_event_checks_its_date_and_times():
    assert PersonalEvent(**PERSONAL).end_time == ""
    assert PersonalEvent(**PERSONAL, end_time="16:45").end_time == "16:45"
    for bad in ({"date": "2026-13-45"}, {"time": "3:30 PM"}, {"time": "25:00"}, {"end_time": "4pm"}, {"title": ""}):
        with pytest.raises(ValidationError):
            PersonalEvent(**{**PERSONAL, **bad})


def test_a_personal_event_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        PersonalEvent(**PERSONAL, colour="red")


def test_the_calendar_has_size_limits():
    SavedCalendar(saved=[EVENT] * MAX_SAVED_EVENTS, personal=[PERSONAL] * MAX_PERSONAL_EVENTS)
    with pytest.raises(ValidationError):
        SavedCalendar(saved=[EVENT] * (MAX_SAVED_EVENTS + 1))
    with pytest.raises(ValidationError):
        SavedCalendar(personal=[PERSONAL] * (MAX_PERSONAL_EVENTS + 1))


def test_an_empty_calendar_is_fine():
    assert SavedCalendar().saved == [] and SavedCalendar().personal == []
