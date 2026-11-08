"""Start to finish: flyer text in, a student's swipe deck out.

Real code all the way (parser, tagger, saving, loading, filtering, scoring, deck,
response). Only two things are pretend: the AI (a fake that answers from a script)
and the OCR step (the flyers arrive as already-read text).

Save this file as: tests/test_end_to_end.py
Run from the backend folder with:  python -m pytest
"""

import json
from datetime import date, datetime

from app import event_store
from app.ingestion.event_builder import build_events
from app.schedules_service import build_response
from app.schemas.flyer import FlyerText
from app.schemas.user_profile import UserProfile

TODAY = date(2026, 11, 8)  # the Sunday before the planning week
NOW = datetime.fromisoformat("2026-11-08T09:00:00-05:00")

FLYERS = {
    "ai-club": "AI Club Kickoff\nThursday, Nov 12\n6:00 PM - 7:30 PM\nBoyd 328",
    "guitar-jam": "Guitar Jam Night\nFriday Nov 13 at 7 PM\nTate Plaza",
    "career-fair": "Terry Career Fair\nFriday, Nov 13\n12:00 PM - 1:00 PM\nTerry College of Business",
    "halloween": "Halloween Social\n7 PM at Tate Plaza\nCome in costume!",  # the OCR lost the date
    "chess": "Chess Night\nOct 12 at 6 PM",  # already over
    "unreadable": "",
}

# What the fake AI "decides" for each flyer.
AI = {
    "ai-club": {"title": "AI Club Kickoff", "location": "Boyd 328", "organizer": "AI Club",
                "start_time": "18:00", "end_time": "19:30",
                "categories": ["technology-coding"], "specialties": ["technology-coding:ai"], "colleges": []},
    "guitar-jam": {"title": "Guitar Jam Night", "location": "Tate Plaza", "start_time": "19:00",
                   "categories": ["music"], "specialties": ["music:guitar"], "colleges": []},
    "career-fair": {"title": "Terry Career Fair", "location": "Terry College", "start_time": "12:00", "end_time": "13:00",
                    "categories": ["career-leadership"], "specialties": [], "colleges": ["terry"]},
}


class FakeAI:
    """Answers the parser's and the tagger's questions from the AI table above."""

    model = "fake-model"

    def __init__(self):
        self.calls = 0

    def complete_json(self, prompt, schema):
        self.calls += 1
        fields = schema["properties"]["results"]["items"]["properties"]
        results = []
        for flyer_id in fields["id"]["enum"]:
            row = {"id": flyer_id}
            for name, spec in fields.items():
                if name == "id":
                    continue
                default = [] if spec.get("type") == "array" else ("none" if "enum" in spec else "")
                row[name] = AI.get(flyer_id, {}).get(name, default)
            results.append(row)
        return json.dumps({"results": results})


def flyer_texts():
    return [FlyerText(flyer_id=i, year=2026, status="ok" if text else "failed", text=text, read_at=datetime(2026, 11, 1))
            for i, text in FLYERS.items()]


def weekly_job(tmp_path, ai=None):
    ai = ai or FakeAI()
    result = build_events(flyer_texts(), ai, today=TODAY,
                          parse_cache_path=tmp_path / "parse.json", tag_cache_path=tmp_path / "tags.json",
                          overrides_path=tmp_path / "overrides.json")
    path = tmp_path / "events.json"
    event_store.save_events(result.events, [{"flyer_id": r.flyer_id, "reason": r.reason} for r in result.review], path)
    return result, path


def student(majors, interests, busy=()):
    return UserProfile(week_start="2026-11-09", majors=majors, interests=interests, busy=list(busy))


def ids(body):
    return [card["id"] for card in body["events"]]


# ---- the weekly job ----


def test_the_weekly_job_sorts_flyers_into_events_review_and_skipped(tmp_path):
    result, _path = weekly_job(tmp_path)
    assert [e.id for e in result.events] == ["ai-club", "career-fair", "guitar-jam"]  # in time order
    assert result.skipped_past == ["chess"]
    assert {r.flyer_id: r.reason for r in result.review}.keys() == {"halloween", "unreadable"}
    ai_club = next(e for e in result.events if e.id == "ai-club")
    assert ai_club.start.isoformat() == "2026-11-12T18:00:00-05:00"
    assert ai_club.interest_tags == ["technology-coding:ai"] and ai_club.relevant_colleges == []


def test_running_the_weekly_job_twice_costs_no_second_round_of_ai_calls(tmp_path):
    first = FakeAI()
    weekly_job(tmp_path, first)
    second = FakeAI()
    weekly_job(tmp_path, second)
    assert first.calls > 0 and second.calls == 0


# ---- a student's request ----


def test_a_cs_student_gets_a_matching_deck(tmp_path):
    _result, path = weekly_job(tmp_path)
    events = event_store.load_events(path)
    body = build_response(student(["computer-science"], ["technology-coding:ai", "music"]), events, now=NOW)
    # The two matches come first. The career fair names Terry College but is open to everyone,
    # so it is still there: it only fills out the short deck, with no match behind it.
    assert ids(body) == ["ai-club", "guitar-jam", "career-fair"]
    assert body["events"][2]["match_kind"] == "none"
    first = body["events"][0]
    assert first["match_kind"] == "interest" and first["reason"] == "Matches your interest in Technology & Coding / AI"
    assert first["start"] == "2026-11-12T18:00:00-05:00" and first["location"] == "Boyd 328"
    assert json.loads(json.dumps(body)) == body


def test_busy_time_removes_the_event_that_clashes(tmp_path):
    _result, path = weekly_job(tmp_path)
    thursday_evening = [{"day": "thu", "start": "17:30", "end": "19:00"}]
    body = build_response(student(["computer-science"], ["technology-coding:ai", "music"], thursday_evening),
                          event_store.load_events(path), now=NOW)
    assert ids(body) == ["guitar-jam", "career-fair"]  # no AI Club (clashes); the fair only fills out the deck


def test_an_undecided_student_gets_the_career_fair_too(tmp_path):
    _result, path = weekly_job(tmp_path)
    body = build_response(student(["undecided"], ["career-leadership"]), event_store.load_events(path), now=NOW)
    assert ids(body)[0] == "career-fair"


def test_a_terry_student_gets_the_terry_fair_ranked_by_their_interest(tmp_path):
    _result, path = weekly_job(tmp_path)
    body = build_response(student(["finance"], ["career-leadership"]), event_store.load_events(path), now=NOW)
    assert "career-fair" in ids(body)


def test_events_that_need_review_never_reach_students(tmp_path):
    _result, path = weekly_job(tmp_path)
    body = build_response(student(["undecided"], ["music"]), event_store.load_events(path), now=NOW)
    assert "halloween" not in ids(body) and "chess" not in ids(body) and "unreadable" not in ids(body)


def test_fixing_a_flyer_by_hand_puts_it_in_the_next_weekly_run(tmp_path):
    (tmp_path / "overrides.json").write_text(json.dumps(
        {"halloween": {"date": "2026-11-14", "start_time": "19:00", "title": "Halloween Social"}}))
    result, path = weekly_job(tmp_path)
    assert "halloween" in [e.id for e in result.events]
    assert "halloween" not in [r.flyer_id for r in result.review]