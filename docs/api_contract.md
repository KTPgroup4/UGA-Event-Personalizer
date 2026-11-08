# API contract: frontend <-> backend

This is the agreement between the frontend and backend. If either side needs to
change something here, change this file in a pull request first.

Status: **DRAFT**. The request side is final. The response side has open
decisions, listed at the bottom.

- While developing, the frontend dev server (port 5173) proxies `/api` to the backend on
  **port 3000** (see `vite.config.ts`), so the frontend just calls `/api/...`.
  Start the backend from the `backend` folder with:
  `python -m uvicorn app.main:app --reload --port 3000`
  and try every endpoint at <http://localhost:3000/docs>.
- Everything is JSON.
- The backend stores nothing about users. Every request carries the full profile.
- Do **not** send names or any personal details. Unknown fields are rejected (422).
- Do not log request bodies on the backend.

---

## 1. `GET /api/options`

Returns every choice the questionnaire should show. **The frontend must not hardcode
interests or majors**; it draws the screens from this response. Full real example:
[`sample_options.json`](sample_options.json) (generated from `app/taxonomy.py`, and a
test fails if it drifts out of date).

Shape (shortened):

```json
{
  "interests": [
    {
      "id": "technology-coding",
      "name": "Technology & Coding",
      "children": [
        {"id": "technology-coding:ai", "name": "AI"},
        {"id": "technology-coding:programming", "name": "Programming"}
      ]
    }
  ],
  "colleges": [
    {
      "id": "computing",
      "name": "School of Computing",
      "majors": [{"id": "computer-science", "name": "Computer Science"}]
    }
  ],
  "special_majors": [
    {"id": "undecided", "name": "Undecided"},
    {"id": "other", "name": "Other"}
  ],
  "major_rules": {
    "min": 1,
    "max": 2,
    "co_major_ids": ["international-business"],
    "exclusive_ids": ["undecided"]
  }
}
```

How the frontend uses it:

| Part | What to show |
|---|---|
| `interests` | A category can be chosen on its own ("anything in Music") or narrowed to specialties ("Guitar"). 48 categories and 309 specialties in total, so show categories first and let the user open one to pick specialties. |
| `colleges` | Majors grouped under their college. |
| `special_majors` | "Undecided" and "Other", shown separately from the colleges. |
| `major_rules` | Choose `min` to `max` majors. A `co_major_ids` major can only be chosen together with another major. An `exclusive_ids` major cannot be combined with any other. Enforce these in the UI; the backend checks them again. |

Always send **IDs** (like `computer-science`), never display names.

---

## 2. `POST /api/schedules`

### Request (the profile)

Example file: [`sample_profile_request.json`](sample_profile_request.json)

```json
{
  "week_start": "2026-11-09",
  "majors": ["computer-science"],
  "interests": ["technology-coding:ai", "music", "career-leadership"],
  "busy": [
    {"day": "mon", "start": "09:00", "end": "09:50"},
    {"day": "tue", "start": "16:00", "end": "20:00"}
  ]
}
```

| Field | Rules |
|---|---|
| `week_start` | `YYYY-MM-DD`, must be a **Monday**. This is the week to plan. |
| `majors` | Major IDs from `/api/options`. 1 or 2. See `major_rules`. |
| `interests` | Interest IDs (category or `category:specialty`). 1 to 15 (most students pick 2 to 7). If a specialty and its category are both sent, the category is dropped. |
| `busy` | Optional. Up to 100 weekly blocks the student is NOT free. |
| `busy[].day` | `mon` `tue` `wed` `thu` `fri` `sat` `sun` (lowercase, Sunday included). |
| `busy[].start` / `end` | Local Athens clock time, 24-hour `HH:MM`, no timezone. `end` must be after `start`. A block that runs past midnight must be sent as two blocks. |

The backend turns each recurring block into real date and time ranges for `week_start`'s
week in America/New_York, so a 9:00 class stays 9:00 on the clock when daylight saving
changes. Overlapping or touching blocks are merged.

### Response (200)  **DRAFT (proposed: swipe deck)**

