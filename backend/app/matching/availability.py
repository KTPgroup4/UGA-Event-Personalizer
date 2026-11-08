"""Step one of matching: drop events that happen while the student is busy.

An event is dropped if ANY part of it overlaps a busy block. Events that only
touch a busy block (an event that starts exactly when class ends) are kept.

Save this file as: app/matching/availability.py
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.busy_block import BusyBlock
from app.schemas.event import Event


@dataclass
class AvailabilityResult:
    free: list[Event]  # events the student can attend, in the original order
    blocked: list[Event]  # events that clash with a busy block, in the original order


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    """True if the two time ranges share any moment.

    Ranges are half-open: they include their start but not their end, so
    9:00-10:00 and 10:00-11:00 do NOT overlap. Everything is compared in UTC,
    because Python compares two times in the same timezone by clock time and
    that goes wrong around daylight saving changes.
    """
    a0, a1 = start_a.astimezone(timezone.utc), end_a.astimezone(timezone.utc)
    b0, b1 = start_b.astimezone(timezone.utc), end_b.astimezone(timezone.utc)
    return a0 < b1 and b0 < a1


def clashes_with_busy(event: Event, busy: list[BusyBlock]) -> bool:
    """True if the event overlaps any busy block."""
    end = event.effective_end()  # events without an end time count as DEFAULT_EVENT_MINUTES long
    return any(overlaps(event.start, end, block.start, block.end) for block in busy)


def filter_free_events(events: list[Event], busy: list[BusyBlock]) -> AvailabilityResult:
    """Split events into the ones the student can attend and the ones that clash."""
    free: list[Event] = []
    blocked: list[Event] = []
    for event in events:
        (blocked if clashes_with_busy(event, busy) else free).append(event)
    return AvailabilityResult(free=free, blocked=blocked)