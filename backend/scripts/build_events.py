"""The weekly job: read the flyers, turn them into tagged events, save them.

Run from the backend folder (the AI in your .env must be reachable):

    python -m scripts.build_events

It reads the flyers in data/flyer_manifest.json (saved text is reused; flyers not
read yet are read with OCR.space), skips flyers whose event is over, finds each
event's date and time, asks the AI for title and tags, and writes data/events.json.
Student requests only ever read that file, so they never call the AI.

Answers are saved in data/cache/, so running it again costs almost nothing.
Flyers it could not turn into an event are listed under "needs review". Fix one by
adding a line to data/flyer_overrides.json (see app/ingestion/flyer_parser.py).

Save this file as: scripts/build_events.py   (next to scripts/__init__.py)
"""

import argparse
import logging
import sys
import time

from app import event_store, taxonomy
from app.ai.llm_client import LLMUnavailable, get_client
from app.ingestion import flyer_reader
from app.ingestion.event_builder import build_events


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build data/events.json from the flyers.")
    parser.add_argument("--no-cache", action="store_true", help="ignore saved AI answers and ask again")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    flyers = flyer_reader.read_all_flyers()
    client = get_client()
    print(f"Building events from {len(flyers)} flyers with model '{client.model}'...")
    start = time.time()
    try:
        result = build_events(flyers, client, use_cache=not args.no_cache)
    except LLMUnavailable as exc:
        print(f"\n{exc}")
        return

    review = [{"flyer_id": item.flyer_id, "reason": item.reason} for item in result.review]
    path = event_store.save_events(result.events, needs_review=review)

    print(f"\n{len(result.events)} events saved to {path}  ({time.time() - start:.0f} seconds)")
    for event in result.events:
        tags = ", ".join(taxonomy.LABELS[t] for t in event.interest_tags) or "(no tags)"
        end = f"-{event.end:%H:%M}" if event.end else " (no end time)"
        print(f"  {event.start:%a %b %d %H:%M}{end}  {event.title}  [{event.id}]")
        print(f"      {event.location or '(no location)'} | {tags}")

    if result.skipped_past:
        print(f"\nSkipped, event already over: {', '.join(result.skipped_past)}")
    if result.review:
        print("\nNeeds review (not saved as events):")
        for item in result.review:
            print(f"  {item.flyer_id}: {item.reason}")
        print("  Fix one by adding it to data/flyer_overrides.json, then run this again.")
    if result.untagged:
        print(f"\nSaved without tags (the AI failed on them, run again to retry): {', '.join(result.untagged)}")
    if result.parser_ai_failed:
        print(f"\nTitle/time came from the flyer text only (the AI failed): {', '.join(result.parser_ai_failed)}")


if __name__ == "__main__":
    main()