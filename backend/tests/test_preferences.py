"""Tests for the questionnaire answers a student can save (app/schemas/preferences.py).

Save this file as: tests/test_preferences.py
"""

import pytest
from pydantic import ValidationError

from app.schemas.preferences import MAX_NAME_LENGTH, Preferences, SavedPreferences
from app.schemas.user_profile import UserProfile

BASE = {"majors": ["computer-science"], "interests": ["technology-coding:ai"]}


def test_saved_preferences_follow_the_same_rules_as_the_questionnaire():
    SavedPreferences(**BASE)
    with pytest.raises(ValidationError):
        SavedPreferences(majors=["not-a-major"], interests=["music"])
    with pytest.raises(ValidationError):
        SavedPreferences(majors=["computer-science"], interests=[])
    with pytest.raises(ValidationError):
        SavedPreferences(**BASE, busy=[{"day": "mon", "start": "10:00", "end": "09:00"}])


def test_the_week_is_not_saved():
    with pytest.raises(ValidationError):
        SavedPreferences(**BASE, week_start="2026-11-09")


def test_the_profile_is_the_same_rules_plus_a_week():
    assert issubclass(UserProfile, Preferences)
    profile = UserProfile(**BASE, week_start="2026-11-09")
    assert profile.majors == ["computer-science"]
    with pytest.raises(ValidationError, match="Monday"):
        UserProfile(**BASE, week_start="2026-11-10")


def test_the_name_is_trimmed_and_limited():
    assert SavedPreferences(**BASE, name="  Alex  ").name == "Alex"
    assert SavedPreferences(**BASE).name == ""
    with pytest.raises(ValidationError, match="at most"):
        SavedPreferences(**BASE, name="x" * (MAX_NAME_LENGTH + 1))


def test_busy_times_are_written_as_hh_mm():
    saved = SavedPreferences(**BASE, busy=[{"day": "tue", "start": "16:00", "end": "20:00"}])
    assert saved.model_dump(mode="json")["busy"] == [{"day": "tue", "start": "16:00", "end": "20:00"}]
