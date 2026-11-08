"""Try the matcher with made-up students and made-up (already tagged) events.

No AI, no internet, no flyers needed. Run from the backend folder:

    python -m scripts.try_matching

It prints the swipe deck each pretend student would get. Read the decks and ask:
do the first cards look right for this student, and is there variety?

Save this file as: scripts/try_matching.py   (next to scripts/__init__.py)
"""

import sys
from datetime import datetime

from app import taxonomy
from app.matching.pipeline import recommend
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

WEEK = "2026-11-09"  # a Monday; standard time (daylight saving ended Nov 1)
NOW = datetime.fromisoformat("2026-11-08T09:00:00-05:00")


def when(day: int, clock: str) -> str:
    return f"2026-11-{day:02d}T{clock}:00-05:00"


# (id, title, day, start, end or None, tags, colleges)
RAW = [
    ("e01", "AI Club Kickoff", 9, "18:00", "19:30", ["technology-coding:ai"], []),
    ("e02", "Intro to Web Development Workshop", 9, "12:00", None, ["technology-coding:web-development"], []),
    ("e03", "Resume and Career Night", 10, "17:00", "18:30", ["career-leadership"], []),
    ("e04", "Acoustic Open Mic", 10, "19:00", "21:00", ["music:live-music"], []),
    ("e05", "Cybersecurity CTF Practice", 10, "18:00", "19:30", ["technology-coding:cybersecurity"], []),
    ("e06", "Cooking Demo: Quick Dorm Meals", 11, "12:30", "13:30", ["food-cooking"], []),
    ("e07", "Hackathon Info Session", 11, "18:00", "20:00", ["technology-coding:hackathons"], []),
    ("e08", "Intramural Volleyball Sign-up", 11, "18:30", "19:30", ["sports-recreation"], []),
    ("e09", "Startup Pitch Night", 12, "17:30", "19:00", ["business-entrepreneurship:startups"], []),
    ("e10", "Yoga on the Lawn", 12, "18:00", "19:00", ["fitness-wellness"], []),
    ("e11", "Campus Symphony Concert", 12, "19:00", "21:00", ["music:concerts"], []),
    ("e12", "Investing Club: Intro to Stocks", 12, "18:00", "20:00", ["finance-investing:investing"], []),
    ("e13", "Terry Career Fair", 13, "12:00", "13:00", ["career-leadership", "finance-investing"], ["terry"]),
    ("e14", "School of Computing Industry Panel", 13, "14:00", "15:00", ["technology-coding", "career-leadership"], ["computing"]),
    ("e15", "Movie Night on the Quad", 13, "19:00", None, ["film-photography"], []),
    ("e16", "Community Cleanup Day", 14, "10:00", "14:00", ["community-service", "environment-sustainability:cleanup"], []),
    ("e17", "Football Watch Party", 14, "14:00", "17:00", ["spectator-sports"], []),
    ("e18", "Stargazing Night", 14, "19:30", None, ["astronomy-space"], []),
    ("e19", "Python for Beginners", 15, "13:00", "15:00", ["technology-coding:programming"], []),
    ("e20", "Poetry Reading", 15, "16:00", None, ["writing-literature"], []),
    ("e21", "Early Morning Run Club", 9, "09:00", "10:00", ["fitness-wellness"], []),
    ("e22", "Last Week's Game Night", 6, "19:00", None, ["sports-recreation"], []),  # before the planning week
]

STUDENTS = {
    "Alex: CS major, loves AI, music and careers; has class Mon 9-9:50 and Tue 16-20": dict(
        majors=["computer-science"],
        interests=["technology-coding:ai", "music", "career-leadership"],
        busy=[{"day": "mon", "start": "09:00", "end": "09:50"}, {"day": "tue", "start": "16:00", "end": "20:00"}],
    ),
    "Sam: Undecided, into food and wellness, free all week": dict(
        majors=["undecided"],
        interests=["food-cooking", "fitness-wellness"],
        busy=[],
    ),
    "Jordan: Finance major, picks only Tech (a whole category) and Investing": dict(
        majors=["finance"],
        interests=["technology-coding", "finance-investing:investing"],
        busy=[{"day": "wed", "start": "08:00", "end": "11:00"}],
    ),
    "Riley: Music major, picks only Music (watch the filler cards)": dict(
        majors=["music-major"],
        interests=["music"],
        busy=[],
    ),
}


def load_events() -> list[Event]:
    events = []
    for event_id, title, day, start, end, tags, colleges in RAW:
        event = Event(
            id=event_id, title=title, start=when(day, start), end=when(day, end) if end else None,
            interest_tags=tags, relevant_colleges=colleges,
        )
        assert event.interest_tags == tags, f"{event_id} has a tag that is not in the taxonomy"
        events.append(event)
    return events


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    events = load_events()
    titles = {e.id: e.title for e in events}
    print(f"{len(events)} events. Pretend today is {NOW:%a %b %d %Y}.")

    for label, answers in STUDENTS.items():
        profile = UserProfile(week_start=WEEK, **answers)
        rec = recommend(profile, events, NOW)
        print(f"\n=== {label}")
        print(
            f"    left out: {len(rec.out_of_week)} not this week, {len(rec.already_started)} already started, "
            f"{len(rec.busy)} during busy time, "
            f"{rec.not_chosen} left over"
        )
        for number, card in enumerate(rec.deck, start=1):
            s = card.scored
            clash = "  clashes with: " + ", ".join(titles[i] for i in card.conflicts_with) if card.conflicts_with else ""
            print(f"  {number:>2}. {s.event.start:%a %H:%M}  {s.event.title}  [{s.kind} {s.score:g}]")
            print(f"        {s.reason or '-'}{clash}")


if __name__ == "__main__":
    main()