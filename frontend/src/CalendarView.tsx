import { useEffect, useMemo, useState, type FormEvent } from "react"
import type { CampusEvent } from "./App"

type CalendarViewProps = {
  selectedEvents: CampusEvent[]
  name: string
  major: string
  interests: string[]
  onBack: () => void
}

type PersonalEvent = {
  id: string
  title: string
  date: string
  time: string
}

const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
]
const monthLookup: Record<string, number> = {
  Jan: 0,
  Feb: 1,
  Mar: 2,
  Apr: 3,
  May: 4,
  Jun: 5,
  Jul: 6,
  Aug: 7,
  Sep: 8,
  Oct: 9,
  Nov: 10,
  Dec: 11,
}
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function toDateKey(year: number, month: number, day: number) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

export default function CalendarView({
  selectedEvents,
  name,
  major,
  interests,
  onBack,
}: CalendarViewProps) {
  const [displayDate, setDisplayDate] = useState(new Date(2026, 9, 1))
  const [mode, setMode] = useState<"month" | "list">("month")
  const [showForm, setShowForm] = useState(false)
  const [personalEvents, setPersonalEvents] = useState<PersonalEvent[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("uga-personal-events") || "[]")
    } catch {
      return []
    }
  })

  useEffect(() => {
    localStorage.setItem("uga-personal-events", JSON.stringify(personalEvents))
  }, [personalEvents])

  const year = displayDate.getFullYear()
  const month = displayDate.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const startingDay = new Date(year, month, 1).getDay()

  const savedCampusEvents = useMemo(
    () =>
      selectedEvents.map((event) => {
        const [monthName, day] = event.date.split(" ")
        return {
          id: `campus-${event.id}`,
          title: event.title,
          date: toDateKey(2026, monthLookup[monthName] ?? 9, Number(day)),
          time: event.time,
          type: "campus" as const,
        }
      }),
    [selectedEvents],
  )

  const allEvents = useMemo(
    () => [
      ...savedCampusEvents,
      ...personalEvents.map((event) => ({
        ...event,
        type: "personal" as const,
      })),
    ],
    [personalEvents, savedCampusEvents],
  )

  const cells = Array.from({ length: 42 }, (_, index) => {
    const day = index - startingDay + 1
    return day > 0 && day <= daysInMonth ? day : null
  })

  const changeMonth = (direction: number) => {
    setDisplayDate(new Date(year, month + direction, 1))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setPersonalEvents((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        title: String(form.get("title")),
        date: String(form.get("date")),
        time: String(form.get("time")),
      },
    ])
    event.currentTarget.reset()
    setShowForm(false)
  }

  const initials =
    name
      .split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2) || "A"

  return (
    <div className="calendar-page">
      <aside className="calendar-profile">
        <div className="calendar-person">
          <span>{initials}</span>
          <div>
            <strong>{name || "UGA Student"}</strong>
            <small>{major}</small>
          </div>
        </div>
        <p className="profile-label">My interests</p>
        <div className="calendar-interests">
          {interests.slice(0, 4).map((interest) => (
            <span key={interest}>{interest}</span>
          ))}
        </div>
        <hr />
        <p className="profile-label">Saved events</p>
        <div className="profile-event-list">
          {selectedEvents.length ? (
            selectedEvents.map((event) => (
              <span key={event.id}>
                <i />
                {event.title}
              </span>
            ))
          ) : (
            <small>No events saved yet.</small>
          )}
        </div>
        <button type="button" onClick={onBack}>
          Edit answers
        </button>
      </aside>

      <section className="calendar-main">
        <div className="calendar-title-row">
          <div>
            <p>Step 2 of 2</p>
            <h1>My calendar</h1>
          </div>
          <button
            className="add-event-button"
            type="button"
            onClick={() => setShowForm(!showForm)}
          >
            {showForm ? "Close" : "+ Add event"}
          </button>
        </div>

        <div className="calendar-legend">
          <span>
            <i className="personal-dot" /> Added by me
          </span>
          <span>
            <i className="campus-dot" /> Saved UGA events
          </span>
        </div>

        {showForm && (
          <form className="calendar-form" onSubmit={handleSubmit}>
            <label>
              Event title
              <input name="title" placeholder="Study group" required />
            </label>
            <label>
              Date
              <input name="date" type="date" required />
            </label>
            <label>
              Time
              <input name="time" type="time" required />
            </label>
            <button type="submit">Add to calendar</button>
          </form>
        )}

        <div className="calendar-toolbar">
          <div className="month-controls">
            <button type="button" onClick={() => changeMonth(-1)}>
              ←
            </button>
            <strong>
              {monthNames[month]} {year}
            </strong>
            <button type="button" onClick={() => changeMonth(1)}>
              →
            </button>
          </div>
          <div className="view-controls">
            <button
              className={mode === "month" ? "active" : ""}
              type="button"
              onClick={() => setMode("month")}
            >
              Month
            </button>
            <button
              className={mode === "list" ? "active" : ""}
              type="button"
              onClick={() => setMode("list")}
            >
              List
            </button>
          </div>
        </div>

        {mode === "month" ? (
          <div className="calendar-grid">
            {weekdays.map((day) => (
              <div className="weekday" key={day}>
                {day}
              </div>
            ))}
            {cells.map((day, index) => {
              const dateKey = day ? toDateKey(year, month, day) : ""
              const dayEvents = allEvents.filter(
                (event) => event.date === dateKey,
              )
              return (
                <div
                  className={`calendar-cell ${day ? "" : "outside"}`}
                  key={`${dateKey}-${index}`}
                >
                  {day && <span className="day-number">{day}</span>}
                  {dayEvents.map((event) => (
                    <div
                      className={`calendar-event ${event.type}`}
                      key={event.id}
                      title={`${event.time} ${event.title}`}
                    >
                      {event.time && <small>{event.time}</small>}
                      {event.title}
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="calendar-list">
            {allEvents
              .slice()
              .sort((a, b) => a.date.localeCompare(b.date))
              .map((event) => (
                <div key={event.id}>
                  <time>
                    {new Date(`${event.date}T12:00:00`).toLocaleDateString(
                      "en-US",
                      { month: "short", day: "numeric" },
                    )}
                  </time>
                  <span>
                    <strong>{event.title}</strong>
                    <small>{event.time || "All day"}</small>
                  </span>
                  <i className={`${event.type}-dot`} />
                </div>
              ))}
            {!allEvents.length && (
              <p className="calendar-empty">
                Swipe right on an event or add your own to get started.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  )
}