/**
 * FamilySelector Component
 * 
 * Dropdown selector for choosing which family the chef wants to 
 * work with in the Sous Chef assistant. Lists both platform customers
 * and CRM leads (manually added contacts).
 */

import React, { useState, useEffect, useMemo } from 'react'
import { getClients, getLeads } from '../api/chefCrmClient'

export default function FamilySelector({ 
  selectedFamilyId,
  selectedFamilyType,
  onFamilySelect,
  className = '',
  openDirection = 'down'  // 'down' or 'up' - controls dropdown direction
}) {
  const [customers, setCustomers] = useState([])
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  // Fetch both customers and leads on mount
  useEffect(() => {
    let mounted = true
    
    async function fetchFamilies() {
      try {
        setLoading(true)
        
        // Fetch both in parallel
        const [customersData, leadsData] = await Promise.all([
          getClients({ status: 'accepted', page_size: 100 }).catch(() => ({ results: [] })),
          getLeads({ page_size: 100 }).catch(() => ({ results: [] }))
        ])
        
        if (mounted) {
          setCustomers(customersData?.results || [])
          setLeads(leadsData?.results || [])
          setError(null)
        }
      } catch (err) {
        if (mounted) {
          setError(err.message || 'Failed to load families')
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }
    
    fetchFamilies()
    return () => { mounted = false }
  }, [])

  // Combine and normalize families from both sources
  const allFamilies = useMemo(() => {
    const normalized = []
    
    // Add platform customers
    for (const customer of customers) {
      normalized.push({
        id: customer.customer_id,
        type: 'customer',
        firstName: customer.first_name || '',
        lastName: customer.last_name || '',
        username: customer.username || '',
        email: customer.email || '',
        householdSize: customer.household_size || 1,
        dietaryPreferences: customer.dietary_preferences || [],
        allergies: customer.allergies || [],
        totalOrders: customer.total_orders || 0,
        source: 'Platform Customer'
      })
    }
    
    // Add CRM leads (manual contacts)
    for (const lead of leads) {
      normalized.push({
        id: lead.id,
        type: 'lead',
        firstName: lead.first_name || '',
        lastName: lead.last_name || '',
        username: '',
        email: lead.email || '',
        phone: lead.phone || '',
        householdSize: lead.household_size || 1,
        dietaryPreferences: lead.dietary_preferences || [],
        allergies: lead.allergies || [],
        totalOrders: 0,
        status: lead.status || 'new',
        source: lead.source_display || 'Manual Contact'
      })
    }
    
    return normalized
  }, [customers, leads])

  // Filter families based on search
  const filteredFamilies = useMemo(() => {
    if (!search.trim()) return allFamilies
    
    const searchLower = search.toLowerCase()
    return allFamilies.filter(family => {
      const name = `${family.firstName} ${family.lastName}`.toLowerCase()
      const username = family.username.toLowerCase()
      const email = family.email.toLowerCase()
      return name.includes(searchLower) || username.includes(searchLower) || email.includes(searchLower)
    })
  }, [allFamilies, search])

  // Get selected family info
  const selectedFamily = useMemo(() => {
    if (!selectedFamilyId) return null
    return allFamilies.find(f => f.id === selectedFamilyId && f.type === selectedFamilyType)
  }, [allFamilies, selectedFamilyId, selectedFamilyType])

  const handleSelect = (family) => {
    onFamilySelect({
      familyId: family.id,
      familyType: family.type,
      familyName: formatFamilyName(family)
    })
    setIsOpen(false)
    setSearch('')
  }

  const handleClear = (e) => {
    e.stopPropagation()  // Prevent dropdown from opening
    onFamilySelect({ familyId: null, familyType: null, familyName: null })
    setSearch('')
  }

  const handleSelectGeneralMode = () => {
    onFamilySelect({ familyId: null, familyType: null, familyName: null })
    setIsOpen(false)
    setSearch('')
  }

  const formatFamilyName = (family) => {
    const fullName = `${family.firstName} ${family.lastName}`.trim()
    return fullName || family.username || family.email || 'Family'
  }

  // Get initials for avatar display (matches formatFamilyName fallback order)
  const getInitials = (family) => {
    const first = family.firstName?.[0] || ''
    const last = family.lastName?.[0] || ''
    if (first || last) {
      return (first + last).toUpperCase()
    }
    // Fall back to username, then email (same order as formatFamilyName)
    if (family.username) {
      return family.username[0].toUpperCase()
    }
    return family.email?.[0]?.toUpperCase() || '?'
  }

  const getTypeBadge = (family) => {
    if (family.type === 'customer') {
      // Use CSS classes instead of inline styles for better theme support
      return { label: 'Platform', className: 'badge-platform' }
    }
    return { label: 'Manual', className: 'badge-manual' }
  }

  if (loading) {
    return (
      <div className={`family-selector ${className}`}>
        <div className="family-selector-loading">
          <span className="spinner-sm" /> Loading families...
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`family-selector ${className}`}>
        <div className="family-selector-error">
          Failed to load families: {error}
        </div>
      </div>
    )
  }

  if (allFamilies.length === 0) {
    return (
      <div className={`family-selector ${className}`}>
        <div className="family-selector-empty">
          No families yet. Add contacts in the Clients tab or connect with platform customers.
        </div>
      </div>
    )
  }

  return (
    <div className={`family-selector ${className}`}>
      <div 
        className={`family-selector-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        {selectedFamily ? (
          <div className="selected-family">
            <div className="family-avatar" data-type={selectedFamily.type}>
              {getInitials(selectedFamily)}
            </div>
            <div className="family-info">
              <div className="family-name">
                {formatFamilyName(selectedFamily)}
                <span className={`type-badge ${getTypeBadge(selectedFamily).className}`}>
                  {getTypeBadge(selectedFamily).label}
                </span>
              </div>
            </div>
            <button
              className="family-clear-btn"
              onClick={handleClear}
              title="Clear selection (General Mode)"
              aria-label="Clear family selection"
            >
              ×
            </button>
          </div>
        ) : (
          <div className="placeholder">
            <span className="icon">👨‍👩‍👧‍👦</span>
            <span>Select a family...</span>
          </div>
        )}
        <span className="chevron">{isOpen ? '▲' : '▼'}</span>
      </div>

      {isOpen && (
        <div className={`family-selector-dropdown ${openDirection === 'up' ? 'open-up' : 'open-down'}`}>
          <div className="search-wrapper">
            <input
              type="text"
              className="search-input"
              placeholder="Search families..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
            />
          </div>
          
          <div className="family-list">
            {/* General Mode option - always shown at top */}
            <div
              className={`family-option general-mode-option ${!selectedFamilyId ? 'selected' : ''}`}
              onClick={handleSelectGeneralMode}
            >
              <div className="family-avatar general-mode-avatar">
                🌐
              </div>
              <div className="family-details">
                <div className="family-name">
                  General Mode
                  <span className="type-badge badge-general">All Clients</span>
                </div>
                <div className="family-email muted">
                  Work without a specific client selected
                </div>
              </div>
            </div>
            <div className="group-divider" />

            {filteredFamilies.length === 0 ? (
              <div className="no-results">No families match your search</div>
            ) : (
              <>
                {/* Group: Manual Contacts (Leads) first since that's what user is asking about */}
                {filteredFamilies.filter(f => f.type === 'lead').length > 0 && (
                  <>
                    <div className="group-header">📋 Manual Contacts</div>
                    {filteredFamilies.filter(f => f.type === 'lead').map(family => (
                      <FamilyOption
                        key={`lead-${family.id}`}
                        family={family}
                        isSelected={selectedFamilyId === family.id && selectedFamilyType === 'lead'}
                        onSelect={handleSelect}
                        formatFamilyName={formatFamilyName}
                        getInitials={getInitials}
                        getTypeBadge={getTypeBadge}
                      />
                    ))}
                  </>
                )}
                
                {/* Group: Platform Customers */}
                {filteredFamilies.filter(f => f.type === 'customer').length > 0 && (
                  <>
                    <div className="group-header">👤 Platform Customers</div>
                    {filteredFamilies.filter(f => f.type === 'customer').map(family => (
                      <FamilyOption
                        key={`customer-${family.id}`}
                        family={family}
                        isSelected={selectedFamilyId === family.id && selectedFamilyType === 'customer'}
                        onSelect={handleSelect}
                        formatFamilyName={formatFamilyName}
                        getInitials={getInitials}
                        getTypeBadge={getTypeBadge}
                      />
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      <style>{`
        .family-selector {
          position: relative;
          width: 100%;
        }
        
        .family-selector-trigger {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0.75rem 1rem;
          background: var(--surface);
          color: var(--text);
          border: 1px solid var(--border);
          border-radius: 8px;
          cursor: pointer;
          transition: border-color 0.2s, box-shadow 0.2s;
        }

        .family-selector-trigger:hover {
          border-color: var(--primary);
        }

        .family-selector-trigger.open {
          border-color: var(--primary);
          box-shadow: 0 0 0 3px var(--primary-bg);
        }
        
        .selected-family {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        
        .family-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--primary);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 0.9rem;
          text-transform: uppercase;
          flex-shrink: 0;
        }

        .family-avatar[data-type="lead"] {
          background: var(--manual-color);
        }

        .family-avatar[data-type="customer"] {
          background: var(--platform-color);
        }
        
        .family-info {
          display: flex;
          flex-direction: column;
          gap: 0.125rem;
        }
        
        .family-name {
          font-weight: 500;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        
        .type-badge {
          font-size: 0.65rem;
          padding: 0.125rem 0.375rem;
          border-radius: 4px;
          font-weight: 600;
          text-transform: uppercase;
        }
        
        .type-badge.badge-platform {
          background: var(--platform-bg);
          color: var(--platform-color);
        }

        .type-badge.badge-manual {
          background: var(--manual-bg);
          color: var(--manual-color);
        }

        .type-badge.badge-general {
          background: var(--success-bg);
          color: var(--success);
        }

        .family-clear-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          border: none;
          border-radius: 50%;
          background: transparent;
          color: var(--muted);
          font-size: 1.25rem;
          line-height: 1;
          cursor: pointer;
          transition: background 0.15s, color 0.15s;
          margin-left: auto;
          margin-right: 0.5rem;
          flex-shrink: 0;
        }

        .family-clear-btn:hover {
          background: var(--danger-bg);
          color: var(--danger);
        }

        .placeholder {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--muted);
        }

        .placeholder .icon {
          font-size: 1.25rem;
        }

        .chevron {
          font-size: 0.75rem;
          color: var(--muted);
        }
        
        .family-selector-dropdown {
          position: absolute;
          left: 0;
          right: 0;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          box-shadow: var(--shadow-lg);
          z-index: 100;
          max-height: min(60vh, 520px);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        
        /* Dropdown opens downward (default) */
        .family-selector-dropdown.open-down {
          top: calc(100% + 4px);
        }
        
        /* Dropdown opens upward */
        .family-selector-dropdown.open-up {
          bottom: calc(100% + 4px);
          top: auto;
          flex-direction: column-reverse;
        }
        
        /* When opening up, reverse the internal order */
        .family-selector-dropdown.open-up .family-list {
          display: flex;
          flex-direction: column-reverse;
        }
        
        .family-selector-dropdown.open-up .search-wrapper {
          border-bottom: none;
          border-top: 1px solid var(--border);
        }
        
        .search-wrapper {
          padding: 0.75rem;
          border-bottom: 1px solid var(--border);
          position: sticky;
          top: 0;
          background: var(--surface);
          z-index: 2;
        }

        .search-input {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border: 1px solid var(--border);
          border-radius: 6px;
          font-size: 0.9rem;
          background: var(--surface-2);
          color: var(--text);
        }

        .search-input:focus {
          outline: none;
          border-color: var(--primary);
          box-shadow: 0 0 0 3px var(--primary-bg);
        }
        
        .family-list {
          overflow-y: auto;
          max-height: 100%;
        }
        
        .group-header {
          padding: 0.5rem 1rem;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--muted);
          background: var(--surface-2);
          border-bottom: 1px solid var(--border);
          position: sticky;
          top: 0;
        }

        .group-divider {
          height: 1px;
          background: var(--border);
          margin: 0;
        }

        .general-mode-option {
          background: var(--surface);
        }

        .general-mode-option:hover {
          background: var(--success-bg);
        }

        .general-mode-option.selected {
          background: var(--success-bg);
          border-left: 3px solid var(--success);
        }

        .general-mode-avatar {
          background: var(--success);
          font-size: 1.1rem;
        }
        
        .family-option {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          cursor: pointer;
          transition: background 0.15s, border-color 0.15s;
          border-bottom: 1px solid var(--border);
        }

        .family-option:hover {
          background: var(--surface-2);
        }

        .family-option.selected {
          background: var(--primary-bg);
          border-color: var(--primary);
        }
        
        .family-details {
          flex: 1;
          min-width: 0;
        }
        
        .family-email {
          font-size: 0.8rem;
          margin-top: 0.125rem;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .no-results {
          padding: 2rem 1rem;
          text-align: center;
          color: var(--muted);
        }

        .family-selector-loading,
        .family-selector-error,
        .family-selector-empty {
          padding: 1rem;
          text-align: center;
          color: var(--muted);
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
        }

        .family-selector-error {
          color: var(--danger);
          border-color: var(--danger);
        }

        .spinner-sm {
          display: inline-block;
          width: 14px;
          height: 14px;
          border: 2px solid var(--border);
          border-top-color: var(--primary);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-right: 0.5rem;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

/**
 * Individual family option in the dropdown.
 */
function FamilyOption({
  family,
  isSelected,
  onSelect,
  formatFamilyName,
  getInitials,
  getTypeBadge
}) {
  const badge = getTypeBadge(family)

  return (
    <div
      className={`family-option ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect(family)}
    >
      <div className="family-avatar" data-type={family.type}>
        {getInitials(family)}
      </div>
      <div className="family-details">
        <div className="family-name">
          {formatFamilyName(family)}
          <span className={`type-badge ${badge.className}`}>
            {badge.label}
          </span>
        </div>
        {family.email && (
          <div className="family-email muted">
            {family.email}
          </div>
        )}
      </div>
    </div>
  )
}
