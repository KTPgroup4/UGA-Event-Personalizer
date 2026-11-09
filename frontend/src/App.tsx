
import { useEffect, useState, type ReactNode } from "react"
import CalendarView from "./CalendarView"
import {
  getOptions,
  getSchedules,
  type BusyBlock,
  type OptionsResponse,
  type RecommendedEvent,
} from "./api"

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

function validMonday(date: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) &&
    new Date(date + "T12:00:00Z").getUTCDay() === 1
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
  }
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

      if (previous.length >= 40) return previous

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

  function interestLabel(id: string) {
    for (const category of options?.interests ?? []) {
      if (category.id === id) return category.name

      const child = category.children.find(item => item.id === id)

      if (child) return child.name
    }

    return id
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
          onClick={() => setView("discover")}
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
            Calendar <span className="nav-count">{favorites.length}</span>
          </button>
        </nav>

        <button
          className="profile-button"
          type="button"
          aria-label="Your profile"
        >
          <span className="avatar">
            {name
              .split(" ")
              .filter(Boolean)
              .map(part => part[0])
              .join("")
              .slice(0, 2) || "G"}
          </span>

          <span className="profile-name">
            {name || "Your profile"}
          </span>

          <Icon name="chevron" size={15} />
        </button>
      </header>

      {view === "calendar" ? (
        <CalendarView
          selectedEvents={events.filter(event =>
            favorites.includes(event.id)
          )}
          name={name}
          major={majorName}
          interests={selectedInterests}
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
                    Interests <small>(choose 1–40)</small>
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

                    {options?.interests.map(category => (
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
                        {category.children.map(child => (
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

              <div className="form-section identity-grid">
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
                  <input
                    type="date"
                    value={weekStart}
                    onChange={event => setWeekStart(event.target.value)}
                  />
                </label>
              </div>

              <div className="form-section">
                <span className="busy-title">
                  Times you are busy (optional)
                </span>
                <p className="compact-hint">
                  Add your class or work times. We will not show events
                  that clash with them. These repeat every week.
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

