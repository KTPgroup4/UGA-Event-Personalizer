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
- `/api/schedules` stores nothing: every request carries the full profile. Accounts (section 3) are
  optional and only remember a student's questionnaire answers so they don't have to retype them.
- Do **not** send names or any personal details to `/api/schedules`. Unknown fields are rejected (422).
- Do not log request bodies on the backend. Never log emails, passwords or tokens.

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

## 3. Accounts

Accounts are optional. A guest uses the whole app without one. An account remembers:

- the student's questionnaire answers (majors, interests, busy times and an optional display name),
  so they come back filled in. The week to plan is **not** saved, because every week is different.
- the student's **calendar**: the UGA events they saved by swiping right, and the events they added
  by hand.

- Sign up and log in use an **email and password**. There is no email verification yet.
- Passwords are stored only as salted scrypt hashes, and session tokens only as SHA-256 hashes.
- Sign up and log in return a **session token** (valid 30 days). The frontend keeps it in
  `localStorage` and sends it on later requests as the header `Authorization: Bearer <token>`.
- Emails are trimmed and lowercased, so `Alex@UGA.edu` and `alex@uga.edu` are the same account.
- Password: 8 to 128 characters.
- Where accounts live: `data/accounts.db` (a local file) unless `DATABASE_URL` is set to a Postgres
  database (see `app/database.py`). The live site must use `DATABASE_URL`, because Render's free plan
  erases local files whenever the server restarts.

The **user** object used below is
`{"email": "alex@uga.edu", "preferences": <preferences or null>, "calendar": <calendar or null>}`
and **preferences** looks like this (`name` may be `""`):

```json
{
  "name": "Alex",
  "majors": ["computer-science"],
  "interests": ["technology-coding:ai", "music"],
  "busy": [{"day": "mon", "start": "09:00", "end": "09:50"}]
}
```

`majors`, `interests` and `busy` follow exactly the same rules as in section 2. `name` is at most 60
characters. Unknown fields (for example `week_start`) are rejected with 422. If the questionnaire
changes later (an interest is renamed), saved answers that no longer fit are returned as `null`
and the student fills the questionnaire in again.

The **calendar** holds two lists. Send the **whole** calendar every time; it replaces the old one
(last save wins). Busy times are not in it: they are saved with the preferences.

```json
{
  "saved": [
    {
      "id": "flyer-101", "title": "AI Club Kickoff", "description": "Meet the club.",
      "start": "2026-11-12T18:00:00-05:00", "end": "2026-11-12T19:00:00-05:00",
      "end_is_estimated": true, "location": "Boyd 328", "organizer": "AI Club",
      "url": null, "interest_tags": ["technology-coding:ai"]
    }
  ],
  "personal": [
    {"id": "9f1c...", "title": "Study group", "date": "2026-11-11", "time": "15:30", "end_time": "16:30"}
  ]
}
```

- `saved[]` is a card from `POST /api/schedules` kept as it was received (`reason`, `match_kind` and
  `conflicts_with` may be included and are ignored). Only `id`, `title` and `start` are required.
  At most 300.
- `personal[]` events: `date` is `YYYY-MM-DD`, `time` and `end_time` are 24-hour `HH:MM`, and
  `end_time` is `""` when there is no end. At most 500. Unknown fields are rejected (422).

| Endpoint | Needs token | Request | Success response |
|---|---|---|---|
| `POST /api/auth/signup` | no | `{"email", "password"}` | `{"token": "...", "user": {...}}` |
| `POST /api/auth/login` | no | `{"email", "password"}` | `{"token": "...", "user": {...}}` |
| `POST /api/auth/logout` | optional | none | `{"ok": true}` (always succeeds) |
| `GET /api/me` | yes | none | `{"user": {...}}` |
| `PUT /api/me/preferences` | yes | preferences (above) | `{"preferences": {...}}` |
| `PUT /api/me/calendar` | yes | calendar (above) | `{"calendar": {...}}` |

Errors always have a readable string in `detail` (except 422 from `PUT /api/me/preferences`, which
uses FastAPI's list format like section 2). Show `detail` to the student as it is.

| Status | When |
|---|---|
| 401 | Wrong email or password (the same message for both, on purpose), or a missing, unknown or expired token. On a 401 from `/api/me` or `/api/me/preferences`, clear the saved token and treat the student as a guest. |
| 409 | Sign up with an email that already has an account. |
| 422 | Not a valid email, or a password that is too short or too long. |
| 429 | Too many wrong passwords for one email in 15 minutes. Wait and try again. |
| 503 | The accounts database can't be reached. Try again in a minute. |

Frontend behavior:

- Sign up is two steps (email, then create a password). Log in is one page with both fields.
- On page load, if a token is saved, call `GET /api/me`. On success, fill the questionnaire from
  `preferences` (if not `null`).
- After a successful "Find my events" while logged in, call `PUT /api/me/preferences`. The result
  doesn't block the deck: if the save fails, the student still sees their events.
- Log out calls `POST /api/auth/logout`, deletes the saved token and clears the questionnaire and calendar.
- Swiping right adds the card to the calendar's `saved` list. It stays there across weeks until the
  student removes it. Any change to the calendar (swipe right, add, remove) is sent with
  `PUT /api/me/calendar` shortly afterwards.
- Busy times are shown on the calendar once, on the next day that matches (today counts). They are
  not stored as events.

---

## 4. Development helpers (temporary)

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
