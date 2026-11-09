"""Make made-up demo events, kept in their own file (data/demo_events.json).

Run from the backend folder:

    python -m scripts.add_fake_events                     write ~29 demo events for the week of Nov 9, 2026
    python -m scripts.add_fake_events --week 2026-11-16   same events, shifted to another Monday
    python -m scripts.add_fake_events --remove            delete the demo file

They are NOT mixed into data/events.json. To use them, add this line to your .env:

    INCLUDE_DEMO_EVENTS=true

Then the API and `try_student` show real events plus the demo ones. Delete that line
(or set it to false) to go back to real flyers only. `build_events` never touches the
demo file, so rebuilding the real events keeps your demo data.

The demo events are already tagged (no AI is called), spread over every day and many odd
times, with about a third in computing. Their ids start with "fake_". Move them to the
week of your demo with --week, because events that have already started are never shown.

Save this file as: scripts/add_fake_events.py   (next to scripts/__init__.py)
"""

import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app import event_store
from app.schemas.event import Event

CAMPUS_TZ = ZoneInfo("America/New_York")
FIRST_MONDAY = date(2026, 11, 9)
PREFIX = "fake_"

# (title, day 0=Mon..6=Sun, start, end or None, interest tags, colleges, location, organizer)
FAKE = [
    # ---- computing ----
    ("Intro to Machine Learning Workshop", 0, "10:15", "11:45", ["technology-coding:ai"], [], "Boyd 302", "AI Club"),
    ("Hackathon Team-Building Mixer", 0, "19:30", "21:00", ["technology-coding:hackathons"], [], "Student Learning Center", "Hack Club"),
    ("Lunch and Learn: AI Ethics", 1, "12:00", "13:00", ["technology-coding:ai"], [], "Boyd 222", "Computing Society"),
    ("Python for Beginners", 1, "13:15", "14:30", ["technology-coding:programming"], [], "Boyd 328", "Code Dawgs"),
    ("Cybersecurity CTF Night", 1, "21:00", "23:00", ["technology-coding:cybersecurity"], [], "Boyd 302", "Security Club"),
    ("Resume Review for Tech Internships", 2, "11:30", "12:30", ["career-leadership:resume-workshops", "technology-coding"], [], "Career Center", "Career Center"),
    ("Web Dev Bootcamp: Build a Portfolio Site", 2, "16:45", "18:45", ["technology-coding:web-development"], [], "Boyd 222", "Code Dawgs"),
    ("Git and GitHub Crash Course", 3, "14:45", "15:45", ["technology-coding:software"], [], "Boyd 328", "Computing Society"),
    ("Computing Industry Mixer", 3, "18:30", "20:00", ["technology-coding", "career-leadership:networking"], ["computing"], "Georgia Center", "School of Computing"),
    ("Data Structures Study Jam", 4, "10:00", "12:00", ["technology-coding:computer-science", "education-mentoring:tutoring"], [], "Main Library, 3rd Floor", "Computing Society"),
    ("Game Dev Showcase", 5, "15:30", None, ["gaming-esports:video-games", "technology-coding:software"], [], "Tate Student Center", "Game Dev Club"),
    ("Robotics Club Build Night", 6, "17:00", "19:30", ["engineering-making:robotics"], [], "Driftmier 1240", "Robotics Club"),
    # ---- everything else, at unusual times ----
    ("Sunrise Yoga", 1, "08:30", "09:15", ["fitness-wellness:yoga"], [], "Memorial Hall Lawn", "Wellness Club"),
    ("Mock Trial Open Practice", 0, "12:30", "13:30", ["law-government-policy:mock-trial"], [], "Law School 105", "Mock Trial Team"),
    ("Pickup Basketball", 0, "17:15", None, ["sports-recreation:basketball"], [], "Ramsey Center", "Intramurals"),
    ("Investing 101", 1, "15:45", "16:45", ["finance-investing:investing"], [], "Correll 222", "Investment Club"),
    ("Pottery Wheel Intro", 2, "14:00", "15:30", ["visual-art-design:pottery"], [], "Lamar Dodd Annex", "Art Club"),
    ("Terry Finance Society Networking", 2, "19:00", "20:30", ["finance-investing:finance", "career-leadership:networking"], ["terry"], "Amos Hall", "Finance Society"),
    ("Improv Comedy Workshop", 2, "20:00", "21:30", ["dance-performing-arts:improv"], [], "Fine Arts Theatre", "Improv Troupe"),
    ("Startup Pitch Practice", 3, "10:30", "11:30", ["business-entrepreneurship:pitch-competitions"], [], "Correll 301", "Entrepreneurship Club"),
    ("Pre-Med Society: MCAT Q and A", 3, "12:15", "13:15", ["healthcare-medicine:pre-med"], [], "Science Library 120", "Pre-Med Society"),
    ("Acoustic Guitar Circle", 4, "15:15", "16:15", ["music:guitar", "music:jam-sessions"], [], "Tate Plaza", "Guitar Club"),
    ("Poetry Slam", 4, "19:30", "21:30", ["writing-literature:poetry"], [], "Ciné", "Creative Writing Club"),
    ("Midnight Movie: Sci-Fi Classics", 4, "23:00", None, ["film-photography:movie-nights"], [], "Tate Theatre", "Film Society"),
    ("Campus Cleanup and Compost", 5, "09:30", "12:00", ["community-service:volunteering", "environment-sustainability:cleanup"], [], "North Campus Quad", "Sustainability Club"),
    ("Intramural Soccer Scrimmage", 5, "11:00", "13:00", ["sports-recreation:soccer"], [], "Intramural Fields", "Intramurals"),
    ("Stargazing at the Observatory", 5, "20:15", None, ["astronomy-space:stargazing"], [], "Physics Building Roof", "Astronomy Club"),
    ("Sunday Brunch Cooking Class", 6, "11:00", "12:30", ["food-cooking:cooking"], [], "Hill Hall Kitchen", "Culinary Club"),
    ("Board Game Night", 6, "14:00", "17:00", ["board-games-tabletop-rpgs"], [], "Tate 4th Floor", "Tabletop Club"),
]