```json
{
  "week_start": "2026-11-09",
  "target_picks": 5,
  "events": [
    {
      "id": "flyer-101",
      "title": "AI Club Kickoff",
      "description": "Meet the club and see what members are building this semester.",
      "start": "2026-11-12T18:00:00-05:00",
      "end": "2026-11-12T19:00:00-05:00",
      "end_is_estimated": true,
      "location": "Boyd 328",
      "organizer": "AI Club",
      "url": null,
      "interest_tags": ["technology-coding:ai"],
      "match_kind": "interest",
      "reason": "Matches your interest in Technology & Coding / AI",
      "conflicts_with": ["flyer-104"]
    }
  ]
}
```

`events` is the **swipe deck**: about 15 events, already in the order to show them.

- **Description.** `description` is one or two short sentences written by the AI from the flyer,
  or `""` when the flyer gave no details. Hide the description area when it is empty.
- **Order and variety.** The backend orders the deck so the first cards cover different
  interests instead of 5 events about one topic. Show the cards in the order given.
- **Clashes.** `conflicts_with` lists the ids of *other cards in this deck* that overlap in time.
  When the student swipes right on a card, hide every card whose id is in its
  `conflicts_with`. They can't attend both. The frontend needs no time maths for this.
- **Stopping.** Stop the swipe step after `target_picks` right swipes, or when the deck runs out.
  Build the calendar from the cards they kept. Nothing needs to go back to the backend.
- **`reason`** is one plain sentence to show on the card. The frontend must not compute its own
  match score or reason.
- **`match_kind`** is why the event is in the deck: `interest` (inside something they picked),
  `related` (same area as a specialty they picked), `major`, `college`, or `none` (a "something
  different" filler, only used when too few events match). Use it for a badge or styling if you like.
- All times are ISO 8601 **with a UTC offset**. The frontend formats them for display (for example
  with `Intl.DateTimeFormat` and `timeZone: "America/New_York"`) and must not parse "Oct 24" style strings.
- `end_is_estimated` is `true` when the flyer showed no end time and a default length was used.
- Events during the student's busy blocks, events that are already over, and events outside the
  week are never in the deck. A college named on a flyer never hides an event: every event is open to everyone.
- If no events exist at all, `events` is an empty list (still a 200).

### Errors

Invalid input returns **422** with FastAPI's standard body:

```json
{"detail": [{"loc": ["body", "majors"], "msg": "Value error, Choose at most 2 majors.", "type": "value_error"}]}
```

`loc` says which field is wrong and `msg` is written to be readable. If the weekly job has not run yet (no saved events), the response is **503** with
`{"detail": "No events yet. Run: python -m scripts.build_events"}`. Other server problems
return **500** with `{"detail": "..."}` and never include the profile.

---

## 3. Development helpers (temporary)

These exist so the frontend has real data to work with before the matcher is built. They are
not part of the final product flow and may be removed.

- `GET /api/health` returns `{"status": "ok"}`.
- `GET /api/flyers` returns the flyers we have:

```json
{
  "count": 1,
  "flyers": [
    {
      "flyer_id": "flyer-101",
      "year": 2026,
      "image_url": "/api/flyer-images/APhA.png",
      "status": "ok",
      "text": "Join us ...",
      "date_status": "upcoming"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `image_url` | Load the picture from this URL (`<img src=...>`). `null` if there is no picture. |
| `status` | `ok` (text was read), `not_read` (picture exists, run `python -m app.ingestion.flyer_reader` to read it), or `missing_image` (listed in the manifest but the file isn't there). |
| `text` | The text read from the flyer. Empty unless `status` is `ok`. |
| `date_status` | `upcoming`, `past` or `unknown`, from the dates printed on the flyer. |

The text comes from a local cache on the machine running the backend, so each person sees
text only for flyers they have read themselves. This endpoint never calls the OCR service.

- `GET /api/flyer-images/<filename>` serves the pictures in `backend/data/flyers/`.

---

## Open decisions (settle before building the response)

1. **Swipe deck or schedule versions?** This draft assumes the **swipe deck** (the current frontend flow),
   so the old `schedules` and `match_percent` fields are gone. If the team prefers showing ready-made
   schedule versions instead, the response gets a `schedules` list back and the swipe step goes away.
2. **Default event length** when a flyer has no end time (proposed: 1 hour, flagged by `end_is_estimated`).
3. **Deck size** (proposed: about 15) and **`target_picks`** (proposed: 5). Both are single numbers on the backend.