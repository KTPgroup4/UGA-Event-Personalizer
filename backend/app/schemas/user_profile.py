"""The answers a student gives in the questionnaire.

The frontend sends this as JSON in POST /api/schedules. The backend does not
store it: every request carries the full profile.

Save this file as: app/schemas/user_profile.py
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from app import taxonomy
from app.schemas.busy_block import BusyBlock, BusyBlockInput, expand_busy_blocks

MAX_INTERESTS = 40  # generous; stops absurdly large requests
MAX_BUSY_BLOCKS = 100


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. a stray "name" field is rejected

    week_start: date  # the Monday of the week to plan
    majors: list[str]
    interests: list[str]
    busy: list[BusyBlockInput] = []

    @field_validator("week_start")
    @classmethod
    def _must_be_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be a Monday.")
        return value

    @field_validator("majors")
    @classmethod
    def _check_majors(cls, value: list[str]) -> list[str]:
        # Raises a readable error for unknown IDs, too many majors, a lone co-major, etc.
        return taxonomy.check_majors(value)

    @field_validator("interests")
    @classmethod
    def _check_interests(cls, value: list[str]) -> list[str]:
        if len(value) > MAX_INTERESTS:
            raise ValueError(f"Choose at most {MAX_INTERESTS} interests.")
        tidy = [taxonomy.normalize_tag(v) if isinstance(v, str) else v for v in value]
        if not tidy:
            raise ValueError("Choose at least one interest.")
        # When a specialty and its category are both chosen, only the specialty is kept.
        kept = taxonomy.canonical_selection(tidy)
        return [tag for tag in dict.fromkeys(tidy) if tag in kept]  # keep the user's order

    @field_validator("busy")
    @classmethod
    def _limit_busy(cls, value: list[BusyBlockInput]) -> list[BusyBlockInput]:
        if len(value) > MAX_BUSY_BLOCKS:
            raise ValueError(f"At most {MAX_BUSY_BLOCKS} busy blocks.")
        return value

    # ---- what the rest of the backend asks for ----

    def colleges(self) -> set[str]:
        """The colleges the user's majors belong to (empty for Undecided / Other)."""
        return taxonomy.colleges_for_majors(self.majors)

    def busy_ranges(self) -> list[BusyBlock]:
        """The busy blocks as real timezone-aware ranges for this profile's week."""
        return expand_busy_blocks(self.week_start, self.busy)