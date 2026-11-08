"""Tests for dropping events that happen while the student is busy.

Save this file as: tests/test_availability.py
Run from the backend folder with:  python -m pytest
"""

from datetime import datetime

from app.matching.availability import clashes_with_busy, filter_free_events, overlaps
from app.schemas.busy_block import BusyBlock
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile


def at(text):
    return datetime.fromisoformat(text)


def event(event_id, start, end=None):
    return Event(id=event_id, title=f"Event {event_id}", start=start, end=end)


# One busy block: Monday Nov 9, 2026, 9:00-9:50 (New York, standard time).
BUSY = [BusyBlock(start=at("2026-11-09T09:00:00-05:00"), end=at("2026-11-09T09:50:00-05:00"))]


def ids(events):
    return [e.id for e in events]


# ---- the overlap rule ----


def test_overlap_basics():
    assert overlaps(at("2026-11-09T09:00:00-05:00"), at("2026-11-09T10:00:00-05:00"),
                    at("2026-11-09T09:30:00-05:00"), at("2026-11-09T10:30:00-05:00"))
    assert not overlaps(at("2026-11-09T09:00:00-05:00"), at("2026-11-09T10:00:00-05:00"),
                        at("2026-11-09T11:00:00-05:00"), at("2026-11-09T12:00:00-05:00"))


def test_ranges_that_only_touch_do_not_overlap():
    assert not overlaps(at("2026-11-09T09:00:00-05:00"), at("2026-11-09T10:00:00-05:00"),
                        at("2026-11-09T10:00:00-05:00"), at("2026-11-09T11:00:00-05:00"))
    assert not overlaps(at("2026-11-09T10:00:00-05:00"), at("2026-11-09T11:00:00-05:00"),
                        at("2026-11-09T09:00:00-05:00"), at("2026-11-09T10:00:00-05:00"))


def test_overlap_works_across_different_timezones():
    # 14:30Z is 9:30 in New York.
    assert overlaps(at("2026-11-09T14:30:00+00:00"), at("2026-11-09T15:30:00+00:00"),
                    at("2026-11-09T09:00:00-05:00"), at("2026-11-09T09:50:00-05:00"))


# ---- filtering ----


def test_no_busy_time_keeps_everything():
    events = [event("a", "2026-11-09T09:00:00-05:00"), event("b", "2026-11-10T12:00:00-05:00")]
    result = filter_free_events(events, [])
    assert ids(result.free) == ["a", "b"] and result.blocked == []


def test_an_event_inside_a_busy_block_is_dropped():
    result = filter_free_events([event("a", "2026-11-09T09:10:00-05:00", "2026-11-09T09:40:00-05:00")], BUSY)
    assert ids(result.blocked) == ["a"] and result.free == []


def test_partial_overlaps_are_dropped_on_both_sides():
    starts_before = event("a", "2026-11-09T08:00:00-05:00", "2026-11-09T09:15:00-05:00")
    ends_after = event("b", "2026-11-09T09:45:00-05:00", "2026-11-09T11:00:00-05:00")
    result = filter_free_events([starts_before, ends_after], BUSY)
    assert ids(result.blocked) == ["a", "b"]


def test_an_event_that_surrounds_a_busy_block_is_dropped():
    result = filter_free_events([event("a", "2026-11-09T08:00:00-05:00", "2026-11-09T12:00:00-05:00")], BUSY)
    assert ids(result.blocked) == ["a"]


def test_events_that_only_touch_the_busy_block_are_kept():
    ends_when_busy_starts = event("a", "2026-11-09T08:00:00-05:00", "2026-11-09T09:00:00-05:00")
    starts_when_busy_ends = event("b", "2026-11-09T09:50:00-05:00", "2026-11-09T10:50:00-05:00")
    result = filter_free_events([ends_when_busy_starts, starts_when_busy_ends], BUSY)
    assert ids(result.free) == ["a", "b"]


def test_an_event_on_another_day_is_kept():
    result = filter_free_events([event("a", "2026-11-10T09:10:00-05:00", "2026-11-10T09:40:00-05:00")], BUSY)
    assert ids(result.free) == ["a"]


