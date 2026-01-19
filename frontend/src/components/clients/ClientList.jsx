import React from 'react'
import ClientCard from './ClientCard'

/**
 * Scrollable client list with header
 */
export default function ClientList({
  clients,
  loading,
  selected,
  searchQuery,
  sourceFilter,
  getConnectionForCustomer,
  onSelectClient
}) {
  return (
    <div className="cc-client-list">
      <div className="cc-client-list-header">
        <h3 className="cc-client-list-title">
          {loading ? 'Loading...' : `${clients.length} Client${clients.length !== 1 ? 's' : ''}`}
        </h3>
      </div>

      <div className="cc-client-list-content">
        {loading ? (
          // Loading skeleton
          <div className="cc-empty-state">
            <div className="cc-skeleton cc-skeleton-avatar" style={{ margin: '0 auto 1rem' }} />
            <div className="cc-skeleton cc-skeleton-title" style={{ margin: '0 auto 0.5rem', width: '60%' }} />
            <div className="cc-skeleton cc-skeleton-text" style={{ margin: '0 auto', width: '80%' }} />
          </div>
        ) : clients.length === 0 ? (
          <div className="cc-empty-state">
            <div className="cc-empty-icon">📋</div>
            <div className="cc-empty-title">
              {searchQuery || sourceFilter ? 'No clients match your search' : 'No clients yet'}
            </div>
            <div className="cc-empty-text">
              {searchQuery || sourceFilter
                ? 'Try adjusting your filters'
                : 'Add your first client to get started!'}
            </div>
          </div>
        ) : (
          clients.map(client => {
            // Get connection status for platform clients
            const clientConnection = client.source_type === 'platform'
              ? getConnectionForCustomer(client.customer_id)
              : null
            const isPending = clientConnection?.isPending

            return (
              <ClientCard
                key={client.id}
                client={client}
                isSelected={selected?.id === client.id}
                isPending={isPending}
                onClick={() => onSelectClient(client)}
              />
            )
          })
        )}
      </div>
    </div>
  )
}
