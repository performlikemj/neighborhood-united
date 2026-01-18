/**
 * MealPlanWeekView Component
 * 
 * Responsive calendar view for meal plans:
 * - Desktop: 7-column grid with 3 rows (B/L/D)
 * - Mobile: Vertical accordion, one day at a time
 */

import React, { useState, useMemo } from 'react'

// Lowercase values match the backend ChefMealPlanItem model
const MEAL_TYPES = ['breakfast', 'lunch', 'dinner', 'snack']
const MEAL_TYPE_LABELS = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snack: 'Snack' }
const MEAL_ICONS = { breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎' }

export default function MealPlanWeekView({
  planDetail,
  onSlotClick,
  readOnly = false,
  currentWeekIndex: controlledWeekIndex,
  onWeekChange
}) {
  const [expandedDay, setExpandedDay] = useState(null)
  // Support both controlled (via props) and uncontrolled (internal) week state
  const [internalWeekIndex, setInternalWeekIndex] = useState(0)
  const currentWeekIndex = controlledWeekIndex ?? internalWeekIndex
  const setCurrentWeekIndex = onWeekChange ?? setInternalWeekIndex

  // Build days with their items
  const daysData = useMemo(() => {
    if (!planDetail) return []

    const { start_date, end_date, days = [] } = planDetail
    const result = []

    const start = new Date(start_date)
    const end = new Date(end_date)

    // Today's date at midnight for comparison
    const today = new Date()
    today.setHours(0, 0, 0, 0)

    // Build a map of existing days by date
    const daysMap = {}
    for (const day of days) {
      daysMap[day.date] = day
    }

    // Iterate through date range
    const current = new Date(start)
    while (current <= end) {
      const dateStr = current.toISOString().split('T')[0]
      const dayName = current.toLocaleDateString('en-US', { weekday: 'long' })
      const dayShort = current.toLocaleDateString('en-US', { weekday: 'short' })
      const dayNum = current.getDate()
      const month = current.toLocaleDateString('en-US', { month: 'short' })

      // Today/past comparison
      const currentMidnight = new Date(current)
      currentMidnight.setHours(0, 0, 0, 0)
      const isToday = currentMidnight.getTime() === today.getTime()
      const isPast = currentMidnight < today

      const existingDay = daysMap[dateStr]
      const items = existingDay?.items || []

      // Map items by meal type
      const itemsByType = {}
      for (const item of items) {
        itemsByType[item.meal_type] = item
      }

      result.push({
        date: dateStr,
        dayName,
        dayShort,
        dayNum,
        month,
        isToday,
        isPast,
        isSkipped: existingDay?.is_skipped || false,
        skipReason: existingDay?.skip_reason || '',
        items: itemsByType,
        dayId: existingDay?.id
      })

      current.setDate(current.getDate() + 1)
    }

    return result
  }, [planDetail])

  // Split days into weeks (7 days each)
  const weeks = useMemo(() => {
    const result = []
    for (let i = 0; i < daysData.length; i += 7) {
      result.push(daysData.slice(i, i + 7))
    }
    return result
  }, [daysData])

  // Current week's days
  const currentWeekDays = weeks[currentWeekIndex] || []
  const totalWeeks = weeks.length
  const hasMultipleWeeks = totalWeeks > 1

  // Find which week contains today and auto-navigate there on load
  React.useEffect(() => {
    if (weeks.length > 0) {
      const todayWeekIndex = weeks.findIndex(week => week.some(day => day.isToday))
      if (todayWeekIndex >= 0) {
        setCurrentWeekIndex(todayWeekIndex)
      }
    }
  }, [weeks.length])

  // Auto-expand first day on mobile
  React.useEffect(() => {
    if (currentWeekDays.length > 0 && expandedDay === null) {
      setExpandedDay(currentWeekDays[0].date)
    }
  }, [currentWeekDays])

  // Week navigation
  const goToPrevWeek = () => setCurrentWeekIndex(i => Math.max(0, i - 1))
  const goToNextWeek = () => setCurrentWeekIndex(i => Math.min(totalWeeks - 1, i + 1))

  // Format week range for display
  const weekRangeLabel = useMemo(() => {
    if (currentWeekDays.length === 0) return ''
    const first = currentWeekDays[0]
    const last = currentWeekDays[currentWeekDays.length - 1]
    if (first.month === last.month) {
      return `${first.month} ${first.dayNum} - ${last.dayNum}`
    }
    return `${first.month} ${first.dayNum} - ${last.month} ${last.dayNum}`
  }, [currentWeekDays])

  const handleSlotClick = (date, mealType, item) => {
    if (readOnly || !onSlotClick) return
    onSlotClick(date, mealType, item)
  }

  if (!planDetail) {
    return <div className="mpw-empty">No plan data</div>
  }

  // Number of days in current week for dynamic grid
  const numDays = currentWeekDays.length

  return (
    <div className="mpw-container">
      {/* Week Navigation */}
      {hasMultipleWeeks && (
        <div className="mpw-week-nav">
          <button
            className="mpw-week-nav-btn"
            onClick={goToPrevWeek}
            disabled={currentWeekIndex === 0}
            aria-label="Previous week"
          >
            ← Prev
          </button>
          <div className="mpw-week-nav-info">
            <span className="mpw-week-label">{weekRangeLabel}</span>
            <span className="mpw-week-indicator">
              Week {currentWeekIndex + 1} of {totalWeeks}
              {currentWeekDays.length < 7 && ` (${currentWeekDays.length} days)`}
            </span>
          </div>
          <button
            className="mpw-week-nav-btn"
            onClick={goToNextWeek}
            disabled={currentWeekIndex === totalWeeks - 1}
            aria-label="Next week"
          >
            Next →
          </button>
        </div>
      )}

      {/* Desktop Grid View */}
      <div className="mpw-grid-desktop" style={{ '--num-days': numDays }}>
        {/* Header Row */}
        <div className="mpw-grid-header">
          <div className="mpw-grid-corner"></div>
          {currentWeekDays.map(day => (
            <div
              key={day.date}
              className={`mpw-grid-day-header ${day.isSkipped ? 'skipped' : ''} ${day.isToday ? 'is-today' : ''} ${day.isPast ? 'is-past' : ''}`}
            >
              <span className="mpw-day-short">{day.dayShort}</span>
              <span className="mpw-day-num">{day.dayNum}</span>
              <span className="mpw-day-month">{day.month}</span>
            </div>
          ))}
        </div>

        {/* Meal Type Rows */}
        {MEAL_TYPES.map(mealType => (
          <div key={mealType} className="mpw-grid-row">
            <div className="mpw-grid-type-label">
              <span className="mpw-type-icon">{MEAL_ICONS[mealType]}</span>
              <span className="mpw-type-name">{MEAL_TYPE_LABELS[mealType]}</span>
            </div>
            {currentWeekDays.map(day => {
              const item = day.items[mealType]
              return (
                <div
                  key={`${day.date}-${mealType}`}
                  className={`mpw-grid-cell ${item ? 'has-meal' : 'empty'} ${day.isSkipped ? 'skipped' : ''} ${readOnly ? 'readonly' : ''} ${day.isToday ? 'is-today' : ''} ${day.isPast ? 'is-past' : ''}`}
                  onClick={() => !day.isSkipped && handleSlotClick(day.date, mealType, item)}
                >
                  {day.isSkipped ? (
                    <span className="mpw-skipped-label">Skipped</span>
                  ) : item ? (
                    <div className={`mpw-meal-card ${item.dishes?.length > 1 ? 'composed' : ''}`}>
                      <span className="mpw-meal-name">{item.name}</span>
                      {item.dishes?.length > 1 && (
                        <span className="mpw-dish-count">{item.dishes.length} dishes</span>
                      )}
                    </div>
                  ) : !readOnly ? (
                    <span className="mpw-add-icon">+</span>
                  ) : null}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Mobile Accordion View */}
      <div className="mpw-accordion-mobile">
        {currentWeekDays.map(day => (
          <div
            key={day.date}
            className={`mpw-accordion-day ${day.isSkipped ? 'skipped' : ''} ${day.isToday ? 'is-today' : ''} ${day.isPast ? 'is-past' : ''}`}
          >
            <button
              className={`mpw-accordion-header ${expandedDay === day.date ? 'expanded' : ''}`}
              onClick={() => setExpandedDay(expandedDay === day.date ? null : day.date)}
            >
              <div className="mpw-accordion-day-info">
                <span className="mpw-accordion-day-name">{day.dayName}</span>
                <span className="mpw-accordion-day-date">{day.month} {day.dayNum}</span>
              </div>
              <div className="mpw-accordion-summary">
                {day.isSkipped ? (
                  <span className="mpw-skipped-badge">Skipped</span>
                ) : (
                  <span className="mpw-meal-count">
                    {Object.keys(day.items).length} / 3 meals
                  </span>
                )}
                <span className="mpw-accordion-chevron">
                  {expandedDay === day.date ? '▲' : '▼'}
                </span>
              </div>
            </button>
            
            {expandedDay === day.date && !day.isSkipped && (
              <div className="mpw-accordion-content">
                {MEAL_TYPES.map(mealType => {
                  const item = day.items[mealType]
                  return (
                    <div 
                      key={mealType}
                      className={`mpw-accordion-slot ${item ? 'has-meal' : 'empty'} ${readOnly ? 'readonly' : ''}`}
                      onClick={() => handleSlotClick(day.date, mealType, item)}
                    >
                      <div className="mpw-accordion-slot-type">
                        <span className="mpw-type-icon">{MEAL_ICONS[mealType]}</span>
                        <span>{MEAL_TYPE_LABELS[mealType]}</span>
                      </div>
                      <div className="mpw-accordion-slot-meal">
                        {item ? (
                          <>
                            <span className="mpw-meal-name">{item.name}</span>
                            {item.dishes?.length > 1 && (
                              <div className="mpw-dishes-breakdown">
                                {item.dishes.map((dish, idx) => (
                                  <span key={idx} className="mpw-dish-item">{dish.name}</span>
                                ))}
                              </div>
                            )}
                            {item.description && !item.dishes?.length && (
                              <span className="mpw-meal-desc">{item.description}</span>
                            )}
                          </>
                        ) : !readOnly ? (
                          <span className="mpw-add-prompt">+ Add meal</span>
                        ) : (
                          <span className="mpw-empty-slot">No meal</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <style>{`
        .mpw-container {
          width: 100%;
        }

        .mpw-empty {
          text-align: center;
          padding: 2rem;
          color: var(--muted, #666);
        }

        /* ========================================
           Week Navigation
           ======================================== */
        .mpw-week-nav {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0.75rem 0;
          margin-bottom: 0.75rem;
          border-bottom: 1px solid var(--border, #e5e7eb);
        }

        .mpw-week-nav-btn {
          padding: 0.5rem 1rem;
          background: var(--surface-2, #f3f4f6);
          border: 1px solid var(--border, #e5e7eb);
          border-radius: 8px;
          font-size: 0.85rem;
          font-weight: 500;
          cursor: pointer;
          color: var(--text, #333);
          transition: all 0.15s;
        }

        .mpw-week-nav-btn:hover:not(:disabled) {
          background: var(--surface, #fff);
          border-color: var(--primary, #5cb85c);
          color: var(--primary, #5cb85c);
        }

        .mpw-week-nav-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .mpw-week-nav-info {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.15rem;
        }

        .mpw-week-label {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text, #333);
        }

        .mpw-week-indicator {
          font-size: 0.75rem;
          color: var(--muted, #666);
        }

        /* ========================================
           Desktop Grid View
           ======================================== */
        .mpw-grid-desktop {
          display: none;
        }

        @media (min-width: 768px) {
          .mpw-grid-desktop {
            display: block;
            border: 1px solid var(--border, #e5e7eb);
            border-radius: 12px;
            overflow: hidden;
          }

          .mpw-accordion-mobile {
            display: none;
          }
        }

        .mpw-grid-header {
          display: grid;
          grid-template-columns: 90px repeat(var(--num-days, 7), 1fr);
          background: var(--surface-2, #f9fafb);
          border-bottom: 1px solid var(--border, #e5e7eb);
        }

        .mpw-grid-corner {
          padding: 0.75rem;
        }

        .mpw-grid-day-header {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.75rem 0.5rem;
          text-align: center;
          border-left: 1px solid var(--border, #e5e7eb);
          min-width: 0;
        }

        .mpw-grid-day-header.skipped {
          opacity: 0.5;
        }

        .mpw-day-short {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--muted, #666);
          text-transform: uppercase;
        }

        .mpw-day-num {
          font-size: 1.1rem;
          font-weight: 700;
          color: var(--text, #333);
        }

        .mpw-day-month {
          font-size: 0.65rem;
          color: var(--muted, #999);
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        /* Today highlight - desktop header */
        .mpw-grid-day-header.is-today {
          background: rgba(92, 184, 92, 0.08);
          border-bottom: 2px solid var(--primary, #5cb85c);
        }

        .mpw-grid-day-header.is-today .mpw-day-num {
          color: var(--primary, #5cb85c);
          font-weight: 800;
        }

        /* Past days dimmed - desktop header */
        .mpw-grid-day-header.is-past:not(.is-today) {
          opacity: 0.65;
        }

        .mpw-grid-row {
          display: grid;
          grid-template-columns: 90px repeat(var(--num-days, 7), 1fr);
          border-bottom: 1px solid var(--border, #e5e7eb);
        }

        .mpw-grid-row:last-child {
          border-bottom: none;
        }

        .mpw-grid-type-label {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.5rem;
          background: var(--surface-2, #f9fafb);
          border-right: 1px solid var(--border, #e5e7eb);
        }

        .mpw-type-icon {
          font-size: 1rem;
          margin-bottom: 0.15rem;
        }

        .mpw-type-name {
          font-size: 0.7rem;
          font-weight: 500;
          color: var(--muted, #666);
        }

        .mpw-grid-cell {
          min-height: 80px;
          padding: 0.5rem;
          border-left: 1px solid var(--border, #e5e7eb);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: background 0.15s;
        }

        .mpw-grid-cell.readonly {
          cursor: default;
        }

        .mpw-grid-cell:not(.readonly):hover {
          background: var(--surface-2, #f9fafb);
        }

        .mpw-grid-cell.skipped {
          background: repeating-linear-gradient(
            45deg,
            transparent,
            transparent 5px,
            var(--surface-2, #f3f4f6) 5px,
            var(--surface-2, #f3f4f6) 10px
          );
          cursor: default;
        }

        /* Today highlight - grid cells */
        .mpw-grid-cell.is-today {
          background: rgba(92, 184, 92, 0.04);
        }

        /* Past days dimmed - grid cells */
        .mpw-grid-cell.is-past:not(.has-meal) {
          opacity: 0.7;
        }

        .mpw-skipped-label {
          font-size: 0.7rem;
          color: var(--muted, #999);
        }

        .mpw-meal-card {
          width: 100%;
          padding: 0.5rem 0.5rem;
          background: var(--primary, #5cb85c);
          color: white;
          border-radius: 6px;
          text-align: center;
          min-height: 44px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
        }

        .mpw-meal-card.composed {
          background: linear-gradient(135deg, var(--primary, #5cb85c), var(--primary-700, #4a9d4a));
          border: 1px solid var(--primary-700, #4a9d4a);
        }

        .mpw-meal-name {
          font-size: 0.8rem;
          font-weight: 500;
          line-height: 1.2;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          word-break: break-word;
        }

        .mpw-dish-count {
          display: block;
          font-size: 0.65rem;
          opacity: 0.9;
          margin-top: 0.15rem;
        }

        .mpw-add-icon {
          font-size: 1.5rem;
          color: var(--muted, #ccc);
        }

        .mpw-grid-cell.empty:not(.readonly):hover .mpw-add-icon {
          color: var(--primary, #5cb85c);
        }

        /* ========================================
           Mobile Accordion View
           ======================================== */
        .mpw-accordion-mobile {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        @media (min-width: 768px) {
          .mpw-accordion-mobile {
            display: none;
          }
        }

        .mpw-accordion-day {
          border: 1px solid var(--border, #e5e7eb);
          border-radius: 10px;
          overflow: hidden;
        }

        .mpw-accordion-day.skipped {
          opacity: 0.6;
        }

        /* Today highlight - mobile accordion */
        .mpw-accordion-day.is-today {
          border-left: 3px solid var(--primary, #5cb85c);
        }

        .mpw-accordion-day.is-today .mpw-accordion-day-name {
          color: var(--primary, #5cb85c);
        }

        /* Past days dimmed - mobile accordion */
        .mpw-accordion-day.is-past:not(.is-today) {
          opacity: 0.7;
        }

        .mpw-accordion-header {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.85rem 1rem;
          background: var(--surface, #fff);
          border: none;
          cursor: pointer;
          text-align: left;
        }

        .mpw-accordion-header.expanded {
          border-bottom: 1px solid var(--border, #e5e7eb);
          background: var(--surface-2, #f9fafb);
        }

        .mpw-accordion-day-info {
          display: flex;
          flex-direction: column;
        }

        .mpw-accordion-day-name {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text, #333);
        }

        .mpw-accordion-day-date {
          font-size: 0.8rem;
          color: var(--muted, #666);
        }

        .mpw-accordion-summary {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .mpw-meal-count {
          font-size: 0.8rem;
          color: var(--muted, #666);
        }

        .mpw-skipped-badge {
          font-size: 0.75rem;
          padding: 0.2rem 0.5rem;
          background: var(--surface-2, #f3f4f6);
          border-radius: 4px;
          color: var(--muted, #666);
        }

        .mpw-accordion-chevron {
          font-size: 0.75rem;
          color: var(--muted, #999);
        }

        .mpw-accordion-content {
          background: var(--surface, #fff);
        }

        .mpw-accordion-slot {
          display: flex;
          align-items: flex-start;
          gap: 1rem;
          padding: 0.85rem 1rem;
          border-bottom: 1px solid var(--border, #eee);
          cursor: pointer;
          transition: background 0.15s;
        }

        .mpw-accordion-slot:last-child {
          border-bottom: none;
        }

        .mpw-accordion-slot.readonly {
          cursor: default;
        }

        .mpw-accordion-slot:not(.readonly):hover {
          background: var(--surface-2, #f9fafb);
        }

        .mpw-accordion-slot-type {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          min-width: 100px;
          font-size: 0.9rem;
          font-weight: 500;
          color: var(--muted, #666);
        }

        .mpw-accordion-slot-meal {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 0.2rem;
        }

        .mpw-accordion-slot.has-meal .mpw-meal-name {
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--text, #333);
        }

        .mpw-meal-desc {
          font-size: 0.8rem;
          color: var(--muted, #666);
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .mpw-dishes-breakdown {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
          margin-top: 0.35rem;
        }

        .mpw-dish-item {
          font-size: 0.75rem;
          padding: 0.15rem 0.5rem;
          background: var(--primary-50, #f0fdf4);
          color: var(--primary-700, #4a9d4a);
          border-radius: 99px;
          border: 1px solid var(--primary-200, #bbf7d0);
        }

        .mpw-add-prompt {
          font-size: 0.9rem;
          color: var(--primary, #5cb85c);
          font-weight: 500;
        }

        .mpw-empty-slot {
          font-size: 0.85rem;
          color: var(--muted, #999);
          font-style: italic;
        }

        /* Dark mode adjustments */
        [data-theme="dark"] .mpw-grid-day-header.is-today {
          background: rgba(92, 184, 92, 0.12);
        }

        [data-theme="dark"] .mpw-grid-cell.is-today {
          background: rgba(92, 184, 92, 0.06);
        }

        [data-theme="dark"] .mpw-grid-day-header.is-past:not(.is-today),
        [data-theme="dark"] .mpw-accordion-day.is-past:not(.is-today) {
          opacity: 0.55;
        }
      `}</style>
    </div>
  )
}

