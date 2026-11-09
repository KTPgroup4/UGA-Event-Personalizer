"""The answers a student gives in the questionnaire.

The frontend sends this as JSON in POST /api/schedules. The backend does not
store it: every request carries the full profile. (Logged-in students also get their
questionnaire answers remembered by their account: see app/schemas/preferences.py.)

The rules for majors, interests and busy times live in app/schemas/preferences.py. This
file only adds the week to plan, and what the matcher asks for.

Save this file as: app/schemas/user_profile.py
"""

from datetime import date

from pydantic import field_validator

from app import taxonomy
from app.schemas.busy_block import BusyBlock, expand_busy_blocks
from app.schemas.preferences import MAX_BUSY_BLOCKS, MAX_INTERESTS, Preferences  # noqa: F401  (re-exported)


class UserProfile(Preferences):
    week_start: date  # the Monday of the week to plan

    @field_validator("week_start")
    @classmethod
    def _must_be_monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be a Monday.")
        return value

    # ---- what the rest of the backend asks for ----

    def colleges(self) -> set[str]:
        """The colleges the user's majors belong to (empty for Undecided / Other)."""
        return taxonomy.colleges_for_majors(self.majors)

    def busy_ranges(self) -> list[BusyBlock]:
        """The busy blocks as real timezone-aware ranges for this profile's week."""
        return expand_busy_blocks(self.week_start, self.busy)
