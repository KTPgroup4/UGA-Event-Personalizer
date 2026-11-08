"""Tests for scoring events against a student.

Save this file as: tests/test_scorer.py
Run from the backend folder with:  python -m pytest
"""

from datetime import datetime, timedelta

from app import taxonomy
from app.matching.scorer import (
    COLLEGE_POINTS,
    EXTRA_MATCH_POINTS,
    INTEREST_POINTS,
    MAJOR_CATEGORY_POINTS,
    MAJOR_SPECIALTY_POINTS,
    RELATED_POINTS,
    score_event,
    score_events,
)
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

BASE = datetime.fromisoformat("2026-11-09T08:00:00-05:00")


def student(interests=("music",), majors=("undecided",)):
    return UserProfile(week_start="2026-11-09", majors=list(majors), interests=list(interests))


def event(event_id="e1", tags=(), colleges=(), hours=0):
    return Event(
        id=event_id,
        title=f"Event {event_id}",
        start=BASE + timedelta(hours=hours),
        interest_tags=list(tags),
        relevant_colleges=list(colleges),
    )


# ---- the student's own picks ----


def test_picked_specialty_and_event_with_that_specialty_is_the_top_match():
    s = score_event(event(tags=["technology-coding:ai"]), student(["technology-coding:ai"]))
    assert (s.score, s.kind, s.topic) == (INTEREST_POINTS, "interest", "technology-coding")
    assert s.matched == ["technology-coding:ai"]
    assert s.reason == "Matches your interest in Technology & Coding / AI"


def test_picked_category_matches_every_event_inside_it():
    s = score_event(event(tags=["technology-coding:ai"]), student(["technology-coding"]))
    assert (s.score, s.kind) == (INTEREST_POINTS, "interest")
    s = score_event(event(tags=["technology-coding"]), student(["technology-coding"]))
    assert s.score == INTEREST_POINTS


def test_picked_specialty_and_a_sibling_specialty_event_is_only_related():
    s = score_event(event(tags=["technology-coding:hackathons"]), student(["technology-coding:ai"]))
    assert (s.score, s.kind, s.topic) == (RELATED_POINTS, "related", "technology-coding")
    assert s.reason == "In the same area as your interest in Technology & Coding / AI"


def test_picked_specialty_and_a_category_only_event_is_related_not_exact():
    # The event says "technology" but nothing about AI, so we can't promise it is about AI.
    s = score_event(event(tags=["technology-coding"]), student(["technology-coding:ai"]))
    assert (s.score, s.kind) == (RELATED_POINTS, "related")


def test_an_event_about_something_else_scores_zero():
    s = score_event(event(tags=["music:guitar"]), student(["technology-coding:ai"]))
    assert (s.score, s.kind, s.reason, s.matched) == (0, "none", "", [])


def test_an_untagged_event_scores_zero_with_a_safe_topic():
    s = score_event(event(tags=[]), student(["music"]))
    assert (s.score, s.topic) == (0, "other")


def test_several_matching_picks_add_a_small_capped_bonus():
    two = score_event(event(tags=["technology-coding:ai", "career-leadership"]), student(["technology-coding", "career-leadership"]))
    assert two.score == INTEREST_POINTS + EXTRA_MATCH_POINTS
    assert two.reason == f"Matches your interests in {taxonomy.LABELS['technology-coding']} and {taxonomy.LABELS['career-leadership']}"
    tags = ["technology-coding", "career-leadership", "music", "food-cooking"]
    four = score_event(event(tags=tags), student(tags))
    assert four.score == INTEREST_POINTS + 2 * EXTRA_MATCH_POINTS  # capped at +2


# ---- the major ----


def test_the_major_alone_can_connect_a_student_to_an_event():
    cs = student(["music"], ["computer-science"])
    ai = score_event(event(tags=["technology-coding:ai"]), cs)
    assert (ai.score, ai.kind) == (MAJOR_CATEGORY_POINTS, "major")
    assert ai.reason == "Related to your major, Computer Science"
    programming = score_event(event(tags=["technology-coding:programming"]), cs)
    assert programming.score == MAJOR_SPECIALTY_POINTS
    assert ai.topic == "technology-coding"


def test_overlap_between_picks_and_major_is_not_counted_twice():
    both = student(["technology-coding"], ["computer-science"])
    assert score_event(event(tags=["technology-coding:ai"]), both).score == INTEREST_POINTS
    assert score_event(event(tags=["technology-coding:ai"]), both).kind == "interest"


def test_a_pick_always_beats_the_major():
    assert INTEREST_POINTS > RELATED_POINTS > MAJOR_SPECIALTY_POINTS > MAJOR_CATEGORY_POINTS
    s = student(["technology-coding:ai"], ["computer-science"])
    assert score_event(event(tags=["technology-coding:programming"]), s).kind == "related"


def test_undecided_and_other_get_no_major_boost():
    for major in ("undecided", "other"):
        assert score_event(event(tags=["technology-coding"]), student(["music"], [major])).score == 0


# ---- colleges ----


def test_an_event_for_the_students_college_gets_a_small_boost():
    s = score_event(event(colleges=["computing"]), student(["music"], ["computer-science"]))
    assert (s.score, s.kind) == (COLLEGE_POINTS, "college")
    assert s.reason == "Connected to your college, School of Computing"


def test_a_pick_beats_a_college_match():
    s = score_event(event(tags=["music"], colleges=["computing"]), student(["music"], ["computer-science"]))
    assert s.kind == "interest"


def test_a_college_on_the_flyer_never_hides_the_event():
    # Every event is open to everyone, whatever college the flyer names.
    cs = student(["music"], ["computer-science"])
    events = [event("terry", tags=["music"], colleges=["terry"]), event("open", tags=["music"]),
              event("mine", tags=["music"], colleges=["computing", "terry"])]
    assert {s.event.id for s in score_events(events, cs)} == {"terry", "open", "mine"}


def test_a_college_on_the_flyer_only_matters_to_students_in_that_college():
    terry_only = event("terry", colleges=["terry"])
    assert score_event(terry_only, student(["music"], ["computer-science"])).score == 0  # no match, but not hidden
    assert score_event(terry_only, student(["music"], ["finance"])).score == COLLEGE_POINTS
    assert score_event(terry_only, student(["music"], ["undecided"])).score == 0


# ---- ordering ----


def test_events_come_back_best_first_with_ties_broken_by_time_then_id():
    s = student(["music"], ["undecided"])
    events = [
        event("zero", tags=["food-cooking"], hours=0),
        event("late", tags=["music"], hours=5),
        event("b", tags=["music"], hours=1),
        event("a", tags=["music"], hours=1),
    ]
    order = [x.event.id for x in score_events(events, s)]
    assert order == ["a", "b", "late", "zero"]


def test_scoring_does_not_change_the_events_it_is_given():
    events = [event("e1", tags=["music"])]
    before = events[0].model_dump()
    score_events(events, student(["music"]))
    assert events[0].model_dump() == before