"""Data shapes for the flyer reader.

Save this file as: app/schemas/flyer.py
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class FlyerEntry(BaseModel):
    """One entry from data/flyer_manifest.json (what we type in by hand)."""

    flyer_id: str
    path: str
    year: int

    @field_validator("flyer_id", "path")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("year")
    @classmethod
    def year_is_reasonable(cls, value: int) -> int:
        # Catches typos like 202 or 2062. Next year is allowed because a
        # flyer posted in December can be for a January event.
        this_year = date.today().year
        if not (this_year - 1 <= value <= this_year + 1):
            raise ValueError(
                f"year {value} is not between {this_year - 1} and {this_year + 1}"
            )
        return value


class FlyerText(BaseModel):
    """What the reader returns for one flyer."""

    flyer_id: str
    year: int  # travels with the text so the date parser can use it later
    status: Literal["ok", "empty", "failed"]
    text: str = ""
    image_hash: str = ""
    error: Optional[str] = None
    read_at: datetime