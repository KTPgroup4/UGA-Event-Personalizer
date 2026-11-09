"""What an account remembers about a student's calendar.

Two kinds of events:
  - saved events: UGA events the student swiped right on. We keep a copy of each one, because
    the swipe deck changes every week and the event would otherwise be gone.
  - personal events: events the student typed in themselves ("Study group").

The frontend sends the WHOLE calendar every time it changes (PUT /api/me/calendar), and the
backend replaces what it had. Busy times are not part of this: they are saved with the
questionnaire answers (app/schemas/preferences.py).

Save this file as: app/schemas/calendar.py
"""

from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_SAVED_EVENTS = 300
MAX_PERSONAL_EVENTS = 500
CLOCK = r"^([01]\d|2[0-3]):[0-5]\d$"  # 24-hour "HH:MM"


class SavedEvent(BaseModel):
    """A UGA event the student saved. It has the same fields as a card from POST /api/schedules.

    Fields we don't keep (reason, match_kind, conflicts_with) are ignored, not rejected,
    so the frontend can send a card as it received it.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    start: datetime
    end: datetime | None = None
    end_is_estimated: bool = False
    location: str | None = Field(default=None, max_length=300)
    organizer: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=500)
    interest_tags: list[str] = Field(default_factory=list, max_length=40)


class PersonalEvent(BaseModel):
    """An event the student added by hand."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    date: DateType
    time: str = Field(pattern=CLOCK)  # start, like "15:30"
    end_time: str = Field(default="", pattern=r"^(([01]\d|2[0-3]):[0-5]\d)?$")  # "" when there is no end


class SavedCalendar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saved: list[SavedEvent] = Field(default_factory=list, max_length=MAX_SAVED_EVENTS)
    personal: list[PersonalEvent] = Field(default_factory=list, max_length=MAX_PERSONAL_EVENTS)
