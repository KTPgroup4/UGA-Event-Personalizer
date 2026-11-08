"""The whole per-student pipeline in one function.

    events + profile  ->  drop events outside the planning week or already started
                      ->  drop events that clash with busy blocks
                      ->  drop events limited to other colleges and score the rest
                      ->  build the varied swipe deck

It never talks to the AI or the internet: the events arrive already tagged.

Save this file as: app/matching/pipeline.py
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.matching.availability import filter_free_events
from app.matching.deck import DEFAULT_DECK_SIZE, DeckCard, build_deck
from app.matching.scorer import score_events
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

CAMPUS_TZ = ZoneInfo("America/New_York")


@dataclass
class Recommendation:
    deck: list[DeckCard]
    out_of_week: list[Event] = field(default_factory=list)  # not in the planning week
    already_started: list[Event] = field(default_factory=list)  # began before "now"
    busy: list[Event] = field(default_factory=list)  # clash with a busy block
    other_college: list[Event] = field(default_factory=list)  # limited to other colleges
    not_chosen: int = 0  # scored fine but didn't make the deck


def week_window(profile: UserProfile) -> tuple[datetime, datetime]:
    """Midnight Monday to the next midnight Monday, on campus time."""
    start = datetime(profile.week_start.year, profile.week_start.month, profile.week_start.day, tzinfo=CAMPUS_TZ)
    following = profile.week_start + timedelta(days=7)
    end = datetime(following.year, following.month, following.day, tzinfo=CAMPUS_TZ)
    return start, end


def recommend(
    profile: UserProfile,
    events: list[Event],
    now: datetime | None = None,
    deck_size: int = DEFAULT_DECK_SIZE,
) -> Recommendation:
    """Turn tagged events and one student's profile into their swipe deck."""
    now = now or datetime.now(timezone.utc)
    window_start, window_end = week_window(profile)

    in_week, out_of_week = [], []
    for event in events:
        inside = window_start <= event.start.astimezone(CAMPUS_TZ) < window_end
        (in_week if inside else out_of_week).append(event)

    upcoming, started = [], []
    for event in in_week:
        (started if event.start.astimezone(timezone.utc) <= now.astimezone(timezone.utc) else upcoming).append(event)

    availability = filter_free_events(upcoming, profile.busy_ranges())
    scoring = score_events(availability.free, profile)
    deck = build_deck(scoring.scored, profile, deck_size)

    return Recommendation(
        deck=deck,
        out_of_week=out_of_week,
        already_started=started,
        busy=availability.blocked,
        other_college=scoring.excluded,
        not_chosen=len(scoring.scored) - len(deck),
    )