# One or two plain sentences for each fake event, keyed by its title (shown on the swipe card).
DESCRIPTIONS = {
    "Intro to Machine Learning Workshop": "A hands-on beginner workshop on how machine learning models learn from data. No experience needed; bring a laptop.",
    "Hackathon Team-Building Mixer": "Meet other students, pitch ideas and form a team before the next hackathon. Beginners and experienced coders welcome.",
    "Lunch and Learn: AI Ethics": "A casual discussion over lunch about fairness, privacy and responsibility in the AI tools people use every day.",
    "Python for Beginners": "Learn the basics of Python step by step, from variables to your first small program. No coding background required.",
    "Cybersecurity CTF Night": "Solve security puzzles in teams in a friendly capture-the-flag competition. Great practice for beginners and veterans.",
    "Resume Review for Tech Internships": "Get one-on-one feedback on your resume from career advisors, with tips for landing a tech internship.",
    "Web Dev Bootcamp: Build a Portfolio Site": "Build and publish your own portfolio website in one evening using HTML, CSS and a little JavaScript.",
    "Git and GitHub Crash Course": "Learn version control from scratch: commits, branches and pull requests, with practice exercises.",
    "Computing Industry Mixer": "Meet students, alumni and industry guests from the computing world over light refreshments. A good place to start networking.",
    "Data Structures Study Jam": "Work through data structures practice problems with other students and peer tutors. Bring your questions.",
    "Game Dev Showcase": "See games built by UGA students, try them out and chat with the creators about how they were made.",
    "Robotics Club Build Night": "Help build and test the club's robots. All skill levels are welcome, and no experience is needed.",
    "Sunrise Yoga": "Start the day with a gentle outdoor yoga session on the lawn. Beginners welcome; bring a mat if you have one.",
    "Mock Trial Open Practice": "Watch or join a practice round of mock trial and learn how student attorneys prepare and argue a case.",
    "Pickup Basketball": "Casual pickup games open to all skill levels. Show up, join a team and play.",
    "Investing 101": "A beginner-friendly introduction to stocks, funds and how to start investing on a student budget.",
    "Pottery Wheel Intro": "Try the pottery wheel for the first time and make your own small bowl or cup, with instructors guiding you.",
    "Terry Finance Society Networking": "Meet finance students and professionals, practice your introduction and make connections in the industry.",
    "Improv Comedy Workshop": "Play improv games and learn the basics of thinking fast and being funny on stage. No experience needed.",
    "Startup Pitch Practice": "Practice a three-minute startup pitch and get feedback from fellow founders before the next competition.",
    "Pre-Med Society: MCAT Q and A": "Ask upperclassmen and advisors about MCAT prep, study schedules and the pre-med path.",
    "Acoustic Guitar Circle": "Bring a guitar or just a song request. Players of every level trade songs and jam together outdoors.",
    "Poetry Slam": "An open-mic night of original poetry. Sign up to perform or just come listen.",
    "Midnight Movie: Sci-Fi Classics": "A late-night screening of a sci-fi classic for fans and first-timers alike.",
    "Campus Cleanup and Compost": "Join other volunteers to clean up the quad and learn how campus composting works. Gloves and bags are provided.",
    "Intramural Soccer Scrimmage": "A friendly scrimmage open to all skill levels. Teams are mixed on the spot, so you do not need to bring a group.",
    "Stargazing at the Observatory": "Look at planets and stars through the club's telescopes, with members on hand to point out what you are seeing.",
    "Sunday Brunch Cooking Class": "Cook a simple brunch recipe from start to finish with the Culinary Club, then eat what you make.",
    "Board Game Night": "Pick from a big shelf of board games or learn a new one. Beginners and regulars welcome.",
}


