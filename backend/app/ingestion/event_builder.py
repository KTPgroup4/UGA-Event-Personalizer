"""The weekly job: flyers in, ready-to-match events out.

    flyer text -> skip flyers whose event is over -> find date/time/title (flyer_parser)
               -> AI tags (tagger, only for flyers that became events) -> Event list

Nothing here is per student. The result is saved with app/event_store.py and
every student request reads it.

Save this file as: app/ingestion/event_builder.py
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.ai.llm_client import LLMClient
from app.ingestion import flyer_date_filter
from app.ingestion.flyer_parser import FlyerParser, ReviewItem
from app.schemas.event import Event
from app.schemas.flyer import FlyerText
from app.tagging.tagger import TagInput, Tagger

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    events: list[Event] = field(default_factory=list)
    review: list[ReviewItem] = field(default_factory=list)  # flyers a person needs to fix
    skipped_past: list[str] = field(default_factory=list)  # flyer ids whose event is over
    untagged: dict[str, str] = field(default_factory=dict)  # event id -> why the AI tags are missing
    parser_ai_failed: dict[str, str] = field(default_factory=dict)  # events with fallback title/time


def build_events(
    flyers: list[FlyerText],
    client: LLMClient,
    today: date | None = None,
    use_cache: bool = True,
    parse_cache_path: Path | None = None,
    tag_cache_path: Path | None = None,
    overrides_path: Path | None = None,
) -> BuildResult:
    """Build the week's events. Raises LLMUnavailable if the AI service can't be used at all."""
    today = today or flyer_date_filter.get_today()
    result = BuildResult()

    dates = flyer_date_filter.filter_past_flyers(flyers, today)
    result.skipped_past = [d.flyer.flyer_id for d in dates.dropped]

    # Undated flyers go to the parser too: a hand-typed override can supply the date.
    parser = FlyerParser(client, cache_path=parse_cache_path, overrides_path=overrides_path)
    parsed = parser.parse(dates.kept, today=today, use_cache=use_cache)
    result.review = parsed.review
    result.parser_ai_failed = parsed.ai_failed

    texts = {f.flyer_id: f.text for f in dates.kept}
    tagger = Tagger(client, cache_path=tag_cache_path)
    tagged = tagger.tag([TagInput(e.id, texts.get(e.id, e.description)) for e in parsed.events], use_cache=use_cache)
    result.untagged = dict(tagged.failed)

    for event in parsed.events:
        tags = tagged.tags.get(event.id)
        if tags is not None:
            event = event.model_copy(update={"interest_tags": tags.interest_tags, "relevant_colleges": tags.relevant_colleges})
        result.events.append(event)
    result.events.sort(key=lambda e: (e.start.timestamp(), e.id))
    return result