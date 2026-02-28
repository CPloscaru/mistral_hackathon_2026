/**
 * CalendarTool - Monthly/annual calendar view for SMART plan events
 *
 * Monthly: 7-column CSS grid with events positioned on days
 * Annual: 12 miniature months with colored dots
 * No external dependencies — pure CSS grid
 */

import { useState, useEffect, useRef } from 'react'

function buildBackendUrl() {
  return `http://${window.location.hostname}:8000`
}

const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
]

function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year, month) {
  const day = new Date(year, month, 1).getDay()
  return day === 0 ? 6 : day - 1 // Monday = 0
}

function formatDate(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function CalendarTool({ sessionId }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState('month') // month | year
  const [currentDate, setCurrentDate] = useState(() => new Date())
  const [popover, setPopover] = useState(null)
  const popoverRef = useRef(null)

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  useEffect(() => {
    if (!sessionId) return
    fetch(`${buildBackendUrl()}/tools/calendar?session_id=${sessionId}`)
      .then(r => r.json())
      .then(data => {
        setEvents(data.events || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sessionId])

  // Close popover on outside click
  useEffect(() => {
    function handleClick(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setPopover(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])


  function prevMonth() {
    setCurrentDate(new Date(year, month - 1, 1))
  }

  function nextMonth() {
    setCurrentDate(new Date(year, month + 1, 1))
  }

  function getEventsForDate(dateStr) {
    return events.filter(ev => ev.date === dateStr)
  }

  function handleEventClick(ev, e) {
    const rect = e.target.getBoundingClientRect()
    setPopover({
      event: ev,
      x: Math.min(rect.left, window.innerWidth - 300),
      y: rect.bottom + 8,
    })
  }

  if (loading) {
    return <div className="crm-tool__empty">Chargement...</div>
  }

  // Build monthly grid
  function renderMonthGrid(gridYear, gridMonth, mini = false) {
    const daysInMonth = getDaysInMonth(gridYear, gridMonth)
    const firstDay = getFirstDayOfWeek(gridYear, gridMonth)
    const prevMonthDays = getDaysInMonth(gridYear, gridMonth - 1)
    const today = new Date()
    const todayStr = formatDate(today.getFullYear(), today.getMonth(), today.getDate())

    const cells = []

    // Previous month fill
    for (let i = firstDay - 1; i >= 0; i--) {
      const d = prevMonthDays - i
      if (mini) {
        cells.push(<div key={`p${d}`} className="calendar-tool__mini-day" />)
      } else {
        cells.push(
          <div key={`p${d}`} className="calendar-tool__day calendar-tool__day--other-month">
            <div className="calendar-tool__day-number">{d}</div>
          </div>
        )
      }
    }

    // Current month days
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = formatDate(gridYear, gridMonth, d)
      const dayEvents = getEventsForDate(dateStr)
      const isToday = dateStr === todayStr
      if (mini) {
        const topEvent = dayEvents[0]
        cells.push(
          <div
            key={d}
            className={`calendar-tool__mini-day ${dayEvents.length > 0 ? 'calendar-tool__mini-day--has-event' : ''}`}
          >
            <span>{d}</span>
            {topEvent && (
              <span className={`calendar-tool__mini-dot calendar-tool__mini-dot--${topEvent.type}`} />
            )}
          </div>
        )
      } else {
        cells.push(
          <div
            key={d}
            className={`calendar-tool__day ${isToday ? 'calendar-tool__day--today' : ''}`}
          >
            <div className="calendar-tool__day-number">{d}</div>
            {dayEvents.map((ev, evIdx) => (
              <div
                key={ev.id}
                className={`calendar-tool__event calendar-tool__event--${ev.type}`}
                onClick={(e) => handleEventClick(ev, e)}
                title={ev.titre}
              >
                {ev.titre}
              </div>
            ))}
          </div>
        )
      }
    }

    // Next month fill
    const totalCells = cells.length
    const remaining = (7 - (totalCells % 7)) % 7
    for (let d = 1; d <= remaining; d++) {
      if (mini) {
        cells.push(<div key={`n${d}`} className="calendar-tool__mini-day" />)
      } else {
        cells.push(
          <div key={`n${d}`} className="calendar-tool__day calendar-tool__day--other-month">
            <div className="calendar-tool__day-number">{d}</div>
          </div>
        )
      }
    }

    return cells
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div className="calendar-tool__controls">
        {view === 'month' && (
          <div className="calendar-tool__nav">
            <button className="calendar-tool__nav-btn" onClick={prevMonth}>&larr;</button>
            <span className="calendar-tool__month-label">
              {MONTH_NAMES[month]} {year}
            </span>
            <button className="calendar-tool__nav-btn" onClick={nextMonth}>&rarr;</button>
          </div>
        )}
        {view === 'year' && (
          <div className="calendar-tool__nav">
            <button className="calendar-tool__nav-btn" onClick={() => setCurrentDate(new Date(year - 1, 0, 1))}>&larr;</button>
            <span className="calendar-tool__month-label">{year}</span>
            <button className="calendar-tool__nav-btn" onClick={() => setCurrentDate(new Date(year + 1, 0, 1))}>&rarr;</button>
          </div>
        )}
        <div className="calendar-tool__view-toggle">
          <button
            className={`calendar-tool__view-btn ${view === 'month' ? 'calendar-tool__view-btn--active' : ''}`}
            onClick={() => setView('month')}
          >
            Mois
          </button>
          <button
            className={`calendar-tool__view-btn ${view === 'year' ? 'calendar-tool__view-btn--active' : ''}`}
            onClick={() => setView('year')}
          >
            Année
          </button>
        </div>
      </div>

      {view === 'month' && (
        <div className="calendar-tool__grid">
          {WEEKDAYS.map(wd => (
            <div key={wd} className="calendar-tool__weekday">{wd}</div>
          ))}
          {renderMonthGrid(year, month)}
        </div>
      )}

      {view === 'year' && (
        <div className="calendar-tool__annual">
          {Array.from({ length: 12 }, (_, m) => (
            <div key={m} className="calendar-tool__mini-month">
              <div className="calendar-tool__mini-month-title">{MONTH_NAMES[m]}</div>
              <div className="calendar-tool__mini-grid">
                {renderMonthGrid(year, m, true)}
              </div>
            </div>
          ))}
        </div>
      )}

      {popover && (
        <div
          ref={popoverRef}
          className="calendar-tool__popover"
          style={{ left: popover.x, top: popover.y }}
        >
          <div className="calendar-tool__popover-title">{popover.event.titre}</div>
          <div className="calendar-tool__popover-date">{popover.event.date} — {popover.event.type}</div>
          <div className="calendar-tool__popover-desc">{popover.event.description}</div>
        </div>
      )}

      {events.length === 0 && (
        <div className="crm-tool__empty" style={{ marginTop: '1rem' }}>
          Aucun événement dans le calendrier pour le moment.
        </div>
      )}
    </div>
  )
}

export default CalendarTool
