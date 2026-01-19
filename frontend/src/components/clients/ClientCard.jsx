import React from 'react'

/**
 * Enhanced client card with avatar, badges, and quick info
 */
export default function ClientCard({
  client,
  isSelected,
  isPending,
  onClick
}) {
  const allergies = client.allergies?.filter(a => a && a !== 'None') || []
  const hasAllergies = allergies.length > 0

  // Get initials for avatar
  const getInitials = (name) => {
    if (!name) return '?'
    const parts = name.split(' ')
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }

  const cardClasses = [
    'cc-client-card',
    isSelected && 'cc-client-card-selected',
    isPending && 'cc-client-card-pending'
  ].filter(Boolean).join(' ')

  const avatarClasses = [
    'cc-client-avatar',
    client.source_type === 'platform' ? 'cc-client-avatar-platform' : 'cc-client-avatar-manual'
  ].join(' ')

  return (
    <div className={cardClasses} onClick={onClick}>
      <div className="cc-client-card-header">
        {/* Avatar with initials */}
        <div className={avatarClasses}>
          {getInitials(client.name)}
        </div>

        {/* Client info */}
        <div className="cc-client-info">
          <div className="cc-client-name">
            {client.name}
            <span className={`cc-badge ${client.source_type === 'platform' ? 'cc-badge-platform' : 'cc-badge-manual'}`}>
              {client.source_type === 'platform' ? '● Platform' : '◉ Manual'}
            </span>
            {isPending && (
              <span className="cc-badge cc-badge-pending">
                ⏳ Pending
              </span>
            )}
          </div>
          {client.email && (
            <div className="cc-client-email">
              {client.email}
            </div>
          )}
        </div>
      </div>

      {/* Quick info badges */}
      <div className="cc-client-meta">
        {/* Household indicator */}
        {client.household_size > 1 && (
          <span className="cc-meta-badge cc-meta-household">
            👥 {client.household_size}
            {client.household_size > (client.household_members?.length || 0) + 1 && (
              <span title="Household profiles incomplete" style={{ color: 'var(--warning)', marginLeft: '2px' }}>!</span>
            )}
          </span>
        )}

        {/* Dietary preferences */}
        {client.dietary_preferences?.length > 0 && (
          <span className="cc-meta-badge cc-meta-dietary">
            🥗 {client.dietary_preferences.slice(0, 2).join(', ')}
            {client.dietary_preferences.length > 2 && ` +${client.dietary_preferences.length - 2}`}
          </span>
        )}

        {/* Allergies - prominent */}
        {hasAllergies && (
          <span className="cc-meta-badge cc-meta-allergy">
            ⚠️ {allergies.slice(0, 2).join(', ')}
            {allergies.length > 2 && ` +${allergies.length - 2}`}
          </span>
        )}
      </div>
    </div>
  )
}
