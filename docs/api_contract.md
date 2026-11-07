# API contract: frontend <-> backend

This is the agreement between the frontend and backend. If either side needs to
change something here, change this file in a pull request first.

Status: **DRAFT**. The request side is final. The response side has two open
decisions, listed at the bottom.

- Base URL while developing: the frontend dev server proxies `/api` to the backend, so the
  frontend just calls `/api/...` (see `vite.config.ts` for the backend port).
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
| `interests` | Interest IDs (category or `category:specialty`). 1 to 40. If a specialty and its category are both sent, the category is dropped. |
| `busy` | Optional. Up to 100 weekly blocks the student is NOT free. |
| `busy[].day` | `mon` `tue` `wed` `thu` `fri` `sat` `sun` (lowercase, Sunday included). |
| `busy[].start` / `end` | Local Athens clock time, 24-hour `HH:MM`, no timezone. `end` must be after `start`. A block that runs past midnight must be sent as two blocks. |

The backend turns each recurring block into real date and time ranges for `week_start`'s
week in America/New_York, so a 9:00 class stays 9:00 on the clock when daylight saving
changes. Overlapping or touching blocks are merged.

### Response (200)  **DRAFT**

```json
{
  "week_start": "2026-11-09",
  "events": [
    {
      "id": "flyer-101",
      "title": "AI Club Kickoff",
      "start": "2026-11-12T18:00:00-05:00",
      "end": "2026-11-12T19:00:00-05:00",
      "end_is_estimated": true,
      "location": "Boyd 328",
      "organizer": "AI Club",
      "url": null,
      "interest_tags": ["technology-coding:ai"],
      "match_percent": 85,
      "reasons": ["Matches your interest in AI", "Relevant to the School of Computing"]
    }
  ],
  "schedules": [
    {"label": "Best match", "event_ids": ["flyer-101"]}
  ]
}
```

- `events` is ranked best first (at most 10). `schedules` lists the same events by `id`, grouped into versions that don't overlap each other.
- All times are ISO 8601 **with a UTC offset**. The frontend formats them for display (for example with `Intl.DateTimeFormat` and `timeZone: "America/New_York"`) and must not parse "Oct 24" style strings.
- `end_is_estimated` is `true` when the flyer showed no end time and a default length was used.
- `match_percent` and `reasons` come from the backend. The frontend must not compute its own match score.
- If nothing matches, `events` and `schedules` are empty lists (still a 200).

### Errors

Invalid input returns **422** with FastAPI's standard body:

```json
{"detail": [{"loc": ["body", "majors"], "msg": "Value error, Choose at most 2 majors.", "type": "value_error"}]}
```

`loc` says which field is wrong and `msg` is written to be readable. Server problems
return **500** with `{"detail": "..."}` and never include the profile.

---

## Open decisions (settle before building the response)

1. **Swipe deck or schedule versions?** The current frontend lets the user swipe through events and builds the calendar from what they keep. The response above also returns ready-made `schedules`. Either the frontend uses `events` for the swipe deck and ignores `schedules`, or the swipe step is replaced by showing the versions.
2. **Default event length** when a flyer has no end time (proposed: 1 hour, flagged by `end_is_estimated`).