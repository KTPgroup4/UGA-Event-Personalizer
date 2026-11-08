"""See the swipe deck a pretend student would get from the saved events.

Run `python -m scripts.build_events` first. No AI is called here. Examples
(from the backend folder):

    python -m scripts.try_student --majors computer-science --interests technology-coding:ai,music
    python -m scripts.try_student --majors undecided --interests food-cooking --busy mon:09:00-09:50,tue:16:00-20:00
    python -m scripts.try_student --majors finance --interests finance-investing --week 2026-11-09 --now 2026-11-08T09:00

--week is the Monday to plan (default: the Monday on or after today).
--now pretends it is a different moment (default: right now).

Save this file as: scripts/try_student.py   (next to scripts/__init__.py)
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone

from app import event_store, schedules_service
from app.schemas.user_profile import UserProfile

DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def parse_busy(text: str) -> list[dict]:
    """'mon:09:00-09:50,tue:16:00-20:00' -> a list of busy blocks."""
    blocks = []
    for part in filter(None, (p.strip() for p in text.split(","))):
        try:
            day, rest = part.split(":", 1)
            start, end = rest.split("-", 1)
        except ValueError:
            raise SystemExit(f"Could not read busy block '{part}'. Use day:HH:MM-HH:MM, like mon:09:00-09:50") from None
        blocks.append({"day": day.strip().lower(), "start": start.strip(), "end": end.strip()})
    return blocks


def next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Show the deck for a pretend student.")
    parser.add_argument("--majors", required=True, help="comma-separated major ids, like computer-science")
    parser.add_argument("--interests", required=True, help="comma-separated interest ids, like music,technology-coding:ai")
    parser.add_argument("--busy", default="", help="busy blocks, like mon:09:00-09:50,tue:16:00-20:00")
    parser.add_argument("--week", default="", help="Monday to plan, YYYY-MM-DD")
    parser.add_argument("--now", default="", help="pretend it is this moment, like 2026-11-08T09:00 (campus time)")
    parser.add_argument("--json", action="store_true", help="print the raw API response instead")
    args = parser.parse_args()

    split = lambda text: [p.strip() for p in text.split(",") if p.strip()]  # noqa: E731
    week = args.week or next_monday(date.today()).isoformat()
    try:
        profile = UserProfile(week_start=week, majors=split(args.majors), interests=split(args.interests),
                              busy=parse_busy(args.busy))
    except ValueError as exc:
        raise SystemExit(f"That profile is not valid:\n{exc}") from None
    try:
        events = event_store.load_events()
    except (event_store.NoEventsYet, ValueError) as exc:
        raise SystemExit(str(exc)) from None

    now = None
    if args.now:
        from app.matching.pipeline import CAMPUS_TZ
        now = datetime.fromisoformat(args.now)
        now = now if now.tzinfo else now.replace(tzinfo=CAMPUS_TZ)
    response = schedules_service.build_response(profile, events, now=now or datetime.now(timezone.utc))

    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return
    titles = {e.id: e.title for e in events}
    print(f"{len(events)} saved events. Week of {week}. {len(response['events'])} cards, "
          f"stop after {response['target_picks']} yeses.")
    for number, card in enumerate(response["events"], start=1):
        start = datetime.fromisoformat(card["start"])
        clash = "  clashes with: " + ", ".join(titles.get(i, i) for i in card["conflicts_with"]) if card["conflicts_with"] else ""
        print(f"\n {number:>2}. {start:%a %b %d %H:%M}  {card['title']}  [{card['match_kind']}]")
        print(f"      {card['reason'] or '-'}{clash}")


if __name__ == "__main__":
    main()