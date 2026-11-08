"""Try the AI tagger on your real flyers and look at the answers yourself.

Run from the backend folder (the AI in your .env must be reachable;
check with `python -m scripts.check_ai` first):

    python -m scripts.try_tagging --limit 10

It reads the flyers the same way the flyer reader does (saved text is reused, and
flyers whose text isn't saved yet are read with OCR.space), skips flyers whose
event is already over, and prints what the AI decided for each one.
Look at the answers: do the tags make sense for each flyer?

Save this file as: scripts/try_tagging.py   (and keep an empty scripts/__init__.py next to it)
"""

import argparse
import hashlib
import logging
import sys
import time

from app import taxonomy
from app.ai.llm_client import LLMUnavailable, get_client
from app.ingestion import flyer_date_filter, flyer_reader
from app.tagging.tagger import TagInput, Tagger

COLLEGE_NAMES = {c["id"]: c["name"] for c in taxonomy.COLLEGES}


def first_line(text: str, width: int = 70) -> str:
    line = " ".join(text.split())
    return line if len(line) <= width else line[: width - 3] + "..."


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # flyers contain odd characters

    parser = argparse.ArgumentParser(description="Try the AI tagger on real flyers.")
    parser.add_argument("--limit", type=int, default=10, help="how many flyers to tag (default 10)")
    parser.add_argument("--no-cache", action="store_true", help="ignore saved answers and ask the AI again")
    parser.add_argument(
        "--include-undated",
        action="store_true",
        help="also tag flyers where no date could be found (normally skipped: an event needs a date)",
    )
    parser.add_argument(
        "--include-past",
        action="store_true",
        help="also tag flyers whose event is already over (handy for testing on more flyers)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    results = flyer_reader.read_all_flyers()
    if args.include_past:
        flyers = results
    else:
        outcome_dates = flyer_date_filter.filter_past_flyers(results)
        flyers = outcome_dates.kept if args.include_undated else outcome_dates.dated
        for flyer in outcome_dates.undated:
            if not args.include_undated:
                print(f"Skipping {flyer.flyer_id}: no date found on the flyer (needs a date added by hand).")
    readable = [f for f in flyers if f.status == "ok"]
    items = [TagInput(f.flyer_id, f.text) for f in readable][: args.limit]
    if not items:
        print("No flyers with readable text were found. Run the flyer reader first.")
        return

    client = get_client()
    print(f"Tagging {len(items)} flyers with {type(client).__name__.replace('Client', '')} model '{client.model}'...")
    start = time.time()
    try:
        outcome = Tagger(client).tag(items, use_cache=not args.no_cache)
    except LLMUnavailable as exc:
        print(f"\n{exc}")
        return

    for item in items:
        saved = "saved answer" if item.id in outcome.cached_ids else "asked the AI"
        text_id = hashlib.sha1(" ".join(item.text.split()).encode()).hexdigest()[:8]
        print(f"\n{item.id} [{saved}, text {text_id}]: {first_line(item.text)}")
        if item.id in outcome.failed:
            print(f"  FAILED: {outcome.failed[item.id]}")
            continue
        result = outcome.tags[item.id]
        tags = ", ".join(taxonomy.LABELS[t] for t in result.interest_tags) or "(none)"
        colleges = ", ".join(COLLEGE_NAMES[c] for c in result.relevant_colleges) or "(open to everyone)"
        print(f"  interests: {tags}")
        print(f"  colleges:  {colleges}")

    print(
        f"\nDone in {time.time() - start:.0f} seconds: {len(outcome.tags)} tagged "
        f"({outcome.from_cache} from the saved answers), {len(outcome.failed)} failed."
    )


if __name__ == "__main__":
    main()