"""Tests for the shared tag lists.

Save this file as: tests/test_taxonomy.py
Run from the project root with:  python -m pytest
"""

import json
import re

import pytest

from app import taxonomy

CIVIL = "engineering-making:civil"
VALID_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*(?::[a-z0-9]+(?:-[a-z0-9]+)*)?$")


# ---- the lists themselves ----


def test_every_tag_id_is_unique():
    ids = [c["id"] for c in taxonomy.INTERESTS]
    ids += [child["id"] for c in taxonomy.INTERESTS for child in c["children"]]
    assert len(ids) == len(set(ids))
    assert len(taxonomy.LABELS) == len(ids)


def test_ids_only_use_lowercase_letters_numbers_and_hyphens():
    bad = [tag for tag in taxonomy.LABELS if not VALID_ID.match(tag)]
    assert bad == [], f"IDs with odd characters: {bad}"


def test_every_child_id_starts_with_its_category_id():
    for category in taxonomy.INTERESTS:
        for child in category["children"]:
            assert child["id"].startswith(category["id"] + ":"), child["id"]


def test_every_category_has_at_least_one_child():
    for category in taxonomy.INTERESTS:
        assert category["children"], category["id"]


def test_label_and_parent_counts_add_up():
    assert len(taxonomy.LABELS) == len(taxonomy.INTERESTS) + len(taxonomy.PARENTS)
    assert taxonomy.CATEGORY_IDS == [c["id"] for c in taxonomy.INTERESTS]


def test_display_names_are_written_correctly():
    names = {child["id"]: child["name"] for c in taxonomy.INTERESTS for child in c["children"]}
    assert names["technology-coding:ai"] == "AI"
    assert names["spectator-sports:uga-football"] == "UGA Football"
    assert names["board-games-tabletop-rpgs:rpg"] == "RPG"
    assert names["indigenous-cultures:cherokee-history-and-culture"] == "Cherokee History and Culture"
    assert names["board-games-tabletop-rpgs:dungeons-and-dragons"] == "Dungeons & Dragons"


def test_engineering_specialties_are_the_agreed_list():
    names = [child["name"] for child in taxonomy.children_of("engineering-making")]
    assert names == ["Mechanical", "Electrical", "Computer", "Aerospace", "Civil",
                     "Biomedical", "Environmental", "Robotics", "CAD", "Fabrication"]


def test_event_types_have_no_duplicates():
    assert len(taxonomy.EVENT_TYPES) == len(set(taxonomy.EVENT_TYPES))
    assert "other" in taxonomy.EVENT_TYPES


# ---- colleges and majors ----


def real_majors():
    return [m for c in taxonomy.COLLEGES for m in c["majors"]]


def test_matches_the_august_2026_checklist_counts():
    assert len(taxonomy.COLLEGES) == 16
    assert len(real_majors()) == 143
    assert len(taxonomy.MAJORS) == 143 + 2  # plus Undecided and Other


def test_every_college_has_majors_and_every_id_is_unique_and_clean():
    for college in taxonomy.COLLEGES:
        assert college["majors"], college["id"]
    assert len(taxonomy.COLLEGE_IDS) == len(set(taxonomy.COLLEGE_IDS))
    assert len(taxonomy.MAJOR_IDS) == len(set(taxonomy.MAJOR_IDS))
    for some_id in taxonomy.COLLEGE_IDS + taxonomy.MAJOR_IDS:
        assert VALID_ID.match(some_id) and ":" not in some_id, some_id


def test_college_major_and_interest_ids_never_overlap():
    colleges, majors = set(taxonomy.COLLEGE_IDS), set(taxonomy.MAJOR_IDS)
    interests = set(taxonomy.LABELS)
    assert colleges.isdisjoint(majors)
    assert colleges.isdisjoint(interests)
    assert majors.isdisjoint(interests)


def test_majors_are_sorted_inside_each_college():
    for college in taxonomy.COLLEGES:
        names = [m["name"].lower() for m in college["majors"]]
        assert names == sorted(names), college["id"]


