import { useEffect, useMemo, useState, type ReactNode } from "react"
import CalendarView from "./CalendarView"
import { getOptions, getSchedules, type OptionsResponse, type RecommendedEvent } from "./api"

type IconName = "arrow" | "book" | "calendar" | "check" | "chevron" | "clock" | "heart" | "location" | "people" | "search" | "spark" | "star" | "user"

export type CampusEvent = {
  id: string
  title: string
  organizer: string
  day: string
  date: string
  dateKey: string
  time: string
  period: "Morning" | "Afternoon" | "Evening"
  location: string
  category: string
  tags: string[]
  majors: string[]
  attendees: number | null
  tone: string
  match: number
  reasons: string[]
  endIsEstimated: boolean
}

const athensDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
})
function mondayOfCurrentWeek() {
  const parts = athensDate.formatToParts(new Date())
  const year = Number(parts.find(p => p.type === "year")?.value)
  const month = Number(parts.find(p => p.type === "month")?.value)
  const day = Number(parts.find(p => p.type === "day")?.value)
  const date = new Date(Date.UTC(year, month - 1, day))
  const offset = (date.getUTCDay() + 6) % 7
  date.setUTCDate(date.getUTCDate() - offset)
  return date.toISOString().slice(0, 10)
}
function isMonday(value: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    new Date(`${value}T12:00:00Z`).getUTCDay() === 1
}
const formatAthens = (value: string, options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat("en-US", { ...options, timeZone: "America/New_York" }).format(new Date(value))

function toCampusEvent(event: RecommendedEvent): CampusEvent {
  const hour = Number(formatAthens(event.start, { hour: "numeric", hourCycle: "h23" }))
  const dateParts = athensDate.formatToParts(new Date(event.start))
  const dateKey = `${dateParts.find(p => p.type === "year")?.value}-${dateParts.find(p => p.type === "month")?.value}-${dateParts.find(p => p.type === "day")?.value}`
  return {
    id: event.id,
    title: event.title,
    organizer: event.organizer ?? "Event organizer",
    day: formatAthens(event.start, { weekday: "long" }),
    date: formatAthens(event.start, { month: "short", day: "numeric" }),
    dateKey,
    time: formatAthens(event.start, { hour: "numeric", minute: "2-digit" }),
    period: hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening",
    location: event.location ?? "Location not provided",
    category: event.interest_tags[0]?.split(":")[0] ?? "Campus",
    tags: event.interest_tags,
    majors: [],
    attendees: null,
    tone: "violet",
    match: event.match_percent,
    reasons: event.reasons,
    endIsEstimated: event.end_is_estimated,
  }
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    book: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      </>
    ),
    calendar: (
      <>
        <rect width="18" height="18" x="3" y="4" rx="2" />
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
    heart: (
      <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8l1.1 1.1L12 21l7.8-7.5a5.5 5.5 0 0 0 1-8.9Z" />
    ),
    location: (
      <>
        <path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z" />
        <circle cx="12" cy="10" r="2.5" />
      </>
    ),
    people: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    spark: (
      <path d="m12 3-1.4 4.1a5.5 5.5 0 0 1-3.5 3.5L3 12l4.1 1.4a5.5 5.5 0 0 1 3.5 3.5L12 21l1.4-4.1a5.5 5.5 0 0 1 3.5-3.5L21 12l-4.1-1.4a5.5 5.5 0 0 1-3.5-3.5L12 3Z" />
    ),
    star: (
      <path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8-6.2-3.2L5.8 21 7 14.2l-5-4.9 6.9-1L12 2Z" />
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
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

export default function App() {
  // Name is display-only and is never included in an API request.
  const [name, setName] = useState("")
  const [options, setOptions] = useState<OptionsResponse | null>(null)
  const [selectedMajors, setSelectedMajors] = useState<string[]>([])
  const [selectedInterests, setSelectedInterests] = useState<string[]>([])
  const [expandedInterests, setExpandedInterests] = useState<string[]>([])
  const [weekStart, setWeekStart] = useState(mondayOfCurrentWeek)
  const [events, setEvents] = useState<CampusEvent[]>([])
  const [error, setError] = useState("")
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [loadingSchedules, setLoadingSchedules] = useState(false)
  const [favorites, setFavorites] = useState<string[]>([])
  const [updated, setUpdated] = useState(false)
  const [started, setStarted] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(null)
  const [dragStart, setDragStart] = useState<number | null>(null)
  const [view, setView] = useState<"discover" | "calendar">("discover")

  useEffect(() => {
    getOptions().then(setOptions).catch(err => setError(err.message))
      .finally(() => setLoadingOptions(false))
  }, [])

  const recommendations = useMemo(() => events, [events])
  const majorChoices = [
    ...(options?.colleges.flatMap(college => college.majors) ?? []),
    ...(options?.special_majors ?? []),
  ]
  const majorName = selectedMajors.map(id =>
    majorChoices.find(major => major.id === id)?.name ?? id
  ).join(", ")

  const toggleMajor = (id: string) => {
    if (!options) return
    const rules = options.major_rules
    let next = selectedMajors.includes(id)
      ? selectedMajors.filter(item => item !== id)
      : [...selectedMajors, id]
    if (rules.exclusive_ids.includes(id)) next = [id]
    else next = next.filter(item => !rules.exclusive_ids.includes(item))
    if (next.length > rules.max) return
    setSelectedMajors(next)
    setUpdated(false)
  }

  const toggleInterest = (id: string) => {
    const next = selectedInterests.includes(id)
      ? selectedInterests.filter(item => item !== id)
      : [...selectedInterests, id]
    if (next.length > 40) return
    setSelectedInterests(next)
    setUpdated(false)
  }

  const loadRecommendations = async () => {
    if (!options || loadingSchedules) return
    const rules = options.major_rules
    if (selectedMajors.length < rules.min || selectedMajors.length > rules.max ||
        selectedMajors.some(id => rules.co_major_ids.includes(id)) && selectedMajors.length < 2) {
      setError(`Choose ${rules.min} to ${rules.max} valid majors (co-majors need a second major).`)
      return
    }
    if (selectedInterests.length < 1 || selectedInterests.length > 40) {
      setError("Choose between 1 and 40 interests.")
      return
    }
    if (!isMonday(weekStart)) {
      setError("The selected week must start on a Monday.")
      return
    }
    setLoadingSchedules(true)
    setError("")
    try {
      const result = await getSchedules({
        week_start: weekStart,
        majors: selectedMajors,
        interests: selectedInterests,
        busy: [], // No busy-time editor yet; do not misrepresent free days as busy blocks.
      })
      setEvents(result.events.map(toCampusEvent))
      setCurrentIndex(0)
      setFavorites([])
      setStarted(true)
      setUpdated(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load recommendations.")
    } finally {
      setLoadingSchedules(false)
    }
  }

  const currentEvent = recommendations[currentIndex]

  const handleSwipe = (save: boolean) => {
    if (!currentEvent || swipeDirection) return
    setSwipeDirection(save ? "right" : "left")
    if (save && !favorites.includes(currentEvent.id)) {
      setFavorites([...favorites, currentEvent.id])
    }
    window.setTimeout(() => {
      setCurrentIndex((index) => index + 1)
      setSwipeDirection(null)
    }, 280)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <button
          className="brand"
          type="button"
          aria-label="UGA Gather home"
          onClick={() => setView("discover")}
        >
          <span className="brand-mark">
            <strong>G</strong>
          </span>
          <span>
            UGA <em>gather</em>
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
          aria-label="Open profile"
        >
          <span className="avatar">
            {name
              .split(" ")
              .map((part) => part[0])
              .join("")
              .slice(0, 2) || "AM"}
          </span>
          <span className="profile-name">{name || "Your profile"}</span>
          <Icon name="chevron" size={15} />
        </button>
      </header>

      {view === "calendar" ? (
        <CalendarView
          selectedEvents={events.filter((event) =>
            favorites.includes(event.id),
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

              {loadingOptions && <p>Loading interests and majors...</p>}
              {error && <p role="alert" style={{ color: "#b42318" }}>{error}</p>}
              <div className="form-section">
                <div className="label-row">
                  <span className="field-label">Interests <small>(1–40)</small></span>
                  <span className="selection-count">{selectedInterests.length} selected</span>
                </div>
                <div className="chip-grid">
                  {options?.interests.map(category => (
                    <div key={category.id}>
                      <button className={`choice-chip ${selectedInterests.includes(category.id) ? "selected" : ""}`}
                        type="button" onClick={() => toggleInterest(category.id)}>
                        {selectedInterests.includes(category.id) && <Icon name="check" size={14}/>}
                        {category.name}
                      </button>
                      {category.children.length > 0 && (
                        <button type="button" className="skip-button"
                          onClick={() => setExpandedInterests(previous =>
                            previous.includes(category.id) ? previous.filter(id => id !== category.id) : [...previous, category.id])}>
                          {expandedInterests.includes(category.id) ? "Hide specialties" : "Show specialties"}
                        </button>
                      )}
                      {expandedInterests.includes(category.id) && (
                        <div className="chip-grid">
                          {category.children.map(child => (
                            <button key={child.id} type="button"
                              className={`choice-chip ${selectedInterests.includes(child.id) ? "selected" : ""}`}
                              onClick={() => toggleInterest(child.id)}>
                              {selectedInterests.includes(child.id) && <Icon name="check" size={14}/>}
                              {child.name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div className="form-section">
                <span className="field-label">Majors <small>({options?.major_rules.min ?? 1}–{options?.major_rules.max ?? 2})</small></span>
                {options?.colleges.map(college => (
                  <div key={college.id}>
                    <p>{college.name}</p>
                    <div className="chip-grid">
                      {college.majors.map(major => (
                        <button key={major.id} type="button"
                          className={`choice-chip ${selectedMajors.includes(major.id) ? "selected" : ""}`}
                          onClick={() => toggleMajor(major.id)}>
                          {selectedMajors.includes(major.id) && <Icon name="check" size={14}/>}
                          {major.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="chip-grid">
                  {options?.special_majors.map(major => (
                    <button key={major.id} type="button"
                      className={`choice-chip ${selectedMajors.includes(major.id) ? "selected" : ""}`}
                      onClick={() => toggleMajor(major.id)}>
                      {major.name}
                    </button>
                  ))}
                </div>
              </div>
              <div className="form-section identity-grid">
                <label>
                  <span>Display name (optional, never sent to backend)</span>
                  <input value={name} onChange={event => setName(event.target.value)}
                    placeholder="Your name" />
                </label>
                <label>
                  <span>Week starting Monday</span>
                  <input type="date" value={weekStart}
                    onChange={event => setWeekStart(event.target.value)} />
                </label>
              </div>
              <div className="form-section">
                <p>Busy-time scheduling is not yet available in this screen. Recommendations currently assume no busy blocks.</p>
              </div>

              <div className="question-actions">
                <button className="primary-button" type="button"
                  disabled={loadingOptions || loadingSchedules || !options}
                  onClick={loadRecommendations}>
                  {loadingSchedules ? "Finding events..." : "Find my events"}
                  <Icon name="arrow" size={17}/>
                </button>
              </div>
            </aside>

            {started && (
              <section className="swipe-experience" aria-live="polite">
                <div className="swipe-header">
                  <button
                    className="edit-preferences"
                    type="button"
                    onClick={() => setStarted(false)}
                  >
                    <Icon name="chevron" size={15} /> Edit preferences
                  </button>
                  <div>
                    <strong>
                      {Math.min(currentIndex + 1, recommendations.length)} of{" "}
                      {recommendations.length}
                    </strong>
                    <span>events reviewed</span>
                  </div>
                </div>
                <div className="progress-track">
                  <span
                    style={{
                      width: `${Math.min(
                        (currentIndex / Math.max(recommendations.length, 1)) * 100,
                        100,
                      )}%`,
                    }}
                  />
                </div>

                {currentEvent ? (
                  <>
                    <div className="swipe-stage">
                      {recommendations[currentIndex + 1] && (
                        <div
                          className="swipe-card next-card"
                          aria-hidden="true"
                        />
                      )}
                      <article
                        className={`swipe-card ${
                          swipeDirection ? `swipe-${swipeDirection}` : ""
                        }`}
                        onPointerDown={(event) => {
                          setDragStart(event.clientX)
                          event.currentTarget.setPointerCapture(event.pointerId)
                        }}
                        onPointerUp={(event) => {
                          if (dragStart !== null) {
                            const distance = event.clientX - dragStart
                            if (Math.abs(distance) > 70)
                              handleSwipe(distance > 0)
                          }
                          setDragStart(null)
                        }}
                      >
                        <div className="swipe-card-top">
                          <span className="swipe-category">
                            {currentEvent.category}
                          </span>
                          <span className="swipe-match">
                            {currentEvent.match}% match
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
                          <div className="swipe-location">
                            <Icon name="location" size={18} />
                            <span>{currentEvent.location}</span>
                          </div>
                          <div className="tag-row">
                            {currentEvent.tags.map((tag) => (
                              <span key={tag}>{tag}</span>
                            ))}
                          </div>
                          {currentEvent.reasons.length > 0 && (
                            <div className="tag-row">
                              {currentEvent.reasons.map((reason, index) => <span key={index}>{reason}</span>)}
                            </div>
                          )}
                          {currentEvent.endIsEstimated && <small>End time estimated</small>}
                        </div>
                        <span className="swipe-stamp pass-stamp">PASS</span>
                        <span className="swipe-stamp save-stamp">ADD IT</span>
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
                      {favorites.length} event
                      {favorites.length === 1 ? "" : "s"} added to your calendar
                    </strong>
                    <div className="saved-event-list">
                      {events
                        .filter((event) => favorites.includes(event.id))
                        .map((event) => (
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
                        setCurrentIndex(0)
                        setFavorites([])
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
            <span>Built for better days at the University of Georgia.</span>
            <span>Personalized from {events.length} recommended events</span>
          </footer>
        </>
      )}
    </main>
  )
}
