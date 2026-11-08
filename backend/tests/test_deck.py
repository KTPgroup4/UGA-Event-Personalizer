"""Tests for choosing and ordering the events a student swipes through.

Save this file as: tests/test_deck.py
Run from the backend folder with:  python -m pytest
"""

from datetime import datetime, timedelta

from app.matching.deck import DECAY, DEFAULT_DECK_SIZE, FILLER_REASON, MIN_DECK_SIZE, build_deck, topic_cap
from app.matching.scorer import score_events
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

BASE = datetime.fromisoformat("2026-11-09T08:00:00-05:00")


def student(interests, majors=("undecided",)):
    return UserProfile(week_start="2026-11-09", majors=list(majors), interests=list(interests))


def events_of(tag, count, prefix=None, first_hour=0):
    """`count` one-hour events about `tag`, two hours apart so none overlap."""
    prefix = prefix or tag.split(":")[0]
    return [
        Event(id=f"{prefix}-{i}", title=f"{prefix} {i}", start=BASE + timedelta(hours=first_hour + 2 * i),
              interest_tags=[tag] if tag else [])
        for i in range(count)
    ]


def deck_for(profile, events, **kwargs):
    return build_deck(score_events(events, profile), profile, **kwargs)


def topics(cards):
    return [c.scored.topic for c in cards]


# ---- variety ----


def test_a_surplus_in_one_topic_does_not_fill_the_front_of_the_deck():
    profile = student(["technology-coding", "music", "food-cooking"])
    events = events_of("technology-coding", 10) + events_of("music", 3) + events_of("food-cooking", 3)
    cards = deck_for(profile, events)
    assert set(topics(cards[:3])) == {"technology-coding", "music", "food-cooking"}
    assert topics(cards[:5]).count("technology-coding") <= 2


def test_no_topic_takes_more_than_its_share_of_the_deck():
    profile = student(["technology-coding", "music", "food-cooking"])
    events = events_of("technology-coding", 30) + events_of("music", 6) + events_of("food-cooking", 6)
    cards = deck_for(profile, events)
    assert len(cards) == DEFAULT_DECK_SIZE
    assert topics(cards).count("technology-coding") <= topic_cap(profile, DEFAULT_DECK_SIZE)


def test_a_much_better_match_can_still_beat_a_weak_one_from_a_new_topic():
    # Tech is exact (10); music is only "related" to a picked specialty (5).
    # After one tech card, the next tech card is worth 7, still above music's 5.
    profile = student(["technology-coding", "music:guitar"])
    events = events_of("technology-coding", 3) + events_of("music:piano", 3, prefix="piano")
    first_three = topics(deck_for(profile, events)[:3])
    assert first_three == ["technology-coding", "technology-coding", "music"]


def test_the_topic_cap_depends_on_how_many_topics_were_picked():
    assert topic_cap(student(["music"]), 15) == 16
    assert topic_cap(student(["music", "technology-coding"]), 15) == 9
    assert topic_cap(student(["music", "technology-coding", "food-cooking", "dance-performing-arts", "faith-spirituality"]), 15) == 4
    # Two specialties in one category are one topic.
    assert topic_cap(student(["music:guitar", "music:piano"]), 15) == 16
    assert 0 < DECAY < 1


def test_a_student_with_few_topics_can_still_get_a_long_deck():
    cards = deck_for(student(["technology-coding", "music"]), events_of("technology-coding", 20) + events_of("music", 20))
    assert len(cards) == DEFAULT_DECK_SIZE


# ---- the minimum deck ----


def test_the_cap_is_relaxed_to_reach_the_minimum_deck_size():
    profile = student(["technology-coding", "music", "food-cooking", "dance-performing-arts", "faith-spirituality"])
    cards = deck_for(profile, events_of("technology-coding", 20))
    assert len(cards) == MIN_DECK_SIZE  # 4 would be the cap, but a deck that short isn't useful


def test_the_deck_stops_at_the_cap_once_it_is_long_enough():
    cards = deck_for(student(["technology-coding", "music"]), events_of("technology-coding", 20))
    assert len(cards) == topic_cap(student(["technology-coding", "music"]), DEFAULT_DECK_SIZE)
    assert len(cards) >= MIN_DECK_SIZE


def test_unrelated_events_fill_a_thin_deck_and_say_so():
    profile = student(["music"])
    events = events_of("music", 3) + events_of("food-cooking", 12)
    cards = deck_for(profile, events)
    assert len(cards) == MIN_DECK_SIZE
    assert [c.scored.kind for c in cards[:3]] == ["interest"] * 3
    fillers = cards[3:]
    assert all(c.scored.kind == "none" and c.scored.reason == FILLER_REASON for c in fillers)


def test_filler_does_not_change_the_callers_scored_events():
    profile = student(["music"])
    scored = score_events(events_of("food-cooking", 12), profile)
    build_deck(scored, profile)
    assert all(s.reason == "" for s in scored)


def test_unrelated_events_are_never_added_when_there_are_enough_matches():
    profile = student(["music"])
    cards = deck_for(profile, events_of("music", 10) + events_of("food-cooking", 5))
    assert all(c.scored.kind == "interest" for c in cards)


def test_a_small_pool_gives_a_small_deck_and_no_events_gives_none():
    profile = student(["music"])
    assert len(deck_for(profile, events_of("music", 2))) == 2
    assert deck_for(profile, []) == []


def test_the_deck_size_can_be_changed():
    cards = deck_for(student(["music"]), events_of("music", 20), size=5)
    assert len(cards) == 5


# ---- clashes ----


def test_cards_list_the_other_cards_they_clash_with():
    profile = student(["music"])
    a = Event(id="a", title="A", start=BASE, end=BASE + timedelta(hours=2), interest_tags=["music"])
    b = Event(id="b", title="B", start=BASE + timedelta(hours=1), end=BASE + timedelta(hours=3), interest_tags=["music"])
    c = Event(id="c", title="C", start=BASE + timedelta(hours=3), end=BASE + timedelta(hours=4), interest_tags=["music"])
    by_id = {card.scored.event.id: card for card in deck_for(profile, [a, b, c])}
    assert by_id["a"].conflicts_with == ["b"]
    assert by_id["b"].conflicts_with == ["a"]  # b ends at 11:00 exactly when c starts: touching is not a clash
    assert by_id["c"].conflicts_with == []


def test_events_without_an_end_time_clash_using_the_default_length():
    profile = student(["music"])
    a = Event(id="a", title="A", start=BASE, interest_tags=["music"])  # counts as 8:00-9:00
    b = Event(id="b", title="B", start=BASE + timedelta(minutes=30), interest_tags=["music"])
    by_id = {card.scored.event.id: card for card in deck_for(profile, [a, b])}
    assert by_id["a"].conflicts_with == ["b"]


def test_the_same_input_always_gives_the_same_deck():
    profile = student(["technology-coding", "music"])
    events = events_of("technology-coding", 12) + events_of("music", 12)
    first = [c.scored.event.id for c in deck_for(profile, events)]
    second = [c.scored.event.id for c in deck_for(profile, list(events))]
    assert first == second