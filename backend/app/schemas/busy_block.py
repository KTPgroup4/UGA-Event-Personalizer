"""Busy times: the hours each week when a student can't go to events.

The frontend sends WEEKLY blocks ("every Monday 9:00-9:50"). The matcher needs
REAL date-and-time ranges for one specific week. expand_busy_blocks() makes that
conversion and handles daylight saving time correctly.

Save this file as: app/schemas/busy_block.py
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator

# All UGA events happen in Athens, Georgia.
CAMPUS_TZ = ZoneInfo("America/New_York")

# Monday first, to match week_start (which must be a Monday).
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
Day = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class BusyBlockInput(BaseModel):
    """One weekly busy block, exactly as the frontend sends it.

    Times are plain local clock times like "09:00" (no timezone, no date).
    """

    model_config = ConfigDict(extra="forbid")  # a misspelled field is an error, not ignored

    day: Day
    start: time
    end: time

    @field_serializer("start", "end")
    def _as_hh_mm(self, value: time) -> str:
        # When a saved account is read back, times look the way the frontend sends them: "09:00".
        return value.strftime("%H:%M")

    @model_validator(mode="after")
    def _check_times(self):
        if self.start.tzinfo is not None or self.end.tzinfo is not None:
            raise ValueError("Use plain local times like '09:00', without a timezone.")
        if self.end <= self.start:
            raise ValueError("A busy block must end after it starts (overnight blocks: split them in two).")
        return self


class BusyBlock(BaseModel):
    """One busy block on a real date, with timezones. This is what the matcher uses."""

    start: datetime
    end: datetime


def expand_busy_blocks(week_start: date, blocks: list[BusyBlockInput]) -> list[BusyBlock]:
    """Turn weekly blocks into real time ranges for the week starting on `week_start`.

    - Blocks are sorted by start time.
    - Blocks that overlap or touch are merged into one, so the result is tidy.
    - Times are local Athens time, so "9:00" stays 9:00 on the wall clock even when
      the clocks change that week. (The UTC offset changes; the local time does not.)
    """
    ranges = []
    for block in blocks:
        day = week_start + timedelta(days=DAYS.index(block.day))
        ranges.append(
            BusyBlock(
                start=datetime.combine(day, block.start, tzinfo=CAMPUS_TZ),
                end=datetime.combine(day, block.end, tzinfo=CAMPUS_TZ),
            )
        )
    ranges.sort(key=lambda r: r.start)

    merged: list[BusyBlock] = []
    for current in ranges:
        # Compare in UTC. Python subtracts two datetimes that share one timezone by
        # clock time and ignores daylight saving, so UTC is the safe way to compare.
        if merged and current.start.astimezone(timezone.utc) <= merged[-1].end.astimezone(timezone.utc):
            if current.end.astimezone(timezone.utc) > merged[-1].end.astimezone(timezone.utc):
                merged[-1] = BusyBlock(start=merged[-1].start, end=current.end)
        else:
            merged.append(current)
    return merged
