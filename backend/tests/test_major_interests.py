"""Tests for the major-to-interest map.

Save this file as: tests/test_major_interests.py
Run from the backend folder with:  python -m pytest
"""

from app import taxonomy
from app.matching import major_interests
from app.matching.major_interests import MAJOR_INTERESTS, interests_for_majors, major_matches, related_interests


def real_major_ids():
    return [m["id"] for c in taxonomy.COLLEGES for m in c["majors"]]


# ---- the map itself ----


def test_every_major_has_an_entry_and_nothing_extra_is_listed():
    expected = set(taxonomy.MAJOR_IDS)  # all real majors plus Undecided and Other
    assert set(MAJOR_INTERESTS) == expected, (
        f"missing: {sorted(expected - set(MAJOR_INTERESTS))}, unknown: {sorted(set(MAJOR_INTERESTS) - expected)}"
    )


def test_every_interest_id_is_real():
    for major, interests in MAJOR_INTERESTS.items():
        unknown = [i for i in interests if i not in taxonomy.LABELS]
        assert unknown == [], f"{major} lists IDs that are not in the taxonomy: {unknown}"


def test_no_interest_is_listed_twice_for_a_major():
    for major, interests in MAJOR_INTERESTS.items():
        assert len(interests) == len(set(interests)), major


def test_real_majors_have_one_to_four_interests():
    for major in real_major_ids():
        assert 1 <= len(MAJOR_INTERESTS[major]) <= 4, major


def test_undecided_and_other_have_no_related_interests():
    assert MAJOR_INTERESTS["undecided"] == [] and MAJOR_INTERESTS["other"] == []


def test_a_specialty_entry_comes_with_its_category():
    # The category is the baseline match; the specialty only adds precision.
    for major, interests in MAJOR_INTERESTS.items():
        for interest in interests:
            if ":" in interest:
                assert interest.split(":")[0] in interests, f"{major}: {interest} has no category entry"


def test_some_majors_point_where_you_would_expect():
    assert "technology-coding" in MAJOR_INTERESTS["computer-science"]
    assert "engineering-making:civil" in MAJOR_INTERESTS["civil-engineering"]
    assert "finance-investing" in MAJOR_INTERESTS["accounting"]
    assert "music" in MAJOR_INTERESTS["music-major"]
    assert "nature-wildlife:wildlife" in MAJOR_INTERESTS["fisheries-and-wildlife"]
    assert "languages-global-cultures:spanish" in MAJOR_INTERESTS["spanish"]


# ---- looking things up ----


def test_related_interests_returns_a_copy_and_tolerates_unknown_majors():
    assert related_interests("computer-science") == MAJOR_INTERESTS["computer-science"]
    related_interests("computer-science").clear()
    assert MAJOR_INTERESTS["computer-science"]
    assert related_interests("not-a-major") == []
    assert related_interests(" Computer-Science ") == MAJOR_INTERESTS["computer-science"]


def test_interests_for_majors_combines_without_repeats_in_order():
    combined = interests_for_majors(["computer-science", "data-science"])
    assert combined[:3] == MAJOR_INTERESTS["computer-science"]
    assert len(combined) == len(set(combined))
    assert "science-research" in combined and "technology-coding:ai" in combined
    assert interests_for_majors(["undecided"]) == [] and interests_for_majors([]) == []


# ---- matching an event ----


def test_a_specialty_event_matches_the_majors_category():
    # The event is about AI; Computer Science lists the whole Technology & Coding category.
    assert major_matches(["technology-coding:ai"], ["computer-science"]) == {"computer-science": ["technology-coding"]}


def test_a_specialty_event_matches_the_majors_specialty_too():
    hits = major_matches(["engineering-making:civil"], ["civil-engineering"])
    assert hits == {"civil-engineering": ["engineering-making", "engineering-making:civil"]}


def test_a_different_specialty_in_the_same_category_only_matches_the_category():
    hits = major_matches(["engineering-making:civil"], ["mechanical-engineering"])
    assert hits == {"mechanical-engineering": ["engineering-making"]}


def test_a_category_only_event_never_matches_a_specialty():
    hits = major_matches(["engineering-making"], ["civil-engineering"])
    assert hits == {"civil-engineering": ["engineering-making"]}


def test_an_unrelated_event_matches_nothing():
    assert major_matches(["sports-recreation:badminton"], ["computer-science", "accounting"]) == {}


def test_undecided_other_and_unknown_majors_never_match():
    for majors in (["undecided"], ["other"], ["not-a-major"], []):
        assert major_matches(["technology-coding:ai", "music"], majors) == {}


def test_events_without_usable_tags_match_nothing():
    assert major_matches([], ["computer-science"]) == {}
    assert major_matches(["made-up-tag", "technology-coding:made-up"], ["computer-science"]) == {}


def test_two_majors_can_both_match_and_keep_the_users_order():
    hits = major_matches(["technology-coding:ai", "finance-investing:markets"], ["finance", "computer-science"])
    assert list(hits) == ["finance", "computer-science"]
    assert "finance-investing:markets" in hits["finance"]


def test_the_helpers_do_not_import_the_event_schema():
    # Keeps the dependency one-way: schemas may use matching, but not the reverse.
    assert not hasattr(major_interests, "Event")