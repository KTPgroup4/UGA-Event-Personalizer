"""Print every saved event's title, time, place and description, so you can read them.

Run from the backend folder:

    python -m scripts.show_events

Add --real to hide the demo/fake events.

Save this file as: scripts/show_events.py   (next to scripts/__init__.py)
"""

import argparse
import sys

from app import event_store


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Show the saved events.")
    parser.add_argument("--real", action="store_true", help="only the events built from flyers")
    args = parser.parse_args()

    events = event_store.load_events(include_demo=False if args.real else None)  # None = follow .env
    print(f"{len(events)} events\n")
    for event in events:
        print(f"{event.id}  {event.start:%a %b %d %H:%M}  {event.title}")
        print(f"    where: {event.location or '-'}   by: {event.organizer or '-'}")
        print(f"    about: {event.description or '(no description)'}")
        print(f"    tags:  {', '.join(event.interest_tags) or '-'}\n")


if __name__ == "__main__":
    main()