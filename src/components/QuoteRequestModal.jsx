import React, { useState } from 'react'
import { api, buildErrorMessage } from '../api'

const DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const MEAL_TIMES = ['Breakfast', 'Lunch', 'Dinner', 'Snack']

export default function QuoteRequestModal({ isOpen, onClose, chef, authUser }) {
  const [serviceType, setServiceType] = useState('') // 'in_house' or 'bulk_prep'
  const [selectedSlots, setSelectedSlots] = useState({}) // { 'Monday-Breakfast': true, ... }
  const [formData, setFormData] = useState({
    numberOfPeople: '',
    eventDate: '',
    eventTime: '',
    duration: '',
    dietaryRestrictions: '',
    allergies: '',
    budget: '',
    additionalNotes: '',
    contactPhone: '',
    preferredContactMethod: 'email'
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  if (!isOpen) return null

  const toggleSlot = (day, mealTime) => {
    const key = `${day}-${mealTime}`
    setSelectedSlots(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const isSlotSelected = (day, mealTime) => {
    return Boolean(selectedSlots[`${day}-${mealTime}`])
  }

  const getSelectedSlotsCount = () => {
    return Object.values(selectedSlots).filter(Boolean).length
  }

  const getSelectedSlotsFormatted = () => {
    const slots = []
    Object.entries(selectedSlots).forEach(([key, selected]) => {
      if (selected) {
        const [day, mealTime] = key.split('-')
        slots.push({ day, meal_time: mealTime })
      }
    })
    return slots
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!serviceType) {
      setError('Please select a service type')
      return
    }

    if (serviceType === 'bulk_prep' && getSelectedSlotsCount() === 0) {
      setError('Please select at least one meal slot for bulk prep')
      return
    }

    if (serviceType === 'in_house' && !formData.eventDate) {
      setError('Please provide an event date for in-house service')
      return
    }

    if (!formData.numberOfPeople) {
      setError('Please specify the number of people')
      return
    }

    setSubmitting(true)

    try {
      const payload = {
        chef_id: chef?.id,
        chef_username: chef?.user?.username,
        service_type: serviceType,
        number_of_people: parseInt(formData.numberOfPeople, 10),
        dietary_restrictions: formData.dietaryRestrictions,
        allergies: formData.allergies,
        budget_range: formData.budget,
        additional_notes: formData.additionalNotes,
        contact_phone: formData.contactPhone,
        preferred_contact_method: formData.preferredContactMethod
      }

      if (serviceType === 'in_house') {
        payload.event_date = formData.eventDate
        payload.event_time = formData.eventTime || null
        payload.duration_hours = formData.duration ? parseFloat(formData.duration) : null
      } else if (serviceType === 'bulk_prep') {
        payload.meal_slots = getSelectedSlotsFormatted()
      }

      const response = await api.post('/services/quote-requests/', payload)

      if (response.status === 200 || response.status === 201) {
        setSuccess(true)
        setTimeout(() => {
          onClose()
          // Reset form
          setServiceType('')
          setSelectedSlots({})
          setFormData({
            numberOfPeople: '',
            eventDate: '',
            eventTime: '',
            duration: '',
            dietaryRestrictions: '',
            allergies: '',
            budget: '',
            additionalNotes: '',
            contactPhone: '',
            preferredContactMethod: 'email'
          })
          setSuccess(false)
        }, 2000)

        // Show success toast
        if (typeof window !== 'undefined') {
          try {
            window.dispatchEvent(new CustomEvent('global-toast', {
              detail: { text: 'Quote request submitted! The chef will be in touch soon.', tone: 'success' }
            }))
          } catch {}
        }
      }
    } catch (err) {
      let message = 'Failed to submit quote request. Please try again.'
      if (err?.response) {
        message = buildErrorMessage(err.response.data, message, err.response.status)
      } else if (err?.message) {
        message = err.message
      }
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const updateField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  return (
    <>
      <div className="modal-overlay" onClick={onClose} />
      <div className="modal-container quote-request-modal">
        <div className="modal-header">
          <h2 className="modal-title">
            <i className="fa-solid fa-file-invoice" style={{ marginRight: '.5rem' }}></i>
            Request a Custom Quote
          </h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-times"></i>
          </button>
        </div>

        <div className="modal-body">
          {success ? (
            <div className="quote-success">
              <i className="fa-solid fa-check-circle" style={{ fontSize: '3rem', color: 'var(--primary)' }}></i>
              <h3>Quote Request Submitted!</h3>
              <p className="muted">
                {chef?.user?.username} will review your request and get back to you soon.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {/* Service Type Selection */}
              <div className="form-section">
                <label className="label">Select Service Type *</label>
                <div className="service-type-grid">
                  <div
                    className={`service-type-card ${serviceType === 'in_house' ? 'selected' : ''}`}
                    onClick={() => setServiceType('in_house')}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="service-type-icon">
                      <i className="fa-solid fa-home"></i>
                    </div>
                    <h3 className="service-type-title">In-House Personal Chef</h3>
                    <p className="service-type-description">
                      Chef comes to your home to prepare meals on-site for a special occasion or ongoing service
                    </p>
                    <div className="service-type-features">
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Fresh cooking in your kitchen</span>
                      </div>
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Personalized menus</span>
                      </div>
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Clean-up included</span>
                      </div>
                    </div>
                  </div>

                  <div
                    className={`service-type-card ${serviceType === 'bulk_prep' ? 'selected' : ''}`}
                    onClick={() => setServiceType('bulk_prep')}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="service-type-icon">
                      <i className="fa-solid fa-box"></i>
                    </div>
                    <h3 className="service-type-title">Bulk Meal Prep</h3>
                    <p className="service-type-description">
                      Pre-made meals delivered or ready for pickup based on your weekly schedule
                    </p>
                    <div className="service-type-features">
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Choose your meal schedule</span>
                      </div>
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Refrigerated or frozen</span>
                      </div>
                      <div className="feature-item">
                        <i className="fa-solid fa-check"></i>
                        <span>Convenient & affordable</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bulk Prep Meal Slot Picker */}
              {serviceType === 'bulk_prep' && (
                <div className="form-section">
                  <label className="label">
                    Select Meal Schedule *
                    <span className="muted" style={{ marginLeft: '.5rem', fontWeight: 'normal' }}>
                      ({getSelectedSlotsCount()} meals selected)
                    </span>
                  </label>
                  <div className="meal-slot-picker">
                    <div className="meal-slot-grid">
                      <div className="meal-slot-header"></div>
                      {MEAL_TIMES.map(mealTime => (
                        <div key={mealTime} className="meal-slot-header">
                          {mealTime}
                        </div>
                      ))}
                      {DAYS_OF_WEEK.map(day => (
                        <React.Fragment key={day}>
                          <div className="meal-slot-day">{day}</div>
                          {MEAL_TIMES.map(mealTime => (
                            <button
                              key={`${day}-${mealTime}`}
                              type="button"
                              className={`meal-slot ${isSlotSelected(day, mealTime) ? 'selected' : ''}`}
                              onClick={() => toggleSlot(day, mealTime)}
                              aria-label={`${day} ${mealTime}`}
                            >
                              <i className={`fa-solid fa-${isSlotSelected(day, mealTime) ? 'check-circle' : 'circle'}`}></i>
                            </button>
                          ))}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* In-House Event Details */}
              {serviceType === 'in_house' && (
                <div className="form-section">
                  <div className="form-row">
                    <div className="form-field">
                      <label className="label">Event Date *</label>
                      <input
                        type="date"
                        className="input"
                        value={formData.eventDate}
                        onChange={e => updateField('eventDate', e.target.value)}
                        required
                        min={new Date().toISOString().split('T')[0]}
                      />
                    </div>
                    <div className="form-field">
                      <label className="label">Preferred Time</label>
                      <input
                        type="time"
                        className="input"
                        value={formData.eventTime}
                        onChange={e => updateField('eventTime', e.target.value)}
                      />
                    </div>
                    <div className="form-field">
                      <label className="label">Duration (hours)</label>
                      <input
                        type="number"
                        className="input"
                        value={formData.duration}
                        onChange={e => updateField('duration', e.target.value)}
                        placeholder="e.g. 3"
                        min="1"
                        step="0.5"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Common Fields */}
              {serviceType && (
                <>
                  <div className="form-section">
                    <div className="form-row">
                      <div className="form-field">
                        <label className="label">Number of People *</label>
                        <input
                          type="number"
                          className="input"
                          value={formData.numberOfPeople}
                          onChange={e => updateField('numberOfPeople', e.target.value)}
                          placeholder="How many people?"
                          min="1"
                          required
                        />
                      </div>
                      <div className="form-field">
                        <label className="label">Budget Range</label>
                        <select
                          className="select"
                          value={formData.budget}
                          onChange={e => updateField('budget', e.target.value)}
                        >
                          <option value="">Select budget</option>
                          <option value="under_500">Under $500</option>
                          <option value="500_1000">$500 - $1,000</option>
                          <option value="1000_2000">$1,000 - $2,000</option>
                          <option value="2000_5000">$2,000 - $5,000</option>
                          <option value="over_5000">Over $5,000</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  <div className="form-section">
                    <label className="label">Dietary Restrictions</label>
                    <input
                      type="text"
                      className="input"
                      value={formData.dietaryRestrictions}
                      onChange={e => updateField('dietaryRestrictions', e.target.value)}
                      placeholder="Vegetarian, Vegan, Keto, etc."
                    />
                  </div>

                  <div className="form-section">
                    <label className="label">Allergies</label>
                    <input
                      type="text"
                      className="input"
                      value={formData.allergies}
                      onChange={e => updateField('allergies', e.target.value)}
                      placeholder="Nuts, Dairy, Gluten, etc."
                    />
                  </div>

                  <div className="form-section">
                    <label className="label">Additional Notes</label>
                    <textarea
                      className="textarea"
                      rows={4}
                      value={formData.additionalNotes}
                      onChange={e => updateField('additionalNotes', e.target.value)}
                      placeholder="Tell us more about your needs, preferences, or special requests..."
                    />
                  </div>

                  <div className="form-section">
                    <div className="form-row">
                      <div className="form-field">
                        <label className="label">Contact Phone</label>
                        <input
                          type="tel"
                          className="input"
                          value={formData.contactPhone}
                          onChange={e => updateField('contactPhone', e.target.value)}
                          placeholder="Optional"
                        />
                      </div>
                      <div className="form-field">
                        <label className="label">Preferred Contact Method</label>
                        <select
                          className="select"
                          value={formData.preferredContactMethod}
                          onChange={e => updateField('preferredContactMethod', e.target.value)}
                        >
                          <option value="email">Email</option>
                          <option value="phone">Phone</option>
                          <option value="either">Either</option>
                        </select>
                      </div>
                    </div>
                  </div>

                  {error && (
                    <div className="form-error" role="alert">
                      <i className="fa-solid fa-exclamation-circle"></i>
                      {error}
                    </div>
                  )}

                  <div className="form-actions">
                    <button
                      type="submit"
                      className="btn btn-primary btn-lg"
                      disabled={submitting}
                      style={{ width: '100%' }}
                    >
                      {submitting ? (
                        <>
                          <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2, marginRight: '.5rem' }}></div>
                          Submitting...
                        </>
                      ) : (
                        <>
                          <i className="fa-solid fa-paper-plane" style={{ marginRight: '.5rem' }}></i>
                          Submit Quote Request
                        </>
                      )}
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={onClose}
                      disabled={submitting}
                      style={{ width: '100%' }}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              )}
            </form>
          )}
        </div>
      </div>
    </>
  )
}



