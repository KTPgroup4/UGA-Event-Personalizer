"""One campus event, in the shape the whole backend shares.

The weekly pipeline fills this in (flyer text -> fields -> AI tags). The matcher
reads it. The tag fields are checked against app/taxonomy.py, so a tag the AI
made up is dropped instead of reaching the matcher.

Save this file as: app/schemas/event.py
"""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator, model_validator

from app import taxonomy

# Most flyers show a start time but no end time. When that happens we assume the
# event lasts this long. Change it in one place if the team picks another length.
DEFAULT_EVENT_MINUTES = 60


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a misspelled field is an error, not ignored

    id: str
    title: str
    description: str = ""
    start: datetime  # must include a timezone, e.g. 2026-11-12T18:00:00-05:00
    end: datetime | None = None  # None = the flyer gave no end time
    location: str = ""
    organizer: str = ""
    url: HttpUrl | None = None
    source: str = "flyer"
    flyer_id: str | None = None  # which flyer this came from, if any

    interest_tags: list[str] = []  # IDs from taxonomy.INTERESTS (categories and/or specialties)
    relevant_colleges: list[str] = []  # IDs from taxonomy.COLLEGES; empty = open to everyone
    event_type: str = "other"  # one of taxonomy.EVENT_TYPES

    # ---- checks ----

    @field_validator("id", "title")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("start", "end")
    @classmethod
    def _needs_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("must include a timezone, e.g. 2026-11-12T18:00:00-05:00")
        return value

    @model_validator(mode="after")
    def _end_after_start(self):
        # Compare as real moments in time (UTC), not as clock times.
        if self.end is not None and self.end.astimezone(timezone.utc) <= self.start.astimezone(timezone.utc):
            raise ValueError("end must be after start")
        return self

    # The AI sometimes invents tags or misspells them. Drop those quietly rather
    # than rejecting the whole event.
    @field_validator("interest_tags", mode="before")
    @classmethod
    def _keep_real_interests(cls, value):
        return taxonomy.keep_valid(value, list(taxonomy.LABELS)) if isinstance(value, list) else value

    @field_validator("relevant_colleges", mode="before")
    @classmethod
    def _keep_real_colleges(cls, value):
        return taxonomy.keep_valid(value, taxonomy.COLLEGE_IDS) if isinstance(value, list) else value

    @field_validator("event_type", mode="before")
    @classmethod
    def _known_event_type(cls, value):
        tidy = taxonomy.normalize_tag(value) if isinstance(value, str) else value
        return tidy if tidy in taxonomy.EVENT_TYPES else "other"

    # ---- helpers the matcher uses ----

    @property
    def end_is_estimated(self) -> bool:
        return self.end is None

    def effective_end(self) -> datetime:
        """The real end time, or start + DEFAULT_EVENT_MINUTES when the flyer had none."""
        if self.end is not None:
            return self.end
        # Add in UTC so a clock change during the event can't shift the answer by an hour.
        as_utc = self.start.astimezone(timezone.utc) + timedelta(minutes=DEFAULT_EVENT_MINUTES)
        return as_utc.astimezone(self.start.tzinfo)