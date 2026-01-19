import React from 'react'

/**
 * Pending connection requests banner with attention-grabbing design
 */
export default function PendingRequests({
  pendingConnections,
  onAccept,
  onDecline,
  connectionMutating,
  connectionActionId
}) {
  if (!pendingConnections?.length) return null

  return (
    <div className="cc-pending-banner">
      <div className="cc-pending-header">
        <div className="cc-pending-icon">
          🔔
        </div>
        <div>
          <h3 className="cc-pending-title">
            {pendingConnections.length} New Connection Request{pendingConnections.length > 1 ? 's' : ''}
          </h3>
          <p className="cc-pending-subtitle">
            {pendingConnections.length === 1
              ? 'Someone wants to work with you!'
              : 'People want to work with you!'}
          </p>
        </div>
      </div>

      <div className="cc-pending-list">
        {pendingConnections.map(connection => {
          // Extract customer info from various possible field locations
          const customerName =
            (connection.customer_first_name && connection.customer_last_name
              ? `${connection.customer_first_name} ${connection.customer_last_name}`.trim()
              : connection.customer_first_name)
            || connection.customer_username
            || connection.customer?.name
            || connection.customer?.full_name
            || (connection.customer?.first_name && connection.customer?.last_name
              ? `${connection.customer.first_name} ${connection.customer.last_name}`.trim()
              : connection.customer?.first_name)
            || connection.customer?.username
            || connection.customerName
            || null

          const customerEmail = connection.customer_email || connection.customer?.email || ''
          const requestDate = connection.created_at || connection.requested_at
          const isThisBusy = connectionMutating && String(connectionActionId) === String(connection.id)

          return (
            <div key={connection.id} className="cc-pending-card">
              <div className="cc-pending-info">
                {customerName ? (
                  <>
                    <div className="cc-pending-name">{customerName}</div>
                    {customerEmail && (
                      <div className="cc-pending-email">
                        <span style={{ opacity: 0.6, fontSize: '0.75rem' }}>📧</span>
                        {customerEmail}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="cc-pending-name" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <span style={{ opacity: 0.6, fontSize: '0.85rem' }}>📧</span>
                    {customerEmail || 'New connection request'}
                  </div>
                )}
                {requestDate && (
                  <div className="cc-pending-date">
                    Requested {new Date(requestDate).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: requestDate.slice(0, 4) !== new Date().getFullYear().toString() ? 'numeric' : undefined
                    })}
                  </div>
                )}
              </div>

              <div className="cc-pending-actions">
                {connection.canAccept && (
                  <button
                    className="cc-btn cc-btn-primary cc-btn-sm"
                    onClick={() => onAccept(connection.id)}
                    disabled={isThisBusy}
                  >
                    {isThisBusy ? 'Accepting...' : '✓ Accept'}
                  </button>
                )}
                {connection.canDecline && (
                  <button
                    className="cc-btn cc-btn-secondary cc-btn-sm"
                    onClick={() => onDecline(connection.id)}
                    disabled={isThisBusy}
                  >
                    Decline
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
