"""Step three of matching: choose which events to show, in what order.

The student swipes through a "deck" of events. A plain top-N by score would be
boring: if the campus has lots of tech events, someone who picked Tech, Music
and Cooking would see five tech events in a row. So the deck is built one card
at a time, and each card must earn its place:

  * Diminishing returns. Every time a topic (an interest category) is already in
    the deck, new events of that topic are worth 30% less (DECAY). A strong
    tech event still beats a weak music event, but not three times in a row.
  * A fair-share cap. No topic gets more than its share of the deck
    (deck size / number of topics the student picked, plus one spare).
  * A minimum. If sticking to those rules would leave the student with fewer
    than MIN_DECK_SIZE cards, the cap is relaxed, and if that is still not
    enough, events with no connection to them are added (marked "something
    different"), so the student always has something to swipe on.

Why ~15 cards and not 5: the student will say no to many of them, and every
"yes" removes the cards that clash with it. Each card lists the ids it clashes
with (conflicts_with), so the frontend can hide those after a swipe right and
stop at 5 yeses without asking the backend again.

Save this file as: app/matching/deck.py
"""

from collections import Counter
from dataclasses import dataclass, field, replace
from math import ceil

from app.matching.availability import overlaps
from app.matching.scorer import ScoredEvent, category_of
from app.schemas.user_profile import UserProfile

DEFAULT_DECK_SIZE = 15
MIN_DECK_SIZE = 8
DECAY = 0.7  # each earlier card of the same topic multiplies a new card's value by this

FILLER_REASON = "Something different happening on campus"


@dataclass
class DeckCard:
    scored: ScoredEvent
    conflicts_with: list[str] = field(default_factory=list)  # ids of OTHER cards that overlap this one in time


def topic_cap(profile: UserProfile, size: int) -> int:
    """The most cards one topic may take: its fair share of the deck, plus one spare."""
    topics = {category_of(tag) for tag in profile.interests}
    return ceil(size / max(len(topics), 1)) + 1


def _mark_conflicts(chosen: list[ScoredEvent]) -> list[DeckCard]:
    cards = [DeckCard(s) for s in chosen]
    for i, a in enumerate(chosen):
        for j in range(i + 1, len(chosen)):
            b = chosen[j]
            if overlaps(a.event.start, a.event.effective_end(), b.event.start, b.event.effective_end()):
                cards[i].conflicts_with.append(b.event.id)
                cards[j].conflicts_with.append(a.event.id)
    return cards


def build_deck(scored: list[ScoredEvent], profile: UserProfile, size: int = DEFAULT_DECK_SIZE) -> list[DeckCard]:
    """Pick up to `size` events, best first, with variety. `scored` must be best-first."""
    size = max(size, 1)
    remaining = [s for s in scored if s.score > 0]
    unmatched = [s for s in scored if s.score <= 0]
    cap = topic_cap(profile, size)
    per_topic: Counter = Counter()
    chosen: list[ScoredEvent] = []

    def best(allow_over_cap: bool) -> ScoredEvent | None:
        top, top_value = None, 0.0
        for s in remaining:  # already best-first, so on a tie the earlier one stays
            used = per_topic[s.topic]
            if used >= cap and not allow_over_cap:
                continue
            value = s.score * DECAY**used
            if value > top_value:
                top, top_value = s, value
        return top

    while len(chosen) < size and remaining:
        pick = best(allow_over_cap=False)
        if pick is None:
            if len(chosen) >= MIN_DECK_SIZE:
                break  # varied enough and long enough: stop rather than repeat a topic
            pick = best(allow_over_cap=True)
        chosen.append(pick)
        remaining.remove(pick)
        per_topic[pick.topic] += 1

    for filler in unmatched:
        if len(chosen) >= min(MIN_DECK_SIZE, size):
            break
        chosen.append(replace(filler, reason=FILLER_REASON))  # a copy: don't change the caller's object

    return _mark_conflicts(chosen)