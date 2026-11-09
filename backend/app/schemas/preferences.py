"""The answers a student gives about themselves: majors, interests and busy times.

Two other models build on this one:
  - UserProfile (app/schemas/user_profile.py) adds `week_start`. It is what the frontend sends
    to POST /api/schedules. The backend does not store it.
  - SavedPreferences (below) adds an optional display name. It is what a logged-in student's
    account remembers, so they don't have to type everything in again.

Keeping the rules in one place means a saved account can never hold something the
questionnaire would have rejected.

Save this file as: app/schemas/preferences.py
"""

from pydantic import BaseModel, ConfigDict, field_validator

from app import taxonomy
from app.schemas.busy_block import BusyBlockInput

MAX_INTERESTS = 15  # students pick about 2-7; this stops absurdly large requests
MAX_BUSY_BLOCKS = 100
MAX_NAME_LENGTH = 60


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. a stray "email" field is rejected

    majors: list[str]
    interests: list[str]
    busy: list[BusyBlockInput] = []

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


class SavedPreferences(Preferences):
    """What an account remembers: the questionnaire answers plus an optional display name.

    There is no week here, because every week is different. The student picks the week
    each time; everything else comes back filled in.
    """

    name: str = ""

    @field_validator("name")
    @classmethod
    def _tidy_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) > MAX_NAME_LENGTH:
            raise ValueError(f"Your name can be at most {MAX_NAME_LENGTH} characters.")
        return value