def fake_events(week_start: date = FIRST_MONDAY) -> list[Event]:
    """The fake events, moved to the week starting on `week_start` (a Monday)."""
    if week_start.weekday() != 0:
        raise ValueError(f"{week_start} is not a Monday")
    events = []
    for number, (title, day, start, end, tags, colleges, location, organizer) in enumerate(FAKE, start=1):
        base = week_start + timedelta(days=day)

        def at(clock: str) -> datetime:
            hour, minute = clock.split(":")
            return datetime(base.year, base.month, base.day, int(hour), int(minute), tzinfo=CAMPUS_TZ)

        event = Event(
            id=f"{PREFIX}{number:02d}", title=title, description=DESCRIPTIONS[title],
            start=at(start), end=at(end) if end else None,
            location=location, organizer=organizer,
            interest_tags=tags, relevant_colleges=colleges, source="fake",
        )
        assert event.interest_tags == tags, f"{title}: a tag is not in the taxonomy"
        events.append(event)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Write or delete the demo events file.")
    parser.add_argument("--week", default=FIRST_MONDAY.isoformat(), help="Monday to put them in (default 2026-11-09)")
    parser.add_argument("--remove", action="store_true", help="delete the demo events file instead")
    args = parser.parse_args()

    path = event_store.DEMO_EVENTS_PATH
    if args.remove:
        if path.is_file():
            path.unlink()
            print(f"Deleted {path}.")
        else:
            print("There was no demo events file.")
        return

    try:
        events = fake_events(date.fromisoformat(args.week))
    except ValueError as exc:
        raise SystemExit(f"--week must be a Monday like 2026-11-09 ({exc})") from None
    event_store.save_events(events, path=path)
    print(f"Wrote {len(events)} demo events (week of {args.week}) to {path}.")
    if event_store.demo_events_enabled():
        print("INCLUDE_DEMO_EVENTS is on, so the API and try_student will show them.")
    else:
        print("To show them, add INCLUDE_DEMO_EVENTS=true to your .env file.")


if __name__ == "__main__":
    main()