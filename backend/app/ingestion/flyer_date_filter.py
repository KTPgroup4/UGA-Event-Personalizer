"""Finds the dates printed on flyers and removes flyers whose events already happened.

Save this file as: app/ingestion/flyer_date_filter.py

Two ways to use it:

1. In the pipeline (nothing is deleted, past flyers are just skipped):
       results = read_all_flyers()
       outcome = filter_past_flyers(results)
       outcome.kept        # pass these to the next step

2. From the terminal, to clean old flyers out of data/flyer_manifest.json:
       python -m app.ingestion.flyer_date_filter            (dry run: only shows what it would remove)
       python -m app.ingestion.flyer_date_filter --apply    (really removes them from the manifest)

How a flyer is judged:
    - We look for every date in its text and take the LATEST one.
    - Latest date before today  -> "past"      (removed)
    - Latest date today or later -> "upcoming"  (kept)
    - No date found at all       -> "unknown"   (kept, because we can't be sure)
    A flyer is only removed when we are confident the event is over.

Dates without a year (like "Oct 28") use the year from the manifest, unless the
flyer itself prints a year.
"""

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.ingestion.flyer_reader import MANIFEST_PATH, _resolve, read_all_flyers
from app.schemas.flyer import FlyerText

logger = logging.getLogger(__name__)

TIMEZONE = "America/New_York"  # "today" means today in Georgia, not on the server

# ------------------------------------------------------------ finding dates

_MONTH_NUMBER = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Full names and common short forms: Oct, Oct., October, Sept, Sep ...
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_ORDINAL = r"(?:st|nd|rd|th)?"
_YEAR = r"(?:\s*,?\s*(?P<year>20\d{2})(?!\d))?"

# "Oct 28", "October 28th", "Oct. 28, 2026", "Oct 28-30", "Oct28"
_MONTH_FIRST = re.compile(
    rf"\b(?P<month>{_MONTH})(?![a-z])\.?\s*(?P<day>\d{{1,2}})(?!\d|:){_ORDINAL}\b"
    rf"(?:\s*(?:[-–—]|to\b|through\b|thru\b)\s*"
    rf"(?P<end_day>\d{{1,2}})(?!\d|:|\s*[ap]\.?m\b){_ORDINAL})?"
    rf"{_YEAR}",
    re.IGNORECASE,
)

# "28 October", "28th of Oct", "28 Oct 2026"
_DAY_FIRST = re.compile(
    rf"(?<![\d/:.])(?P<day>\d{{1,2}}){_ORDINAL}\s*(?:of\s+)?(?P<month>{_MONTH})(?![a-z])\.?"
    rf"{_YEAR}",
    re.IGNORECASE,
)

# "10/28", "10/28/26", "10/28/2026"  (US order: month first)
_NUMERIC = re.compile(
    r"(?<![\d/.])(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{4}|\d{2}))?(?![\d/])"
)


def _make_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:  # Feb 30, month 24, and so on
        return None


def _from_month_first(match: re.Match, default_year: int) -> list[date]:
    month = _MONTH_NUMBER[match["month"][:3].lower()]
    year = int(match["year"]) if match["year"] else default_year
    day = int(match["day"])
    found = [_make_date(year, month, day)]
    if match["end_day"] and int(match["end_day"]) >= day:  # "Oct 28-30"
        found.append(_make_date(year, month, int(match["end_day"])))
    return [d for d in found if d]


def _from_day_first(match: re.Match, default_year: int) -> list[date]:
    month = _MONTH_NUMBER[match["month"][:3].lower()]
    year = int(match["year"]) if match["year"] else default_year
    found = _make_date(year, month, int(match["day"]))
    return [found] if found else []


def _from_numeric(match: re.Match, default_year: int) -> list[date]:
    year = default_year
    if match["year"]:
        year = int(match["year"])
        if year < 100:
            year += 2000
        if not 2000 <= year <= 2099:
            return []
    found = _make_date(year, int(match["month"]), int(match["day"]))
    return [found] if found else []


def find_dates(text: str, default_year: int) -> list[date]:
    """Every valid date printed in the text, oldest first.

    Each pattern's matches are blanked out before the next pattern runs, so one
    date is never read twice (for example "Oct 28 Nov 3" is not also "28 Nov").
    """
    found: set[date] = set()
    for pattern, convert in (
        (_MONTH_FIRST, _from_month_first),
        (_DAY_FIRST, _from_day_first),
        (_NUMERIC, _from_numeric),
    ):
        spans = []
        for match in pattern.finditer(text):
            found.update(convert(match, default_year))
            spans.append(match.span())
        for start, end in spans:
            text = text[:start] + " " * (end - start) + text[end:]
    return sorted(found)


# --------------------------------------------------------------- judging


