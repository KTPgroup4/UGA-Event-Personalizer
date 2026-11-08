"""Turns a flyer's text into an Event (title, start, end, location).

The AI is NOT trusted with dates or times. Ordinary code finds the dates and
times printed in the text, and the AI only chooses between them (which time is
the start? which is the end?) and writes the title, location and organizer.
If the AI picks a time that is not on the flyer, or is unavailable, we fall
back to the first time in the text. So the AI can make a title worse, but it
can never invent an hour.

A flyer that has no date, or no start time, becomes a "needs review" item
instead of a guessed event. Someone can fix it by hand in data/flyer_overrides.json:

    {
      "flyer_003": {"date": "2026-10-30", "start_time": "18:00", "end_time": "19:30",
                    "title": "Halloween Social", "location": "Tate Plaza"}
    }

Every field is optional. A field that is given replaces what was found on the flyer.

Save this file as: app/ingestion/flyer_parser.py
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from app.ai.llm_client import LLMClient, LLMError, LLMUnavailable
from app.ingestion import flyer_date_filter
from app.schemas.event import Event
from app.schemas.flyer import FlyerText

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # the backend folder
CACHE_PATH = "data/cache/parse_cache.json"
OVERRIDES_PATH = "data/flyer_overrides.json"
CAMPUS_TZ = ZoneInfo("America/New_York")

PARSER_VERSION = "1"  # change when the prompt changes, so old cached answers are not reused
DEFAULT_BATCH_SIZE = 5
MAX_TEXT_CHARS = 1500
MAX_TITLE_CHARS = 120
MAX_DESCRIPTION_CHARS = 600
NONE = "none"  # what the AI answers when no listed time fits

# ---------------------------------------------------------------- finding times

# "6 PM", "6:30pm", "6-8 PM", "6:30 - 8:00 p.m."
_AMPM = re.compile(
    r"(?<![\d:])(?P<h1>\d{1,2})(?::(?P<m1>\d{2}))?\s*"
    r"(?:(?:[-–—]|to)\s*(?P<h2>\d{1,2})(?::(?P<m2>\d{2}))?\s*)?"
    r"(?P<ap>[ap])\.?\s?m\b\.?",
    re.IGNORECASE,
)
# 24-hour clock with a two-digit hour: "18:30". A bare "6:30" with no AM/PM is ambiguous, so it is ignored.
_CLOCK_24 = re.compile(r"(?<![\d:])(?P<h>[01]\d|2[0-3]):(?P<m>[0-5]\d)(?!\d|\s*[ap]\.?\s?m\b)", re.IGNORECASE)
_NOON = re.compile(r"\bnoon\b", re.IGNORECASE)


def _to_24(hour: int, meridiem: str) -> int:
    return hour % 12 + (12 if meridiem == "p" else 0)


def find_times(text: str) -> list[time]:
    """Every clock time printed in the text, in the order it appears, no repeats."""
    found: list[tuple[int, time]] = []  # (position in text, time)

    taken: list[tuple[int, int]] = []  # parts of the text already read as AM/PM times
    for match in _AMPM.finditer(text):
        taken.append(match.span())
        meridiem = match["ap"].lower()
        first_hour, minute1 = int(match["h1"]), int(match["m1"] or 0)
        if not (1 <= first_hour <= 12 and minute1 < 60):
            continue
        start = _to_24(first_hour, meridiem)
        if match["h2"]:  # a range like "6-8 PM": both ends share the AM/PM
            second_hour, minute2 = int(match["h2"]), int(match["m2"] or 0)
            if not (1 <= second_hour <= 12 and minute2 < 60):
                continue
            end = _to_24(second_hour, meridiem)
            if (start, minute1) >= (end, minute2):  # "11-1 PM" really means 11 AM to 1 PM
                start = _to_24(first_hour, "a" if meridiem == "p" else "p")
            found.append((match.start(), time(start, minute1)))
            found.append((match.start() + 1, time(end, minute2)))
        else:
            found.append((match.start(), time(start, minute1)))

    for match in _CLOCK_24.finditer(text):
        if any(start <= match.start() < end for start, end in taken):
            continue
        found.append((match.start(), time(int(match["h"]), int(match["m"]))))
    for match in _NOON.finditer(text):
        found.append((match.start(), time(12, 0)))

    ordered: list[time] = []
    for _position, value in sorted(found, key=lambda pair: pair[0]):
        if value not in ordered:
            ordered.append(value)
    return ordered


def _hhmm(value: time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _read_hhmm(value) -> time | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", value)
    if not match or int(match[1]) > 23 or int(match[2]) > 59:
        return None
    return time(int(match[1]), int(match[2]))


# ---------------------------------------------------------------- what comes out


@dataclass
class ReviewItem:
    flyer_id: str
    reason: str  # plain words, shown to the person who fixes it


@dataclass
class ParseOutcome:
    events: list[Event] = field(default_factory=list)  # no tags yet; the tagger adds those
    review: list[ReviewItem] = field(default_factory=list)  # flyers that need a person
    from_cache: int = 0  # flyers whose AI answer was already saved
    ai_failed: dict[str, str] = field(default_factory=dict)  # flyer id -> why the AI part failed


def _clean(text: str) -> str:
    return " ".join(text.split())[:MAX_TEXT_CHARS]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            return line[:MAX_TITLE_CHARS]
    return ""


def _choose_date(dates: list[date], today: date) -> date | None:
    """The first date that is today or later. If every date is past, there is no event to show."""
    return next((d for d in sorted(dates) if d >= today), None)


# ---------------------------------------------------------------- the AI part

_PROMPT = """You read University of Georgia campus event flyers and pull out basic details.

