import React from 'react'

/**
 * Dietary insights visualization component
 * Shows breakdown of dietary preferences and allergies across all clients
 */
export default function ClientInsights({ summary }) {
  if (!summary) return null

  const dietaryBreakdown = summary.dietary_breakdown || {}
  const allergyBreakdown = summary.allergy_breakdown || {}

  // Filter out empty values and "None"
  const dietaryEntries = Object.entries(dietaryBreakdown)
    .filter(([key]) => key && key !== 'None')
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  const allergyEntries = Object.entries(allergyBreakdown)
    .filter(([key]) => key && key !== 'None')
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)

  // Don't render if no data
  if (dietaryEntries.length === 0 && allergyEntries.length === 0) {
    return null
  }

  // Calculate max for percentage bars
  const maxDietary = Math.max(...dietaryEntries.map(([, v]) => v), 1)
  const maxAllergy = Math.max(...allergyEntries.map(([, v]) => v), 1)

  return (
    <div className="cc-insights">
      {/* Dietary Preferences */}
      {dietaryEntries.length > 0 && (
        <>
          <div className="cc-insights-header">
            <div className="cc-insights-icon">🥗</div>
            <div>
              <h3 className="cc-insights-title">Dietary Preferences</h3>
              <p className="cc-insights-subtitle">
                Requirements across your client base
              </p>
            </div>
          </div>
          <div className="cc-insight-bars">
            {dietaryEntries.map(([name, count]) => {
              const percent = (count / maxDietary) * 100
              return (
                <div key={name} className="cc-insight-row">
                  <span className="cc-insight-label">{name}</span>
                  <div className="cc-insight-track">
                    <div
                      className="cc-insight-fill cc-insight-fill-dietary"
                      style={{ width: `${Math.max(percent, 8)}%` }}
                    />
                  </div>
                  <span className="cc-insight-count">{count}</span>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Allergy Alerts */}
      {allergyEntries.length > 0 && (
        <div style={{ marginTop: dietaryEntries.length > 0 ? '1.5rem' : 0 }}>
          <div className="cc-insights-header">
            <div className="cc-insights-icon" style={{ background: 'var(--danger-bg)' }}>⚠️</div>
            <div>
              <h3 className="cc-insights-title">Allergy Alerts</h3>
              <p className="cc-insights-subtitle">
                Critical dietary restrictions to remember
              </p>
            </div>
          </div>
          <div className="cc-insight-bars">
            {allergyEntries.map(([name, count]) => {
              const percent = (count / maxAllergy) * 100
              return (
                <div key={name} className="cc-insight-row">
                  <span className="cc-insight-label">{name}</span>
                  <div className="cc-insight-track">
                    <div
                      className="cc-insight-fill cc-insight-fill-allergy"
                      style={{ width: `${Math.max(percent, 8)}%` }}
                    />
                  </div>
                  <span className="cc-insight-count">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
