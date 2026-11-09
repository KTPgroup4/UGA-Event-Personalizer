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
  endTime?: string // events saved before end times existed do not have one
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
const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function toDateKey(year: number, month: number, day: number) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

// "15:26" -> "3:26 PM". UGA events already say "4:00 PM", so those are left alone.
function formatClock(value?: string) {
  if (!value) return ""
  const match = /^(\d{1,2}):(\d{2})$/.exec(value.trim())
  if (!match) return value
  const hour = Number(match[1])
  return `${hour % 12 || 12}:${match[2]} ${hour < 12 ? "AM" : "PM"}`
}

// "4:00 PM – 5:00 PM". A "~" in front of the end means the end time is a guess.
function timeRange(start: string, end?: string, estimated = false) {
  const from = formatClock(start)
  const to = formatClock(end)
  if (!from) return ""
  if (!to) return from
  return `${from} – ${estimated ? "~" : ""}${to}`
}

// Minutes since midnight, for putting a day's events in order. Handles "4:00 PM" and "16:00".
function toMinutes(value?: string) {
  const match = /^(\d{1,2}):(\d{2})\s*([AP]M)?$/i.exec((value ?? "").trim())
  if (!match) return 24 * 60 // no time: show last
  let hour = Number(match[1])
  if (match[3]) hour = (hour % 12) + (match[3].toUpperCase() === "PM" ? 12 : 0)
  return hour * 60 + Number(match[2])
}

export default function CalendarView({
  selectedEvents,
  name,
  major,
  interests,
  onBack,
}: CalendarViewProps) {
  const [displayDate, setDisplayDate] = useState(new Date())
  const [mode, setMode] = useState<"month" | "list">("month")
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState("")
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
        return {
          id: `campus-${event.id}`,
          title: event.title,
          date: event.dateKey,
          time: event.time,
          endTime: event.endTime,
          endEstimated: event.endIsEstimated,
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
        endEstimated: false,
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

  // Only events you added yourself can be removed. Saved UGA events come from the swipe step.
  const removePersonalEvent = (id: string) => {
    setPersonalEvents((current) => current.filter((event) => event.id !== id))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const time = String(form.get("time"))
    const endTime = String(form.get("endTime") || "")

    if (endTime && endTime <= time) {
      setFormError("The end time has to be after the start time.")
      return
    }

    setFormError("")
    setPersonalEvents((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        title: String(form.get("title")),
        date: String(form.get("date")),
        time,
        endTime,
      },
    ])
    formElement.reset()
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
            onClick={() => {
              setShowForm(!showForm)
              setFormError("")
            }}
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
              Start time
              <input name="time" type="time" required />
            </label>
            <label>
              End time (optional)
              <input name="endTime" type="time" />
            </label>
            <button type="submit">Add to calendar</button>
            {formError && <p className="calendar-form-error">{formError}</p>}
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
              const dayEvents = allEvents
                .filter((event) => event.date === dateKey)
                .sort((a, b) => toMinutes(a.time) - toMinutes(b.time))
              return (
                <div
                  className={`calendar-cell ${day ? "" : "outside"}`}
                  key={`${dateKey}-${index}`}
                >
                  {day && <span className="day-number">{day}</span>}
                  {dayEvents.map((event) => {
                    const when = timeRange(
                      event.time,
                      event.endTime,
                      event.endEstimated,
                    )
                    return (
                      <div
                        className={`calendar-event ${event.type}`}
                        key={event.id}
                        title={`${when} ${event.title}${
                          event.endEstimated ? " (end time estimated)" : ""
                        }`}
                      >
                        {when && <small>{when}</small>}
                        {event.title}
                        {event.type === "personal" && (
                          <button
                            className="event-remove"
                            type="button"
                            aria-label={`Remove ${event.title}`}
                            title="Remove this event"
                            onClick={() => removePersonalEvent(event.id)}
                          >
                            ×
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="calendar-list">
            {allEvents
              .slice()
              .sort(
                (a, b) =>
                  a.date.localeCompare(b.date) ||
                  toMinutes(a.time) - toMinutes(b.time),
              )
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
                    <small>
                      {timeRange(event.time, event.endTime, event.endEstimated) ||
                        "All day"}
                    </small>
                  </span>
                  <span className="list-actions">
                    {event.type === "personal" && (
                      <button
                        className="list-remove"
                        type="button"
                        aria-label={`Remove ${event.title}`}
                        onClick={() => removePersonalEvent(event.id)}
                      >
                        Remove
                      </button>
                    )}
                    <i className={`${event.type}-dot`} />
                  </span>
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