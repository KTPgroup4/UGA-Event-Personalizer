import { useMemo, useState, type FormEvent } from "react"
import type { CampusEvent, PersonalEvent } from "./App"
import type { BusyBlock } from "./api"
import "./calendar.css"

type CalendarViewProps = {
  // UGA events the student saved by swiping right
  savedEvents: CampusEvent[]
  // Events the student added by hand
  personalEvents: PersonalEvent[]
  // Busy times from the questionnaire, shown in the week the student is planning
  busyBlocks: BusyBlock[]
  // The Monday of that week, "YYYY-MM-DD"
  weekStart: string
  name: string
  major: string
  interests: string[]
  onBack: () => void
  onAddPersonal: (event: PersonalEvent) => void
  onRemovePersonal: (id: string) => void
  onRemoveSaved: (id: string) => void
}

// Days of the week in the same order as the planned week, which starts on a Monday.
const WEEK_ORDER: BusyBlock["day"][] = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
]

// The date of `day` inside the week that starts on `weekStart` (a Monday), as "YYYY-MM-DD".
function dateInWeek(weekStart: string, day: BusyBlock["day"]) {
  const date = new Date(weekStart + "T12:00:00Z")
  date.setUTCDate(date.getUTCDate() + WEEK_ORDER.indexOf(day))
  return date.toISOString().slice(0, 10)
}

// "2026-11-09" -> "Nov 9"
function weekLabel(weekStart: string) {
  return new Date(weekStart + "T12:00:00Z").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  })
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
  savedEvents,
  personalEvents,
  busyBlocks,
  weekStart,
  name,
  major,
  interests,
  onBack,
  onAddPersonal,
  onRemovePersonal,
  onRemoveSaved,
}: CalendarViewProps) {
  const [displayDate, setDisplayDate] = useState(new Date())
  const [mode, setMode] = useState<"month" | "list">("month")
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState("")
  const year = displayDate.getFullYear()
  const month = displayDate.getMonth()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const startingDay = new Date(year, month, 1).getDay()

  const savedCampusEvents = useMemo(
    () =>
      savedEvents.map((event) => {
        return {
          id: `campus-${event.id}`,
          eventId: event.id,
          title: event.title,
          date: event.dateKey,
          time: event.time,
          endTime: event.endTime,
          endEstimated: event.endIsEstimated,
          type: "campus" as const,
        }
      }),
    [savedEvents],
  )

  // Each busy block appears once, on its day of the week the student is planning.
  const busyEvents = useMemo(
    () =>
      busyBlocks.map((block, index) => ({
        id: `busy-${index}`,
        title: "Busy",
        date: dateInWeek(weekStart, block.day),
        time: block.start,
        endTime: block.end,
        endEstimated: false,
        type: "busy" as const,
      })),
    [busyBlocks, weekStart],
  )

  const allEvents = useMemo(
    () => [
      ...savedCampusEvents,
      ...busyEvents,
      ...personalEvents.map((event) => ({
        ...event,
        endEstimated: false,
        type: "personal" as const,
      })),
    ],
    [personalEvents, savedCampusEvents, busyEvents],
  )

  const cells = Array.from({ length: 42 }, (_, index) => {
    const day = index - startingDay + 1
    return day > 0 && day <= daysInMonth ? day : null
  })

  const changeMonth = (direction: number) => {
    setDisplayDate(new Date(year, month + direction, 1))
  }

  // Personal and saved events can be removed. Busy times are changed in "Edit answers".
  const removeEvent = (event: (typeof allEvents)[number]) => {
    if (event.type === "personal") onRemovePersonal(event.id)
    if (event.type === "campus") onRemoveSaved(event.eventId)
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
    onAddPersonal({
      id: crypto.randomUUID(),
      title: String(form.get("title")).trim(),
      date: String(form.get("date")),
      time,
      endTime,
    })
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
          {savedEvents.length ? (
            savedEvents.map((event) => (
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
          {busyBlocks.length > 0 && (
            <span>
              <i className="busy-dot" /> Busy
            </span>
          )}
        </div>

        {busyBlocks.length > 0 && (
          <p className="calendar-legend-note">
            Busy times show in the week you are planning (the week of{" "}
            {weekLabel(weekStart)}). Change them with Edit answers.
          </p>
        )}

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
                        {event.type !== "busy" && (
                          <button
                            className="event-remove"
                            type="button"
                            aria-label={`Remove ${event.title}`}
                            title="Remove this event"
                            onClick={() => removeEvent(event)}
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
                    {event.type !== "busy" && (
                      <button
                        className="list-remove"
                        type="button"
                        aria-label={`Remove ${event.title}`}
                        onClick={() => removeEvent(event)}
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