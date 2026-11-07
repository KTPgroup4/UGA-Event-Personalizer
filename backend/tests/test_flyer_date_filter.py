"""Tests for the flyer date filter. No OCR and no internet needed.

Save this file as: tests/test_flyer_date_filter.py
Run from the project root with:  python -m pytest
"""

import json
from datetime import date, datetime, timezone

from app.ingestion import flyer_date_filter as fdf
from app.schemas.flyer import FlyerText

TODAY = date(2026, 10, 28)


def make_flyer(text, flyer_id="f1", year=2026, status="ok"):
    return FlyerText(
        flyer_id=flyer_id,
        year=year,
        status=status,
        text=text,
        read_at=datetime.now(timezone.utc),
    )


def check(cases, default_year=2026):
    """Each case is (text, expected list of dates). Shows the text if one is wrong."""
    for text, expected in cases:
        got = fdf.find_dates(text, default_year)
        assert got == expected, f"{text!r}: expected {expected}, got {got}"


# ---- finding dates: formats we should understand ----


def test_month_name_dates():
    check([
        ("Oct 28", [date(2026, 10, 28)]),
        ("OCT 28", [date(2026, 10, 28)]),
        ("October 28th at 7pm", [date(2026, 10, 28)]),
        ("Tuesday, Oct. 28 @ 7:00 PM", [date(2026, 10, 28)]),
        ("Sept 3", [date(2026, 9, 3)]),
        ("SEPT. 3rd", [date(2026, 9, 3)]),
        ("Oct28", [date(2026, 10, 28)]),  # OCR often drops the space
        ("Oct 5\nTate Student Center", [date(2026, 10, 5)]),
    ])


def test_day_first_dates():
    check([
        ("28 October", [date(2026, 10, 28)]),
        ("Tue 28 Oct 7pm", [date(2026, 10, 28)]),
        ("28th of October", [date(2026, 10, 28)]),
    ])


def test_numeric_dates():
    check([
        ("10/28", [date(2026, 10, 28)]),
        ("Join us 10/28 at 7", [date(2026, 10, 28)]),
        ("10/28/26", [date(2026, 10, 28)]),
        ("10/28/2027", [date(2027, 10, 28)]),
    ])


def test_year_printed_on_the_flyer_beats_the_default_year():
    check([
        ("Nov 5, 2027", [date(2027, 11, 5)]),
        ("Nov 5 2027", [date(2027, 11, 5)]),
        ("5 Nov 2027", [date(2027, 11, 5)]),
    ], default_year=2025)


# ---- ranges ----


def test_ranges_include_the_last_day():
    check([
        ("Oct 28-30", [date(2026, 10, 28), date(2026, 10, 30)]),
        ("Oct 28 – 30", [date(2026, 10, 28), date(2026, 10, 30)]),
        ("October 28th to 30th", [date(2026, 10, 28), date(2026, 10, 30)]),
        ("Oct 28 - Nov 2", [date(2026, 10, 28), date(2026, 11, 2)]),
    ])


def test_a_time_after_a_dash_is_not_a_second_date():
    check([
        ("Oct 28 - 7pm", [date(2026, 10, 28)]),
        ("Oct 28 - 7 PM", [date(2026, 10, 28)]),
        ("Oct 28 - 7:00", [date(2026, 10, 28)]),
        ("Oct 28 to 10pm", [date(2026, 10, 28)]),
    ])


# ---- things that look like dates but aren't ----


def test_non_dates_are_ignored():
    check([
        ("Oct 2026", []),                  # a month and a year, no day
        ("Call 706-542-1234", []),         # phone number
        ("Visit the Market 5 times", []),  # "mar" inside a word
        ("You may join us", []),           # the word "may"
        ("Oct 7:30pm", []),                # a time, not a day
        ("24/7 support", []),              # no month 24
        ("2/30", []),                      # Feb 30 doesn't exist
        ("example.com/10/28", []),         # a web address
    ])


def test_one_date_is_not_read_twice():
    # Without the blanking-out step, "28 Nov" would also be read as Nov 28.
    check([("Oct 28 Nov 3", [date(2026, 10, 28), date(2026, 11, 3)])])


def test_duplicates_are_listed_once():
    check([("Oct 28 ... again Oct 28 ... 10/28", [date(2026, 10, 28)])])


# ---- judging past vs upcoming ----