def test_an_event_with_no_end_time_counts_as_one_hour_long():
    # 8:30 + 60 minutes = 9:30, which runs into the 9:00 class...
    assert clashes_with_busy(event("a", "2026-11-09T08:30:00-05:00"), BUSY)
    # ...but 7:30 + 60 minutes = 8:30 finishes before it.
    assert not clashes_with_busy(event("b", "2026-11-09T07:30:00-05:00"), BUSY)


def test_original_order_is_kept_in_both_lists():
    events = [
        event("a", "2026-11-09T09:10:00-05:00", "2026-11-09T09:20:00-05:00"),  # blocked
        event("b", "2026-11-09T12:00:00-05:00", "2026-11-09T13:00:00-05:00"),
        event("c", "2026-11-09T09:30:00-05:00", "2026-11-09T09:45:00-05:00"),  # blocked
        event("d", "2026-11-09T14:00:00-05:00", "2026-11-09T15:00:00-05:00"),
    ]
    result = filter_free_events(events, BUSY)
    assert ids(result.free) == ["b", "d"] and ids(result.blocked) == ["a", "c"]


def test_several_busy_blocks_are_all_checked():
    busy = BUSY + [BusyBlock(start=at("2026-11-09T16:00:00-05:00"), end=at("2026-11-09T20:00:00-05:00"))]
    result = filter_free_events(
        [event("a", "2026-11-09T17:00:00-05:00", "2026-11-09T18:00:00-05:00"),
         event("b", "2026-11-09T12:00:00-05:00", "2026-11-09T13:00:00-05:00")],
        busy,
    )
    assert ids(result.blocked) == ["a"] and ids(result.free) == ["b"]


def test_every_event_lands_in_exactly_one_list():
    events = [event(str(i), f"2026-11-09T{h:02d}:00:00-05:00") for i, h in enumerate(range(6, 22))]
    result = filter_free_events(events, BUSY)
    assert len(result.free) + len(result.blocked) == len(events)
    assert not set(ids(result.free)) & set(ids(result.blocked))


# ---- from the user's request all the way to the filter ----


def profile(week_start, busy):
    return UserProfile(week_start=week_start, majors=["undecided"], interests=["music"], busy=busy)


def test_a_profile_with_a_morning_class_blocks_the_right_events():
    p = profile("2026-11-09", [{"day": "mon", "start": "09:00", "end": "09:50"}])
    events = [
        event("clash", "2026-11-09T14:30:00+00:00", "2026-11-09T15:00:00+00:00"),  # 9:30 New York
        event("free", "2026-11-09T15:00:00+00:00", "2026-11-09T16:00:00+00:00"),  # 10:00 New York
    ]
    result = filter_free_events(events, p.busy_ranges())
    assert ids(result.blocked) == ["clash"] and ids(result.free) == ["free"]


def test_daylight_saving_does_not_move_the_class():
    # Week of Oct 26, 2026. Clocks go back on Sunday Nov 1 at 2:00 am.
    p = profile("2026-10-26", [
        {"day": "mon", "start": "09:00", "end": "10:00"},  # daylight time: 13:00-14:00 UTC
        {"day": "sun", "start": "09:00", "end": "10:00"},  # standard time: 14:00-15:00 UTC
    ])
    events = [
        event("mon-clash", "2026-10-26T13:30:00+00:00", "2026-10-26T13:45:00+00:00"),  # 9:30 EDT
        event("mon-free", "2026-10-26T14:30:00+00:00", "2026-10-26T14:45:00+00:00"),   # 10:30 EDT
        event("sun-free", "2026-11-01T13:30:00+00:00", "2026-11-01T13:45:00+00:00"),   # 8:30 EST
        event("sun-clash", "2026-11-01T14:30:00+00:00", "2026-11-01T14:45:00+00:00"),  # 9:30 EST
    ]
    result = filter_free_events(events, p.busy_ranges())
    assert ids(result.blocked) == ["mon-clash", "sun-clash"]
    assert ids(result.free) == ["mon-free", "sun-free"]