def test_majors_sit_in_the_right_college():
    owner = {m["id"]: c["id"] for c in taxonomy.COLLEGES for m in c["majors"]}
    assert owner["computer-science"] == "computing"
    assert owner["data-science"] == "computing"
    assert owner["accounting"] == "terry"
    assert owner["management-information-systems"] == "terry"
    assert owner["civil-engineering"] == "engineering"
    assert owner["psychology"] == "franklin"
    assert owner["journalism"] == "grady"
    assert owner["ecology"] == "odum"


def test_awkward_names_got_clean_ids_and_display_names():
    names = {m["id"]: m["name"] for m in real_majors()}
    assert names["womens-and-gender-studies"] == "Women's and Gender Studies"
    assert names["art-interdisciplinary-art"] == "Art: Interdisciplinary Art"
    assert names["parks-recreation-and-tourism-management"] == "Parks, Recreation, & Tourism Management"
    assert names["family-and-consumer-sciences-education"] == "Family & Consumer Sciences Education"
    assert names["criminal-justice"] == "Criminal Justice"  # the "(also in Franklin)" note is dropped
    assert names["international-business"] == "International Business (Co-Major)"


def test_every_name_and_id_is_plain_readable_text():
    # Guards against invisible junk characters copied in from a PDF.
    everything = [c["name"] for c in taxonomy.COLLEGES] + [m["name"] for m in taxonomy.MAJORS]
    everything += list(taxonomy.LABELS.values()) + taxonomy.COLLEGE_IDS + taxonomy.MAJOR_IDS
    for text in everything:
        assert all(32 <= ord(ch) < 127 for ch in text), repr(text)
        assert text == text.strip() and "  " not in text, repr(text)


def test_ids_that_would_have_clashed_were_renamed():
    majors = {m["id"]: m["name"] for m in real_majors()}
    assert majors["music-major"] == "Music"        # "music" is an interest category
    assert majors["social-work"] == "Social Work"  # the college is "school-of-social-work"
    assert "school-of-social-work" in taxonomy.COLLEGE_IDS
    assert "music" not in taxonomy.MAJOR_IDS and "music" in taxonomy.CATEGORY_IDS


def test_criminal_justice_belongs_to_two_colleges():
    assert taxonomy.MAJOR_TO_COLLEGES["criminal-justice"] == ["public-and-international-affairs", "franklin"]
    assert taxonomy.MAJOR_TO_COLLEGES["accounting"] == ["terry"]
    assert taxonomy.MAJOR_TO_COLLEGES["undecided"] == []
    assert set(taxonomy.MAJOR_TO_COLLEGES) == set(taxonomy.MAJOR_IDS)


def test_colleges_for_majors():
    assert taxonomy.colleges_for_majors(["computer-science", "accounting"]) == {"computing", "terry"}
    assert taxonomy.colleges_for_majors(["undecided"]) == set()
    assert taxonomy.colleges_for_majors(["criminal-justice"]) == {"public-and-international-affairs", "franklin"}
    assert taxonomy.colleges_for_majors(["not-a-major"]) == set()


# ---- checking the majors a user chose ----


def test_check_majors_accepts_valid_choices_and_tidies_them():
    assert taxonomy.check_majors(["computer-science"]) == ["computer-science"]
    assert taxonomy.check_majors([" Computer-Science ", "computer-science", "accounting"]) == [
        "computer-science", "accounting"]
    assert taxonomy.check_majors(["undecided"]) == ["undecided"]
    assert taxonomy.check_majors(["other"]) == ["other"]


def test_check_majors_rejects_bad_choices():
    cases = [
        ([], "at least one"),
        (["not-a-major"], "Unknown majors"),
        (["computer-science", "accounting", "finance"], "at most 2"),
        (["international-business"], "co-major"),
        (["undecided", "accounting"], "Undecided"),
        ([5], "Unknown majors"),
    ]
    for chosen, message in cases:
        with pytest.raises(ValueError, match=message):
            taxonomy.check_majors(chosen)


