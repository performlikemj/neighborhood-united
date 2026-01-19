import React from 'react'

/**
 * Hero header component for Client Management page
 * Displays compelling headline with client/people counts and primary actions
 */
export default function ClientsHeader({
  totalClients = 0,
  totalPeople = 0,
  showAddForm,
  onToggleAddForm
}) {
  return (
    <header className="cc-hero">
      <div className="cc-hero-content">
        <div className="cc-hero-text">
          <h1 className="cc-hero-title">Client Management</h1>
          <p className="cc-hero-subtitle">
            {totalClients > 0 ? (
              <>
                Your complete view of <strong>{totalClients} {totalClients === 1 ? 'family' : 'families'}</strong>
                {totalPeople > totalClients && (
                  <> and <strong>{totalPeople} people</strong></>
                )} you serve
              </>
            ) : (
              <>Build your client base and track their dietary needs</>
            )}
          </p>
        </div>
        <div className="cc-hero-actions">
          <button
            className="cc-btn cc-btn-primary"
            onClick={onToggleAddForm}
          >
            {showAddForm ? '✕ Cancel' : '+ Add Client'}
          </button>
        </div>
      </div>
    </header>
  )
}
