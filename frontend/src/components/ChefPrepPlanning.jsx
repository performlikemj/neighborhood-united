/**
 * Chef Prep Planning Component - Live View
 *
 * Shows upcoming commitments and shopping list immediately without requiring
 * plan generation. Chefs can see what they need to cook and buy right away.
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  getLiveCommitments,
  getLiveShoppingList
} from '../api/chefPrepPlanClient'

// Helper: format date for display
function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr + 'T00:00:00')
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    }).format(date)
  } catch {
    return dateStr
  }
}

// Timing status badge colors and human-readable labels
const TIMING_CONFIG = {
  optimal: { label: 'On track', bg: 'var(--success-bg)', color: 'var(--success)' },
  tight: { label: 'Buy soon', bg: 'var(--warning-bg)', color: 'var(--warning)' },
  problematic: { label: 'Plan ahead', bg: 'var(--warning-bg)', color: 'var(--warning)' },
  impossible: { label: "Won't last", bg: 'var(--danger-bg)', color: 'var(--danger)' }
}

// Storage type icons
const STORAGE_ICONS = {
  refrigerated: '🧊',
  frozen: '❄️',
  pantry: '🏠',
  counter: '🍌'
}

// Days selector options
const DAYS_OPTIONS = [7, 14, 21, 30]

function StatusBadge({ status }) {
  const config = TIMING_CONFIG[status] || { label: status, bg: 'var(--neutral-bg)', color: 'var(--neutral)' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '12px',
        fontSize: '0.75rem',
        fontWeight: 500,
        background: config.bg,
        color: config.color
      }}
    >
      {config.label}
    </span>
  )
}

function SummaryCard({ title, value, subtitle, icon }) {
  return (
    <div className="card" style={{ padding: '1rem', textAlign: 'center' }}>
      {icon && <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{icon}</div>}
      <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--color-primary)' }}>{value}</div>
      <div style={{ fontWeight: 500 }}>{title}</div>
      {subtitle && <div className="muted" style={{ fontSize: '0.85rem' }}>{subtitle}</div>}
    </div>
  )
}

// Empty state: Chef has no upcoming meals
function EmptyStateNoMeals({ onNavigateToClients }) {
  return (
    <div className="card" style={{ padding: '2rem', textAlign: 'center', maxWidth: '500px', margin: '2rem auto' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📋</div>
      <h3 style={{ marginBottom: '0.5rem' }}>No Upcoming Meals</h3>
      <p className="muted" style={{ marginBottom: '1.5rem' }}>
        Create meal plans for your clients to see what you need to cook and buy.
        Your shopping list and upcoming meals will appear here automatically.
      </p>
      <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', textAlign: 'left' }}>
        <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>How it works:</div>
        <ul style={{ margin: 0, paddingLeft: '1.25rem' }} className="muted">
          <li>Create meal plans for clients in the Clients tab</li>
          <li>Your shopping list is automatically calculated</li>
          <li>Purchase timing is based on ingredient shelf life</li>
        </ul>
      </div>
      {onNavigateToClients && (
        <button className="btn btn-primary" onClick={onNavigateToClients}>
          Go to Clients
        </button>
      )}
    </div>
  )
}

export default function ChefPrepPlanning({ onNavigateToClients }) {
  // State - split loading for progressive UX
  const [commitmentsLoading, setCommitmentsLoading] = useState(true)
  const [shoppingLoading, setShoppingLoading] = useState(false)
  const [error, setError] = useState(null)
  const [daysAhead, setDaysAhead] = useState(7)
  const [listGroupBy, setListGroupBy] = useState('date')
  const [commitments, setCommitments] = useState([])
  const [shoppingList, setShoppingList] = useState({})
  const [summary, setSummary] = useState(null)
  const [totalItems, setTotalItems] = useState(0)

  // Compute unique clients from commitments
  const uniqueClients = useMemo(() => {
    const clientNames = new Set()
    commitments.forEach(c => {
      if (c.customer_name) clientNames.add(c.customer_name)
    })
    return Array.from(clientNames)
  }, [commitments])

  // Group commitments by client for display
  const commitmentsByClient = useMemo(() => {
    const grouped = {}
    commitments.forEach(c => {
      const client = c.customer_name || 'Other'
      if (!grouped[client]) grouped[client] = []
      grouped[client].push(c)
    })
    return grouped
  }, [commitments])

  // Load commitments first (fast)
  const loadCommitments = useCallback(async () => {
    setCommitmentsLoading(true)
    setError(null)
    try {
      const data = await getLiveCommitments({ days: daysAhead })
      setCommitments(data?.commitments || [])
      setSummary(data?.summary)
    } catch (err) {
      console.error('Failed to load commitments:', err)
      setError('Failed to load meal data. Please try again.')
    } finally {
      setCommitmentsLoading(false)
    }
  }, [daysAhead])

  // Load shopping list (slower - may involve AI)
  const loadShoppingList = useCallback(async () => {
    setShoppingLoading(true)
    try {
      const data = await getLiveShoppingList({ days: daysAhead, groupBy: listGroupBy })
      setShoppingList(data?.shopping_list || {})
      setTotalItems(data?.total_items || 0)
    } catch (err) {
      console.error('Failed to load shopping list:', err)
      // Don't set main error - shopping list failure shouldn't block the view
    } finally {
      setShoppingLoading(false)
    }
  }, [daysAhead, listGroupBy])

  // Load commitments on mount and when days change
  useEffect(() => {
    loadCommitments()
  }, [loadCommitments])

  // Load shopping list after commitments, or when groupBy changes
  useEffect(() => {
    if (!commitmentsLoading && commitments.length > 0) {
      loadShoppingList()
    }
  }, [commitmentsLoading, commitments.length, listGroupBy, loadShoppingList])

  // Refresh all data
  const handleRefresh = useCallback(() => {
    loadCommitments()
    // Shopping list will reload via the useEffect above
  }, [loadCommitments])

  // Render shopping list items
  const renderShoppingItems = () => {
    if (shoppingLoading) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <div style={{ marginBottom: '0.5rem' }}>Calculating shopping list...</div>
          <div className="muted" style={{ fontSize: '0.85rem' }}>
            Analyzing ingredients and shelf life
          </div>
        </div>
      )
    }

    const groupKeys = Object.keys(shoppingList).sort()

    if (groupKeys.length === 0) {
      return <div className="muted">No items to purchase</div>
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {groupKeys.map(groupKey => {
          const items = shoppingList[groupKey]
          const groupLabel = listGroupBy === 'date'
            ? formatDate(groupKey)
            : groupKey.charAt(0).toUpperCase() + groupKey.slice(1)

          return (
            <div key={groupKey}>
              <h4 style={{ margin: '0 0 0.75rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {listGroupBy === 'category' && STORAGE_ICONS[groupKey]}
                {groupLabel}
                <span className="muted" style={{ fontWeight: 400, fontSize: '0.85rem' }}>
                  ({items.length} item{items.length !== 1 ? 's' : ''})
                </span>
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {items.map((item, idx) => (
                  <div
                    key={idx}
                    className="card"
                    style={{
                      padding: '0.75rem 1rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem'
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 500 }}>
                        {item.ingredient}
                      </div>
                      <div className="muted" style={{ fontSize: '0.85rem' }}>
                        {item.quantity} {item.unit}
                        {item.meals && item.meals.length > 0 && (
                          <span> • {item.meals.length} meal{item.meals.length !== 1 ? 's' : ''}</span>
                        )}
                      </div>
                      {/* Show which meals use this ingredient */}
                      {item.meals && item.meals.length > 0 && (
                        <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {item.meals.slice(0, 3).map((meal, mIdx) => (
                            <span
                              key={mIdx}
                              style={{
                                fontSize: '0.7rem',
                                padding: '1px 6px',
                                borderRadius: '8px',
                                background: 'var(--surface-2)',
                                color: 'var(--muted)'
                              }}
                            >
                              {meal.name?.split(' - ')[0] || meal.name}
                            </span>
                          ))}
                          {item.meals.length > 3 && (
                            <span style={{ fontSize: '0.7rem', opacity: 0.7 }}>
                              +{item.meals.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <StatusBadge status={item.timing_status} />
                      <div className="muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                        {STORAGE_ICONS[item.storage]} {item.shelf_life_days}d shelf life
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Render commitments by client
  const renderCommitments = () => {
    if (commitments.length === 0) {
      return <div className="muted">No upcoming meals</div>
    }

    // Group by client if multiple clients
    if (uniqueClients.length > 1) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {Object.entries(commitmentsByClient).map(([clientName, clientCommitments]) => (
            <div key={clientName}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '0.75rem',
                paddingBottom: '0.5rem',
                borderBottom: '2px solid var(--success)'
              }}>
                <span style={{ fontSize: '1.1rem' }}>👤</span>
                <span style={{ fontWeight: 600, fontSize: '1rem' }}>{clientName}</span>
                <span className="muted" style={{ fontSize: '0.85rem' }}>
                  ({clientCommitments.length} meals, {clientCommitments.reduce((s, c) => s + c.servings, 0)} servings)
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingLeft: '0.5rem' }}>
                {clientCommitments.map((c, idx) => {
                  const typeColors = {
                    'client_meal_plan': { bg: 'var(--success-bg)', color: 'var(--success)', dot: 'var(--success)' },
                    'meal_event': { bg: 'var(--info-bg)', color: 'var(--info)', dot: 'var(--info)' },
                    'service_order': { bg: 'var(--warning-bg)', color: 'var(--warning)', dot: 'var(--warning)' }
                  }
                  const colors = typeColors[c.commitment_type] || typeColors.service_order

                  return (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
                      <div style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: colors.dot,
                        flexShrink: 0
                      }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.meal_name}
                        </div>
                        <div className="muted" style={{ fontSize: '0.85rem' }}>
                          {formatDate(c.service_date)} • {c.servings} servings
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )
    }

    // Single client or no client grouping
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {commitments.map((c, idx) => {
          const typeColors = {
            'client_meal_plan': { bg: 'var(--success-bg)', color: 'var(--success)', dot: 'var(--success)' },
            'meal_event': { bg: 'var(--info-bg)', color: 'var(--info)', dot: 'var(--info)' },
            'service_order': { bg: 'var(--warning-bg)', color: 'var(--warning)', dot: 'var(--warning)' }
          }
          const colors = typeColors[c.commitment_type] || typeColors.service_order
          const typeLabel = c.commitment_type === 'client_meal_plan' ? 'Client Plan'
            : c.commitment_type === 'meal_event' ? 'Meal Event' : 'Service'

          return (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                background: colors.dot,
                flexShrink: 0
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.meal_name}
                </div>
                <div className="muted" style={{ fontSize: '0.85rem' }}>
                  {formatDate(c.service_date)} • {c.servings} servings
                  {c.customer_name && <span> • <strong>{c.customer_name}</strong></span>}
                </div>
              </div>
              <span style={{
                padding: '2px 8px',
                borderRadius: '12px',
                fontSize: '0.75rem',
                background: colors.bg,
                color: colors.color,
                flexShrink: 0
              }}>
                {typeLabel}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  if (commitmentsLoading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <div className="muted">Loading meals...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center', borderColor: 'var(--warning)' }}>
        <div>{error}</div>
        <button className="btn btn-outline" onClick={handleRefresh} style={{ marginTop: '1rem' }}>
          Retry
        </button>
      </div>
    )
  }

  // Empty state: No upcoming meals
  if (commitments.length === 0) {
    return (
      <div>
        <header style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ margin: '0 0 0.25rem 0' }}>Prep Planning</h2>
          <p className="muted">What do I need to cook and buy?</p>
        </header>
        <EmptyStateNoMeals onNavigateToClients={onNavigateToClients} />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <header style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 0.25rem 0' }}>Prep Planning</h2>
        <p className="muted">What do I need to cook and buy?</p>
      </header>

      {/* Controls */}
      <div className="card" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span className="muted" style={{ fontSize: '0.9rem' }}>Days:</span>
            {DAYS_OPTIONS.map(days => (
              <button
                key={days}
                className={`btn btn-sm ${daysAhead === days ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setDaysAhead(days)}
              >
                {days}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className="btn btn-outline btn-sm"
              onClick={handleRefresh}
              disabled={commitmentsLoading || shoppingLoading}
              title="Refresh data"
            >
              {commitmentsLoading || shoppingLoading ? 'Loading...' : '🔄 Refresh'}
            </button>
            {onNavigateToClients && (
              <button
                className="btn btn-outline btn-sm"
                onClick={onNavigateToClients}
                title="Manage client meal plans"
              >
                👥 Clients
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-4" style={{ marginBottom: '1.5rem' }}>
        <SummaryCard
          icon="🍽️"
          title="Meals"
          value={summary?.total_meals || 0}
          subtitle="To prepare"
        />
        <SummaryCard
          icon="🍴"
          title="Servings"
          value={summary?.total_servings || 0}
          subtitle="Total"
        />
        <SummaryCard
          icon="👥"
          title="Clients"
          value={summary?.unique_clients || 0}
          subtitle="This period"
        />
        <SummaryCard
          icon="🛒"
          title="Ingredients"
          value={shoppingLoading ? '...' : totalItems}
          subtitle="To purchase"
        />
      </div>

      {/* Main Content - Two Column Layout */}
      <div className="grid grid-2">
        {/* Shopping List */}
        <div className="card">
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h3 style={{ margin: 0 }}>Shopping List</h3>
                <div className="muted" style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                  When to buy based on shelf life
                </div>
              </div>
            </div>
          </div>

          {/* Group by toggle */}
          <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Group by:</span>
            <button
              className={`btn btn-sm ${listGroupBy === 'date' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setListGroupBy('date')}
            >
              Date
            </button>
            <button
              className={`btn btn-sm ${listGroupBy === 'category' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setListGroupBy('category')}
            >
              Category
            </button>
          </div>

          <div style={{ padding: '1rem', maxHeight: '500px', overflowY: 'auto' }}>
            {renderShoppingItems()}
          </div>
        </div>

        {/* Upcoming Meals */}
        <div className="card">
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
            <h3 style={{ margin: 0 }}>Upcoming Meals</h3>
            <div className="muted" style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
              {uniqueClients.length > 1
                ? `Serving ${uniqueClients.length} clients`
                : 'Your scheduled meals'}
            </div>
          </div>

          <div style={{ padding: '1rem', maxHeight: '500px', overflowY: 'auto' }}>
            {renderCommitments()}
          </div>
        </div>
      </div>
    </div>
  )
}