def test_classify():
    assert fdf.classify([], TODAY) == "unknown"
    assert fdf.classify([date(2026, 10, 27)], TODAY) == "past"
    assert fdf.classify([date(2026, 10, 28)], TODAY) == "upcoming"  # today is not past
    assert fdf.classify([date(2026, 11, 1)], TODAY) == "upcoming"


def test_the_latest_date_decides():
    # A deadline in the past must not hide an event that is still ahead.
    flyer = make_flyer("Registration closes Oct 10. Event on Nov 12!")
    outcome = fdf.filter_past_flyers([flyer], TODAY)
    assert [f.flyer_id for f in outcome.kept] == ["f1"]
    assert outcome.dropped == []


def test_filter_splits_past_upcoming_and_undated():
    flyers = [
        make_flyer("Chess Night\nOct 12", flyer_id="past"),
        make_flyer("Startup Panel\nNov 4", flyer_id="future"),
        make_flyer("Weekly meetings every Tuesday!", flyer_id="undated"),
    ]
    outcome = fdf.filter_past_flyers(flyers, TODAY)

    assert [d.flyer.flyer_id for d in outcome.dropped] == ["past"]
    assert outcome.dropped[0].latest_date == date(2026, 10, 12)
    assert [f.flyer_id for f in outcome.kept] == ["future", "undated"]
    assert [f.flyer_id for f in outcome.undated] == ["undated"]


def test_event_today_is_kept_and_event_yesterday_is_dropped():
    flyers = [make_flyer("Oct 28", flyer_id="today"), make_flyer("Oct 27", flyer_id="yesterday")]
    outcome = fdf.filter_past_flyers(flyers, TODAY)
    assert [f.flyer_id for f in outcome.kept] == ["today"]
    assert [d.flyer.flyer_id for d in outcome.dropped] == ["yesterday"]


def test_manifest_year_is_used_when_the_flyer_prints_none():
    old = fdf.filter_past_flyers([make_flyer("Oct 28", year=2025)], TODAY)
    new = fdf.filter_past_flyers([make_flyer("Oct 28", year=2026)], TODAY)
    assert len(old.dropped) == 1
    assert len(new.dropped) == 0


def test_year_printed_on_the_flyer_beats_the_manifest_year():
    outcome = fdf.filter_past_flyers([make_flyer("Oct 28, 2027", year=2025)], TODAY)
    assert outcome.dropped == []


def test_flyers_that_were_not_read_pass_through_untouched():
    flyers = [
        make_flyer("", flyer_id="empty", status="empty"),
        make_flyer("", flyer_id="failed", status="failed"),
    ]
    outcome = fdf.filter_past_flyers(flyers, TODAY)
    assert [f.flyer_id for f in outcome.kept] == ["empty", "failed"]
    assert outcome.dropped == []
    assert outcome.undated == []


# ---- changing the manifest ----


def write_manifest(tmp_path, ids):
    path = tmp_path / "manifest.json"
    entries = [{"flyer_id": i, "path": f"data/flyers/{i}.png", "year": 2026} for i in ids]
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def test_prune_manifest_removes_only_the_chosen_entries(tmp_path):
    path = write_manifest(tmp_path, ["a", "b", "c"])

    removed = fdf.prune_manifest(str(path), {"a", "c"})

    remaining = json.loads(path.read_text(encoding="utf-8"))
    assert removed == 2
    assert [e["flyer_id"] for e in remaining] == ["b"]
    assert remaining[0] == {"flyer_id": "b", "path": "data/flyers/b.png", "year": 2026}


def test_prune_manifest_leaves_the_file_alone_when_nothing_matches(tmp_path):
    path = write_manifest(tmp_path, ["a", "b"])
    before = path.read_text(encoding="utf-8")

    removed = fdf.prune_manifest(str(path), {"zzz"})

    assert removed == 0
    assert path.read_text(encoding="utf-8") == before


def test_pruned_manifest_still_loads_with_the_reader(tmp_path):
    from app.ingestion import flyer_reader

    path = write_manifest(tmp_path, ["a", "b", "c"])
    fdf.prune_manifest(str(path), {"b"})
    entries = flyer_reader.load_manifest(str(path))
    assert [e.flyer_id for e in entries] == ["a", "c"]


# ---- today ----


def test_get_today_returns_a_date():
    assert isinstance(fdf.get_today(), date)