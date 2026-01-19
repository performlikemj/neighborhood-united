import React from 'react'

/**
 * Business value metrics dashboard
 * Shows key KPIs that demonstrate value to chefs
 */
export default function ClientMetrics({
  summary,
  pendingCount = 0,
  sourceFilter,
  onFilterChange
}) {
  if (!summary) return null

  // Calculate total people served (all household members)
  const totalPeople = summary.total_people || summary.total || 0

  // Get unique dietary requirements count
  const dietaryCount = Object.keys(summary.dietary_breakdown || {}).length

  // Get unique allergy requirements count
  const allergyCount = Object.keys(summary.allergy_breakdown || {}).filter(k => k !== 'None').length

  const metrics = [
    {
      id: 'total',
      icon: '👥',
      iconClass: 'cc-metric-icon-primary',
      value: summary.total,
      valueClass: '',
      label: 'Total Clients',
      filter: '',
      isActive: sourceFilter === ''
    },
    ...(pendingCount > 0 ? [{
      id: 'pending',
      icon: '🔔',
      iconClass: 'cc-metric-icon-warning',
      value: pendingCount,
      valueClass: 'cc-metric-value-warning',
      label: 'Pending Requests',
      isWarning: true
    }] : []),
    {
      id: 'platform',
      icon: '🌐',
      iconClass: 'cc-metric-icon-success',
      value: summary.platform,
      valueClass: 'cc-metric-value-platform',
      label: 'Platform Clients',
      filter: 'platform',
      isActive: sourceFilter === 'platform'
    },
    {
      id: 'manual',
      icon: '📋',
      iconClass: 'cc-metric-icon-info',
      value: summary.contacts,
      valueClass: 'cc-metric-value-manual',
      label: 'Manual Contacts',
      filter: 'contact',
      isActive: sourceFilter === 'contact'
    },
    ...(dietaryCount > 0 || allergyCount > 0 ? [{
      id: 'dietary',
      icon: '🍽️',
      iconClass: 'cc-metric-icon-success',
      value: dietaryCount + allergyCount,
      valueClass: 'cc-metric-value-primary',
      label: 'Dietary Requirements',
      trend: allergyCount > 0 ? `${allergyCount} allergies` : null
    }] : [])
  ]

  return (
    <div className="cc-metrics">
      <div className="cc-metrics-grid">
        {metrics.map((metric) => (
          <div
            key={metric.id}
            className={`cc-metric-card ${metric.isActive ? 'cc-metric-active' : ''} ${metric.isWarning ? 'cc-metric-warning' : ''}`}
            onClick={() => metric.filter !== undefined && onFilterChange(metric.isActive ? '' : metric.filter)}
            style={{ cursor: metric.filter !== undefined ? 'pointer' : 'default' }}
          >
            <div className={`cc-metric-icon ${metric.iconClass}`}>
              {metric.icon}
            </div>
            <div className={`cc-metric-value ${metric.valueClass}`}>
              {metric.value}
            </div>
            <div className="cc-metric-label">{metric.label}</div>
            {metric.trend && (
              <div className="cc-metric-trend">{metric.trend}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
