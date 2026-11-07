"""Tests for the user's profile and weekly busy times.

Save this file as: tests/test_user_profile.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import taxonomy
from app.schemas.busy_block import BusyBlock, BusyBlockInput, expand_busy_blocks
from app.schemas.user_profile import UserProfile

DOCS = Path(__file__).resolve().parents[2] / "docs"  # <repo>/docs


def block(day, start, end):
    return BusyBlockInput(day=day, start=start, end=end)


def profile(**changes):
    data = {
        "week_start": "2026-11-09",
        "majors": ["computer-science"],
        "interests": ["technology-coding:ai"],
        "busy": [],
    }
    data.update(changes)
    return UserProfile(**data)


def utc_hours(start: datetime, end: datetime) -> float:
    """Real elapsed hours. (Plain end - start ignores daylight saving for local times.)"""
    return (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 3600


# ---- one weekly busy block ----


def test_a_busy_block_reads_plain_clock_times():
    b = block("mon", "09:00", "09:50")
    assert b.start == time(9, 0) and b.end == time(9, 50)


def test_a_block_must_end_after_it_starts():
    for start, end in [("10:00", "10:00"), ("10:00", "09:00")]:
        with pytest.raises(ValidationError, match="end after it starts"):
            block("mon", start, end)


def test_unknown_day_names_are_rejected():
    with pytest.raises(ValidationError):
        block("monday", "09:00", "10:00")


def test_times_with_a_timezone_are_rejected():
    with pytest.raises(ValidationError, match="without a timezone"):
        block("mon", "09:00:00Z", "10:00:00Z")


def test_misspelled_block_fields_are_rejected():
    with pytest.raises(ValidationError):
        BusyBlockInput(day="mon", start="09:00", end="10:00", label="class")


# ---- turning weekly blocks into real time ranges ----


def test_blocks_land_on_the_right_dates_and_stay_timezone_aware():
    week = date(2026, 11, 9)  # a Monday, after daylight saving ended
    ranges = expand_busy_blocks(week, [block("wed", "14:00", "15:15")])
    assert len(ranges) == 1
    r = ranges[0]
    assert r.start.date() == date(2026, 11, 11) and r.start.time() == time(14, 0)
    assert r.end.time() == time(15, 15)
    assert r.start.utcoffset() == timedelta(hours=-5)  # EST


def test_sunday_is_the_last_day_of_the_week():
    r = expand_busy_blocks(date(2026, 11, 9), [block("sun", "10:00", "11:00")])[0]
    assert r.start.date() == date(2026, 11, 15)


def test_fall_back_week_keeps_the_same_clock_time():
    # Clocks go back on Sunday Nov 1, 2026, inside the week of Oct 26.
    ranges = expand_busy_blocks(date(2026, 10, 26), [block("mon", "09:00", "10:00"), block("sun", "09:00", "10:00")])
    monday, sunday = ranges
    assert monday.start.time() == sunday.start.time() == time(9, 0)
    assert monday.start.utcoffset() == timedelta(hours=-4)  # still daylight time
    assert sunday.start.utcoffset() == timedelta(hours=-5)  # standard time


def test_spring_forward_week_keeps_the_same_clock_time():
    # Clocks go forward on Sunday Mar 14, 2027, inside the week of Mar 8.
    monday, sunday = expand_busy_blocks(
        date(2027, 3, 8), [block("mon", "09:00", "10:00"), block("sun", "09:00", "10:00")]
    )
    assert monday.start.utcoffset() == timedelta(hours=-5)
    assert sunday.start.utcoffset() == timedelta(hours=-4)
    assert monday.start.time() == sunday.start.time() == time(9, 0)


def test_a_block_that_crosses_the_clock_change_counts_the_real_hours():
    # Midnight to 9:00 on Nov 1 is 10 real hours because 1:00-2:00 happens twice.
    r = expand_busy_blocks(date(2026, 10, 26), [block("sun", "00:00", "09:00")])[0]
    assert utc_hours(r.start, r.end) == 10


def test_blocks_are_sorted_by_start():
    ranges = expand_busy_blocks(date(2026, 11, 9), [block("fri", "09:00", "10:00"), block("mon", "09:00", "10:00")])
    assert [r.start.date().day for r in ranges] == [9, 13]


def test_overlapping_and_touching_blocks_are_merged():
    ranges = expand_busy_blocks(
        date(2026, 11, 9),
        [block("mon", "09:00", "10:00"), block("mon", "09:30", "11:00"), block("mon", "11:00", "12:00")],
    )
    assert len(ranges) == 1
    assert ranges[0].start.time() == time(9, 0) and ranges[0].end.time() == time(12, 0)


def test_a_block_inside_another_does_not_shrink_it():
    ranges = expand_busy_blocks(date(2026, 11, 9), [block("tue", "08:00", "17:00"), block("tue", "10:00", "11:00")])
    assert len(ranges) == 1 and ranges[0].end.time() == time(17, 0)


def test_separate_blocks_stay_separate():
    ranges = expand_busy_blocks(date(2026, 11, 9), [block("mon", "09:00", "10:00"), block("mon", "10:01", "11:00")])
    assert len(ranges) == 2


def test_no_blocks_gives_an_empty_list():
    assert expand_busy_blocks(date(2026, 11, 9), []) == []


# ---- the whole profile ----


def test_a_valid_profile_is_accepted():
    p = profile(busy=[{"day": "mon", "start": "09:00", "end": "09:50"}])
    assert p.majors == ["computer-science"]
    assert p.week_start == date(2026, 11, 9)
    assert len(p.busy) == 1


def test_week_start_must_be_a_monday():
    with pytest.raises(ValidationError, match="must be a Monday"):
        profile(week_start="2026-11-10")


def test_bad_majors_are_rejected_with_a_readable_message():
    cases = [
        ([], "at least one"),
        (["not-a-major"], "Unknown majors"),
        (["computer-science", "accounting", "finance"], "at most 2"),
        (["international-business"], "co-major"),
        (["undecided", "accounting"], "Undecided"),
    ]
    for majors, message in cases:
        with pytest.raises(ValidationError, match=message):
            profile(majors=majors)


def test_majors_are_tidied():
    assert profile(majors=[" Computer-Science ", "computer-science", "accounting"]).majors == [
        "computer-science", "accounting"]


def test_unknown_or_missing_interests_are_rejected():
    with pytest.raises(ValidationError, match="Unknown interests"):
        profile(interests=["music", "not-real"])
    with pytest.raises(ValidationError, match="at least one interest"):
        profile(interests=[])
    with pytest.raises(ValidationError):
        profile(interests=[5])


def test_interests_are_tidied_and_keep_the_users_order():
    p = profile(interests=[" Music:Guitar ", "technology-coding:ai", "music:guitar"])
    assert p.interests == ["music:guitar", "technology-coding:ai"]


def test_a_category_is_dropped_when_its_specialty_is_also_chosen():
    p = profile(interests=["engineering-making", "engineering-making:civil", "music"])
    assert p.interests == ["engineering-making:civil", "music"]


def test_too_many_interests_or_busy_blocks_are_rejected():
    everything = list(taxonomy.LABELS)
    with pytest.raises(ValidationError, match="at most 40"):
        profile(interests=everything)
    many = [{"day": "mon", "start": "09:00", "end": "10:00"}] * 101
    with pytest.raises(ValidationError, match="At most 100"):
        profile(busy=many)


def test_extra_fields_such_as_a_name_are_rejected():
    with pytest.raises(ValidationError):
        profile(name="Alex Morgan")


def test_colleges_come_from_the_majors():
    assert profile(majors=["computer-science", "accounting"]).colleges() == {"computing", "terry"}
    assert profile(majors=["undecided"]).colleges() == set()


def test_busy_ranges_use_the_profiles_own_week():
    p = profile(week_start="2026-10-26", busy=[{"day": "sun", "start": "09:00", "end": "10:00"}])
    (r,) = p.busy_ranges()
    assert isinstance(r, BusyBlock)
    assert r.start.date() == date(2026, 11, 1) and r.start.utcoffset() == timedelta(hours=-5)


# ---- the sample files in docs/ must stay valid ----


def test_the_documented_sample_request_is_valid():
    path = DOCS / "sample_profile_request.json"
    if not path.exists():
        return  # docs folder not next to backend/ (e.g. tests copied elsewhere)
    p = UserProfile.model_validate_json(path.read_text(encoding="utf-8"))
    assert p.busy_ranges()


def test_the_documented_sample_options_match_the_taxonomy():
    path = DOCS / "sample_options.json"
    if not path.exists():
        return
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == taxonomy.questionnaire_options(), "docs/sample_options.json is out of date: regenerate it"