def get_today() -> date:
    """Today's date in Georgia. Falls back to the computer's own date if the
    timezone database is missing (on Windows, install it with: pip install tzdata)."""
    try:
        return datetime.now(ZoneInfo(TIMEZONE)).date()
    except ZoneInfoNotFoundError:
        logger.warning("Timezone data not found (pip install tzdata); using this computer's date")
        return date.today()


def classify(dates: list[date], today: date) -> str:
    """'past', 'upcoming' or 'unknown'. An event happening today is NOT past."""
    if not dates:
        return "unknown"
    return "past" if max(dates) < today else "upcoming"


@dataclass
class DroppedFlyer:
    flyer: FlyerText
    latest_date: date
    dates: list[date]


@dataclass
class FilterResult:
    kept: list[FlyerText] = field(default_factory=list)  # what the next step should use
    dropped: list[DroppedFlyer] = field(default_factory=list)  # events already over
    undated: list[FlyerText] = field(default_factory=list)  # kept, but no date was found

    @property
    def dated(self) -> list[FlyerText]:
        """Kept flyers that DO show a date. Events need a start time, so use this when
        building events; the undated ones need a person to add the date first."""
        undated_ids = {f.flyer_id for f in self.undated}
        return [f for f in self.kept if f.flyer_id not in undated_ids]


def filter_past_flyers(results: list[FlyerText], today: date | None = None) -> FilterResult:
    """Split flyers into the ones to keep and the ones whose events already happened.

    Flyers whose status isn't "ok" (empty or failed) are passed through
    untouched: they have no text to judge, and are handled elsewhere.
    """
    today = today or get_today()
    outcome = FilterResult()

    for flyer in results:
        if flyer.status != "ok":
            outcome.kept.append(flyer)
            continue

        dates = find_dates(flyer.text, flyer.year)
        verdict = classify(dates, today)

        if verdict == "past":
            outcome.dropped.append(DroppedFlyer(flyer, max(dates), dates))
            logger.info("%s: event over (latest date %s), skipping", flyer.flyer_id, max(dates))
            continue

        outcome.kept.append(flyer)
        if verdict == "unknown":
            outcome.undated.append(flyer)
            logger.info("%s: no date found in the text, keeping it", flyer.flyer_id)

    return outcome


# ------------------------------------------------------------ the manifest


def prune_manifest(manifest_path: str, flyer_ids: set[str]) -> int:
    """Remove these flyer_ids from the manifest file. Returns how many were removed.

    The image files in data/flyers are NOT deleted. Git keeps the old manifest,
    so a removal can always be undone.
    """
    path = _resolve(manifest_path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    remaining = [
        item for item in entries
        if not (isinstance(item, dict) and item.get("flyer_id") in flyer_ids)
    ]
    removed = len(entries) - len(remaining)
    if removed:
        temp = path.with_suffix(".tmp")  # write a temp file first so a crash can't damage the manifest
        temp.write_text(json.dumps(remaining, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
    return removed


# ----------------------------------------------------------------- terminal


def _first_line(text: str, width: int = 45) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:width]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find flyers whose events already happened, and optionally remove them from the manifest."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="really remove them from the manifest (without this, nothing is changed)",
    )
    parser.add_argument("--today", help="pretend today is this date, as YYYY-MM-DD (for testing)")
    parser.add_argument("--no-cache", action="store_true", help="re-read every flyer with OCR")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    today = date.fromisoformat(args.today) if args.today else get_today()

    results = read_all_flyers(use_cache=not args.no_cache)
    outcome = filter_past_flyers(results, today)

    print(f"Today: {today.isoformat()}")
    print(f"Flyers read: {len(results)} | still upcoming or unknown: {len(outcome.kept)} "
          f"| already over: {len(outcome.dropped)}")

    if outcome.undated:
        print("\nNo date found (kept, worth a look):")
        for flyer in outcome.undated:
            print(f"  {flyer.flyer_id}  {_first_line(flyer.text)}")

    if not outcome.dropped:
        print("\nNothing to remove.")
        return

    print("\nEvents already over:")
    for item in outcome.dropped:
        dates = ", ".join(d.strftime("%b %d, %Y") for d in item.dates)
        print(f"  {item.flyer.flyer_id}  {_first_line(item.flyer.text)}")
        print(f"      dates found: {dates}")

    count = len(outcome.dropped)
    if not args.apply:
        print(f"\nDry run: nothing was changed. Check the list above, then run again with "
              f"--apply to remove {'this entry' if count == 1 else f'these {count} entries'} "
              f"from the manifest.")
        return

    removed = prune_manifest(MANIFEST_PATH, {d.flyer.flyer_id for d in outcome.dropped})
    print(f"\nRemoved {removed} {'entry' if removed == 1 else 'entries'} from {MANIFEST_PATH}. "
          f"The images in data/flyers were not deleted.")


if __name__ == "__main__":
    main()