/**
 * TodayDashboard Component
 * 
 * Smart contextual view for chefs showing:
 * - Upcoming orders needing action
 * - Unread messages with quick actions
 * - Pending client requests
 * - Next meal share countdown
 * - Quick action buttons
 */

import React, { useMemo } from 'react'

// Helper to format relative time
function formatRelativeTime(date) {
  const now = new Date()
  const target = new Date(date)
  const diffMs = target - now
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffMs < 0) return 'Past due'
  if (diffHours < 1) return 'Less than an hour'
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''}`
  if (diffDays === 1) return 'Tomorrow'
  if (diffDays < 7) return `${diffDays} days`
  return target.toLocaleDateString()
}

// Helper to format currency
function formatCurrency(amount, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency
  }).format(amount || 0)
}

// Helper to extract customer name from various order object shapes
function getCustomerName(order = {}) {
  // Try direct name fields first
  const directName = order.customer_display_name
    || order.customer_name
    || order.customer_full_name
  if (directName) return directName

  // Try combining first + last name
  const firstName = order.customer_first_name
  const lastName = order.customer_last_name
  if (firstName || lastName) {
    return [firstName, lastName].filter(Boolean).join(' ')
  }

  // Try nested customer object (meal_event_details or customer_details)
  const details = order.meal_event_details || order.customer_details || order.customer_profile || order.customer || {}
  if (typeof details === 'object') {
    const nestedName = details.full_name
      || details.display_name
      || details.name
    if (nestedName) return nestedName

    const nestedFirst = details.first_name
    const nestedLast = details.last_name
    if (nestedFirst || nestedLast) {
      return [nestedFirst, nestedLast].filter(Boolean).join(' ')
    }
  }

  // Fallback to username/email
  const fallback = order.customer_username || order.customer_email
  if (fallback) return fallback

  return 'Customer'
}

export default function TodayDashboard({
  orders = [],
  serviceOrders = [],
  events = [],
  pendingConnections = [],
  unreadMessageCount = 0,
  onNavigate,
  onViewOrder,
  onViewConnection,
  onViewMessages,
  isOnboardingComplete = false,
  onboardingCompletionState = {},
  meetingConfig = {},
  className = '',
  // Break mode props
  isOnBreak = false,
  breakBusy = false,
  breakReason = '',
  onBreakReasonChange,
  onToggleBreak
}) {
  // Get orders needing attention (next 48 hours, not completed)
  const upcomingOrders = useMemo(() => {
    const now = new Date()
    const in48Hours = new Date(now.getTime() + 48 * 60 * 60 * 1000)
    
    const allOrders = [...orders, ...serviceOrders]
      .filter(order => {
        const status = String(order.status || '').toLowerCase()
        if (['completed', 'cancelled', 'declined'].includes(status)) return false
        
        const orderDate = new Date(order.event_date || order.scheduled_date || order.created_at)
        return orderDate <= in48Hours
      })
      .sort((a, b) => {
        const dateA = new Date(a.event_date || a.scheduled_date || a.created_at)
        const dateB = new Date(b.event_date || b.scheduled_date || b.created_at)
        return dateA - dateB
      })
      .slice(0, 5)
    
    return allOrders
  }, [orders, serviceOrders])

  // Get next upcoming meal share
  const nextMealShare = useMemo(() => {
    const now = new Date()
    return events
      .filter(e => new Date(e.event_date) > now)
      .sort((a, b) => new Date(a.event_date) - new Date(b.event_date))[0]
  }, [events])

  // Calculate stats
  const stats = useMemo(() => {
    const pendingOrderCount = [...orders, ...serviceOrders].filter(o => 
      ['pending', 'confirmed'].includes(String(o.status || '').toLowerCase())
    ).length
    
    return {
      pendingOrders: pendingOrderCount,
      pendingClients: pendingConnections.length,
      unreadMessages: unreadMessageCount
    }
  }, [orders, serviceOrders, pendingConnections, unreadMessageCount])

  // Calculate onboarding progress (filter out meeting step if Calendly disabled, matching OnboardingChecklist)
  const onboardingProgress = useMemo(() => {
    const activeSteps = Object.entries(onboardingCompletionState).filter(([key]) => {
      // Filter out meeting step if feature is disabled (consistent with OnboardingChecklist)
      if (key === 'meeting' && !meetingConfig?.feature_enabled) return false
      return true
    })
    const completed = activeSteps.filter(([, value]) => value).length
    const total = activeSteps.length
    return { completed, total, percent: total > 0 ? Math.round((completed / total) * 100) : 0 }
  }, [onboardingCompletionState, meetingConfig])

  const hasUrgentItems = stats.pendingClients > 0 || upcomingOrders.length > 0 || stats.unreadMessages > 0

  return (
    <div className={`today-dashboard ${className}`}>
      {/* Welcome & Quick Stats */}
      <div className="today-header">
        <div className="today-greeting">
          <h1>Today</h1>
          <p className="muted">
            {hasUrgentItems 
              ? `You have ${[
                  stats.pendingOrders > 0 && `${stats.pendingOrders} pending order${stats.pendingOrders > 1 ? 's' : ''}`,
                  stats.pendingClients > 0 && `${stats.pendingClients} client request${stats.pendingClients > 1 ? 's' : ''}`,
                  stats.unreadMessages > 0 && `${stats.unreadMessages} unread message${stats.unreadMessages > 1 ? 's' : ''}`
                ].filter(Boolean).join(', ')}`
              : 'All caught up! No urgent items.'
            }
          </p>
        </div>
      </div>

      {/* Onboarding Progress (for new chefs) */}
      {!isOnboardingComplete && (
        <div className="today-card today-onboarding">
          <div className="card-header">
            <span className="card-icon">🚀</span>
            <div className="card-title">
              <h3>Complete Your Setup</h3>
              <p className="muted">{onboardingProgress.completed} of {onboardingProgress.total} steps complete</p>
            </div>
            <div className="progress-badge">{onboardingProgress.percent}%</div>
          </div>
          <div className="progress-bar-container">
            <div className="progress-bar" style={{ width: `${onboardingProgress.percent}%` }} />
          </div>
          <button 
            className="btn btn-primary btn-sm"
            onClick={() => onNavigate?.('dashboard')}
          >
            Continue Setup
          </button>
        </div>
      )}

      {/* Urgent Action Items */}
      {hasUrgentItems && (
        <div className="today-section">
          <h2 className="section-title">Needs Attention</h2>
          <div className="today-cards">
            {/* Pending Client Requests */}
            {stats.pendingClients > 0 && (
              <button 
                className="today-card today-card-action urgent"
                onClick={() => onNavigate?.('clients')}
              >
                <div className="card-icon-wrapper orange">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                    <circle cx="9" cy="7" r="4"/>
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                  </svg>
                </div>
                <div className="card-content">
                  <div className="card-value">{stats.pendingClients}</div>
                  <div className="card-label">Client Request{stats.pendingClients > 1 ? 's' : ''}</div>
                </div>
                <svg className="card-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 18l6-6-6-6"/>
                </svg>
              </button>
            )}

            {/* Unread Messages */}
            {stats.unreadMessages > 0 && (
              <button 
                className="today-card today-card-action"
                onClick={() => onNavigate?.('messages')}
              >
                <div className="card-icon-wrapper blue">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                </div>
                <div className="card-content">
                  <div className="card-value">{stats.unreadMessages}</div>
                  <div className="card-label">Unread Message{stats.unreadMessages > 1 ? 's' : ''}</div>
                </div>
                <svg className="card-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M9 18l6-6-6-6"/>
                </svg>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Upcoming Orders */}
      {upcomingOrders.length > 0 && (
        <div className="today-section">
          <div className="section-header">
            <h2 className="section-title">Upcoming Orders</h2>
            <button 
              className="btn btn-outline btn-xs"
              onClick={() => onNavigate?.('orders')}
            >
              View All
            </button>
          </div>
          <div className="today-orders">
            {upcomingOrders.map((order, idx) => (
              <button 
                key={order.id || idx}
                className="today-order-item"
                onClick={() => onViewOrder?.(order)}
              >
                <div className="order-status-dot" data-status={String(order.status || '').toLowerCase()} />
                <div className="order-info">
                  <div className="order-customer">
                    {getCustomerName(order)}
                  </div>
                  <div className="order-details muted">
                    {order.service_name || order.meal_name || 'Order'} · {formatCurrency(order.total_price || order.total_value_for_chef)}
                  </div>
                </div>
                <div className="order-time">
                  {formatRelativeTime(order.event_date || order.scheduled_date || order.created_at)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Next Meal Share */}
      {nextMealShare && (
        <div className="today-section">
          <h2 className="section-title">Next Meal Share</h2>
          <div className="today-card today-meal-share">
            <div className="meal-share-date">
              <div className="meal-share-month">{new Date(nextMealShare.event_date).toLocaleDateString('en-US', { month: 'short' })}</div>
              <div className="meal-share-day">{new Date(nextMealShare.event_date).getDate()}</div>
            </div>
            <div className="meal-share-info">
              <div className="meal-share-name">{nextMealShare.meal?.name || 'Meal Share'}</div>
              <div className="meal-share-details muted">
                {nextMealShare.order_count || 0} order{(nextMealShare.order_count || 0) !== 1 ? 's' : ''} · 
                {formatRelativeTime(nextMealShare.event_date)}
              </div>
            </div>
            <button 
              className="btn btn-outline btn-sm"
              onClick={() => onNavigate?.('services')}
            >
              View
            </button>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="today-section">
        <h2 className="section-title">Quick Actions</h2>
        <div className="quick-actions">
          <button
            className="quick-action"
            onClick={() => onNavigate?.('orders')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="4" width="18" height="18" rx="2"/>
              <path d="M16 2v4M8 2v4M3 10h18"/>
            </svg>
            <span>Orders</span>
          </button>
          <button
            className="quick-action"
            onClick={() => onNavigate?.('menu')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>
            </svg>
            <span>Menu</span>
          </button>
          <button
            className="quick-action"
            onClick={() => onNavigate?.('clients')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
            </svg>
            <span>Clients</span>
          </button>
          <button
            className="quick-action"
            onClick={() => onNavigate?.('profile')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            <span>Profile</span>
          </button>
        </div>
      </div>

      {/* Take a Break Section */}
      {onToggleBreak && (
        <div className="today-section today-break-section">
          <div className="today-card today-break-card">
            <div className="break-header">
              <div className="break-icon-wrapper">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
                  <line x1="12" y1="2" x2="12" y2="12"/>
                </svg>
              </div>
              <div className="break-title">
                <h3>Need a break?</h3>
                <p className="muted">Pause bookings and step away when you need to recharge.</p>
              </div>
            </div>
            <div className="break-controls">
              <label className="break-toggle">
                <input
                  type="checkbox"
                  checked={isOnBreak}
                  disabled={breakBusy}
                  onChange={e => onToggleBreak(e.target.checked)}
                />
                <span className="break-status">{isOnBreak ? 'End break' : 'Go on break'}</span>
                {breakBusy && <span className="spinner" aria-hidden />}
              </label>
              {isOnBreak && (
                <input
                  className="input break-reason-input"
                  placeholder="Note for guests (e.g., 'Back in 2 weeks')"
                  value={breakReason}
                  disabled={breakBusy}
                  onChange={e => onBreakReasonChange?.(e.target.value)}
                />
              )}
            </div>
            {!isOnBreak && (
              <p className="muted break-warning">
                Turning this on will cancel upcoming events and refund paid orders.
              </p>
            )}
          </div>
        </div>
      )}

      <style>{styles}</style>
    </div>
  )
}

const styles = `
  .today-dashboard {
    max-width: 100%;
    color: var(--text);
  }

  /* Large screens - expand Today dashboard */
  @media (min-width: 1600px) {
    .today-dashboard {
      max-width: 100%;
    }
    .today-cards {
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    }
    .quick-actions {
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    }
  }

  @media (min-width: 2400px) {
    .today-cards {
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1rem;
    }
  }

  .today-dashboard .muted {
    color: var(--muted);
  }

  .today-header {
    margin-bottom: 1.5rem;
  }

  .today-greeting h1 {
    margin: 0 0 0.25rem 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text);
  }

  .today-greeting .muted {
    margin: 0;
    font-size: 0.95rem;
    color: var(--muted);
  }

  .today-section {
    margin-bottom: 1.5rem;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }

  .section-title {
    margin: 0 0 0.75rem 0;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--muted);
  }

  .section-header .section-title {
    margin-bottom: 0;
  }

  .today-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.75rem;
  }

  .today-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
    color: var(--text);
  }

  .today-card-action {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
  }

  .today-card-action:hover {
    border-color: var(--primary);
    background: var(--surface-2);
  }

  .today-card-action.urgent {
    border-color: var(--warning);
    background: var(--warning-bg);
  }

  .today-card-action.urgent:hover {
    border-color: var(--warning);
    background: var(--warning-bg);
    filter: brightness(1.05);
  }

  .card-icon-wrapper {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .card-icon-wrapper.orange {
    background: var(--warning-bg);
    color: var(--warning);
  }

  .card-icon-wrapper.blue {
    background: var(--info-bg);
    color: var(--info);
  }

  .card-content {
    flex: 1;
    min-width: 0;
  }

  .card-value {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
    color: var(--text);
  }

  .card-label {
    font-size: 0.85rem;
    color: var(--muted);
  }

  .card-arrow {
    color: var(--muted);
    flex-shrink: 0;
  }

  /* Onboarding Card */
  .today-onboarding {
    background: var(--surface-2);
    border-color: var(--primary);
  }

  .today-onboarding .card-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .today-onboarding .card-icon {
    font-size: 1.5rem;
  }

  .today-onboarding .card-title {
    flex: 1;
  }

  .today-onboarding .card-title h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
  }

  .today-onboarding .card-title .muted {
    margin: 0;
    font-size: 0.8rem;
    color: var(--muted);
  }

  .progress-badge {
    background: var(--primary);
    color: white;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.25rem 0.5rem;
    border-radius: 10px;
  }

  .progress-bar-container {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    margin-bottom: 0.75rem;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--primary-600));
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  /* Orders List */
  .today-orders {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .today-order-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    width: 100%;
    color: var(--text);
  }

  .today-order-item:hover {
    border-color: var(--primary);
    background: var(--surface-2);
  }

  .order-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--muted);
  }

  .order-status-dot[data-status="pending"] {
    background: var(--warning);
  }

  .order-status-dot[data-status="confirmed"] {
    background: var(--info);
  }

  .order-status-dot[data-status="in_progress"] {
    background: var(--pending);
  }

  .order-info {
    flex: 1;
    min-width: 0;
  }

  .order-customer {
    font-weight: 500;
    font-size: 0.95rem;
    color: var(--text);
  }

  .order-details {
    font-size: 0.8rem;
    color: var(--muted);
  }

  .order-time {
    font-size: 0.8rem;
    color: var(--muted);
    flex-shrink: 0;
    font-weight: 500;
  }

  /* Meal Share Card */
  .today-meal-share {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .meal-share-date {
    width: 50px;
    height: 50px;
    background: var(--primary);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }

  .meal-share-month {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .meal-share-day {
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1;
  }

  .meal-share-info {
    flex: 1;
    min-width: 0;
  }

  .meal-share-name {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text);
  }

  .meal-share-details {
    font-size: 0.8rem;
    color: var(--muted);
  }

  /* Quick Actions */
  .quick-actions {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
  }

  .quick-action {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
    color: var(--text);
  }

  .quick-action:hover {
    border-color: var(--primary);
    background: var(--surface-2);
    color: var(--primary);
  }

  .quick-action span {
    font-size: 0.8rem;
    font-weight: 500;
  }

  /* Dark mode - CSS variables already handle this automatically */

  @media (max-width: 640px) {
    .today-cards {
      grid-template-columns: 1fr;
    }

    .quick-actions {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  /* Take a Break Section */
  .today-break-section {
    margin-top: 1rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
  }

  .today-break-card {
    background: var(--surface-2);
    border-color: var(--border);
  }

  .break-header {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .break-icon-wrapper {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: var(--surface);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: var(--muted);
  }

  .break-title {
    flex: 1;
  }

  .break-title h3 {
    margin: 0 0 0.15rem 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
  }

  .break-title .muted {
    margin: 0;
    font-size: 0.85rem;
  }

  .break-controls {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .break-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
  }

  .break-toggle input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .break-status {
    font-weight: 500;
    font-size: 0.9rem;
    color: var(--text);
  }

  .break-reason-input {
    font-size: 0.9rem;
    padding: 0.5rem 0.75rem;
  }

  .break-warning {
    margin: 0.75rem 0 0 0;
    font-size: 0.8rem;
  }

  @media (max-width: 640px) {
    .break-header {
      flex-direction: column;
      gap: 0.5rem;
    }
  }
`