For each flyer return:
- title: the name of the event, short, without dates or times
- location: the building, room or address where it happens ("" if the flyer does not say)
- organizer: the group hosting it ("" if the flyer does not say)
- start_time: which of that flyer's TIMES FOUND is when the event starts, or "{none}"
- end_time: which of that flyer's TIMES FOUND is when the event ends, or "{none}"

Use only times from that flyer's own TIMES FOUND list. Never make up a time.

FLYERS:
{flyers}"""


def _schema(ids: list[str], all_times: list[str]) -> dict:
    time_choice = {"type": "string", "enum": [*all_times, NONE]}
    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": ids},
            "title": {"type": "string"},
            "location": {"type": "string"},
            "organizer": {"type": "string"},
            "start_time": time_choice,
            "end_time": time_choice,
        },
        "required": ["id", "title", "location", "organizer", "start_time", "end_time"],
    }
    return {"type": "object", "properties": {"results": {"type": "array", "items": item}}, "required": ["results"]}


def _prompt_for(batch: list[tuple[str, str, list[time]]]) -> str:
    blocks = []
    for flyer_id, text, times in batch:
        listed = ", ".join(_hhmm(t) for t in times) or NONE
        blocks.append(f"[id: {flyer_id}]\nTIMES FOUND: {listed}\n{_clean(text)}\n")
    return _PROMPT.format(none=NONE, flyers="\n".join(blocks))


def _string(value, limit: int) -> str:
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


class FlyerParser:
    def __init__(self, client: LLMClient, batch_size: int = DEFAULT_BATCH_SIZE, cache_path: Path | None = None,
                 overrides_path: Path | None = None):
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.client = client
        self.batch_size = batch_size
        self.cache_path = cache_path or PROJECT_ROOT / CACHE_PATH
        self.overrides_path = overrides_path or PROJECT_ROOT / OVERRIDES_PATH

    # ---- saved answers (only the AI's answer is saved; dates are re-checked every run) ----

    def _key(self, text: str) -> str:
        basis = "|".join([PARSER_VERSION, self.client.model, _clean(text)])
        return hashlib.sha256(basis.encode()).hexdigest()

    def _load_cache(self) -> dict[str, dict]:
        if not self.cache_path.is_file():
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            logger.warning("Parse cache file was unreadable, starting fresh")
            return {}

    def _save_cache(self, cache: dict[str, dict]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(".tmp")
        temp.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        temp.replace(self.cache_path)

    def _load_overrides(self) -> dict[str, dict]:
        if not self.overrides_path.is_file():
            return {}
        try:
            data = json.loads(self.overrides_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.overrides_path.name} is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{self.overrides_path.name} must be an object like {{\"flyer_001\": {{...}}}}")
        return data

    # ---- asking the AI ----

    def _ask(self, batch: list[tuple[str, str, list[time]]]) -> dict[str, dict]:
        ids = [flyer_id for flyer_id, _text, _times in batch]
        all_times = list(dict.fromkeys(_hhmm(t) for _i, _x, times in batch for t in times))
        raw = self.client.complete_json(_prompt_for(batch), _schema(ids, all_times))
        try:
            results = json.loads(raw).get("results")
        except (json.JSONDecodeError, TypeError, AttributeError):
            results = None
        if not isinstance(results, list):
            raise LLMError("the reply was not in the expected format")
        answers: dict[str, dict] = {}
        for item in results:
            if isinstance(item, dict) and item.get("id") in ids and item["id"] not in answers:
                answers[item["id"]] = {
                    "title": _string(item.get("title"), MAX_TITLE_CHARS),
                    "location": _string(item.get("location"), 200),
                    "organizer": _string(item.get("organizer"), 200),
                    "start_time": item.get("start_time") if isinstance(item.get("start_time"), str) else NONE,
                    "end_time": item.get("end_time") if isinstance(item.get("end_time"), str) else NONE,
                }
        return answers

    # ---- the public method ----

    def parse(self, flyers: list[FlyerText], today: date | None = None, use_cache: bool = True) -> ParseOutcome:
        """Turn flyers into events. Raises LLMUnavailable only if the AI service can't be reached at all."""
        today = today or flyer_date_filter.get_today()
        overrides = self._load_overrides()
        outcome = ParseOutcome()
        cache = self._load_cache()

        # Step 1: everything code can find, plus which flyers still need the AI.
        prepared: dict[str, dict] = {}
        for flyer in flyers:
            fix = overrides.get(flyer.flyer_id) or {}
            if flyer.status != "ok" or not flyer.text.strip():
                if not fix:
                    outcome.review.append(ReviewItem(flyer.flyer_id, "the flyer's text could not be read"))
                    continue
            dates = flyer_date_filter.find_dates(flyer.text, flyer.year)
            prepared[flyer.flyer_id] = {
                "flyer": flyer, "fix": fix, "times": find_times(flyer.text),
                "day": _read_date(fix.get("date")) or _choose_date(dates, today),
                "had_dates": bool(dates),
            }

        # Step 2: ask the AI about flyers that have a date and at least one time (and no saved answer).
        answers: dict[str, dict] = {}
        todo: list[tuple[str, str, list[time]]] = []
        for flyer_id, info in prepared.items():
            text = info["flyer"].text
            cached = cache.get(self._key(text)) if use_cache else None
            if cached is not None:
                answers[flyer_id] = cached
                outcome.from_cache += 1
            elif info["day"] is not None and info["times"] and _clean(text):
                todo.append((flyer_id, text, info["times"]))
        for start in range(0, len(todo), self.batch_size):
            batch = todo[start:start + self.batch_size]
            logger.info("Reading details, batch %d of %d", start // self.batch_size + 1,
                        -(-len(todo) // self.batch_size))
            try:
                got = self._ask(batch)
            except LLMUnavailable:
                raise
            except LLMError as exc:
                for flyer_id, _text, _times in batch:
                    outcome.ai_failed[flyer_id] = str(exc)
                continue
            for flyer_id, text, _times in batch:
                if flyer_id in got:
                    answers[flyer_id] = got[flyer_id]
                    cache[self._key(text)] = got[flyer_id]
                else:
                    outcome.ai_failed[flyer_id] = "the model skipped this flyer"
            self._save_cache(cache)

        # Step 3: check everything and build the events.
        for flyer_id, info in prepared.items():
            self._build(flyer_id, info, answers.get(flyer_id), outcome)
        return outcome

    def _build(self, flyer_id: str, info: dict, answer: dict | None, outcome: ParseOutcome) -> None:
        flyer, fix, times = info["flyer"], info["fix"], info["times"]
        day = info["day"]
        if day is None:
            reason = "no date was found on the flyer" if not info["had_dates"] else "every date on the flyer is in the past"
            outcome.review.append(ReviewItem(flyer_id, reason))
            return

        answer = answer or {}
        by_ai = _read_hhmm(answer.get("start_time"))
        start_time = _read_hhmm(fix.get("start_time")) or (by_ai if by_ai in times else None) or (times[0] if times else None)
        if start_time is None:
            outcome.review.append(ReviewItem(flyer_id, "no start time was found on the flyer"))
            return
        end_ai = _read_hhmm(answer.get("end_time"))
        end_time = _read_hhmm(fix.get("end_time")) or (end_ai if end_ai in times else None)
        if end_time is not None and end_time <= start_time:
            end_time = None  # we only handle events that end the same day

        title = _string(fix.get("title"), MAX_TITLE_CHARS) or answer.get("title") or _first_line(flyer.text) or flyer_id
        start = datetime.combine(day, start_time, tzinfo=CAMPUS_TZ)
        end = datetime.combine(day, end_time, tzinfo=CAMPUS_TZ) if end_time else None
        try:
            outcome.events.append(Event(
                id=flyer_id, title=title, description=_clean(flyer.text)[:MAX_DESCRIPTION_CHARS],
                start=start, end=end,
                location=_string(fix.get("location"), 200) or answer.get("location", ""),
                organizer=_string(fix.get("organizer"), 200) or answer.get("organizer", ""),
                flyer_id=flyer_id,
            ))
        except ValueError as exc:
            outcome.review.append(ReviewItem(flyer_id, f"the details did not make a valid event ({exc})"))


def _read_date(value) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None