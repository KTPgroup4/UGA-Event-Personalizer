"""Step two of matching: score every event the student could attend.

An event's score says how well it fits THIS student. It is built from the best
single reason the event fits, not from adding every reason together, so a
student whose major and interests overlap is not counted twice.

The reasons, strongest first (the numbers are the points; change them below):

  interest  10  The event is inside something the student picked. A picked
                specialty needs that exact specialty. A picked category matches
                any event in that category.
  related    5  The student picked a specialty (say Technology / AI) and the
                event is in the same category but not that specialty
                (a hackathon, or an event tagged only "Technology").
  major      3  The student's major lists a specialty the event has.
  major      2  The student's major lists the event's category.
  college    2  The flyer names the student's college (a small nudge, never a filter).

Small extras: an event that matches several different picks gets +1 for each
extra pick (at most +2), so "AI career panel" beats "AI talk" for someone who
picked both AI and Careers.

A college named on a flyer never hides the event: those events are open to
everyone. The college only helps rank an event for students in that college.

Save this file as: app/matching/scorer.py
"""

from dataclasses import dataclass, field

from app import taxonomy
from app.matching.major_interests import major_matches
from app.schemas.event import Event
from app.schemas.user_profile import UserProfile

# ---- points: the one place to tune the ranking ----
INTEREST_POINTS = 10
RELATED_POINTS = 5
MAJOR_SPECIALTY_POINTS = 3
MAJOR_CATEGORY_POINTS = 2
COLLEGE_POINTS = 2
EXTRA_MATCH_POINTS = 1
MAX_EXTRA_MATCHES = 2  # so at most +2 from extra matches

COLLEGE_NAMES = {c["id"]: c["name"] for c in taxonomy.COLLEGES}
MAJOR_NAMES = {m["id"]: m["name"] for m in taxonomy.MAJORS}


@dataclass
class ScoredEvent:
    event: Event
    score: float  # 0 = no connection to this student
    kind: str  # "interest", "related", "major", "college" or "none"
    topic: str  # the interest category this event is "about" for this student (used for variety)
    matched: list[str] = field(default_factory=list)  # IDs that caused the match (interests, majors or colleges)
    reason: str = ""  # one plain sentence the frontend can show


def category_of(tag: str) -> str:
    """The category a tag belongs to (a category is its own category)."""
    return taxonomy.PARENTS.get(tag, tag)


def _join(names: list[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def score_event(event: Event, profile: UserProfile) -> ScoredEvent:
    """Score one event for one student."""
    event_tags = taxonomy.expand_with_parents(event.interest_tags)  # a specialty also counts for its category
    first_tag = event.interest_tags[0] if event.interest_tags else None
    fallback_topic = category_of(first_tag) if first_tag else "other"

    # 1. Something the student picked is inside the event.
    exact = [tag for tag in profile.interests if tag in event_tags]
    if exact:
        extra = min(len(exact) - 1, MAX_EXTRA_MATCHES) * EXTRA_MATCH_POINTS
        names = [taxonomy.LABELS[tag] for tag in exact[:3]]
        word = "interest" if len(names) == 1 else "interests"
        return ScoredEvent(event, INTEREST_POINTS + extra, "interest", category_of(exact[0]), exact,
                           f"Matches your {word} in {_join(names)}")

    # 2. The student picked a specialty and the event is elsewhere in the same category.
    related = [tag for tag in profile.interests if tag in taxonomy.PARENTS and taxonomy.PARENTS[tag] in event_tags]
    if related:
        return ScoredEvent(event, RELATED_POINTS, "related", category_of(related[0]), related,
                           f"In the same area as your interest in {taxonomy.LABELS[related[0]]}")

    # 3. The student's major points at this kind of event.
    by_major = major_matches(event.interest_tags, profile.majors)
    if by_major:
        major = next(iter(by_major))
        hits = by_major[major]
        points = MAJOR_SPECIALTY_POINTS if any(":" in hit for hit in hits) else MAJOR_CATEGORY_POINTS
        return ScoredEvent(event, points, "major", category_of(hits[0]), [major],
                           f"Related to your major, {MAJOR_NAMES.get(major, major)}")

    # 4. The event is aimed at the student's college.
    shared = [c for c in event.relevant_colleges if c in profile.colleges()]
    if shared:
        return ScoredEvent(event, COLLEGE_POINTS, "college", fallback_topic, shared,
                           f"Connected to your college, {COLLEGE_NAMES.get(shared[0], shared[0])}")

    return ScoredEvent(event, 0, "none", fallback_topic, [], "")


def score_events(events: list[Event], profile: UserProfile) -> list[ScoredEvent]:
    """Score every event for one student, best first.

    Ties are broken by the earlier start, then by id, so the same input always
    gives the same order. Nothing is dropped here, including events with score 0.
    """
    scored = [score_event(event, profile) for event in events]
    scored.sort(key=lambda s: (-s.score, s.event.start.timestamp(), s.event.id))
    return scored