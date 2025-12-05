import React, { useState, useEffect } from 'react'
import {
  getLeads, createLead, deleteLead, updateLead,
  addLeadInteraction, getLeadInteractions,
  addHouseholdMember, deleteHouseholdMember,
  DIETARY_OPTIONS, ALLERGY_OPTIONS
} from '../api/chefCrmClient.js'

const INITIAL_FORM = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  notes: '',
  dietary_preferences: [],
  allergies: [],
  household_members: []
}

const INITIAL_MEMBER = {
  name: '',
  relationship: '',
  age: '',
  dietary_preferences: [],
  allergies: [],
  notes: ''
}

export default function ChefContacts() {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({ ...INITIAL_FORM })
  const [selected, setSelected] = useState(null)
  const [interactions, setInteractions] = useState([])
  const [noteForm, setNoteForm] = useState({ summary: '', interaction_type: 'note' })
  const [noteSaving, setNoteSaving] = useState(false)
  const [showMemberForm, setShowMemberForm] = useState(false)
  const [memberForm, setMemberForm] = useState({ ...INITIAL_MEMBER })
  const [memberSaving, setMemberSaving] = useState(false)

  const loadContacts = async () => {
    setLoading(true)
    try {
      const data = await getLeads({ status: 'won' })
      setContacts(Array.isArray(data?.results) ? data.results : Array.isArray(data) ? data : [])
    } catch (err) {
      console.warn('Failed to load contacts:', err)
      setContacts([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadContacts()
  }, [])

  const handleSubmit = async (e) => {
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
        household_members: form.household_members,
        source: 'referral',
        status: 'won'
      })
      setForm({ ...INITIAL_FORM })
      setShowForm(false)
      await loadContacts()
    } catch (err) {
      console.error('Failed to create contact:', err)
      alert('Failed to save contact')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Remove this contact and their household?')) return
    try {
      await deleteLead(id)
      await loadContacts()
      if (selected?.id === id) setSelected(null)
    } catch (err) {
      console.error('Failed to delete contact:', err)
    }
  }

  const selectContact = async (contact) => {
    setSelected(contact)
    setShowMemberForm(false)
    if (contact?.id) {
      try {
        const data = await getLeadInteractions(contact.id)
        setInteractions(Array.isArray(data) ? data : [])
      } catch {
        setInteractions([])
      }
    } else {
      setInteractions([])
    }
  }

  const handleAddNote = async (e) => {
    e.preventDefault()
    if (!selected?.id || !noteForm.summary.trim()) return
    setNoteSaving(true)
    try {
      await addLeadInteraction(selected.id, {
        summary: noteForm.summary.trim(),
        interaction_type: noteForm.interaction_type
      })
      setNoteForm({ summary: '', interaction_type: 'note' })
      const data = await getLeadInteractions(selected.id)
      setInteractions(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to add note:', err)
    } finally {
      setNoteSaving(false)
    }
  }

  const handleAddMember = async (e) => {
    e.preventDefault()
    if (!selected?.id || !memberForm.name.trim()) return
    setMemberSaving(true)
    try {
      await addHouseholdMember(selected.id, {
        name: memberForm.name.trim(),
        relationship: memberForm.relationship.trim(),
        age: memberForm.age ? parseInt(memberForm.age) : null,
        dietary_preferences: memberForm.dietary_preferences,
        allergies: memberForm.allergies,
        notes: memberForm.notes.trim()
      })
      setMemberForm({ ...INITIAL_MEMBER })
      setShowMemberForm(false)
      // Refresh contact to get updated household
      await loadContacts()
      const updated = contacts.find(c => c.id === selected.id)
      if (updated) setSelected(updated)
    } catch (err) {
      console.error('Failed to add household member:', err)
    } finally {
      setMemberSaving(false)
    }
  }

  const handleDeleteMember = async (memberId) => {
    if (!selected?.id || !confirm('Remove this household member?')) return
    try {
      await deleteHouseholdMember(selected.id, memberId)
      await loadContacts()
    } catch (err) {
      console.error('Failed to delete member:', err)
    }
  }

  const togglePreference = (list, item) => {
    return list.includes(item) 
      ? list.filter(i => i !== item)
      : [...list, item]
  }

  const renderDietaryPills = (items = []) => {
    if (!items.length) return <span className="muted">None specified</span>
    return items.map(item => (
      <span key={item} className="chip small" style={{ marginRight: '.25rem', marginBottom: '.25rem' }}>
        {item}
      </span>
    ))
  }

  return (
    <div>
      <header style={{ marginBottom: '1rem' }}>
        <h2 style={{ margin: 0 }}>My Clients</h2>
        <p className="muted" style={{ marginTop: '.25rem' }}>
          Track clients and their households with dietary preferences and allergies.
        </p>
      </header>

      {/* Add Contact Form */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '.5rem' }}>
          <h3 style={{ margin: 0 }}>Add New Client</h3>
          <button className="btn btn-outline btn-sm" onClick={() => setShowForm(!showForm)}>
            {showForm ? 'Cancel' : '+ Add Client'}
          </button>
        </div>
        {showForm && (
          <form onSubmit={handleSubmit} style={{ marginTop: '1rem' }}>
            <div className="grid grid-2" style={{ gap: '.75rem' }}>
              <div>
                <label className="form-label">First Name *</label>
                <input type="text" className="form-input" value={form.first_name} 
                  onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))} required />
              </div>
              <div>
                <label className="form-label">Last Name</label>
                <input type="text" className="form-input" value={form.last_name}
                  onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))} />
              </div>
              <div>
                <label className="form-label">Email</label>
                <input type="email" className="form-input" value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              </div>
              <div>
                <label className="form-label">Phone</label>
                <input type="tel" className="form-input" value={form.phone}
                  onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} />
              </div>
            </div>
            
            <div style={{ marginTop: '.75rem' }}>
              <label className="form-label">Dietary Preferences</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
                {DIETARY_OPTIONS.map(opt => (
                  <button key={opt} type="button"
                    className={`chip small ${form.dietary_preferences.includes(opt) ? 'active' : ''}`}
                    style={{ cursor: 'pointer', background: form.dietary_preferences.includes(opt) ? 'var(--accent)' : undefined, color: form.dietary_preferences.includes(opt) ? 'white' : undefined }}
                    onClick={() => setForm(f => ({ ...f, dietary_preferences: togglePreference(f.dietary_preferences, opt) }))}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
            
            <div style={{ marginTop: '.75rem' }}>
              <label className="form-label">Allergies</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
                {ALLERGY_OPTIONS.map(opt => (
                  <button key={opt} type="button"
                    className={`chip small ${form.allergies.includes(opt) ? 'active' : ''}`}
                    style={{ cursor: 'pointer', background: form.allergies.includes(opt) ? '#d9534f' : undefined, color: form.allergies.includes(opt) ? 'white' : undefined }}
                    onClick={() => setForm(f => ({ ...f, allergies: togglePreference(f.allergies, opt) }))}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
            
            <div style={{ marginTop: '.75rem' }}>
              <label className="form-label">Notes</label>
              <textarea className="form-input" rows="2" value={form.notes}
                onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                placeholder="How did you meet? Any special requirements?" />
            </div>
            
            <div style={{ marginTop: '.75rem' }}>
              <button type="submit" className="btn btn-primary" disabled={saving || !form.first_name.trim()}>
                {saving ? 'Saving...' : 'Save Client'}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Contacts List and Detail */}
      <div className="grid grid-2" style={{ gap: '1rem' }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Clients ({contacts.length})</h3>
          {loading ? (
            <div className="muted">Loading...</div>
          ) : contacts.length === 0 ? (
            <div className="muted">No clients yet. Add your first client above!</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.5rem' }}>
              {contacts.map(c => (
                <div key={c.id} className="card"
                  style={{ padding: '.75rem', cursor: 'pointer', border: selected?.id === c.id ? '2px solid var(--accent)' : '1px solid var(--border)' }}
                  onClick={() => selectContact(c)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <strong>{c.first_name} {c.last_name}</strong>
                      {c.household_size > 1 && (
                        <span className="chip small" style={{ marginLeft: '.5rem', background: 'var(--surface-2)' }}>
                          👥 {c.household_size}
                        </span>
                      )}
                      {c.email && <div className="muted" style={{ fontSize: '.85rem' }}>{c.email}</div>}
                    </div>
                    <button className="btn btn-outline btn-sm" style={{ color: '#d33' }}
                      onClick={(e) => { e.stopPropagation(); handleDelete(c.id) }}>✕</button>
                  </div>
                  {(c.dietary_preferences?.length > 0 || c.allergies?.length > 0) && (
                    <div style={{ marginTop: '.4rem', fontSize: '.8rem' }}>
                      {c.dietary_preferences?.map(p => (
                        <span key={p} className="chip small" style={{ marginRight: '.2rem', fontSize: '.7rem' }}>{p}</span>
                      ))}
                      {c.allergies?.filter(a => a !== 'None').map(a => (
                        <span key={a} className="chip small" style={{ marginRight: '.2rem', fontSize: '.7rem', background: '#ffeeba', color: '#856404' }}>⚠️ {a}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Contact Detail */}
        <div className="card" style={{ maxHeight: '80vh', overflowY: 'auto' }}>
          {selected ? (
            <>
              <h3 style={{ marginTop: 0 }}>{selected.first_name} {selected.last_name}</h3>
              {selected.email && <p className="muted" style={{ margin: '0 0 .25rem 0' }}>📧 {selected.email}</p>}
              {selected.phone && <p className="muted" style={{ margin: '0 0 .5rem 0' }}>📞 {selected.phone}</p>}
              
              {/* Dietary Info */}
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '.9rem' }}>Dietary Preferences:</strong>
                <div style={{ marginTop: '.25rem' }}>{renderDietaryPills(selected.dietary_preferences)}</div>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <strong style={{ fontSize: '.9rem' }}>Allergies:</strong>
                <div style={{ marginTop: '.25rem' }}>{renderDietaryPills(selected.allergies?.filter(a => a !== 'None'))}</div>
              </div>
              
              {selected.notes && (
                <p style={{ margin: '0 0 1rem 0', padding: '.5rem', background: 'var(--surface-2)', borderRadius: '8px', fontSize: '.9rem' }}>
                  {selected.notes}
                </p>
              )}

              {/* Household Members */}
              <div style={{ marginBottom: '1rem', padding: '.75rem', background: 'var(--surface-2)', borderRadius: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h4 style={{ margin: 0 }}>👥 Household ({(selected.household_members?.length || 0) + 1})</h4>
                  <button className="btn btn-outline btn-sm" onClick={() => setShowMemberForm(!showMemberForm)}>
                    {showMemberForm ? 'Cancel' : '+ Add'}
                  </button>
                </div>
                
                {/* Primary contact */}
                <div style={{ marginTop: '.5rem', padding: '.5rem', background: 'var(--background)', borderRadius: '6px' }}>
                  <strong>{selected.first_name}</strong> <span className="muted">(Primary)</span>
                </div>
                
                {/* Other members */}
                {selected.household_members?.map(m => (
                  <div key={m.id} style={{ marginTop: '.5rem', padding: '.5rem', background: 'var(--background)', borderRadius: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <div>
                        <strong>{m.name}</strong>
                        {m.relationship && <span className="muted"> ({m.relationship})</span>}
                        {m.age && <span className="muted">, {m.age}y</span>}
                      </div>
                      <button className="btn btn-outline btn-sm" style={{ color: '#d33', padding: '0 .5rem' }}
                        onClick={() => handleDeleteMember(m.id)}>✕</button>
                    </div>
                    {(m.dietary_preferences?.length > 0 || m.allergies?.length > 0) && (
                      <div style={{ marginTop: '.3rem', fontSize: '.8rem' }}>
                        {m.dietary_preferences?.map(p => (
                          <span key={p} className="chip small" style={{ marginRight: '.2rem', fontSize: '.7rem' }}>{p}</span>
                        ))}
                        {m.allergies?.filter(a => a !== 'None').map(a => (
                          <span key={a} className="chip small" style={{ marginRight: '.2rem', fontSize: '.7rem', background: '#ffeeba', color: '#856404' }}>⚠️ {a}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                
                {/* Add member form */}
                {showMemberForm && (
                  <form onSubmit={handleAddMember} style={{ marginTop: '.75rem', padding: '.5rem', background: 'var(--background)', borderRadius: '6px' }}>
                    <div className="grid grid-2" style={{ gap: '.5rem' }}>
                      <input type="text" className="form-input" placeholder="Name *" value={memberForm.name}
                        onChange={e => setMemberForm(f => ({ ...f, name: e.target.value }))} required />
                      <input type="text" className="form-input" placeholder="Relationship" value={memberForm.relationship}
                        onChange={e => setMemberForm(f => ({ ...f, relationship: e.target.value }))} />
                    </div>
                    <input type="number" className="form-input" placeholder="Age" value={memberForm.age}
                      onChange={e => setMemberForm(f => ({ ...f, age: e.target.value }))} style={{ marginTop: '.5rem', width: '80px' }} />
                    <div style={{ marginTop: '.5rem' }}>
                      <label className="form-label" style={{ fontSize: '.8rem' }}>Dietary</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.2rem' }}>
                        {DIETARY_OPTIONS.slice(0, 8).map(opt => (
                          <button key={opt} type="button" className="chip small"
                            style={{ cursor: 'pointer', fontSize: '.7rem', background: memberForm.dietary_preferences.includes(opt) ? 'var(--accent)' : undefined, color: memberForm.dietary_preferences.includes(opt) ? 'white' : undefined }}
                            onClick={() => setMemberForm(f => ({ ...f, dietary_preferences: togglePreference(f.dietary_preferences, opt) }))}
                          >{opt}</button>
                        ))}
                      </div>
                    </div>
                    <div style={{ marginTop: '.5rem' }}>
                      <label className="form-label" style={{ fontSize: '.8rem' }}>Allergies</label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.2rem' }}>
                        {ALLERGY_OPTIONS.slice(0, 6).map(opt => (
                          <button key={opt} type="button" className="chip small"
                            style={{ cursor: 'pointer', fontSize: '.7rem', background: memberForm.allergies.includes(opt) ? '#d9534f' : undefined, color: memberForm.allergies.includes(opt) ? 'white' : undefined }}
                            onClick={() => setMemberForm(f => ({ ...f, allergies: togglePreference(f.allergies, opt) }))}
                          >{opt}</button>
                        ))}
                      </div>
                    </div>
                    <button type="submit" className="btn btn-primary btn-sm" style={{ marginTop: '.5rem' }} disabled={memberSaving || !memberForm.name.trim()}>
                      {memberSaving ? 'Adding...' : 'Add Member'}
                    </button>
                  </form>
                )}
              </div>

              {/* Notes/Interactions */}
              <h4 style={{ marginBottom: '.5rem' }}>📝 Notes</h4>
              <form onSubmit={handleAddNote}>
                <input type="text" className="form-input" value={noteForm.summary}
                  onChange={e => setNoteForm(f => ({ ...f, summary: e.target.value }))}
                  placeholder="Add a note..." style={{ marginBottom: '.5rem' }} />
                <div style={{ display: 'flex', gap: '.5rem' }}>
                  <select className="form-input" value={noteForm.interaction_type}
                    onChange={e => setNoteForm(f => ({ ...f, interaction_type: e.target.value }))} style={{ width: 'auto' }}>
                    <option value="note">📝 Note</option>
                    <option value="call">📞 Call</option>
                    <option value="meeting">🤝 Meeting</option>
                    <option value="email">📧 Email</option>
                  </select>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={noteSaving || !noteForm.summary.trim()}>
                    {noteSaving ? '...' : 'Add'}
                  </button>
                </div>
              </form>

              {interactions.length > 0 && (
                <div style={{ marginTop: '.75rem' }}>
                  {interactions.map(int => (
                    <div key={int.id} style={{ padding: '.5rem', background: 'var(--surface-2)', borderRadius: '6px', fontSize: '.9rem', marginBottom: '.4rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <strong>{int.summary}</strong>
                        <span className="muted" style={{ fontSize: '.8rem' }}>{new Date(int.happened_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="muted" style={{ textAlign: 'center', padding: '2rem' }}>
              Select a client to see their profile and household
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
