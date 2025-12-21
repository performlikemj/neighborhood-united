import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import {
  createLead, updateLead, deleteLead,
  addHouseholdMember, updateHouseholdMember, deleteHouseholdMember,
  DIETARY_OPTIONS, ALLERGY_OPTIONS
} from '../api/chefCrmClient.js'
import { useConnections } from '../hooks/useConnections.js'
import MealPlanSlideout from './MealPlanSlideout.jsx'

const API_BASE = '/chefs/api/me'

const INITIAL_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  notes: '',
  dietary_preferences: [],
  allergies: []
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

export default function ChefAllClients() {
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

  // Load full client detail when selected
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
        allergies: editForm.allergies
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

  // Handle connection actions (accept/decline/end) for platform clients
  const handleConnectionAction = async (connectionId, action) => {
    if (!connectionId || !action) return
    setConnectionActionId(connectionId)
    try {
      await respondToConnection({ connectionId, action })
      await loadClients() // Refresh the client list
      const message = action === 'accept'
        ? 'Connection accepted!'
        : action === 'decline'
          ? 'Invitation declined.'
          : 'Connection ended.'
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

  const startEdit = () => {
    if (!selected || selected.source_type !== 'contact') return
    setEditForm({
      first_name: selected.name?.split(' ')[0] || '',
      last_name: selected.name?.split(' ').slice(1).join(' ') || '',
      email: selected.email || '',
      phone: selected.phone || '',
      notes: selected.notes || '',
      dietary_preferences: selected.dietary_preferences || [],
      allergies: selected.allergies || []
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

  // Styles
  const styles = {
    container: { maxWidth: '1400px', margin: '0 auto', padding: '0 1rem' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' },
    headerTitle: { margin: 0, fontSize: 'clamp(1.5rem, 4vw, 2rem)', fontWeight: 700 },
    headerSubtitle: { margin: '.5rem 0 0 0', color: 'var(--muted)', fontSize: 'clamp(0.85rem, 2vw, 1rem)' },
    primaryBtn: { background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white', border: 'none', padding: '.75rem 1.5rem', borderRadius: '12px', fontWeight: 600, fontSize: '.95rem', cursor: 'pointer', boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)', transition: 'all 0.2s ease', whiteSpace: 'nowrap' },
    secondaryBtn: { background: 'var(--surface-2)', color: 'var(--text)', border: '1.5px solid var(--border)', padding: '.5rem 1rem', borderRadius: '8px', fontWeight: 500, fontSize: '.9rem', cursor: 'pointer' },
    dangerBtn: { background: 'rgba(220, 38, 38, 0.1)', color: '#dc2626', border: 'none', padding: '.5rem 1rem', borderRadius: '8px', fontSize: '.85rem', fontWeight: 500, cursor: 'pointer' },
    formCard: { background: 'var(--surface)', borderRadius: '16px', padding: 'clamp(1rem, 3vw, 1.5rem)', marginBottom: '1.5rem', border: '1px solid var(--border)', boxShadow: '0 4px 20px rgba(0,0,0,0.05)' },
    formTitle: { margin: '0 0 1.25rem 0', fontSize: '1.25rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '.5rem' },
    formGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' },
    formGroup: { display: 'flex', flexDirection: 'column', gap: '.4rem' },
    formLabel: { fontSize: '.85rem', fontWeight: 500, color: 'var(--text)' },
    formInput: { padding: '.75rem 1rem', borderRadius: '10px', border: '1.5px solid var(--border)', fontSize: '1rem', background: 'var(--surface)', color: 'var(--text)', width: '100%', boxSizing: 'border-box' },
    textarea: { padding: '.75rem 1rem', borderRadius: '10px', border: '1.5px solid var(--border)', fontSize: '1rem', background: 'var(--surface)', color: 'var(--text)', resize: 'vertical', minHeight: '80px', fontFamily: 'inherit', width: '100%', boxSizing: 'border-box' },
    chipContainer: { display: 'flex', flexWrap: 'wrap', gap: '.4rem', marginTop: '.25rem' },
    chip: { padding: '.4rem .75rem', borderRadius: '20px', fontSize: '.8rem', fontWeight: 500, cursor: 'pointer', border: '1.5px solid var(--border)', background: 'var(--surface-2)', transition: 'all 0.15s ease', userSelect: 'none' },
    statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', marginBottom: '1.5rem' },
    statCard: { background: 'var(--surface-1)', borderRadius: '16px', padding: 'clamp(.75rem, 2vw, 1.25rem)', textAlign: 'center', cursor: 'pointer', border: '2px solid transparent', transition: 'all 0.2s ease', boxShadow: '0 2px 10px rgba(0,0,0,0.04)' },
    statNumber: { fontSize: 'clamp(1.75rem, 5vw, 2.5rem)', fontWeight: 700, lineHeight: 1, marginBottom: '.25rem' },
    statLabel: { fontSize: 'clamp(.75rem, 2vw, .9rem)', color: 'var(--muted)', fontWeight: 500 },
    glanceCard: { background: 'var(--surface)', borderRadius: '16px', padding: '1rem 1.25rem', marginBottom: '1rem', border: '1px solid var(--border)' },
    glanceTitle: { margin: '0 0 .75rem 0', fontSize: '.8rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.05em' },
    filterBar: { background: 'var(--surface)', borderRadius: '16px', padding: '1rem', marginBottom: '1rem', border: '1px solid var(--border)' },
    filterRow: { display: 'flex', flexWrap: 'wrap', gap: '.75rem', alignItems: 'center' },
    searchInput: { flex: '1 1 250px', minWidth: '150px', padding: '.75rem 1rem', paddingLeft: '2.5rem', borderRadius: '10px', border: '1.5px solid var(--border)', fontSize: '.95rem', background: 'var(--surface)', color: 'var(--text)', backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%239ca3af'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: '.75rem center', backgroundSize: '1.25rem' },
    select: { padding: '.75rem 2rem .75rem 1rem', borderRadius: '10px', border: '1.5px solid var(--border)', fontSize: '.9rem', background: 'var(--surface)', color: 'var(--text)', cursor: 'pointer', appearance: 'none', backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%236b7280'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right .75rem center', backgroundSize: '1rem', minWidth: '130px' },
    mainGrid: { display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' },
    clientListCard: { background: 'var(--surface)', borderRadius: '16px', border: '1px solid var(--border)', overflow: 'hidden' },
    clientListHeader: { padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', background: 'var(--surface-2)', position: 'sticky', top: 0, zIndex: 10 },
    clientListTitle: { margin: 0, fontSize: '1rem', fontWeight: 600 },
    clientListContent: { padding: '.75rem', maxHeight: '60vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '.5rem' },
    clientCard: { padding: '1rem', borderRadius: '12px', border: '1.5px solid var(--border)', cursor: 'pointer', transition: 'all 0.15s ease', background: 'var(--surface)', color: 'var(--text)' },
    clientCardSelected: { borderColor: 'var(--accent)', background: 'color-mix(in oklab, var(--surface) 85%, var(--accent) 15%)', boxShadow: '0 0 0 3px rgba(16, 185, 129, 0.1)' },
    clientName: { fontWeight: 600, fontSize: '1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '.5rem', flexWrap: 'wrap' },
    badge: { padding: '.2rem .6rem', borderRadius: '6px', fontSize: '.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.03em' },
    badgePlatform: { background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', color: 'white' },
    badgeManual: { background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', color: 'white' },
    householdBadge: { background: 'var(--surface-2)', padding: '.2rem .5rem', borderRadius: '6px', fontSize: '.75rem', fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: '.25rem' },
    detailPanel: { background: 'var(--surface)', borderRadius: '16px', border: '1px solid var(--border)', overflow: 'hidden' },
    detailContent: { padding: '1.5rem', minHeight: isDesktop ? '65vh' : '70vh' },
    detailEmpty: { textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--muted)' },
    detailEmptyIcon: { fontSize: '3.5rem', marginBottom: '1rem', opacity: 0.5 },
    sectionTitle: { margin: '0 0 .75rem 0', fontSize: '.8rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.05em' },
    infoBox: { padding: '1rem', background: 'var(--surface-2)', borderRadius: '12px', marginBottom: '1rem' },
    householdMember: { padding: '.875rem', background: 'var(--surface-2)', borderRadius: '10px', borderLeft: '3px solid var(--accent)', marginBottom: '.5rem' },
  }

  // Components
  const Badge = ({ type }) => (
    <span style={{ ...styles.badge, ...(type === 'platform' ? styles.badgePlatform : styles.badgeManual) }}>
      {type === 'platform' ? '● Platform' : '◉ Manual'}
    </span>
  )

  const DietaryChips = ({ items = [], type = 'dietary' }) => {
    if (!items.length) return <span style={{ color: 'var(--muted)', fontSize: '.85rem' }}>None specified</span>
    const filtered = type === 'allergy' ? items.filter(a => a && a !== 'None') : items
    if (!filtered.length) return <span style={{ color: 'var(--muted)', fontSize: '.85rem' }}>None</span>
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.3rem' }}>
        {filtered.map(item => (
          <span key={item} style={{ padding: '.25rem .6rem', borderRadius: '6px', fontSize: '.75rem', fontWeight: 500, background: type === 'allergy' ? 'rgba(220, 38, 38, 0.1)' : 'rgba(16, 185, 129, 0.1)', color: type === 'allergy' ? '#dc2626' : '#059669' }}>
            {type === 'allergy' && '⚠ '}{item}
          </span>
        ))}
      </div>
    )
  }

  const ChipSelector = ({ options, selected, onChange, type = 'dietary' }) => (
    <div style={styles.chipContainer}>
      {options.slice(0, type === 'allergy' ? 8 : 10).map(opt => (
        <span key={opt} style={{ ...styles.chip, ...(selected.includes(opt) ? (type === 'allergy' ? { background: '#dc2626', color: 'white', borderColor: '#dc2626' } : { background: 'var(--accent)', color: 'white', borderColor: 'var(--accent)' }) : (type === 'allergy' ? { background: '#fef2f2', color: '#dc2626', borderColor: '#fecaca' } : {})) }}
          onClick={() => onChange(togglePreference(selected, opt))}>
          {opt}
        </span>
      ))}
    </div>
  )

  const ClientCard = ({ client, isSelected, onClick }) => {
    // Get connection status for platform clients
    const clientConnection = client.source_type === 'platform' 
      ? getConnectionForCustomer(client.customer_id) 
      : null
    const isPending = clientConnection?.isPending
    const allergies = client.allergies?.filter(a => a && a !== 'None') || []
    const hasAllergies = allergies.length > 0
    
    return (
      <div onClick={onClick} style={{ 
        ...styles.clientCard, 
        ...(isSelected ? styles.clientCardSelected : {}),
        ...(isPending ? { borderColor: 'rgba(245, 158, 11, 0.5)', background: 'rgba(245, 158, 11, 0.03)' } : {})
      }}>
        {/* Top row: Name + badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', flexWrap: 'wrap', marginBottom: '.35rem' }}>
          <span style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text)' }}>{client.name}</span>
          <Badge type={client.source_type} />
          {isPending && (
            <span style={{ 
              padding: '.15rem .5rem', 
              borderRadius: '4px', 
              fontSize: '.65rem', 
              fontWeight: 600,
              background: 'rgba(245, 158, 11, 0.15)', 
              color: '#b45309',
              textTransform: 'uppercase',
              letterSpacing: '.03em'
            }}>
              ⏳ Pending
            </span>
          )}
        </div>
        
        {/* Email */}
        {client.email && (
          <div style={{ color: 'var(--muted)', fontSize: '.8rem', marginBottom: '.5rem', display: 'flex', alignItems: 'center', gap: '.35rem' }}>
            <span style={{ opacity: 0.5, fontSize: '.7rem' }}>📧</span> {client.email}
          </div>
        )}
        
        {/* Quick info row: household + dietary icons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '.75rem', flexWrap: 'wrap' }}>
          {/* Household indicator */}
          {client.household_size > 1 && (
            <span style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: '.25rem',
              fontSize: '.75rem',
              color: 'var(--muted)',
              padding: '.2rem .5rem',
              background: 'var(--surface-2)',
              borderRadius: '4px'
            }}>
              👥 {client.household_size}
              {client.household_size > (client.household_members?.length || 0) + 1 && (
                <span title="Household profiles incomplete" style={{ color: '#f59e0b' }}>⚠</span>
              )}
            </span>
          )}
          
          {/* Dietary preferences - compact icons */}
          {client.dietary_preferences?.length > 0 && (
            <span style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: '.25rem',
              fontSize: '.75rem',
              color: '#059669',
              padding: '.2rem .5rem',
              background: 'rgba(16, 185, 129, 0.08)',
              borderRadius: '4px'
            }}>
              🥗 {client.dietary_preferences.slice(0, 2).join(', ')}
              {client.dietary_preferences.length > 2 && ` +${client.dietary_preferences.length - 2}`}
            </span>
          )}
          
          {/* Allergies - prominent warning */}
          {hasAllergies && (
            <span style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              gap: '.25rem',
              fontSize: '.75rem',
              color: '#dc2626',
              fontWeight: 600,
              padding: '.2rem .5rem',
              background: 'rgba(220, 38, 38, 0.1)',
              borderRadius: '4px'
            }}>
              ⚠️ {allergies.slice(0, 2).join(', ')}
              {allergies.length > 2 && ` +${allergies.length - 2}`}
            </span>
          )}
        </div>
      </div>
    )
  }

  // Member Form Component
  const MemberForm = ({ isEditing, onSubmit, onCancel }) => (
    <div style={{ ...styles.formCard, marginTop: '1rem', background: 'var(--surface-2)' }}>
      <h4 style={{ margin: '0 0 1rem 0', fontSize: '1rem' }}>{isEditing ? '✏️ Edit Household Member' : '➕ Add Household Member'}</h4>
      <form onSubmit={onSubmit}>
        <div style={styles.formGrid}>
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Name *</label>
            <input type="text" style={styles.formInput} value={memberForm.name} onChange={e => setMemberForm(f => ({ ...f, name: e.target.value }))} placeholder="Jane" required />
          </div>
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Relationship</label>
            <input type="text" style={styles.formInput} value={memberForm.relationship} onChange={e => setMemberForm(f => ({ ...f, relationship: e.target.value }))} placeholder="Spouse, Child, etc." />
          </div>
          <div style={styles.formGroup}>
            <label style={styles.formLabel}>Age</label>
            <input type="number" style={styles.formInput} value={memberForm.age} onChange={e => setMemberForm(f => ({ ...f, age: e.target.value }))} placeholder="35" min="0" max="120" />
          </div>
        </div>
        <div style={{ marginTop: '1rem' }}>
          <label style={styles.formLabel}>Dietary Preferences</label>
          <ChipSelector options={DIETARY_OPTIONS} selected={memberForm.dietary_preferences} onChange={v => setMemberForm(f => ({ ...f, dietary_preferences: v }))} type="dietary" />
        </div>
        <div style={{ marginTop: '.75rem' }}>
          <label style={styles.formLabel}>Allergies</label>
          <ChipSelector options={ALLERGY_OPTIONS.filter(a => a !== 'None')} selected={memberForm.allergies} onChange={v => setMemberForm(f => ({ ...f, allergies: v }))} type="allergy" />
        </div>
        <div style={{ marginTop: '.75rem' }}>
          <label style={styles.formLabel}>Notes</label>
          <textarea style={styles.textarea} rows="2" value={memberForm.notes} onChange={e => setMemberForm(f => ({ ...f, notes: e.target.value }))} placeholder="Any additional notes..." />
        </div>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '.5rem' }}>
          <button type="submit" style={styles.primaryBtn} disabled={saving || !memberForm.name.trim()}>{saving ? 'Saving...' : isEditing ? 'Update Member' : 'Add Member'}</button>
          <button type="button" style={styles.secondaryBtn} onClick={onCancel}>Cancel</button>
        </div>
      </form>
    </div>
  )

  // Client Detail Component
  const ClientDetail = ({ client, onClose }) => {
    if (!client) return (
      <div style={styles.detailEmpty}>
        <div style={styles.detailEmptyIcon}>👥</div>
        <div style={{ fontSize: '1.1rem', fontWeight: 500, marginBottom: '.5rem' }}>Select a client</div>
        <div style={{ fontSize: '.9rem' }}>View and edit their dietary profile</div>
      </div>
    )

    const canEdit = client.source_type === 'contact'
    
    // For platform clients, get connection details
    const connection = client.source_type === 'platform' 
      ? getConnectionForCustomer(client.customer_id) 
      : null
    const isPlatformPending = connection?.isPending
    const isPlatformAccepted = connection?.isAccepted
    const canAcceptConnection = connection?.canAccept
    const canDeclineConnection = connection?.canDecline
    const canEndConnection = connection?.canEnd
    const isThisConnectionBusy = connectionMutating && String(connectionActionId) === String(connection?.id)

    // Edit Mode View
    if (editMode && canEdit) {
      return (
        <div style={styles.detailContent}>
          <h3 style={{ margin: '0 0 1rem 0' }}>✏️ Edit Client</h3>
          <form onSubmit={handleUpdateClient}>
            <div style={styles.formGrid}>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>First Name *</label>
                <input type="text" style={styles.formInput} value={editForm.first_name} onChange={e => setEditForm(f => ({ ...f, first_name: e.target.value }))} required />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Last Name</label>
                <input type="text" style={styles.formInput} value={editForm.last_name} onChange={e => setEditForm(f => ({ ...f, last_name: e.target.value }))} />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Email</label>
                <input type="email" style={styles.formInput} value={editForm.email} onChange={e => setEditForm(f => ({ ...f, email: e.target.value }))} />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.formLabel}>Phone</label>
                <input type="tel" style={styles.formInput} value={editForm.phone} onChange={e => setEditForm(f => ({ ...f, phone: e.target.value }))} />
              </div>
            </div>
            <div style={{ marginTop: '1rem' }}>
              <label style={styles.formLabel}>Dietary Preferences</label>
              <ChipSelector options={DIETARY_OPTIONS} selected={editForm.dietary_preferences} onChange={v => setEditForm(f => ({ ...f, dietary_preferences: v }))} type="dietary" />
            </div>
            <div style={{ marginTop: '.75rem' }}>
              <label style={styles.formLabel}>Allergies</label>
              <ChipSelector options={ALLERGY_OPTIONS.filter(a => a !== 'None')} selected={editForm.allergies} onChange={v => setEditForm(f => ({ ...f, allergies: v }))} type="allergy" />
            </div>
            <div style={{ marginTop: '.75rem' }}>
              <label style={styles.formLabel}>Notes</label>
              <textarea style={styles.textarea} value={editForm.notes} onChange={e => setEditForm(f => ({ ...f, notes: e.target.value }))} placeholder="Notes about this client..." />
            </div>
            <div style={{ marginTop: '1rem', display: 'flex', gap: '.5rem' }}>
              <button type="submit" style={styles.primaryBtn} disabled={saving}>{saving ? 'Saving...' : 'Save Changes'}</button>
              <button type="button" style={styles.secondaryBtn} onClick={() => setEditMode(false)}>Cancel</button>
            </div>
          </form>
        </div>
      )
    }

    // Normal Detail View
    return (
      <div style={styles.detailContent}>
        {!isDesktop && <button onClick={onClose} style={{ background: 'none', border: 'none', padding: '.5rem 0', marginBottom: '.75rem', cursor: 'pointer', color: 'var(--accent)', fontWeight: 500, fontSize: '.9rem' }}>← Back to list</button>}
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '.5rem' }}>
          <div>
            <h3 style={{ margin: '0 0 .5rem 0', fontSize: '1.35rem', fontWeight: 700 }}>{client.name}</h3>
            <Badge type={client.source_type} />
          </div>
          {canEdit && (
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <button onClick={startEdit} style={styles.secondaryBtn}>✏️ Edit</button>
              <button onClick={() => handleDelete(client)} style={styles.dangerBtn}>Remove</button>
            </div>
          )}
        </div>

        {/* Connection Status & Actions for Platform Clients */}
        {client.source_type === 'platform' && connection && (
          <div style={{ 
            marginBottom: '1.25rem', 
            padding: '1rem', 
            background: isPlatformPending ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.08)', 
            borderRadius: '12px',
            border: `1px solid ${isPlatformPending ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.2)'}`
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '.75rem' }}>
              <div>
                <div style={{ fontSize: '.8rem', color: 'var(--muted)', marginBottom: '.25rem', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '.03em' }}>
                  Connection Status
                </div>
                <div style={{ 
                  display: 'inline-flex', 
                  alignItems: 'center', 
                  gap: '.4rem',
                  padding: '.3rem .75rem',
                  borderRadius: '6px',
                  fontSize: '.85rem',
                  fontWeight: 600,
                  background: isPlatformPending ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  color: isPlatformPending ? '#b45309' : '#059669'
                }}>
                  <span style={{ fontSize: '.6rem' }}>{isPlatformPending ? '⏳' : '✓'}</span>
                  {isPlatformPending ? 'Pending Request' : 'Connected'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
                {canAcceptConnection && (
                  <button
                    onClick={() => handleConnectionAction(connection.id, 'accept')}
                    disabled={isThisConnectionBusy}
                    style={{
                      ...styles.primaryBtn,
                      padding: '.5rem 1rem',
                      fontSize: '.85rem',
                      opacity: isThisConnectionBusy ? 0.6 : 1
                    }}
                  >
                    {isThisConnectionBusy ? 'Updating...' : '✓ Accept'}
                  </button>
                )}
                {canDeclineConnection && (
                  <button
                    onClick={() => handleConnectionAction(connection.id, 'decline')}
                    disabled={isThisConnectionBusy}
                    style={{
                      ...styles.secondaryBtn,
                      padding: '.5rem 1rem',
                      fontSize: '.85rem',
                      opacity: isThisConnectionBusy ? 0.6 : 1
                    }}
                  >
                    Decline
                  </button>
                )}
                {canEndConnection && (
                  <button
                    onClick={() => {
                      if (confirm(`End connection with ${client.name}? They will no longer have access to your personalized offerings.`)) {
                        handleConnectionAction(connection.id, 'end')
                      }
                    }}
                    disabled={isThisConnectionBusy}
                    style={{
                      ...styles.dangerBtn,
                      padding: '.5rem 1rem',
                      fontSize: '.85rem',
                      opacity: isThisConnectionBusy ? 0.6 : 1
                    }}
                  >
                    {isThisConnectionBusy ? 'Ending...' : 'End Connection'}
                  </button>
                )}
              </div>
            </div>
            {respondError && connectionActionId === connection.id && (
              <div style={{ marginTop: '.75rem', padding: '.5rem', background: 'rgba(220, 38, 38, 0.1)', borderRadius: '6px', fontSize: '.85rem', color: '#dc2626' }}>
                {respondError?.response?.data?.detail || respondError?.message || 'Failed to update connection'}
              </div>
            )}
          </div>
        )}

        {/* Contact Info */}
        {(client.email || client.phone) && (
          <div style={styles.infoBox}>
            {client.email && <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: client.phone ? '.5rem' : 0 }}><span style={{ opacity: 0.6 }}>📧</span> {client.email}</div>}
            {client.phone && <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}><span style={{ opacity: 0.6 }}>📞</span> {client.phone}</div>}
          </div>
        )}

        {/* Dietary Profile */}
        <div style={{ marginBottom: '1.25rem' }}>
          <h4 style={styles.sectionTitle}>Dietary Preferences</h4>
          <div style={styles.infoBox}><DietaryChips items={client.dietary_preferences} type="dietary" /></div>
          <h4 style={styles.sectionTitle}>Allergies</h4>
          <div style={styles.infoBox}><DietaryChips items={client.allergies} type="allergy" /></div>
        </div>

        {/* Household Members */}
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <h4 style={{ ...styles.sectionTitle, margin: 0 }}>
              Household ({(client.household_members?.length || 0) + 1})
              {client.household_size > (client.household_members?.length || 0) + 1 && (
                <span style={{ fontWeight: 400, color: '#f59e0b', marginLeft: '.5rem' }} title="Customer indicated more household members">
                  ({client.household_size} claimed)
                </span>
              )}
            </h4>
            {canEdit && !showAddMember && !editingMember && (
              <button onClick={() => { setShowAddMember(true); setMemberForm({ ...INITIAL_MEMBER }) }} style={{ ...styles.secondaryBtn, padding: '.35rem .75rem', fontSize: '.8rem' }}>+ Add Member</button>
            )}
          </div>
          
          {client.household_members?.length > 0 ? (
            client.household_members.map(member => (
              editingMember?.id === member.id ? (
                <MemberForm key={member.id} isEditing={true} onSubmit={handleUpdateMember} onCancel={() => { setEditingMember(null); setMemberForm({ ...INITIAL_MEMBER }) }} />
              ) : (
                <div key={member.id} style={styles.householdMember}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.5rem' }}>
                    <strong style={{ fontSize: '.95rem' }}>{member.name}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem' }}>
                      <span style={{ fontSize: '.8rem', color: 'var(--muted)' }}>{member.relationship}{member.age && `, ${member.age}y`}</span>
                      {canEdit && (
                        <>
                          <button onClick={() => startEditMember(member)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '.2rem', fontSize: '.8rem' }}>✏️</button>
                          <button onClick={() => handleDeleteMember(member.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '.2rem', fontSize: '.8rem', color: '#dc2626' }}>🗑️</button>
                        </>
                      )}
                    </div>
                  </div>
                  {(member.dietary_preferences?.length > 0 || member.allergies?.filter(a => a && a !== 'None').length > 0) && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
                      {member.dietary_preferences?.map(p => (<span key={p} style={{ padding: '.15rem .5rem', borderRadius: '4px', fontSize: '.7rem', background: 'rgba(16, 185, 129, 0.1)', color: '#059669' }}>{p}</span>))}
                      {member.allergies?.filter(a => a && a !== 'None').map(a => (<span key={a} style={{ padding: '.15rem .5rem', borderRadius: '4px', fontSize: '.7rem', background: 'rgba(220, 38, 38, 0.1)', color: '#dc2626' }}>⚠ {a}</span>))}
                    </div>
                  )}
                  {member.notes && <div style={{ marginTop: '.4rem', fontSize: '.8rem', color: 'var(--muted)', fontStyle: 'italic' }}>{member.notes}</div>}
                </div>
              )
            ))
          ) : (
            !showAddMember && (
              <div style={{ ...styles.infoBox, color: 'var(--muted)', fontSize: '.9rem' }}>
                {client.household_size > 1 ? (
                  <>
                    <span style={{ color: '#f59e0b' }}>⚠</span> Customer indicated {client.household_size} household members but profiles haven't been added yet.
                  </>
                ) : (
                  'No additional household members'
                )}
              </div>
            )
          )}
          
          {showAddMember && <MemberForm isEditing={false} onSubmit={handleAddMember} onCancel={() => { setShowAddMember(false); setMemberForm({ ...INITIAL_MEMBER }) }} />}
        </div>

        {/* Meal Plans Section - Available for all clients */}
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <h4 style={{ ...styles.sectionTitle, margin: 0 }}>
              <span style={{ marginRight: '.35rem' }}>📅</span> Meal Plans
            </h4>
          </div>
          <div style={{
            ...styles.infoBox,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '.5rem'
          }}>
            <span style={{ color: 'var(--muted)', fontSize: '.9rem' }}>
              Create personalized meal plans with AI assistance
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setMealPlanOpen(true)
              }}
              style={{
                padding: '.5rem 1rem',
                background: 'linear-gradient(135deg, var(--primary, #5cb85c), #4a9d4a)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '.85rem',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '.35rem',
                position: 'relative',
                zIndex: 10
              }}
            >
              ✨ Manage Plans
            </button>
          </div>
        </div>

        {/* Notes */}
        {client.notes && (
          <div>
            <h4 style={styles.sectionTitle}>Notes</h4>
            <div style={{ ...styles.infoBox, fontStyle: 'italic', color: 'var(--muted)' }}>{client.notes}</div>
          </div>
        )}
      </div>
    )
  }

  // Mobile detail view
  if (!isDesktop && showDetail && selected) {
    return (
      <div style={styles.container}>
        <div style={styles.detailPanel}>
          <ClientDetail client={selected} onClose={() => setShowDetail(false)} />
        </div>
        
        {/* Meal Plan Slideout - must be included in mobile view */}
        <MealPlanSlideout
          isOpen={mealPlanOpen}
          onClose={() => setMealPlanOpen(false)}
          client={selected}
          onPlanUpdate={() => {
            // Optionally refresh client data
          }}
        />
      </div>
    )
  }

  return (
    <div className="clients-page" style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div>
          <h2 style={styles.headerTitle}>My Clients</h2>
          <p style={styles.headerSubtitle}>Manage your clients and their dietary needs</p>
        </div>
        <button style={styles.primaryBtn} onClick={() => setShowAddForm(!showAddForm)}>{showAddForm ? '✕ Cancel' : '+ Add Client'}</button>
      </header>

      {/* Add Client Form */}
      {showAddForm && (
        <div style={styles.formCard}>
          <h3 style={styles.formTitle}><span style={{ fontSize: '1.25rem' }}>👤</span> New Client</h3>
          <form onSubmit={handleAddClient}>
            <div style={styles.formGrid}>
              <div style={styles.formGroup}><label style={styles.formLabel}>First Name *</label><input type="text" style={styles.formInput} value={form.first_name} onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} placeholder="John" required /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Last Name</label><input type="text" style={styles.formInput} value={form.last_name} onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))} placeholder="Doe" /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Email</label><input type="email" style={styles.formInput} value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="john@example.com" /></div>
              <div style={styles.formGroup}><label style={styles.formLabel}>Phone</label><input type="tel" style={styles.formInput} value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="+1 (555) 000-0000" /></div>
            </div>
            <div style={{ marginTop: '1.25rem' }}><label style={styles.formLabel}>Dietary Preferences</label><ChipSelector options={DIETARY_OPTIONS} selected={form.dietary_preferences} onChange={v => setForm(f => ({ ...f, dietary_preferences: v }))} type="dietary" /></div>
            <div style={{ marginTop: '1rem' }}><label style={styles.formLabel}>Allergies</label><ChipSelector options={ALLERGY_OPTIONS.filter(a => a !== 'None')} selected={form.allergies} onChange={v => setForm(f => ({ ...f, allergies: v }))} type="allergy" /></div>
            <div style={{ marginTop: '1.25rem' }}><label style={styles.formLabel}>Notes</label><textarea style={styles.textarea} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="How did you meet? Any special requirements?" /></div>
            <div style={{ marginTop: '1.5rem' }}><button type="submit" style={{ ...styles.primaryBtn, opacity: saving || !form.first_name.trim() ? 0.6 : 1 }} disabled={saving || !form.first_name.trim()}>{saving ? 'Saving...' : '✓ Save Client'}</button></div>
          </form>
        </div>
      )}

      {/* Stats Cards */}
      {summary && !showAddForm && (
        <div style={styles.statsGrid}>
          <div style={{ ...styles.statCard, borderColor: sourceFilter === '' ? 'var(--accent)' : 'transparent', background: sourceFilter === '' ? 'rgba(16, 185, 129, 0.05)' : 'var(--surface-1)' }} onClick={() => setSourceFilter('')}><div style={styles.statNumber}>{summary.total}</div><div style={styles.statLabel}>All Clients</div></div>
          <div style={{ ...styles.statCard, borderColor: sourceFilter === 'platform' ? '#10b981' : 'transparent', background: sourceFilter === 'platform' ? 'rgba(16, 185, 129, 0.05)' : 'var(--surface-1)' }} onClick={() => setSourceFilter(sourceFilter === 'platform' ? '' : 'platform')}><div style={{ ...styles.statNumber, color: '#10b981' }}>{summary.platform}</div><div style={styles.statLabel}>🟢 Platform</div></div>
          <div style={{ ...styles.statCard, borderColor: sourceFilter === 'contact' ? '#6366f1' : 'transparent', background: sourceFilter === 'contact' ? 'rgba(99, 102, 241, 0.05)' : 'var(--surface-1)' }} onClick={() => setSourceFilter(sourceFilter === 'contact' ? '' : 'contact')}><div style={{ ...styles.statNumber, color: '#6366f1' }}>{summary.contacts}</div><div style={styles.statLabel}>📋 Manual</div></div>
        </div>
      )}

      {/* At a Glance */}
      {summary && !showAddForm && (Object.keys(summary.dietary_breakdown || {}).length > 0 || Object.keys(summary.allergy_breakdown || {}).length > 0) && (
        <div style={styles.glanceCard}>
          <h4 style={styles.glanceTitle}>At a Glance</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem' }}>
            {Object.entries(summary.dietary_breakdown || {}).slice(0, 4).map(([pref, count]) => (<span key={pref} style={{ padding: '.4rem .75rem', borderRadius: '8px', fontSize: '.85rem', fontWeight: 500, background: 'rgba(16, 185, 129, 0.1)', color: '#059669' }}>{pref}: {count}</span>))}
            {Object.entries(summary.allergy_breakdown || {}).slice(0, 3).map(([allergy, count]) => (<span key={allergy} style={{ padding: '.4rem .75rem', borderRadius: '8px', fontSize: '.85rem', fontWeight: 500, background: 'rgba(220, 38, 38, 0.1)', color: '#dc2626' }}>⚠ {allergy}: {count}</span>))}
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div style={styles.filterBar}>
        <div style={styles.filterRow}>
          <input type="text" style={styles.searchInput} placeholder="Search clients..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
          <select style={styles.select} value={ordering} onChange={e => setOrdering(e.target.value)}>
            <option value="-connected_since">Newest</option>
            <option value="connected_since">Oldest</option>
            <option value="name">A → Z</option>
            <option value="-name">Z → A</option>
          </select>
          {sourceFilter && <button onClick={() => setSourceFilter('')} style={styles.dangerBtn}>Clear filter</button>}
        </div>
      </div>

      {/* Main Content */}
      <div style={{ ...styles.mainGrid, gridTemplateColumns: isDesktop ? '1fr 1fr' : '1fr' }}>
        {/* Client List */}
        <div style={styles.clientListCard}>
          <div style={styles.clientListHeader}><h3 style={styles.clientListTitle}>{loading ? 'Loading...' : `${clients.length} Client${clients.length !== 1 ? 's' : ''}`}</h3></div>
          <div style={styles.clientListContent}>
            {loading ? (<div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Loading clients...</div>) : clients.length === 0 ? (<div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}><div style={{ fontSize: '2rem', marginBottom: '.5rem', opacity: 0.5 }}>📋</div>{searchQuery || sourceFilter ? 'No clients match your search' : 'No clients yet. Add your first client!'}</div>) : (clients.map(client => (<ClientCard key={client.id} client={client} isSelected={selected?.id === client.id} onClick={() => selectClient(client)} />)))}
          </div>
        </div>

        {/* Detail Panel - Desktop only */}
        {isDesktop && (<div style={styles.detailPanel}><ClientDetail client={selected} onClose={() => setSelected(null)} /></div>)}
      </div>

      {/* Meal Plan Slideout */}
      <MealPlanSlideout
        isOpen={mealPlanOpen}
        onClose={() => setMealPlanOpen(false)}
        client={selected}
        onPlanUpdate={() => {
          // Optionally refresh client data
        }}
      />

      <style>{`
        .clients-page input::placeholder,
        .clients-page textarea::placeholder {
          color: var(--muted, #666);
        }
        .clients-page select option {
          color: var(--text, #333);
          background: var(--surface, #fff);
        }
        .clients-page .client-card:hover {
          border-color: var(--accent, #10b981);
          background: color-mix(in oklab, var(--surface) 80%, var(--accent) 12%);
        }
      `}</style>
    </div>
  )
}
