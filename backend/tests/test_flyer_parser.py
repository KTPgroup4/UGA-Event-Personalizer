"""Tests for turning flyer text into events, using a fake AI.

Save this file as: tests/test_flyer_parser.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import date, datetime, time

import pytest

from app.ai.llm_client import LLMError, LLMUnavailable
from app.ingestion.flyer_parser import FlyerParser, find_times
from app.schemas.flyer import FlyerText

TODAY = date(2026, 11, 8)
AI_KICKOFF = "AI Club Kickoff\nThursday, Nov 12\n6:00 PM - 7:30 PM\nBoyd 328"


class FakeLLM:
    """Answers from `plan` ({flyer id: fields}). script: first replies, in order (str = raw reply, Exception = raise)."""

    def __init__(self, plan=None, script=None, model="fake-model"):
        self.plan, self.script, self.model, self.calls = plan or {}, list(script or []), model, []

    def complete_json(self, prompt, schema):
        self.calls.append((prompt, schema))
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        fields = schema["properties"]["results"]["items"]["properties"]
        defaults = {"title": "", "description": "", "location": "", "organizer": "", "start_time": "none", "end_time": "none"}
        results = [{"id": i, **defaults, **self.plan.get(i, {})} for i in fields["id"]["enum"]]
        return json.dumps({"results": results})


def flyer(flyer_id, text, status="ok"):
    return FlyerText(flyer_id=flyer_id, year=2026, status=status, text=text, read_at=datetime(2026, 11, 1))


def parser(llm, tmp_path, batch_size=5):
    return FlyerParser(llm, batch_size=batch_size, cache_path=tmp_path / "parse_cache.json",
                       overrides_path=tmp_path / "overrides.json")


def times(*pairs):
    return [time(h, m) for h, m in pairs]


# ---- finding times ----


def test_find_times_reads_common_ways_of_writing_a_time():
    assert find_times("starts at 6 PM") == times((18, 0))
    assert find_times("6:30pm sharp") == times((18, 30))
    assert find_times("doors 7 p.m.") == times((19, 0))
    assert find_times("9 AM") == times((9, 0))
    assert find_times("Meet at 18:30") == times((18, 30))
    assert find_times("lunch at noon") == times((12, 0))
    assert find_times("12 AM") == times((0, 0))


def test_find_times_reads_ranges_and_keeps_text_order():
    assert find_times("6-8 PM") == times((18, 0), (20, 0))
    assert find_times("6:30 - 8:00 p.m.") == times((18, 30), (20, 0))
    assert find_times("11-1pm") == times((11, 0), (13, 0))  # 11 AM to 1 PM
    assert find_times("Doors 5:30 PM, show 7 PM, ends 9:15 PM") == times((17, 30), (19, 0), (21, 15))


def test_find_times_ignores_things_that_are_not_times():
    for text in ["Nov 12", "Room 328", "10/28/2026", "Oct 30th!", "13 PM", "Call 706-542-3000", ""]:
        assert find_times(text) == [], text


def test_find_times_does_not_count_a_time_twice():
    assert find_times("6:30 PM and again 6:30 PM, also 18:30") == times((18, 30))


# ---- a normal flyer ----


def test_a_normal_flyer_becomes_an_event(tmp_path):
    plan = {"f1": {"title": "AI Club Kickoff", "location": "Boyd 328", "organizer": "AI Club",
                   "start_time": "18:00", "end_time": "19:30"}}
    outcome = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert outcome.review == []
    event = outcome.events[0]
    assert (event.id, event.title, event.location, event.organizer) == ("f1", "AI Club Kickoff", "Boyd 328", "AI Club")
    assert event.start.isoformat() == "2026-11-12T18:00:00-05:00"
    assert event.end.isoformat() == "2026-11-12T19:30:00-05:00"
    assert event.flyer_id == "f1" and event.interest_tags == []


def test_the_clock_offset_follows_daylight_saving(tmp_path):
    summer = flyer("a", "Cookout Oct 30\n6 PM")  # before the Nov 1 change
    winter = flyer("b", "Cookout Nov 12\n6 PM")
    events = parser(FakeLLM(), tmp_path).parse([summer, winter], date(2026, 10, 1)).events
    assert [e.start.isoformat() for e in events] == ["2026-10-30T18:00:00-04:00", "2026-11-12T18:00:00-05:00"]


def test_the_ai_is_only_asked_about_times_found_in_the_text(tmp_path):
    llm = FakeLLM()
    parser(llm, tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    prompt, schema = llm.calls[0]
    assert "TIMES FOUND: 18:00, 19:30" in prompt
    assert schema["properties"]["results"]["items"]["properties"]["start_time"]["enum"] == ["18:00", "19:30", "none"]


def test_an_invented_time_is_ignored_and_the_first_time_in_the_text_is_used(tmp_path):
    plan = {"f1": {"title": "Kickoff", "start_time": "20:00", "end_time": "23:00"}}
    event = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert event.start.hour == 18 and event.end is None


def test_the_ai_can_choose_a_later_time_as_the_start(tmp_path):
    text = "Concert Nov 13\nDoors 5:30 PM\nShow 7:00 PM"
    plan = {"f1": {"title": "Concert", "start_time": "19:00"}}
    assert parser(FakeLLM(plan), tmp_path).parse([flyer("f1", text)], TODAY).events[0].start.hour == 19


def test_an_end_time_not_after_the_start_is_dropped(tmp_path):
    plan = {"f1": {"title": "X", "start_time": "18:00", "end_time": "17:00"}}
    event = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", "Talk Nov 12 at 5 PM and 6 PM")], TODAY).events[0]
    assert event.end is None


def test_with_several_dates_the_first_one_that_is_not_past_is_used(tmp_path):
    text = "Info session Nov 3 and the final event Nov 20 at 6 PM"
    event = parser(FakeLLM(), tmp_path).parse([flyer("f1", text)], TODAY).events[0]
    assert event.start.date() == date(2026, 11, 20)


def test_a_blank_ai_title_falls_back_to_the_first_line_of_the_flyer(tmp_path):
    event = parser(FakeLLM(), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert event.title == "AI Club Kickoff"


def test_the_ai_writes_a_clean_title_and_description(tmp_path):
    plan = {"f1": {"title": "AI Club Kickoff", "description": "Meet the club and see this semester's projects."}}
    event = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert event.title == "AI Club Kickoff"
    assert event.description == "Meet the club and see this semester's projects."


def test_the_raw_flyer_text_is_never_used_as_the_description(tmp_path):
    event = parser(FakeLLM(), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert event.description == ""
    failed = parser(FakeLLM(script=[LLMError("slow")]), tmp_path / "other").parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert failed.events[0].description == ""


def test_a_long_description_is_cut_short(tmp_path):
    plan = {"f1": {"description": "word " * 200}}
    event = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert len(event.description) <= 300


def test_an_override_can_replace_the_title_and_description(tmp_path):
    (tmp_path / "overrides.json").write_text(json.dumps({"f1": {"title": "Better Title", "description": "Written by hand."}}))
    plan = {"f1": {"title": "Ugly OCR Tittle", "description": "AI wording"}}
    event = parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert (event.title, event.description) == ("Better Title", "Written by hand.")


def test_the_description_is_saved_with_the_answer_so_it_is_only_written_once(tmp_path):
    plan = {"f1": {"title": "Kickoff", "description": "Meet the club."}}
    parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    second = FakeLLM()
    event = parser(second, tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert second.calls == [] and event.description == "Meet the club."


# ---- when the AI doesn't help ----


def test_if_the_ai_fails_the_event_is_still_built_from_the_text(tmp_path):
    outcome = parser(FakeLLM(script=[LLMError("slow")]), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert outcome.events[0].title == "AI Club Kickoff" and outcome.events[0].start.hour == 18
    assert "f1" in outcome.ai_failed


def test_an_unusable_reply_is_treated_like_a_failure(tmp_path):
    outcome = parser(FakeLLM(script=["not json"]), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert len(outcome.events) == 1 and "f1" in outcome.ai_failed


def test_an_unreachable_ai_stops_the_run(tmp_path):
    with pytest.raises(LLMUnavailable):
        parser(FakeLLM(script=[LLMUnavailable("down")]), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)


def test_flyers_are_sent_in_batches(tmp_path):
    flyers = [flyer(f"f{i}", f"Event {i} Nov 12 at 6 PM") for i in range(7)]
    llm = FakeLLM()
    outcome = parser(llm, tmp_path, batch_size=3).parse(flyers, TODAY)
    assert len(llm.calls) == 3 and len(outcome.events) == 7


# ---- needs review ----


def reasons(outcome):
    return {item.flyer_id: item.reason for item in outcome.review}


def test_no_date_means_needs_review(tmp_path):
    outcome = parser(FakeLLM(), tmp_path).parse([flyer("f1", "Halloween Social\n7 PM\nTate Plaza")], TODAY)
    assert outcome.events == [] and "no date" in reasons(outcome)["f1"]


def test_a_date_without_a_time_means_needs_review(tmp_path):
    outcome = parser(FakeLLM(), tmp_path).parse([flyer("f1", "Halloween Social\nOct 30\nTate Plaza")], date(2026, 10, 1))
    assert outcome.events == [] and "no start time" in reasons(outcome)["f1"]


def test_only_past_dates_means_needs_review(tmp_path):
    outcome = parser(FakeLLM(), tmp_path).parse([flyer("f1", "Chess night Oct 12 at 6 PM")], TODAY)
    assert "in the past" in reasons(outcome)["f1"]


def test_unread_flyers_mean_needs_review_and_do_not_reach_the_ai(tmp_path):
    llm = FakeLLM()
    outcome = parser(llm, tmp_path).parse([flyer("f1", "", status="failed"), flyer("f2", "  ", status="ok")], TODAY)
    assert set(reasons(outcome)) == {"f1", "f2"} and llm.calls == []


def test_flyers_with_nothing_to_ask_do_not_cost_an_ai_call(tmp_path):
    llm = FakeLLM()
    parser(llm, tmp_path).parse([flyer("f1", "No date here, 6 PM"), flyer("f2", "Nov 12 but no time")], TODAY)
    assert llm.calls == []


# ---- fixing a flyer by hand ----


def write_overrides(tmp_path, data):
    (tmp_path / "overrides.json").write_text(json.dumps(data))


def test_an_override_can_rescue_a_flyer_with_no_date_or_time(tmp_path):
    write_overrides(tmp_path, {"f1": {"date": "2026-11-14", "start_time": "18:00", "end_time": "19:30",
                                      "title": "Halloween Social", "location": "Tate Plaza"}})
    outcome = parser(FakeLLM(), tmp_path).parse([flyer("f1", "Come dressed up!")], TODAY)
    event = outcome.events[0]
    assert outcome.review == []
    assert (event.title, event.location) == ("Halloween Social", "Tate Plaza")
    assert event.start.isoformat() == "2026-11-14T18:00:00-05:00" and event.end.hour == 19


def test_an_override_replaces_what_was_found(tmp_path):
    write_overrides(tmp_path, {"f1": {"start_time": "19:00"}})
    event = parser(FakeLLM(), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY).events[0]
    assert event.start.hour == 19


def test_an_override_can_rescue_a_flyer_whose_text_could_not_be_read(tmp_path):
    write_overrides(tmp_path, {"f1": {"date": "2026-11-14", "start_time": "18:00", "title": "Mystery Event"}})
    outcome = parser(FakeLLM(), tmp_path).parse([flyer("f1", "", status="failed")], TODAY)
    assert outcome.events[0].title == "Mystery Event"


def test_broken_overrides_give_a_clear_error(tmp_path):
    (tmp_path / "overrides.json").write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        parser(FakeLLM(), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)


# ---- saved answers ----


def test_a_second_run_asks_the_ai_nothing(tmp_path):
    plan = {"f1": {"title": "Kickoff", "start_time": "18:00"}}
    parser(FakeLLM(plan), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    second = FakeLLM(plan)
    outcome = parser(second, tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert second.calls == [] and outcome.from_cache == 1 and outcome.events[0].title == "Kickoff"


def test_saved_answers_do_not_freeze_the_date_choice(tmp_path):
    text = "Info session Nov 3 and the final event Nov 20 at 6 PM"
    parser(FakeLLM(), tmp_path).parse([flyer("f1", text)], date(2026, 11, 1))
    event = parser(FakeLLM(), tmp_path).parse([flyer("f1", text)], date(2026, 11, 8)).events[0]
    assert event.start.date() == date(2026, 11, 20)  # Nov 3 had passed by the second run


def test_a_different_model_asks_again(tmp_path):
    parser(FakeLLM(model="m1"), tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    other = FakeLLM(model="m2")
    parser(other, tmp_path).parse([flyer("f1", AI_KICKOFF)], TODAY)
    assert len(other.calls) == 1