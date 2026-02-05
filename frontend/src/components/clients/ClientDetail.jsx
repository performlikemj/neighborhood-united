import React from 'react'
import HouseholdSection from './HouseholdSection'

/**
 * Redesigned client detail panel with comprehensive profile view
 */
export default function ClientDetail({
  client,
  isDesktop,
  editMode,
  editForm,
  saving,
  showAddMember,
  editingMember,
  memberForm,
  mealPlanOpen,
  connection,
  connectionMutating,
  connectionActionId,
  respondError,
  // Handlers
  onClose,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onDelete,
  onSetEditForm,
  onSetMemberForm,
  onStartAddMember,
  onStartEditMember,
  onCancelMember,
  onSubmitAddMember,
  onSubmitEditMember,
  onDeleteMember,
  onConnectionAction,
  onOpenMealPlan,
  // Helpers
  DIETARY_OPTIONS,
  ALLERGY_OPTIONS,
  ChipSelector,
  DietaryChips,
  MemberForm,
  INITIAL_MEMBER
}) {
  // Empty state
  if (!client) {
    return (
      <div className="cc-detail-empty">
        <div className="cc-detail-empty-icon">👥</div>
        <div className="cc-detail-empty-title">Select a client</div>
        <div className="cc-detail-empty-text">
          View and manage their dietary profile, household members, and meal plans
        </div>
      </div>
    )
  }

  const canEdit = client.source_type === 'contact'
  const isPlatformPending = connection?.isPending
  const isPlatformAccepted = connection?.isAccepted
  const canAcceptConnection = connection?.canAccept
  const canDeclineConnection = connection?.canDecline
  const canEndConnection = connection?.canEnd
  const isThisConnectionBusy = connectionMutating && String(connectionActionId) === String(connection?.id)

  // Get initials for avatar
  const getInitials = (name) => {
    if (!name) return '?'
    const parts = name.split(' ')
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    }
    return name.slice(0, 2).toUpperCase()
  }

  const avatarClasses = [
    'cc-detail-avatar',
    client.source_type === 'platform' ? 'cc-client-avatar-platform' : 'cc-client-avatar-manual'
  ].join(' ')

  // Edit Mode View
  if (editMode && canEdit) {
    return (
      <div className="cc-detail-content">
        <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.25rem', fontWeight: 700 }}>✏️ Edit Client</h3>
        <form onSubmit={onSaveEdit}>
          <div className="cc-form-grid">
            <div className="cc-form-group">
              <label className="cc-form-label">First Name *</label>
              <input
                type="text"
                className="cc-form-input"
                value={editForm.first_name}
                onChange={e => onSetEditForm(f => ({ ...f, first_name: e.target.value }))}
                required
              />
            </div>
            <div className="cc-form-group">
              <label className="cc-form-label">Last Name</label>
              <input
                type="text"
                className="cc-form-input"
                value={editForm.last_name}
                onChange={e => onSetEditForm(f => ({ ...f, last_name: e.target.value }))}
              />
            </div>
            <div className="cc-form-group">
              <label className="cc-form-label">Email</label>
              <input
                type="email"
                className="cc-form-input"
                value={editForm.email}
                onChange={e => onSetEditForm(f => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div className="cc-form-group">
              <label className="cc-form-label">Phone</label>
              <input
                type="tel"
                className="cc-form-input"
                value={editForm.phone}
                onChange={e => onSetEditForm(f => ({ ...f, phone: e.target.value }))}
              />
            </div>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <label className="cc-form-label">Dietary Preferences</label>
            <ChipSelector
              options={DIETARY_OPTIONS}
              selected={editForm.dietary_preferences}
              onChange={v => onSetEditForm(f => ({ ...f, dietary_preferences: v }))}
              type="dietary"
            />
          </div>

          <div style={{ marginTop: '0.75rem' }}>
            <label className="cc-form-label">Allergies</label>
            <ChipSelector
              options={ALLERGY_OPTIONS.filter(a => a !== 'None')}
              selected={editForm.allergies}
              onChange={v => onSetEditForm(f => ({ ...f, allergies: v }))}
              type="allergy"
            />
          </div>

          <div style={{ marginTop: '0.75rem' }}>
            <label className="cc-form-label">Notes</label>
            <textarea
              className="cc-form-textarea"
              value={editForm.notes}
              onChange={e => onSetEditForm(f => ({ ...f, notes: e.target.value }))}
              placeholder="Notes about this client..."
            />
          </div>

          {/* Special Dates Section */}
          <div style={{ marginTop: '1.25rem', padding: '1rem', background: 'var(--surface-2)', borderRadius: '8px' }}>
            <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem', fontWeight: 600 }}>
              🎉 Special Dates
            </h4>

            <div style={{ marginBottom: '0.75rem' }}>
              <label className="cc-form-label">🎂 Birthday</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <select
                  className="cc-form-input"
                  value={editForm.birthday_month || ''}
                  onChange={e => onSetEditForm(f => ({
                    ...f,
                    birthday_month: e.target.value ? parseInt(e.target.value, 10) : null
                  }))}
                  style={{ flex: 1 }}
                >
                  <option value="">Month</option>
                  <option value="1">January</option>
                  <option value="2">February</option>
                  <option value="3">March</option>
                  <option value="4">April</option>
                  <option value="5">May</option>
                  <option value="6">June</option>
                  <option value="7">July</option>
                  <option value="8">August</option>
                  <option value="9">September</option>
                  <option value="10">October</option>
                  <option value="11">November</option>
                  <option value="12">December</option>
                </select>
                <select
                  className="cc-form-input"
                  value={editForm.birthday_day || ''}
                  onChange={e => onSetEditForm(f => ({
                    ...f,
                    birthday_day: e.target.value ? parseInt(e.target.value, 10) : null
                  }))}
                  style={{ flex: 1 }}
                >
                  <option value="">Day</option>
                  {Array.from({ length: 31 }, (_, i) => i + 1).map(day => (
                    <option key={day} value={day}>{day}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="cc-form-label">💍 Anniversary</label>
              <input
                type="date"
                className="cc-form-input"
                value={editForm.anniversary || ''}
                onChange={e => onSetEditForm(f => ({ ...f, anniversary: e.target.value || null }))}
              />
            </div>

            <p style={{ margin: '0.75rem 0 0 0', fontSize: '0.8rem', color: 'var(--muted)' }}>
              ℹ️ Enable birthday/anniversary notifications in Workspace Settings to get reminders.
            </p>
          </div>

          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button type="submit" className="cc-btn cc-btn-primary" disabled={saving}>
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
            <button type="button" className="cc-btn cc-btn-secondary" onClick={onCancelEdit}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    )
  }

  // Normal Detail View
  return (
    <div className="cc-detail-content">
      {/* Mobile back button */}
      {!isDesktop && (
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            padding: '0.5rem 0',
            marginBottom: '0.75rem',
            cursor: 'pointer',
            color: 'var(--primary)',
            fontWeight: 500,
            fontSize: '0.9rem'
          }}
        >
          ← Back to list
        </button>
      )}

      {/* Header with avatar and actions */}
      <div className="cc-detail-header">
        <div>
          <div className={avatarClasses}>
            {getInitials(client.name)}
          </div>
          <h2 className="cc-detail-name">{client.name}</h2>
          <span className={`cc-badge ${client.source_type === 'platform' ? 'cc-badge-platform' : 'cc-badge-manual'}`}>
            {client.source_type === 'platform' ? '● Platform' : '◉ Manual'}
          </span>
        </div>
        {canEdit && (
          <div className="cc-detail-actions">
            <button className="cc-btn cc-btn-secondary cc-btn-sm" onClick={onStartEdit}>
              ✏️ Edit
            </button>
            <button className="cc-btn cc-btn-danger cc-btn-sm" onClick={() => onDelete(client)}>
              Remove
            </button>
          </div>
        )}
      </div>

      {/* Connection Status for Platform Clients */}
      {client.source_type === 'platform' && connection && (
        <div className={`cc-connection-box ${isPlatformPending ? 'cc-connection-box-pending' : 'cc-connection-box-connected'}`}>
          <div>
            <div className="cc-connection-label">Connection Status</div>
            <div
              className="cc-connection-status"
              style={{
                background: isPlatformPending ? 'var(--warning-bg)' : 'var(--platform-bg)',
                color: isPlatformPending ? 'var(--warning)' : 'var(--platform-color)'
              }}
            >
              <span style={{ fontSize: '0.7rem' }}>{isPlatformPending ? '⏳' : '✓'}</span>
              {isPlatformPending ? 'Pending Request' : 'Connected'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {canAcceptConnection && (
              <button
                className="cc-btn cc-btn-primary cc-btn-sm"
                onClick={() => onConnectionAction(connection.id, 'accept')}
                disabled={isThisConnectionBusy}
              >
                {isThisConnectionBusy ? 'Updating...' : '✓ Accept'}
              </button>
            )}
            {canDeclineConnection && (
              <button
                className="cc-btn cc-btn-secondary cc-btn-sm"
                onClick={() => onConnectionAction(connection.id, 'decline')}
                disabled={isThisConnectionBusy}
              >
                Decline
              </button>
            )}
            {canEndConnection && (
              <button
                className="cc-btn cc-btn-danger cc-btn-sm"
                onClick={() => {
                  if (confirm(`End connection with ${client.name}? They will no longer have access to your personalized offerings.`)) {
                    onConnectionAction(connection.id, 'end')
                  }
                }}
                disabled={isThisConnectionBusy}
              >
                {isThisConnectionBusy ? 'Ending...' : 'End Connection'}
              </button>
            )}
          </div>
          {respondError && connectionActionId === connection.id && (
            <div style={{
              marginTop: '0.75rem',
              padding: '0.5rem',
              background: 'var(--danger-bg)',
              borderRadius: '6px',
              fontSize: '0.85rem',
              color: 'var(--danger)',
              width: '100%'
            }}>
              {respondError?.response?.data?.detail || respondError?.message || 'Failed to update connection'}
            </div>
          )}
        </div>
      )}

      {/* Contact Info */}
      {(client.email || client.phone) && (
        <div className="cc-section">
          <h4 className="cc-section-title">📞 Contact</h4>
          <div className="cc-info-box">
            {client.email && (
              <div className="cc-info-row">
                <span className="cc-info-icon">📧</span>
                <a href={`mailto:${client.email}`} style={{ color: 'var(--link)' }}>{client.email}</a>
              </div>
            )}
            {client.phone && (
              <div className="cc-info-row">
                <span className="cc-info-icon">📞</span>
                <a href={`tel:${client.phone}`} style={{ color: 'var(--link)' }}>{client.phone}</a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Dietary Profile */}
      <div className="cc-section">
        <h4 className="cc-section-title">🥗 Dietary Preferences</h4>
        <div className="cc-info-box">
          <DietaryChips items={client.dietary_preferences} type="dietary" />
        </div>
      </div>

      <div className="cc-section">
        <h4 className="cc-section-title">⚠️ Allergies</h4>
        <div className="cc-info-box">
          <DietaryChips items={client.allergies} type="allergy" />
        </div>
      </div>

      {/* Special Dates */}
      {(client.birthday_month || client.anniversary) && (
        <div className="cc-section">
          <h4 className="cc-section-title">🎉 Special Dates</h4>
          <div className="cc-info-box">
            {client.birthday_month && (
              <div className="cc-info-row">
                <span className="cc-info-icon">🎂</span>
                <span>
                  Birthday: {new Date(2000, client.birthday_month - 1, client.birthday_day || 1).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
                </span>
              </div>
            )}
            {client.anniversary && (
              <div className="cc-info-row">
                <span className="cc-info-icon">💍</span>
                <span>
                  Anniversary: {new Date(client.anniversary + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Household Members */}
      <HouseholdSection
        client={client}
        canEdit={canEdit}
        householdMembers={client.household_members}
        showAddMember={showAddMember}
        editingMember={editingMember}
        memberForm={memberForm}
        saving={saving}
        onSetMemberForm={onSetMemberForm}
        onStartAddMember={onStartAddMember}
        onStartEditMember={onStartEditMember}
        onDeleteMember={onDeleteMember}
        onSubmitMember={editingMember ? onSubmitEditMember : onSubmitAddMember}
        onCancelMember={onCancelMember}
        DIETARY_OPTIONS={DIETARY_OPTIONS}
        ALLERGY_OPTIONS={ALLERGY_OPTIONS}
        ChipSelector={ChipSelector}
        MemberForm={MemberForm}
      />

      {/* Meal Plans CTA */}
      <div className="cc-section">
        <h4 className="cc-section-title">📅 Meal Plans</h4>
        <div className="cc-meal-plan-cta">
          <span className="cc-meal-plan-text">
            Create personalized meal plans with AI assistance
          </span>
          <button
            type="button"
            className="cc-btn cc-btn-primary cc-btn-sm"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onOpenMealPlan()
            }}
          >
            ✨ Manage Plans
          </button>
        </div>
      </div>

      {/* Notes */}
      {client.notes && (
        <div className="cc-section">
          <h4 className="cc-section-title">📝 Notes</h4>
          <div className="cc-info-box" style={{ fontStyle: 'italic', color: 'var(--muted)' }}>
            {client.notes}
          </div>
        </div>
      )}
    </div>
  )
}
