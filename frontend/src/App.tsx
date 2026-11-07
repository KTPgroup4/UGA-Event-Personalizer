import { useMemo, useState, type ReactNode } from "react"
import CalendarView from "./CalendarView"

type IconName = "arrow" | "book" | "calendar" | "check" | "chevron" | "clock" | "heart" | "location" | "people" | "search" | "spark" | "star" | "user"

export type CampusEvent = {
  id: number
  title: string
  organizer: string
  day: string
  date: string
  time: string
  period: "Morning" | "Afternoon" | "Evening"
  location: string
  category: string
  tags: string[]
  majors: string[]
  attendees: number
  tone: string
}

const interests = [
  "Technology",
  "Business",
  "Arts & Culture",
  "Sports",
  "Community Service",
  "Career",
  "Wellness",
  "Social",
]

const days = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
]
const periods = ["Morning", "Afternoon", "Evening"] as const

const events: CampusEvent[] = [
  {
    id: 1,
    title: "AI & The Future of Work",
    organizer: "UGA Society for Cyber Security",
    day: "Thursday",
    date: "Oct 24",
    time: "5:30 PM",
    period: "Evening",
    location: "Boyd Graduate Studies, 328",
    category: "Technology",
    tags: ["Technology", "Career"],
    majors: ["Computer Science", "Data Science", "Business"],
    attendees: 84,
    tone: "violet",
  },
  {
    id: 2,
    title: "Creative Portfolio Night",
    organizer: "Lamar Dodd School of Art",
    day: "Friday",
    date: "Oct 25",
    time: "6:00 PM",
    period: "Evening",
    location: "Lamar Dodd, Atrium",
    category: "Arts & Culture",
    tags: ["Arts & Culture", "Career", "Social"],
    majors: ["Graphic Design", "Fine Arts", "Marketing"],
    attendees: 46,
    tone: "coral",
  },
  {
    id: 3,
    title: "Campus Community Garden",
    organizer: "UGArden Club",
    day: "Saturday",
    date: "Oct 26",
    time: "10:00 AM",
    period: "Morning",
    location: "UGArden, South Milledge",
    category: "Community Service",
    tags: ["Community Service", "Wellness"],
    majors: ["Environmental Science", "Biology", "Public Health"],
    attendees: 31,
    tone: "green",
  },
  {
    id: 4,
    title: "Founder Fireside Chat",
    organizer: "UGA Entrepreneurship Program",
    day: "Wednesday",
    date: "Oct 23",
    time: "3:30 PM",
    period: "Afternoon",
    location: "Terry Studio, E-101",
    category: "Business",
    tags: ["Business", "Career", "Technology"],
    majors: ["Business", "Marketing", "Computer Science"],
    attendees: 112,
    tone: "amber",
  },
  {
    id: 5,
    title: "Sunset Yoga at Herty Field",
    organizer: "UGA Recreational Sports",
    day: "Tuesday",
    date: "Oct 22",
    time: "5:00 PM",
    period: "Evening",
    location: "Herty Field",
    category: "Wellness",
    tags: ["Wellness", "Sports", "Social"],
    majors: [],
    attendees: 58,
    tone: "blue",
  },
  {
    id: 6,
    title: "Product Design Sprint",
    organizer: "UGA Design Club",
    day: "Monday",
    date: "Oct 21",
    time: "2:00 PM",
    period: "Afternoon",
    location: "Miller Learning Center, 250",
    category: "Technology",
    tags: ["Technology", "Arts & Culture", "Career"],
    majors: ["Computer Science", "Graphic Design", "Business"],
    attendees: 39,
    tone: "pink",
  },
]

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
  const [name, setName] = useState("Alex Morgan")
  const [major, setMajor] = useState("Computer Science")
  const [selectedInterests, setSelectedInterests] = useState([
    "Technology",
    "Career",
    "Social",
  ])
  const [selectedDays, setSelectedDays] = useState([
    "Thursday",
    "Friday",
    "Saturday",
  ])
  const [selectedPeriods, setSelectedPeriods] = useState<string[]>(["Evening"])
  const [favorites, setFavorites] = useState<number[]>([])
  const [updated, setUpdated] = useState(false)
  const [started, setStarted] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [swipeDirection, setSwipeDirection] = useState<"left" | "right" | null>(
    null,
  )
  const [dragStart, setDragStart] = useState<number | null>(null)
  const [view, setView] = useState<"discover" | "calendar">("discover")

  const recommendations = useMemo(() => {
    return events
      .map((event) => {
        const interestMatches = event.tags.filter((tag) =>
          selectedInterests.includes(tag),
        ).length
        const majorMatch = event.majors.includes(major)
        const dayMatch = selectedDays.includes(event.day)
        const periodMatch = selectedPeriods.includes(event.period)
        const score =
          interestMatches * 25 +
          (majorMatch ? 20 : 0) +
          (dayMatch ? 15 : 0) +
          (periodMatch ? 15 : 0)
        const match = Math.min(98, Math.max(62, 58 + score / 2))
        return { ...event, match: Math.round(match) }
      })
      .sort((a, b) => b.match - a.match)
  }, [major, selectedDays, selectedInterests, selectedPeriods])

  const toggle = (
    value: string,
    list: string[],
    setList: (items: string[]) => void,
  ) => {
    setUpdated(false)
    setList(
      list.includes(value)
        ? list.filter((item) => item !== value)
        : [...list, value],
    )
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
          major={major}
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

              <div className="form-section">
                <div className="label-row">
                  <span className="field-label">
                    Interests <small>(pick any)</small>
                  </span>
                  <span className="selection-count">
                    {selectedInterests.length} selected
                  </span>
                </div>
                <div className="chip-grid">
                  {interests.map((interest) => (
                    <button
                      className={`choice-chip ${
                        selectedInterests.includes(interest) ? "selected" : ""
                      }`}
                      key={interest}
                      type="button"
                      onClick={() =>
                        toggle(
                          interest,
                          selectedInterests,
                          setSelectedInterests,
                        )
                      }
                    >
                      {selectedInterests.includes(interest) && (
                        <Icon name="check" size={14} />
                      )}
                      {interest}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-section identity-grid">
                <label>
                  <span>Your name</span>
                  <input
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value)
                      setUpdated(false)
                    }}
                    placeholder="e.g. Alex Morgan"
                  />
                </label>
                <label>
                  <span>Your major</span>
                  <select
                    value={major}
                    onChange={(e) => {
                      setMajor(e.target.value)
                      setUpdated(false)
                    }}
                  >
                    <option>Computer Science</option>
                    <option>Business</option>
                    <option>Graphic Design</option>
                    <option>Environmental Science</option>
                    <option>Biology</option>
                    <option>Marketing</option>
                    <option>Public Health</option>
                  </select>
                </label>
              </div>

              <div className="form-section">
                <span className="field-label">Days you’re usually free</span>
                <div className="day-picker" aria-label="Available days">
                  {days.map((day) => (
                    <button
                      className={selectedDays.includes(day) ? "selected" : ""}
                      type="button"
                      key={day}
                      onClick={() => toggle(day, selectedDays, setSelectedDays)}
                    >
                      <span>{day.slice(0, 3)}</span>
                      <small>{day.slice(0, 1)}</small>
                    </button>
                  ))}
                </div>
                <span className="field-label time-label">Best time of day</span>
                <div className="period-picker">
                  {periods.map((period) => (
                    <button
                      className={
                        selectedPeriods.includes(period) ? "selected" : ""
                      }
                      type="button"
                      key={period}
                      onClick={() =>
                        toggle(period, selectedPeriods, setSelectedPeriods)
                      }
                    >
                      <Icon name="clock" size={15} /> {period}
                    </button>
                  ))}
                </div>
              </div>

              <div className="question-actions">
                <button
                  className="skip-button"
                  type="button"
                  onClick={() => setStarted(true)}
                >
                  Skip for now
                </button>
                <button
                  className={`primary-button ${updated ? "success" : ""}`}
                  type="button"
                  onClick={() => {
                    setUpdated(true)
                    setStarted(true)
                    setCurrentIndex(0)
                    setFavorites([])
                  }}
                >
                  Continue <Icon name="arrow" size={17} />
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
                        (currentIndex / recommendations.length) * 100,
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
                          <div className="swipe-attendance">
                            <Icon name="people" size={17} />
                            <span>
                              {currentEvent.attendees} UGA students are going
                            </span>
                          </div>
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
            <span>Personalized from {events.length} upcoming events</span>
          </footer>
        </>
      )}
    </main>
  )
}