def test_a_co_major_is_fine_next_to_another_major():
    assert taxonomy.check_majors(["finance", "international-business"]) == ["finance", "international-business"]


# ---- helpers ----


def test_normalize_tag():
    assert taxonomy.normalize_tag("  Music ") == "music"


def test_keep_valid_drops_made_up_tags_and_repeats():
    answer = ["music:guitar", "Music:Guitar ", "music:kazoo-solo", 5, "music"]
    assert taxonomy.keep_valid(answer, list(taxonomy.LABELS)) == ["music:guitar", "music"]


def test_keep_valid_keeps_the_original_order():
    allowed = ["a", "b", "c"]
    assert taxonomy.keep_valid(["c", "a"], allowed) == ["c", "a"]


def test_children_of_unknown_category_is_empty():
    assert taxonomy.children_of("not-a-category") == []


def test_canonical_selection_drops_a_category_when_its_specialty_is_chosen():
    assert taxonomy.canonical_selection([CIVIL, CIVIL, "engineering-making"]) == {CIVIL}
    assert taxonomy.canonical_selection(["engineering-making"]) == {"engineering-making"}


def test_canonical_selection_rejects_unknown_ids():
    with pytest.raises(ValueError, match="Unknown interests"):
        taxonomy.canonical_selection(["music", "not-real"])


def test_specialty_event_counts_for_its_category_but_not_the_other_way():
    assert "engineering-making" in taxonomy.expand_with_parents([CIVIL])
    assert CIVIL not in taxonomy.expand_with_parents(["engineering-making"])


# ---- text for the AI prompt ----


def test_prompt_categories_lists_every_category_once():
    lines = taxonomy.prompt_categories().split("\n")
    assert len(lines) == len(taxonomy.INTERESTS)
    assert "engineering-making: Engineering & Making" in lines


def test_prompt_children_only_includes_the_chosen_categories():
    text = taxonomy.prompt_children(["engineering-making"])
    assert f"{CIVIL}: Civil" in text
    assert "music:guitar" not in text
    assert len(text.split("\n")) == 10


def test_prompt_children_ignores_unknown_categories():
    assert taxonomy.prompt_children(["nope"]) == ""


def test_prompt_colleges_lists_every_college_once():
    lines = taxonomy.prompt_colleges().split("\n")
    assert len(lines) == 16
    assert "computing: School of Computing" in lines
    assert "terry: Terry College of Business" in lines


def test_two_step_prompt_is_much_smaller_than_sending_every_tag():
    # Compare like with like: both use "id: Name" lines.
    everything = "\n".join(f"{tag}: {name}" for tag, name in taxonomy.LABELS.items())
    two_step = taxonomy.prompt_categories() + "\n" + taxonomy.prompt_children(
        ["engineering-making", "technology-coding", "career-leadership"]
    )
    assert len(two_step) < len(everything) / 5


# ---- for the frontend ----


def test_questionnaire_options_can_be_sent_as_json():
    options = taxonomy.questionnaire_options()
    assert set(options) == {"interests", "colleges", "special_majors", "major_rules"}
    assert len(options["interests"]) == len(taxonomy.INTERESTS)
    assert len(options["colleges"]) == 16
    assert [m["id"] for m in options["special_majors"]] == ["undecided", "other"]
    json.dumps(options)  # raises if anything can't be sent as JSON


def test_the_frontend_is_told_the_major_rules():
    rules = taxonomy.questionnaire_options()["major_rules"]
    assert rules == {"min": 1, "max": 2, "co_major_ids": ["international-business"],
                     "exclusive_ids": ["undecided"]}


def test_changing_the_questionnaire_options_cannot_damage_the_real_lists():
    options = taxonomy.questionnaire_options()
    options["interests"][0]["children"].clear()
    options["colleges"][0]["majors"].clear()
    options["special_majors"].clear()
    options["major_rules"]["co_major_ids"].clear()
    assert taxonomy.INTERESTS[0]["children"]
    assert taxonomy.COLLEGES[0]["majors"]
    assert taxonomy.SPECIAL_MAJORS
    assert taxonomy.CO_MAJOR_IDS