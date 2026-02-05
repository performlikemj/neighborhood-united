import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import {
  createLead, updateLead, deleteLead,
  addHouseholdMember, updateHouseholdMember, deleteHouseholdMember,
  DIETARY_OPTIONS, ALLERGY_OPTIONS
} from '../api/chefCrmClient.js'
import { useConnections } from '../hooks/useConnections.js'
import MealPlanSlideout from './MealPlanSlideout.jsx'

// New modular components
import {
  ClientsHeader,
  ClientMetrics,
  ClientInsights,
  ClientList,
  ClientDetail,
  PendingRequests
} from './clients'

// Import the new CSS
import '../styles/chef-clients.css'

const API_BASE = '/chefs/api/me'

// Style hints for detail panel layout
const styles = {
  detailContent: {
    minHeight: '400px',
    flex: 1
  }
}

const INITIAL_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  notes: '',
  dietary_preferences: [],
  allergies: [],
  birthday_month: null,
  birthday_day: null,
  anniversary: null
}

const INITIAL_MEMBER = {
  name: '',
  relationship: '',
  age: '',
  dietary_preferences: [],
  allergies: [],
  notes: ''
}

// Media query helper
const useMediaQuery = (query) => {
  const [matches, setMatches] = useState(false)
  useEffect(() => {
    const media = window.matchMedia(query)
    setMatches(media.matches)
    const listener = () => setMatches(media.matches)
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [query])
  return matches
}

export default function ChefAllClients({ onNavigateToPrep }) {
  // Core state
  const [clients, setClients] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [form, setForm] = useState({ ...INITIAL_FORM })
  const [saving, setSaving] = useState(false)
  const [showDetail, setShowDetail] = useState(false)

  // Edit mode states
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState({ ...INITIAL_FORM })
  const [showAddMember, setShowAddMember] = useState(false)
  const [memberForm, setMemberForm] = useState({ ...INITIAL_MEMBER })
  const [editingMember, setEditingMember] = useState(null)

  // Meal plan slideout
  const [mealPlanOpen, setMealPlanOpen] = useState(false)

  const isDesktop = useMediaQuery('(min-width: 900px)')

  // Connection management for platform clients
  const {
    connections,
    pendingConnections,
    respondToConnection,
    respondStatus,
    respondError
  } = useConnections('chef')
  const [connectionActionId, setConnectionActionId] = useState(null)
  const connectionMutating = respondStatus === 'pending'

  // Get connection for a platform client by customer_id
  const getConnectionForCustomer = useCallback((customerId) => {
    if (!customerId || !connections?.length) return null
    return connections.find(c =>
      String(c.customerId) === String(customerId) ||
      String(c.customer_id) === String(customerId)
    )
  }, [connections])

  // Filters
  const [sourceFilter, setSourceFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [ordering, setOrdering] = useState('-connected_since')

  // Data loading
  const loadClients = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (sourceFilter) params.append('source', sourceFilter)
      if (searchQuery) params.append('search', searchQuery)
      if (ordering) params.append('ordering', ordering)

      const response = await api.get(`${API_BASE}/all-clients/?${params.toString()}`, {
        skipUserId: true,
        withCredentials: true
      })

      setClients(response.data?.results || [])
      setSummary(response.data?.summary || null)
    } catch (err) {
      console.warn('Failed to load clients:', err)
      setClients([])
    } finally {
      setLoading(false)
    }
  }

  const loadClientDetail = async (client) => {
    if (client.source_type !== 'contact') {
      setSelected(client)
      return
    }
    try {
      const response = await api.get(`${API_BASE}/all-clients/${client.id}/`, {
        skipUserId: true,
        withCredentials: true
      })
      setSelected(response.data)
    } catch (err) {
      console.warn('Failed to load client detail:', err)
      setSelected(client)
    }
  }

  useEffect(() => {
    loadClients()
  }, [sourceFilter, ordering])

  useEffect(() => {
    const timeout = setTimeout(() => loadClients(), 300)
    return () => clearTimeout(timeout)
  }, [searchQuery])

  // CRUD handlers
  const handleAddClient = async (e) => {
    e.preventDefault()
    if (!form.first_name.trim()) return
    setSaving(true)
    try {
      await createLead({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        notes: form.notes.trim(),
        dietary_preferences: form.dietary_preferences,
        allergies: form.allergies,
        source: 'referral',
        status: 'won'
      })
      setForm({ ...INITIAL_FORM })
      setShowAddForm(false)
      await loadClients()
    } catch (err) {
      console.error('Failed to create client:', err)
      alert('Failed to save client')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateClient = async (e) => {
    e.preventDefault()
    if (!selected || selected.source_type !== 'contact') return
    setSaving(true)
    try {
      await updateLead(selected.lead_id, {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim(),
        notes: editForm.notes.trim(),
        dietary_preferences: editForm.dietary_preferences,
        allergies: editForm.allergies,
        birthday_month: editForm.birthday_month,
        birthday_day: editForm.birthday_day,
        anniversary: editForm.anniversary
      })
      setEditMode(false)
      await loadClients()
      await loadClientDetail({ ...selected, id: selected.id })
    } catch (err) {
      console.error('Failed to update client:', err)
      alert('Failed to update client')
    } finally {
      setSaving(false)
    }
  }

  const handleAddMember = async (e) => {
    e.preventDefault()
    if (!selected || !memberForm.name.trim()) return
    setSaving(true)
    try {
      await addHouseholdMember(selected.lead_id, {
        name: memberForm.name.trim(),
        relationship: memberForm.relationship.trim(),
        age: memberForm.age ? parseInt(memberForm.age) : null,
        dietary_preferences: memberForm.dietary_preferences,
        allergies: memberForm.allergies,
        notes: memberForm.notes.trim()
      })
      setMemberForm({ ...INITIAL_MEMBER })
      setShowAddMember(false)
      await loadClientDetail({ ...selected, id: selected.id })
    } catch (err) {
      console.error('Failed to add household member:', err)
      alert('Failed to add household member')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdateMember = async (e) => {
    e.preventDefault()
    if (!selected || !editingMember) return
    setSaving(true)
    try {
      await updateHouseholdMember(selected.lead_id, editingMember.id, {
        name: memberForm.name.trim(),
        relationship: memberForm.relationship.trim(),
        age: memberForm.age ? parseInt(memberForm.age) : null,
        dietary_preferences: memberForm.dietary_preferences,
        allergies: memberForm.allergies,
        notes: memberForm.notes.trim()
      })
      setMemberForm({ ...INITIAL_MEMBER })
      setEditingMember(null)
      await loadClientDetail({ ...selected, id: selected.id })
    } catch (err) {
      console.error('Failed to update household member:', err)
      alert('Failed to update household member')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMember = async (memberId) => {
    if (!selected || !confirm('Remove this household member?')) return
    try {
      await deleteHouseholdMember(selected.lead_id, memberId)
      await loadClientDetail({ ...selected, id: selected.id })
    } catch (err) {
      console.error('Failed to delete household member:', err)
    }
  }

  const handleDelete = async (client) => {
    if (client.source_type !== 'contact') {
      alert('Platform connections can be ended using the "End Connection" button in the client detail panel.')
      return
    }
    if (!confirm(`Remove ${client.name} and their household?`)) return
    try {
      await deleteLead(client.lead_id)
      await loadClients()
      if (selected?.id === client.id) setSelected(null)
    } catch (err) {
      console.error('Failed to delete client:', err)
    }
  }

  // Connection actions
  const handleConnectionAction = async (connectionId, action) => {
    if (!connectionId || !action) return
    setConnectionActionId(connectionId)
    try {
      await respondToConnection({ connectionId, action })
      await loadClients()
      const message = action === 'accept'
        ? 'Connection accepted!'
        : action === 'decline'
          ? 'Invitation declined.'
          : action === 'end'
            ? 'Connection ended.'
            : 'Connection updated.'
      try {
        window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: message, tone: 'success' } }))
      } catch {}
    } catch (error) {
      const msg = error?.response?.data?.detail || 'Unable to update this connection. Please try again.'
      try {
        window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: msg, tone: 'error' } }))
      } catch {}
    } finally {
      setConnectionActionId(null)
    }
  }

  // Edit helpers
  const startEdit = () => {
    if (!selected || selected.source_type !== 'contact') return
    setEditForm({
      first_name: selected.name?.split(' ')[0] || '',
      last_name: selected.name?.split(' ').slice(1).join(' ') || '',
      email: selected.email || '',
      phone: selected.phone || '',
      notes: selected.notes || '',
      dietary_preferences: selected.dietary_preferences || [],
      allergies: selected.allergies || [],
      birthday_month: selected.birthday_month || null,
      birthday_day: selected.birthday_day || null,
      anniversary: selected.anniversary || null
    })
    setEditMode(true)
  }

  const startEditMember = (member) => {
    setMemberForm({
      name: member.name || '',
      relationship: member.relationship || '',
      age: member.age?.toString() || '',
      dietary_preferences: member.dietary_preferences || [],
      allergies: member.allergies || [],
      notes: member.notes || ''
    })
    setEditingMember(member)
    setShowAddMember(false)
  }

  const togglePreference = (list, item) => {
    return list.includes(item) ? list.filter(i => i !== item) : [...list, item]
  }

  const selectClient = (client) => {
    loadClientDetail(client)
    setEditMode(false)
    setShowAddMember(false)
    setEditingMember(null)
    if (!isDesktop) setShowDetail(true)
  }

  // Calculate total people served
  const totalPeople = clients.reduce((sum, c) => sum + (c.household_size || 1), 0)

  // Helper Components
  const DietaryChips = ({ items = [], type = 'dietary' }) => {
    if (!items.length) return <span style={{ color: 'var(--muted)', fontSize: '.85rem' }}>None specified</span>
    const filtered = type === 'allergy' ? items.filter(a => a && a !== 'None') : items
    if (!filtered.length) return <span style={{ color: 'var(--muted)', fontSize: '.85rem' }}>None</span>
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.3rem' }}>
        {filtered.map(item => (
          <span
            key={item}
            className={`cc-insight-chip ${type === 'allergy' ? 'cc-insight-chip-allergy' : 'cc-insight-chip-dietary'}`}
          >
            {type === 'allergy' && '⚠ '}{item}
          </span>
        ))}
      </div>
    )
  }

  const ChipSelector = ({ options, selected, onChange, type = 'dietary' }) => (
    <div className="cc-chip-container">
      {options.slice(0, type === 'allergy' ? 8 : 10).map(opt => (
        <span
          key={opt}
          className={`cc-chip ${type === 'allergy' ? 'cc-chip-allergy' : ''} ${selected.includes(opt) ? 'cc-chip-selected' : ''}`}
          onClick={() => onChange(togglePreference(selected, opt))}
        >
          {opt}
        </span>
      ))}
    </div>
  )

  const MemberForm = ({ isEditing, memberForm: mf, saving: sv, onSetMemberForm, onSubmit, onCancel }) => (
    <div className="cc-form-card" style={{ marginTop: '1rem', background: 'var(--surface-2)' }}>
      <h4 className="cc-form-title" style={{ fontSize: '1rem' }}>
        {isEditing ? '✏️ Edit Household Member' : '➕ Add Household Member'}
      </h4>
      <form onSubmit={onSubmit}>
        <div className="cc-form-grid">
          <div className="cc-form-group">
            <label className="cc-form-label">Name *</label>
            <input
              type="text"
              className="cc-form-input"
              value={mf.name}
              onChange={e => onSetMemberForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Jane"
              required
            />
          </div>
          <div className="cc-form-group">
            <label className="cc-form-label">Relationship</label>
            <input
              type="text"
              className="cc-form-input"
              value={mf.relationship}
              onChange={e => onSetMemberForm(f => ({ ...f, relationship: e.target.value }))}
              placeholder="Spouse, Child, etc."
            />
          </div>
          <div className="cc-form-group">
            <label className="cc-form-label">Age</label>
            <input
              type="number"
              className="cc-form-input"
              value={mf.age}
              onChange={e => onSetMemberForm(f => ({ ...f, age: e.target.value }))}
              placeholder="35"
              min="0"
              max="120"
            />
          </div>
        </div>
        <div style={{ marginTop: '1rem' }}>
          <label className="cc-form-label">Dietary Preferences</label>
          <ChipSelector
            options={DIETARY_OPTIONS}
            selected={mf.dietary_preferences}
            onChange={v => onSetMemberForm(f => ({ ...f, dietary_preferences: v }))}
            type="dietary"
          />
        </div>
        <div style={{ marginTop: '.75rem' }}>
          <label className="cc-form-label">Allergies</label>
          <ChipSelector
            options={ALLERGY_OPTIONS.filter(a => a !== 'None')}
            selected={mf.allergies}
            onChange={v => onSetMemberForm(f => ({ ...f, allergies: v }))}
            type="allergy"
          />
        </div>
        <div style={{ marginTop: '.75rem' }}>
          <label className="cc-form-label">Notes</label>
          <textarea
            className="cc-form-textarea"
            rows="2"
            value={mf.notes}
            onChange={e => onSetMemberForm(f => ({ ...f, notes: e.target.value }))}
            placeholder="Any additional notes..."
          />
        </div>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '.5rem' }}>
          <button type="submit" className="cc-btn cc-btn-primary" disabled={sv || !mf.name.trim()}>
            {sv ? 'Saving...' : isEditing ? 'Update Member' : 'Add Member'}
          </button>
          <button type="button" className="cc-btn cc-btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )

  // Mobile detail view
  if (!isDesktop && showDetail && selected) {
    const connection = selected.source_type === 'platform'
      ? getConnectionForCustomer(selected.customer_id)
      : null

    return (
      <div className="cc-container">
        <div className="cc-detail-panel">
          <ClientDetail
            client={selected}
            isDesktop={isDesktop}
            editMode={editMode}
            editForm={editForm}
            saving={saving}
            showAddMember={showAddMember}
            editingMember={editingMember}
            memberForm={memberForm}
            connection={connection}
            connectionMutating={connectionMutating}
            connectionActionId={connectionActionId}
            respondError={respondError}
            onClose={() => setShowDetail(false)}
            onStartEdit={startEdit}
            onCancelEdit={() => setEditMode(false)}
            onSaveEdit={handleUpdateClient}
            onDelete={handleDelete}
            onSetEditForm={setEditForm}
            onSetMemberForm={setMemberForm}
            onStartAddMember={() => { setShowAddMember(true); setMemberForm({ ...INITIAL_MEMBER }) }}
            onStartEditMember={startEditMember}
            onCancelMember={() => { setShowAddMember(false); setEditingMember(null); setMemberForm({ ...INITIAL_MEMBER }) }}
            onSubmitAddMember={handleAddMember}
            onSubmitEditMember={handleUpdateMember}
            onDeleteMember={handleDeleteMember}
            onConnectionAction={handleConnectionAction}
            onOpenMealPlan={() => setMealPlanOpen(true)}
            DIETARY_OPTIONS={DIETARY_OPTIONS}
            ALLERGY_OPTIONS={ALLERGY_OPTIONS}
            ChipSelector={ChipSelector}
            DietaryChips={DietaryChips}
            MemberForm={MemberForm}
            INITIAL_MEMBER={INITIAL_MEMBER}
          />
        </div>

        <MealPlanSlideout
          isOpen={mealPlanOpen}
          onClose={() => setMealPlanOpen(false)}
          client={selected}
          onPlanUpdate={() => {}}
          onNavigateToPrep={onNavigateToPrep}
        />
      </div>
    )
  }

  // Get connection for selected client
  const selectedConnection = selected?.source_type === 'platform'
    ? getConnectionForCustomer(selected.customer_id)
    : null

  return (
    <div className="cc-container">
      {/* Hero Header */}
      <ClientsHeader
        totalClients={summary?.total || 0}
        totalPeople={totalPeople}
        showAddForm={showAddForm}
        onToggleAddForm={() => setShowAddForm(!showAddForm)}
      />

      {/* Add Client Form */}
      {showAddForm && (
        <div className="cc-form-card">
          <h3 className="cc-form-title">
            <span style={{ fontSize: '1.25rem' }}>👤</span> New Client
          </h3>
          <form onSubmit={handleAddClient}>
            <div className="cc-form-grid">
              <div className="cc-form-group">
                <label className="cc-form-label">First Name *</label>
                <input
                  type="text"
                  className="cc-form-input"
                  value={form.first_name}
                  onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))}
                  placeholder="John"
                  required
                />
              </div>
              <div className="cc-form-group">
                <label className="cc-form-label">Last Name</label>
                <input
                  type="text"
                  className="cc-form-input"
                  value={form.last_name}
                  onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))}
                  placeholder="Doe"
                />
              </div>
              <div className="cc-form-group">
                <label className="cc-form-label">Email</label>
                <input
                  type="email"
                  className="cc-form-input"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="john@example.com"
                />
              </div>
              <div className="cc-form-group">
                <label className="cc-form-label">Phone</label>
                <input
                  type="tel"
                  className="cc-form-input"
                  value={form.phone}
                  onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  placeholder="+1 (555) 000-0000"
                />
              </div>
            </div>
            <div style={{ marginTop: '1.25rem' }}>
              <label className="cc-form-label">Dietary Preferences</label>
              <ChipSelector
                options={DIETARY_OPTIONS}
                selected={form.dietary_preferences}
                onChange={v => setForm(f => ({ ...f, dietary_preferences: v }))}
                type="dietary"
              />
            </div>
            <div style={{ marginTop: '1rem' }}>
              <label className="cc-form-label">Allergies</label>
              <ChipSelector
                options={ALLERGY_OPTIONS.filter(a => a !== 'None')}
                selected={form.allergies}
                onChange={v => setForm(f => ({ ...f, allergies: v }))}
                type="allergy"
              />
            </div>
            <div style={{ marginTop: '1.25rem' }}>
              <label className="cc-form-label">Notes</label>
              <textarea
                className="cc-form-textarea"
                value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                placeholder="How did you meet? Any special requirements?"
              />
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <button
                type="submit"
                className="cc-btn cc-btn-primary"
                disabled={saving || !form.first_name.trim()}
              >
                {saving ? 'Saving...' : '✓ Save Client'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Pending Connection Requests */}
      {!showAddForm && (
        <PendingRequests
          pendingConnections={pendingConnections}
          onAccept={(id) => handleConnectionAction(id, 'accept')}
          onDecline={(id) => handleConnectionAction(id, 'decline')}
          connectionMutating={connectionMutating}
          connectionActionId={connectionActionId}
        />
      )}

      {/* Metrics Dashboard */}
      {summary && !showAddForm && (
        <ClientMetrics
          summary={summary}
          pendingCount={pendingConnections?.length || 0}
          sourceFilter={sourceFilter}
          onFilterChange={setSourceFilter}
        />
      )}

      {/* Dietary Insights */}
      {summary && !showAddForm && (
        <ClientInsights summary={summary} />
      )}

      {/* Filter Bar */}
      <div className="cc-filter-bar">
        <div className="cc-filter-row">
          <div className="cc-search-wrapper">
            <span className="cc-search-icon">🔍</span>
            <input
              type="text"
              className="cc-search-input"
              placeholder="Search clients..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>
          <select
            className="cc-select"
            value={ordering}
            onChange={e => setOrdering(e.target.value)}
          >
            <option value="-connected_since">Newest</option>
            <option value="connected_since">Oldest</option>
            <option value="name">A → Z</option>
            <option value="-name">Z → A</option>
          </select>
          {sourceFilter && (
            <button
              className="cc-btn cc-btn-danger cc-btn-sm"
              onClick={() => setSourceFilter('')}
            >
              Clear filter
            </button>
          )}
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="cc-main-grid">
        {/* Client List */}
        <ClientList
          clients={clients}
          loading={loading}
          selected={selected}
          searchQuery={searchQuery}
          sourceFilter={sourceFilter}
          getConnectionForCustomer={getConnectionForCustomer}
          onSelectClient={selectClient}
        />

        {/* Detail Panel - Desktop only */}
        {isDesktop && (
          <div className="cc-detail-panel">
            <ClientDetail
              client={selected}
              isDesktop={isDesktop}
              editMode={editMode}
              editForm={editForm}
              saving={saving}
              showAddMember={showAddMember}
              editingMember={editingMember}
              memberForm={memberForm}
              connection={selectedConnection}
              connectionMutating={connectionMutating}
              connectionActionId={connectionActionId}
              respondError={respondError}
              onClose={() => setSelected(null)}
              onStartEdit={startEdit}
              onCancelEdit={() => setEditMode(false)}
              onSaveEdit={handleUpdateClient}
              onDelete={handleDelete}
              onSetEditForm={setEditForm}
              onSetMemberForm={setMemberForm}
              onStartAddMember={() => { setShowAddMember(true); setMemberForm({ ...INITIAL_MEMBER }) }}
              onStartEditMember={startEditMember}
              onCancelMember={() => { setShowAddMember(false); setEditingMember(null); setMemberForm({ ...INITIAL_MEMBER }) }}
              onSubmitAddMember={handleAddMember}
              onSubmitEditMember={handleUpdateMember}
              onDeleteMember={handleDeleteMember}
              onConnectionAction={handleConnectionAction}
              onOpenMealPlan={() => setMealPlanOpen(true)}
              DIETARY_OPTIONS={DIETARY_OPTIONS}
              ALLERGY_OPTIONS={ALLERGY_OPTIONS}
              ChipSelector={ChipSelector}
              DietaryChips={DietaryChips}
              MemberForm={MemberForm}
              INITIAL_MEMBER={INITIAL_MEMBER}
            />
          </div>
        )}
      </div>

      {/* Meal Plan Slideout */}
      <MealPlanSlideout
        isOpen={mealPlanOpen}
        onClose={() => setMealPlanOpen(false)}
        client={selected}
        onPlanUpdate={() => {}}
        onNavigateToPrep={onNavigateToPrep}
      />
    </div>
  )
}
