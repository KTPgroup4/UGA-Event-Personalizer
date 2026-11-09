
import { useEffect, useRef, useState, type ReactNode } from "react"
import Landing from "./Landing"
import AuthPage, { type AuthMode } from "./AuthPage"
import CalendarView from "./CalendarView"
import {
  ApiError,
  getMe,
  getOptions,
  getSchedules,
  logOut,
  saveCalendar,
  savePreferences,
  type AccountUser,
  type AuthResponse,
  type BusyBlock,
  type OptionsResponse,
  type RecommendedEvent,
  type SavedCalendar,
  type SavedPreferences,
} from "./api"
import { clearToken, loadToken, saveToken } from "./session"
import "./form-layout.css"

export type CampusEvent = {
  id: string
  title: string
  description: string
  organizer: string
  day: string
  date: string
  dateKey: string
  time: string
  endTime: string
  period: "Morning" | "Afternoon" | "Evening"
  location: string
  category: string
  tags: string[]
  majors: string[]
  attendees: number | null
  tone: string
  reason: string
  matchKind: string
  conflictsWith: string[]
  endIsEstimated: boolean
  raw: RecommendedEvent // the card exactly as the backend sent it (this is what gets saved)
}

// An event the student added by hand. Times are "HH:MM"; endTime is "" when there is none.
export type PersonalEvent = {
  id: string
  title: string
  date: string
  time: string
  endTime?: string
}

type IconName =
  | "arrow"
  | "calendar"
  | "check"
  | "chevron"
  | "clock"
  | "location"

function Icon({
  name,
  size = 18,
}: {
  name: IconName
  size?: number
}) {
  const paths: Record<IconName, ReactNode> = {
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    calendar: (
      <>
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    chevron: <path d="m9 18 6-6-6-6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    location: (
      <>
        <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
        <circle cx="12" cy="10" r="2.5" />
      </>
    ),
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  )
}

const formatAthens = (
  date: string,
  options: Intl.DateTimeFormatOptions
) =>
  new Intl.DateTimeFormat("en-US", {
    ...options,
    timeZone: "America/New_York",
  }).format(new Date(date))

function getMonday() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date())

  const year = Number(parts.find(p => p.type === "year")?.value)
  const month = Number(parts.find(p => p.type === "month")?.value)
  const day = Number(parts.find(p => p.type === "day")?.value)

  const date = new Date(Date.UTC(year, month - 1, day))
  const weekday = date.getUTCDay()
  const offset = (weekday + 6) % 7

  date.setUTCDate(date.getUTCDate() - offset + (weekday === 0 ? 7 : 0))

  return date.toISOString().slice(0, 10)
}

// The week picker only offers Mondays: this week's Monday and the next 15, so a student
// can't pick a day that isn't a Monday. Labels look like "Mon, Nov 9 – Sun, Nov 15".
function mondayOptions(thisMonday: string, count = 16) {
  const day = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  })

  return Array.from({ length: count }, (_, index) => {
    const start = new Date(thisMonday + "T12:00:00Z")
    start.setUTCDate(start.getUTCDate() + index * 7)
    const end = new Date(start)
    end.setUTCDate(end.getUTCDate() + 6)

    return {
      value: start.toISOString().slice(0, 10),
      label: `${day.format(start)} – ${day.format(end)}${
        index === 0 ? " (this week)" : ""
      }`,
    }
  })
}

function validMonday(date: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    new Date(date + "T12:00:00Z").getUTCDay() === 1
}

// A-to-Z by display name (copies the list, so the original order is untouched)
function sortByName<T extends { name: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.name.localeCompare(b.name))
}

const BUSY_DAYS: [BusyBlock["day"], string][] = [
  ["mon", "Mon"],
  ["tue", "Tue"],
  ["wed", "Wed"],
  ["thu", "Thu"],
  ["fri", "Fri"],
  ["sat", "Sat"],
  ["sun", "Sun"],
]

