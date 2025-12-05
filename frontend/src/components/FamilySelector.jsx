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
  className = ''
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

  const formatFamilyName = (family) => {
    const fullName = `${family.firstName} ${family.lastName}`.trim()
    return fullName || family.username || family.email || 'Family'
  }

  const formatDietarySummary = (family) => {
    const items = []
    if (family.dietaryPreferences?.length) {
      items.push(...family.dietaryPreferences.slice(0, 2))
    }
    if (family.allergies?.length) {
      items.push(`⚠️ ${family.allergies.length} allergies`)
    }
    return items.length ? items.join(' • ') : 'No restrictions'
  }

  const getTypeIcon = (type) => {
    return type === 'customer' ? '👤' : '📋'
  }

  const getTypeBadge = (family) => {
    if (family.type === 'customer') {
      return { label: 'Platform', color: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' }
    }
    return { label: 'Manual', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.1)' }
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
              {getTypeIcon(selectedFamily.type)}
            </div>
            <div className="family-info">
              <div className="family-name">
                {formatFamilyName(selectedFamily)}
                <span className="type-badge" style={{
                  background: getTypeBadge(selectedFamily).bg,
                  color: getTypeBadge(selectedFamily).color
                }}>
                  {getTypeBadge(selectedFamily).label}
                </span>
              </div>
              <div className="family-meta muted">
                {selectedFamily.householdSize} members
                {selectedFamily.totalOrders > 0 && ` • ${selectedFamily.totalOrders} orders`}
              </div>
            </div>
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
        <div className="family-selector-dropdown">
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
                        formatDietarySummary={formatDietarySummary}
                        getTypeIcon={getTypeIcon}
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
                        formatDietarySummary={formatDietarySummary}
                        getTypeIcon={getTypeIcon}
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
          background: var(--bg-card, #fff);
          color: var(--text, #333);
          border: 1px solid var(--border-color, #ddd);
          border-radius: 8px;
          cursor: pointer;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        
        .family-selector-trigger:hover {
          border-color: var(--accent-color, #3b82f6);
        }
        
        .family-selector-trigger.open {
          border-color: var(--accent-color, #3b82f6);
          box-shadow: 0 0 0 3px var(--accent-color-alpha, rgba(59, 130, 246, 0.1));
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
          background: var(--accent-gradient, linear-gradient(135deg, #3b82f6, #8b5cf6));
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 1.25rem;
        }
        
        .family-avatar[data-type="lead"] {
          background: linear-gradient(135deg, #8b5cf6, #a855f7);
        }
        
        .family-avatar[data-type="customer"] {
          background: linear-gradient(135deg, #10b981, #059669);
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
        
        .family-meta {
          font-size: 0.8rem;
        }
        
        .placeholder {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: var(--text-muted, #888);
        }
        
        .placeholder .icon {
          font-size: 1.25rem;
        }
        
        .chevron {
          font-size: 0.75rem;
          color: var(--text-muted, #888);
        }
        
        .family-selector-dropdown {
          position: absolute;
          top: calc(100% + 4px);
          left: 0;
          right: 0;
          background: var(--bg-card, #fff);
          border: 1px solid var(--border-color, #ddd);
          border-radius: 8px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
          z-index: 100;
          max-height: 450px;
          display: flex;
          flex-direction: column;
        }
        
        .search-wrapper {
          padding: 0.75rem;
          border-bottom: 1px solid var(--border-color, #ddd);
        }

        .search-input {
          width: 100%;
          padding: 0.5rem 0.75rem;
          border: 1px solid var(--border-color, #ddd);
          border-radius: 6px;
          font-size: 0.9rem;
          background: var(--surface, #fff);
          color: var(--text, #333);
        }

        .search-input:focus {
          outline: none;
          border-color: var(--accent-color, #3b82f6);
          box-shadow: 0 0 0 3px var(--accent-color-alpha, rgba(59, 130, 246, 0.14));
        }
        
        .family-list {
          overflow-y: auto;
          max-height: 380px;
        }
        
        .group-header {
          padding: 0.5rem 1rem;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--text-muted, #888);
          background: var(--bg-page, #f9fafb);
          border-bottom: 1px solid var(--border-color, #eee);
          position: sticky;
          top: 0;
        }
        
        .family-option {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem 1rem;
          cursor: pointer;
          transition: background 0.15s, border-color 0.15s;
          border-bottom: 1px solid var(--border-color, #ddd);
        }

        .family-option:hover {
          background: color-mix(in oklab, var(--bg-card, #fff) 70%, var(--accent-color, #3b82f6) 10%);
        }

        .family-option.selected {
          background: var(--accent-color-alpha, rgba(59, 130, 246, 0.1));
          border-color: var(--accent-color, #3b82f6);
        }
        
        .family-details {
          flex: 1;
          min-width: 0;
        }
        
        .family-dietary {
          font-size: 0.8rem;
          margin-top: 0.125rem;
        }
        
        .family-stats {
          font-size: 0.75rem;
          margin-top: 0.125rem;
        }
        
        .no-results {
          padding: 2rem 1rem;
          text-align: center;
          color: var(--text-muted, #888);
        }
        
        .family-selector-loading,
        .family-selector-error,
        .family-selector-empty {
          padding: 1rem;
          text-align: center;
          color: var(--text-muted, #888);
          background: var(--bg-card, #fff);
          border: 1px solid var(--border-color, #ddd);
          border-radius: 8px;
        }
        
        .family-selector-error {
          color: var(--error-color, #ef4444);
          border-color: var(--error-color, #ef4444);
        }
        
        .spinner-sm {
          display: inline-block;
          width: 14px;
          height: 14px;
          border: 2px solid var(--border-color, #ddd);
          border-top-color: var(--accent-color, #3b82f6);
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
  formatDietarySummary,
  getTypeIcon,
  getTypeBadge 
}) {
  const badge = getTypeBadge(family)
  
  return (
    <div
      className={`family-option ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect(family)}
    >
      <div className="family-avatar" data-type={family.type}>
        {getTypeIcon(family.type)}
      </div>
      <div className="family-details">
        <div className="family-name">
          {formatFamilyName(family)}
          <span className="type-badge" style={{ background: badge.bg, color: badge.color }}>
            {badge.label}
          </span>
        </div>
        <div className="family-dietary muted">
          {formatDietarySummary(family)}
        </div>
        <div className="family-stats muted">
          {family.householdSize} members
          {family.totalOrders > 0 && ` • ${family.totalOrders} orders`}
          {family.email && ` • ${family.email}`}
        </div>
      </div>
    </div>
  )
}
