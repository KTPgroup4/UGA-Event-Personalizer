"""Builds the JSON that POST /api/schedules returns (see docs/api_contract.md).

Kept separate from the web code so it can be tested without starting a server.

Save this file as: app/schedules_service.py
"""

from datetime import datetime

from app.matching.deck import DEFAULT_DECK_SIZE, DeckCard
from app.matching.pipeline import recommend
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

TARGET_PICKS = 5  # how many events the student is asked to keep


def card_to_json(card: DeckCard) -> dict:
    scored, event = card.scored, card.scored.event
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start": event.start.isoformat(),
        "end": event.effective_end().isoformat(),
        "end_is_estimated": event.end_is_estimated,
        "location": event.location,
        "organizer": event.organizer,
        "url": str(event.url) if event.url else None,
        "interest_tags": event.interest_tags,
        "match_kind": scored.kind,
        "reason": scored.reason,
        "conflicts_with": card.conflicts_with,
    }


def build_response(
    profile: UserProfile,
    events: list[Event],
    now: datetime | None = None,
    deck_size: int = DEFAULT_DECK_SIZE,
) -> dict:
    """The full response body for one student."""
    recommendation = recommend(profile, events, now=now, deck_size=deck_size)
    return {
        "week_start": profile.week_start.isoformat(),
        "target_picks": TARGET_PICKS,
        "events": [card_to_json(card) for card in recommendation.deck],
    }