// "15:30" -> "3:30 PM"
function clockLabel(value: string) {
  const [hour, minute] = value.split(":").map(Number)
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${
    hour < 12 ? "AM" : "PM"
  }`
}

function busyLabel(block: BusyBlock) {
  const day = BUSY_DAYS.find(([id]) => id === block.day)?.[1] ?? block.day
  return `${day} ${clockLabel(block.start)}–${clockLabel(block.end)}`
}

function convertEvent(event: RecommendedEvent): CampusEvent {
  const date = new Date(event.start)

  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date)

  const year = parts.find(p => p.type === "year")?.value
  const month = parts.find(p => p.type === "month")?.value
  const day = parts.find(p => p.type === "day")?.value

  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      hourCycle: "h23",
    }).format(date)
  )

  return {
    id: event.id,
    title: event.title,
    description: event.description ?? "",
    organizer: event.organizer ?? "Event organizer",
    day: formatAthens(event.start, { weekday: "long" }),
    date: formatAthens(event.start, {
      month: "short",
      day: "numeric",
    }),
    dateKey: `${year}-${month}-${day}`,
    time: formatAthens(event.start, {
      hour: "numeric",
      minute: "2-digit",
    }),
    endTime: event.end
      ? formatAthens(event.end, {
          hour: "numeric",
          minute: "2-digit",
        })
      : "",
    period: hour < 12
      ? "Morning"
      : hour < 17
        ? "Afternoon"
        : "Evening",
    location: event.location ?? "Location not provided",
    category: event.match_kind ?? "Campus",
    tags: event.interest_tags ?? [],
    majors: [],
    attendees: null,
    tone: "violet",
    reason: event.reason ?? "Recommended for you",
    matchKind: event.match_kind ?? "Recommended",
    conflictsWith: event.conflicts_with ?? [],
    endIsEstimated: event.end_is_estimated ?? false,
    raw: event,
  }
}

// ---- the calendar (saved events + events added by hand) ----

const GUEST_PERSONAL_KEY = "uga-personal-events"

// Guests keep the events they add in this browser. (Accounts keep them on the server.)
function loadGuestPersonal(): PersonalEvent[] {
  try {
    const stored = JSON.parse(localStorage.getItem(GUEST_PERSONAL_KEY) || "[]")
    return Array.isArray(stored) ? stored : []
  } catch {
    return []
  }
}

// What gets sent to the backend: saved events as received, personal events in snake_case.
function calendarPayload(
  saved: CampusEvent[],
  personal: PersonalEvent[]
): SavedCalendar {
  return {
    saved: saved.map(event => event.raw),
    personal: personal.map(event => ({
      id: event.id,
      title: event.title,
      date: event.date,
      time: event.time,
      end_time: event.endTime ?? "",
    })),
  }
}

// A saved event comes back from the server without the matching fields (reason etc.).
function savedToCampusEvent(event: RecommendedEvent): CampusEvent {
  return convertEvent({
    ...event,
    reason: "Saved to your calendar",
    match_kind: "saved",
    conflicts_with: [],
  })
}

export default function App() {
  const [name, setName] = useState("")
  const [options, setOptions] =
    useState<OptionsResponse | null>(null)

  const [selectedMajors, setSelectedMajors] =
    useState<string[]>([])

  const [selectedInterests, setSelectedInterests] =
    useState<string[]>([])

  const [activeCategory, setActiveCategory] = useState("")
  const [weekStart, setWeekStart] = useState(getMonday)

  const [events, setEvents] = useState<CampusEvent[]>([])
  const [favorites, setFavorites] = useState<string[]>([])
  const [reviewedIds, setReviewedIds] = useState<string[]>([])
  const [hiddenIds, setHiddenIds] = useState<string[]>([])
  const [targetPicks, setTargetPicks] = useState(5)

  const [busyBlocks, setBusyBlocks] = useState<BusyBlock[]>([])
  const [busyDraft, setBusyDraft] = useState<BusyBlock>({
    day: "mon",
    start: "09:00",
    end: "09:50",
  })
  const [busyError, setBusyError] = useState("")

  const [loading, setLoading] = useState(false)
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [error, setError] = useState("")

  const [started, setStarted] = useState(false)
  const [view, setView] =
    useState<"discover" | "calendar">("discover")

  // Which full screen is showing. The landing page comes first; "Continue as guest",
  // signing up or logging in all lead to the questionnaire ("app").
  const [screen, setScreen] =
    useState<"landing" | "login" | "signup" | "app">("landing")

  // Where the "X" on the sign up / log in screen goes back to.
  const [authReturn, setAuthReturn] =
    useState<"landing" | "app">("landing")

  // Accounts: the login token is kept in this browser; `account` is who it belongs to.
  const [token, setToken] = useState(loadToken)
  const [account, setAccount] = useState<AccountUser | null>(null)
  const [restoring, setRestoring] = useState(() => loadToken() !== "")
  const [saveNote, setSaveNote] = useState("")

  // The calendar. `savedEvents` are UGA events swiped right on, and they stay until removed
  // (even after a new questionnaire). `personalEvents` are the ones the student typed in.
  const [savedEvents, setSavedEvents] = useState<CampusEvent[]>([])
  const [personalEvents, setPersonalEvents] =
    useState<PersonalEvent[]>(loadGuestPersonal)

  // The calendar as last known to the server, so we only save when something really changed.
  const syncedCalendar = useRef("")

  const [swipeDirection, setSwipeDirection] =
    useState<"left" | "right" | null>(null)

  const [dragStart, setDragStart] = useState<number | null>(null)

  useEffect(() => {
    getOptions()
      .then(setOptions)
      .catch(err =>
        setError(err instanceof Error ? err.message : "Cannot load options")
      )
      .finally(() => setLoadingOptions(false))
  }, [])

  // If this browser has a saved login, find out who it is and fill in their saved answers.
  useEffect(() => {
    const saved = loadToken()
    if (!saved) return

    getMe(saved)
      .then(({ user }) => {
        setAccount(user)
        applyPreferences(user.preferences)
        applyCalendar(user.calendar)
        setScreen("app")
      })
      .catch(err => {
        // Only a 401 means the login really ended. After a network hiccup the saved
        // token stays in the browser for next time, but this visit continues as a guest.
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
        }
        setToken("")
      })
      .finally(() => setRestoring(false))
  }, [])

  // Guests: remember the events they add in this browser.
  useEffect(() => {
    if (account) return

    try {
      localStorage.setItem(GUEST_PERSONAL_KEY, JSON.stringify(personalEvents))
    } catch {
      // ignore: the events just won't survive closing the tab
    }
  }, [account, personalEvents])

  // Logged in: save the calendar to the account a moment after it changes.
  useEffect(() => {
    if (!token || !account) return

    const payload = calendarPayload(savedEvents, personalEvents)
    const text = JSON.stringify(payload)

    if (text === syncedCalendar.current) return

    const timer = window.setTimeout(() => {
      saveCalendar(token, payload)
        .then(() => {
          syncedCalendar.current = text
        })
        .catch(err => {
          if (err instanceof ApiError && err.status === 401) {
            sessionExpired("Your login ran out, so your calendar was not saved. Log in again to save it.")
          } else {
            setSaveNote("We could not save your calendar just now.")
          }
        })
    }, 400)

    return () => window.clearTimeout(timer)
  }, [token, account, savedEvents, personalEvents])

  const majorChoices = [
    ...(options?.colleges.flatMap(college => college.majors) ?? []),
    ...(options?.special_majors ?? []),
  ]

  const majorName = selectedMajors
    .map(id => majorChoices.find(major => major.id === id)?.name ?? id)
    .join(", ")

  const availableEvents = events.filter(
    event =>
      !reviewedIds.includes(event.id) &&
      !hiddenIds.includes(event.id)
  )

  const deckComplete =
    favorites.length >= targetPicks || availableEvents.length === 0

  const currentEvent = deckComplete ? undefined : availableEvents[0]
  const reviewedCount = events.length - availableEvents.length

  function toggleInterest(id: string) {
    setSelectedInterests(previous => {
      if (previous.includes(id)) {
        return previous.filter(item => item !== id)
      }

      if (previous.length >= 15) return previous

      return [...previous, id]
    })
  }

  function toggleMajor(id: string) {
    if (!options) return

    const rules = options.major_rules

    setSelectedMajors(previous => {
      if (previous.includes(id)) {
        return previous.filter(item => item !== id)
      }

      if (rules.exclusive_ids.includes(id)) {
        return [id]
      }

      const next = previous.filter(
        item => !rules.exclusive_ids.includes(item)
      )

      if (next.length >= rules.max) return previous

      return [...next, id]
    })
  }

  async function findEvents() {
    if (!options || loading) return

    const rules = options.major_rules

    if (
      selectedMajors.length < rules.min ||
      selectedMajors.length > rules.max
    ) {
      setError(`Please select ${rules.min} to ${rules.max} majors.`)
      return
    }

    if (
      selectedMajors.some(id => rules.co_major_ids.includes(id)) &&
      selectedMajors.length < 2
    ) {
      setError("This co-major must be selected with another major.")
      return
    }

    if (selectedInterests.length < 1 || selectedInterests.length > 15) {
      setError("Please select between 1 and 15 interests.")
      return
    }

    if (!validMonday(weekStart)) {
      setError("Please choose a Monday for your week.")
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await getSchedules({
        week_start: weekStart,
        majors: selectedMajors,
        interests: selectedInterests,
        busy: busyBlocks,
      })

      const cards =
        response.events ?? response.deck ?? response.cards

      if (!Array.isArray(cards)) {
        throw new Error(
          "The backend did not return an events, deck, or cards array."
        )
      }

      if (
        cards.some(
          card =>
            typeof card.id !== "string" ||
            typeof card.start !== "string" ||
            typeof card.title !== "string"
        )
      ) {
        throw new Error("The backend returned an invalid event card.")
      }

      setEvents(cards.map(convertEvent))
      setTargetPicks(
        typeof response.target_picks === "number" &&
        response.target_picks > 0
          ? response.target_picks
          : 5
      )

      setFavorites([])
      setReviewedIds([])
      setHiddenIds([])
      setStarted(true)

      // Logged in: remember these answers for next time. This runs in the background,
      // so a problem saving never stops the student from seeing their events.
      if (token) {
        rememberAnswers(token)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load recommendations."
      )
    } finally {
      setLoading(false)
    }
  }

  function handleSwipe(save: boolean) {
    if (!currentEvent || swipeDirection) return

    const chosen = currentEvent

    setSwipeDirection(save ? "right" : "left")

    window.setTimeout(() => {
      setReviewedIds(previous => [...previous, chosen.id])

      if (save) {
        setFavorites(previous =>
          previous.includes(chosen.id)
            ? previous
            : [...previous, chosen.id]
        )

        // Also keep it on the calendar (and on the account) until the student removes it
        setSavedEvents(previous =>
          previous.some(event => event.id === chosen.id)
            ? previous
            : [...previous, chosen]
        )

        setHiddenIds(previous => [
          ...new Set([...previous, ...chosen.conflictsWith]),
        ])
      }

      setSwipeDirection(null)
    }, 280)
  }

  function addBusyBlock() {
    if (!busyDraft.start || !busyDraft.end) {
      setBusyError("Pick a start and an end time.")
      return
    }

    if (busyDraft.end <= busyDraft.start) {
      setBusyError("The end time has to be after the start time.")
      return
    }

    setBusyError("")
    setBusyBlocks(current =>
      [...current, busyDraft].sort(
        (a, b) =>
          BUSY_DAYS.findIndex(([id]) => id === a.day) -
            BUSY_DAYS.findIndex(([id]) => id === b.day) ||
          a.start.localeCompare(b.start)
      )
    )
  }

  function removeBusyBlock(index: number) {
    setBusyBlocks(current => current.filter((_, i) => i !== index))
  }

  // ---- accounts ----

  // Fill the questionnaire from an account's saved answers (does nothing if there are none).
  function applyPreferences(preferences: SavedPreferences | null) {
    if (!preferences) return

    setName(preferences.name)
    setSelectedMajors(preferences.majors)
    setSelectedInterests(preferences.interests)
    setBusyBlocks(preferences.busy)
  }

  // Show an account's saved calendar. `syncedCalendar` is set to the same thing, so loading
  // it does not cause an immediate save.
  function applyCalendar(calendar: SavedCalendar | null) {
    const saved = (calendar?.saved ?? []).map(savedToCampusEvent)
    const personal: PersonalEvent[] = (calendar?.personal ?? []).map(event => ({
      id: event.id,
      title: event.title,
      date: event.date,
      time: event.time,
      endTime: event.end_time,
    }))

    syncedCalendar.current = JSON.stringify(calendarPayload(saved, personal))
    setSavedEvents(saved)
    setPersonalEvents(personal)
  }

  // The login ended (30 days passed, or the account was logged out elsewhere).
  function sessionExpired(message: string) {
    clearToken()
    setToken("")
    setAccount(null)
    setSaveNote(message)
  }

  // Save the current answers to the account. The week is not saved: every week is different.
  function rememberAnswers(activeToken: string) {
    setSaveNote("")

    savePreferences(activeToken, {
      name: name.trim(),
      majors: selectedMajors,
      interests: selectedInterests,
      busy: busyBlocks,
    }).catch(err => {
      if (err instanceof ApiError && err.status === 401) {
        sessionExpired(
          "Your login ran out, so your answers were not saved. Log in again to save them."
        )
      } else {
        setSaveNote("We could not save your answers just now.")
      }
    })
  }

  function openAuth(mode: AuthMode) {
    setAuthReturn(screen === "app" ? "app" : "landing")
    setScreen(mode)
  }

  function handleAuthSuccess(result: AuthResponse, mode: AuthMode) {
    saveToken(result.token)
    setToken(result.token)
    setAccount(result.user)
    setSaveNote("")
    setError("")

    // Logging in brings back saved answers. A brand new account has none, so anything the
    // student already filled in as a guest stays put.
    if (mode === "login") {
      applyPreferences(result.user.preferences)
      applyCalendar(result.user.calendar)
    } else {
      // A new account starts empty, so the events the student already saved or added
      // are kept, and the sync effect uploads them.
      syncedCalendar.current = JSON.stringify(calendarPayload([], []))
    }

    setView("discover")
    setScreen("app")
  }

  function handleLogout() {
    if (token) {
      logOut(token).catch(() => {
        // Nothing to do: the token is forgotten on this device either way.
      })
    }

    clearToken()
    setToken("")
    setAccount(null)

    // Clear the form so the next person on a shared computer starts fresh.
    setName("")
    setSelectedMajors([])
    setSelectedInterests([])
    setBusyBlocks([])
    setActiveCategory("")
    setEvents([])
    setFavorites([])
    setReviewedIds([])
    setHiddenIds([])
    setSavedEvents([])
    setPersonalEvents(loadGuestPersonal())
    syncedCalendar.current = ""
    setStarted(false)
    setError("")
    setSaveNote("")
    setView("discover")
    setScreen("landing")
  }

  function interestLabel(id: string) {
    for (const category of options?.interests ?? []) {
      if (category.id === id) return category.name

      const child = category.children.find(item => item.id === id)

      if (child) return child.name
    }

    return id
  }

  // A saved login is being checked: show a blank page for a moment instead of
  // flashing the landing page and then jumping into the app.
  if (restoring) {
    return (
      <main className="auth-loading" role="status">
        Loading your account...
      </main>
    )
  }

  if (screen === "landing") {
    return (
      <Landing
        onGuest={() => {
          setView("discover")
          setScreen("app")
        }}
        onLogin={() => openAuth("login")}
        onSignUp={() => openAuth("signup")}
      />
    )
  }

  if (screen === "login" || screen === "signup") {
    return (
      <AuthPage
        mode={screen}
        onModeChange={setScreen}
        onClose={() => setScreen(authReturn)}
        onSuccess={handleAuthSuccess}
      />
    )
  }

  return (
    <main className="app-shell">
      <style>{`
        .compact-field {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 12px;
          font-weight: 600;
        }

        .compact-select {
          width: 100%;
          min-height: 48px;
          padding: 10px 14px;
          border: 2px solid #222;
          border-radius: 13px;
          background: white;
          color: #171717;
          font: inherit;
        }

        .compact-picker {
          margin-top: 12px;
          padding: 14px;
          border: 1px solid #ddd;
          border-radius: 14px;
        }

        .compact-options-scroll {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
          gap: 8px 16px;
          max-height: 220px;
          overflow-y: auto;
          padding: 6px 0;
        }

        .compact-option {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          cursor: pointer;
          padding: 4px 0;
        }

        .compact-option input {
          width: 18px;
          height: 18px;
          accent-color: #c8102e;
        }

        .compact-selected {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 12px;
        }

        .compact-selected .choice-chip {
          font-size: 13px;
          padding: 8px 11px;
        }

        .compact-hint {
          color: #666;
          font-size: 14px;
          margin: 10px 0;
        }
      `}</style>

      <header className="topbar">
        <button
          className="brand"
          type="button"
          aria-label="Dawg Match home"
          onClick={() => {
            // Logged-in students stay in the app; guests go back to the landing page.
            setView("discover")

            if (!account) {
              setScreen("landing")
            }
          }}
        >
          <span className="brand-mark">
            <strong>G</strong>
          </span>
          <span>
            Dawg <em>Match</em>
          </span>
        </button>

        <nav className="nav-links" aria-label="Main navigation">
          <button
            className={view === "discover" ? "active" : ""}
            type="button"
            onClick={() => setView("discover")}
          >
            Discover
          </button>

          <button
            className={view === "calendar" ? "active" : ""}
            type="button"
            onClick={() => setView("calendar")}
          >
            Calendar <span className="nav-count">{savedEvents.length}</span>
          </button>
        </nav>

        <div className="account-area">
          {account ? (
            <>
              <span className="avatar" aria-hidden="true">
                {(name.trim() || account.email)[0].toUpperCase()}
              </span>

              <span className="account-email" title={account.email}>
                {name.trim() || account.email}
              </span>

              <button
                className="account-button account-logout"
                type="button"
                onClick={handleLogout}
              >
                Log out
              </button>
            </>
          ) : (
            <button
              className="account-button account-login"
              type="button"
              onClick={() => openAuth("login")}
            >
              Log in
            </button>
          )}
        </div>
      </header>

      {view === "calendar" ? (
        <CalendarView
          savedEvents={savedEvents}
          personalEvents={personalEvents}
          busyBlocks={busyBlocks}
          weekStart={weekStart}
          name={name}
          major={majorName}
          interests={selectedInterests.map(interestLabel)}
          onAddPersonal={event =>
            setPersonalEvents(current => [...current, event])
          }
          onRemovePersonal={id =>
            setPersonalEvents(current =>
              current.filter(event => event.id !== id)
            )
          }
          onRemoveSaved={id =>
            setSavedEvents(current =>
              current.filter(event => event.id !== id)
            )
          }
          onBack={() => {
            setView("discover")
            setStarted(false)
          }}
        />
      ) : (
        <>
          <div
            className={`content-grid ${
              started ? "swiping" : "questionnaire-only"
            }`}
          >
            <aside className="personalizer-card">
              <div className="card-heading">
                <div className="question-meta">
                  <strong>Step 1 of 2</strong>
                  <strong>About you</strong>
                </div>

                <div className="question-progress">
                  <span />
                </div>

                <h2>What are you into?</h2>
                <p>Pick anything that sounds like you.</p>
              </div>

              {account ? (
                <p className="account-note">
                  Logged in as <strong>{account.email}</strong>. Your
                  answers are saved when you press Find my events.
                </p>
              ) : (
                <p className="account-note">
                  Want to skip this next time?{" "}
                  <button
                    className="link-button"
                    type="button"
                    onClick={() => openAuth("signup")}
                  >
                    Create an account
                  </button>{" "}
                  to save your answers.
                </p>
              )}

              {saveNote && (
                <p className="account-note" role="status">
                  {saveNote}
                </p>
              )}

              {loadingOptions && (
                <p>Loading interests and majors...</p>
              )}

              {error && (
                <p role="alert" style={{ color: "#b42318" }}>
                  {error}
                </p>
              )}

              <div className="form-section">
                <div className="label-row">
                  <span className="field-label">
                    Interests <small>(choose 1–15)</small>
                  </span>
                  <span className="selection-count">
                    {selectedInterests.length} selected
                  </span>
                </div>

                <label className="compact-field">
                  <span>Explore an interest category</span>

                  <select
                    className="compact-select"
                    value={activeCategory}
                    onChange={event =>
                      setActiveCategory(event.target.value)
                    }
                  >
                    <option value="">Choose a category...</option>

                    {sortByName(options?.interests ?? []).map(category => (
                      <option
                        key={category.id}
                        value={category.id}
                      >
                        {category.name}
                      </option>
                    ))}
                  </select>
                </label>

                {options?.interests
                  .filter(category => category.id === activeCategory)
                  .map(category => (
                    <div
                      key={category.id}
                      className="compact-picker"
                    >
                      <label className="compact-option">
                        <input
                          type="checkbox"
                          checked={selectedInterests.includes(category.id)}
                          onChange={() => toggleInterest(category.id)}
                        />

                        <strong>All {category.name} events</strong>
                      </label>

                      {category.children.length > 0 && (
                        <p className="compact-hint">
                          Or select specific interests:
                        </p>
                      )}

                      <div className="compact-options-scroll">
                        {sortByName(category.children).map(child => (
                          <label
                            key={child.id}
                            className="compact-option"
                          >
                            <input
                              type="checkbox"
                              checked={selectedInterests.includes(child.id)}
                              onChange={() => toggleInterest(child.id)}
                            />
                            <span>{child.name}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}

                {selectedInterests.length > 0 && (
                  <div className="compact-selected">
                    {selectedInterests.map(id => (
                      <button
                        key={id}
                        type="button"
                        className="choice-chip selected"
                        onClick={() => toggleInterest(id)}
                      >
                        {interestLabel(id)} ×
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="form-section">
                <div className="label-row">
                  <span className="field-label">
                    Majors{" "}
                    <small>
                      (choose {options?.major_rules.min ?? 1}–
                      {options?.major_rules.max ?? 2})
                    </small>
                  </span>

                  <span className="selection-count">
                    {selectedMajors.length} selected
                  </span>
                </div>

                <label className="compact-field">
                  <span>Add a major</span>

                  <select
                    className="compact-select"
                    value=""
                    onChange={event => {
                      if (event.target.value) {
                        toggleMajor(event.target.value)
                      }
                    }}
                  >
                    <option value="">Choose your major...</option>

                    {options?.colleges.map(college => (
                      <optgroup
                        key={college.id}
                        label={college.name}
                      >
                        {college.majors.map(major => (
                          <option
                            key={major.id}
                            value={major.id}
                          >
                            {major.name}
                          </option>
                        ))}
                      </optgroup>
                    ))}

                    <optgroup label="Other options">
                      {options?.special_majors.map(major => (
                        <option
                          key={major.id}
                          value={major.id}
                        >
                          {major.name}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </label>

                {selectedMajors.length > 0 && (
                  <div className="compact-selected">
                    {selectedMajors.map(id => (
                      <button
                        key={id}
                        type="button"
                        className="choice-chip selected"
                        onClick={() => toggleMajor(id)}
                      >
                        {majorChoices.find(major => major.id === id)?.name ?? id}
                        {" "}×
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="form-section stacked-fields">
                <label>
                  <span>Display name (optional)</span>
                  <input
                    value={name}
                    placeholder="Your name"
                    onChange={event => setName(event.target.value)}
                  />
                </label>

                <label>
                  <span>Week starting Monday</span>
                  <small className="field-hint">
                    Pick the Monday of the week you are planning. We show
                    events from that Monday through Sunday.
                  </small>
                  <select
                    className="compact-select"
                    value={weekStart}
                    onChange={event => setWeekStart(event.target.value)}
                  >
                    {mondayOptions(getMonday()).map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="form-section">
                <span className="busy-title">
                  Times you are busy (optional)
                </span>
                <p className="compact-hint">
                  Add your class or work times. We will not show events
                  that clash with them, and they appear on your calendar
                  in the week you picked above.
                </p>

                <div className="busy-form">
                  <label>
                    <span>Day</span>
                    <select
                      value={busyDraft.day}
                      onChange={event =>
                        setBusyDraft({
                          ...busyDraft,
                          day: event.target.value as BusyBlock["day"],
                        })
                      }
                    >
                      {BUSY_DAYS.map(([id, label]) => (
                        <option key={id} value={id}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span>From</span>
                    <input
                      type="time"
                      value={busyDraft.start}
                      onChange={event =>
                        setBusyDraft({ ...busyDraft, start: event.target.value })
                      }
                    />
                  </label>

                  <label>
                    <span>To</span>
                    <input
                      type="time"
                      value={busyDraft.end}
                      onChange={event =>
                        setBusyDraft({ ...busyDraft, end: event.target.value })
                      }
                    />
                  </label>

                  <button
                    className="busy-add"
                    type="button"
                    onClick={addBusyBlock}
                  >
                    Add
                  </button>
                </div>

                {busyError && <p className="busy-error">{busyError}</p>}

                {busyBlocks.length > 0 && (
                  <div className="compact-selected">
                    {busyBlocks.map((block, index) => (
                      <button
                        key={`${block.day}-${block.start}-${block.end}-${index}`}
                        type="button"
                        className="choice-chip selected"
                        onClick={() => removeBusyBlock(index)}
                      >
                        {busyLabel(block)} ×
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="question-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={loading || loadingOptions || !options}
                  onClick={findEvents}
                >
                  {loading ? "Finding events..." : "Find my events"}
                  <Icon name="arrow" size={17} />
                </button>
              </div>
            </aside>

            {started && (
              <section
                className="swipe-experience"
                aria-live="polite"
              >
                <div className="swipe-header">
                  <button
                    className="edit-preferences"
                    type="button"
                    onClick={() => setStarted(false)}
                  >
                    <Icon name="chevron" size={15} />
                    Edit preferences
                  </button>

                  <div>
                    <strong>
                      {Math.min(reviewedCount + 1, events.length)}
                      {" "}of {events.length}
                    </strong>
                    <span>events reviewed</span>
                  </div>
                </div>

                <div className="progress-track">
                  <span
                    style={{
                      width: `${
                        Math.min(
                          reviewedCount / Math.max(events.length, 1) * 100,
                          100
                        )
                      }%`,
                    }}
                  />
                </div>

                {currentEvent ? (
                  <>
                    <div className="swipe-stage">
                      {availableEvents.length > 1 && (
                        <div
                          className="swipe-card next-card"
                          aria-hidden="true"
                        />
                      )}

                      <article
                        className={`swipe-card ${
                          swipeDirection
                            ? `swipe-${swipeDirection}`
                            : ""
                        }`}
                        onPointerDown={event => {
                          setDragStart(event.clientX)
                          event.currentTarget.setPointerCapture(
                            event.pointerId
                          )
                        }}
                        onPointerUp={event => {
                          if (dragStart !== null) {
                            const distance =
                              event.clientX - dragStart

                            if (Math.abs(distance) > 70) {
                              handleSwipe(distance > 0)
                            }
                          }

                          setDragStart(null)
                        }}
                      >
                        <div className="swipe-card-top">
                          <span className="swipe-category">
                            {currentEvent.category}
                          </span>

                          <span className="swipe-match">
                            {currentEvent.matchKind}
                          </span>
                        </div>

                        <div className="swipe-date">
                          <span>{currentEvent.day}</span>
                          <strong>{currentEvent.date}</strong>
                          <small>{currentEvent.time}</small>
                        </div>

                        <div className="swipe-card-body">
                          <p>{currentEvent.organizer}</p>
                          <h2>{currentEvent.title}</h2>

                          {currentEvent.description && (
                            <div className="swipe-description">
                              {currentEvent.description}
                            </div>
                          )}

                          <div className="swipe-location">
                            <Icon name="location" size={18} />
                            <span>{currentEvent.location}</span>
                          </div>

                          <div className="tag-row">
                            {currentEvent.tags.map(tag => (
                              <span key={tag}>
                                {interestLabel(tag)}
                              </span>
                            ))}
                          </div>

                          <p className="compact-hint">
                            {currentEvent.reason}
                          </p>

                          {currentEvent.endIsEstimated && (
                            <small>End time estimated</small>
                          )}
                        </div>

                        <span className="swipe-stamp pass-stamp">
                          PASS
                        </span>

                        <span className="swipe-stamp save-stamp">
                          ADD IT
                        </span>
                      </article>
                    </div>

                    <div className="swipe-controls">
                      <button
                        className="swipe-button pass-button"
                        type="button"
                        onClick={() => handleSwipe(false)}
                      >
                        <span>×</span>
                        <small>Pass</small>
                      </button>

                      <p>Swipe the card or use the buttons</p>

                      <button
                        className="swipe-button add-button"
                        type="button"
                        onClick={() => handleSwipe(true)}
                      >
                        <Icon name="calendar" size={22} />
                        <small>Add</small>
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="swipe-complete">
                    <span className="complete-icon">
                      <Icon name="check" size={28} />
                    </span>

                    <p>Deck complete</p>
                    <h2>Your week is looking good.</h2>

                    <strong>
                      {favorites.length} of {targetPicks} event picks saved
                    </strong>

                    <div className="saved-event-list">
                      {events
                        .filter(event =>
                          favorites.includes(event.id)
                        )
                        .map(event => (
                          <div key={event.id}>
                            <span>{event.date}</span>

                            <p>
                              <strong>{event.title}</strong>
                              <small>
                                {event.time} · {event.location}
                              </small>
                            </p>

                            <Icon name="check" size={16} />
                          </div>
                        ))}
                    </div>

                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => {
                        setFavorites([])
                        setReviewedIds([])
                        setHiddenIds([])
                      }}
                    >
                      Start over
                    </button>

                    <button
                      className="calendar-link-button"
                      type="button"
                      onClick={() => setView("calendar")}
                    >
                      View my calendar
                    </button>
                  </div>
                )}
              </section>
            )}
          </div>

          <footer>
            <span>
              Built for better days at the University of Georgia.
            </span>

            <span>
              Personalized from {events.length} recommended events
            </span>
          </footer>
        </>
      )}
    </main>
  )
}

