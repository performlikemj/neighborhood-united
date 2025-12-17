import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useCart } from '../context/CartContext'

/**
 * RequestServiceModal - Book chef services directly from My Chef page
 * 
 * Shows available services with pricing tiers and a booking form.
 * Services are filtered based on the customer's location.
 */
export default function RequestServiceModal({ isOpen, onClose, chefId, chefUsername }) {
  const { addToCart, openCart } = useCart()
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Selection state
  const [selectedService, setSelectedService] = useState(null)
  const [selectedTier, setSelectedTier] = useState(null)
  
  // Booking form state
  const [formData, setFormData] = useState({
    householdSize: 1,
    serviceDate: '',
    serviceStartTime: '',
    specialRequests: '',
    scheduleNotes: '',
  })
  const [formErrors, setFormErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const fetchServices = useCallback(async () => {
    if (!chefId) return
    setLoading(true)
    setError(null)
    try {
      const resp = await api.get(`/customer_dashboard/api/my-chefs/${chefId}/catalog/`)
      setServices(resp.data?.services || [])
    } catch (err) {
      console.error('Failed to fetch services:', err)
      setError('Unable to load services. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [chefId])

  useEffect(() => {
    if (isOpen && chefId) {
      fetchServices()
      // Reset selection when opening
      setSelectedService(null)
      setSelectedTier(null)
      setFormData({
        householdSize: 1,
        serviceDate: '',
        serviceStartTime: '',
        specialRequests: '',
        scheduleNotes: '',
      })
      setFormErrors({})
    }
  }, [isOpen, chefId, fetchServices])

  // When a tier is selected, set default household size
  useEffect(() => {
    if (selectedTier) {
      setFormData(prev => ({
        ...prev,
        householdSize: selectedTier.household_min || 1
      }))
    }
  }, [selectedTier])

  const handleServiceSelect = (service) => {
    setSelectedService(service)
    setSelectedTier(null)
    setFormErrors({})
  }

  const handleTierSelect = (tier) => {
    setSelectedTier(tier)
    setFormErrors({})
  }

  const handleFormChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    if (formErrors[field]) {
      setFormErrors(prev => {
        const next = { ...prev }
        delete next[field]
        return next
      })
    }
  }

  const validateForm = () => {
    const errors = {}
    
    if (!selectedTier) {
      errors.tier = 'Please select a pricing tier'
    }
    
    if (!formData.householdSize || formData.householdSize < 1) {
      errors.householdSize = 'Household size must be at least 1'
    } else if (selectedTier) {
      const max = selectedTier.household_max || 999
      if (formData.householdSize < selectedTier.household_min) {
        errors.householdSize = `Minimum ${selectedTier.household_min} people for this tier`
      } else if (formData.householdSize > max) {
        errors.householdSize = `Maximum ${max} people for this tier`
      }
    }
    
    // For home_chef services, date/time is required and must be at least 24 hours away
    if (selectedService?.service_type === 'home_chef') {
      if (!formData.serviceDate) {
        errors.serviceDate = 'Service date is required'
      }
      if (!formData.serviceStartTime) {
        errors.serviceStartTime = 'Start time is required'
      }
      // Check minimum notice (24 hours)
      if (formData.serviceDate && formData.serviceStartTime && !isServiceDateTimeValid(formData.serviceDate, formData.serviceStartTime)) {
        errors.serviceDate = 'Service must be scheduled at least 24 hours in advance'
      }
    }
    
    // For recurring services, schedule notes are helpful
    if (selectedTier?.is_recurring && !formData.scheduleNotes && !formData.serviceDate) {
      errors.scheduleNotes = 'Please provide scheduling preferences or select a start date'
    }
    
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async () => {
    if (!validateForm()) return
    
    setSubmitting(true)
    try {
      const item = {
        type: 'service_tier',
        offering_id: selectedService.id,
        tier_id: selectedTier.id,
        offeringTitle: selectedService.title,
        tierLabel: selectedTier.name,
        price: selectedTier.price_cents,
        householdSize: formData.householdSize,
        serviceDate: formData.serviceDate,
        serviceStartTime: formData.serviceStartTime,
        specialRequests: formData.specialRequests,
        scheduleNotes: formData.scheduleNotes,
        requiresDateTime: selectedService.service_type === 'home_chef',
        needsScheduleNotes: selectedTier.is_recurring,
        tierRecurring: selectedTier.is_recurring,
        serviceType: selectedService.service_type,
      }
      
      await addToCart(item, { username: chefUsername, id: chefId })
      openCart()
      showToast('Service added to cart!', 'success')
      onClose()
    } catch (err) {
      console.error('Failed to add service:', err)
      showToast('Failed to add service. Please try again.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const showToast = (text, tone) => {
    try {
      window.dispatchEvent(new CustomEvent('global-toast', { detail: { text, tone } }))
    } catch {}
  }

  const formatPrice = (cents) => {
    if (typeof cents !== 'number') return '$0.00'
    return `$${(cents / 100).toFixed(2)}`
  }

  // Get minimum date (tomorrow - services require 24 hours notice)
  const getMinDate = () => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    return tomorrow.toISOString().split('T')[0]
  }

  // Check if service datetime is at least 24 hours from now
  const isServiceDateTimeValid = (dateStr, timeStr) => {
    if (!dateStr || !timeStr) return true // Let required validation handle empty fields
    const serviceDateTime = new Date(`${dateStr}T${timeStr}`)
    const minDateTime = new Date()
    minDateTime.setHours(minDateTime.getHours() + 24)
    return serviceDateTime >= minDateTime
  }

  if (!isOpen) return null

  return (
    <>
      <div className="service-modal-overlay" onClick={onClose} />
      <aside className="service-modal" role="dialog" aria-label="Request Service">
        <div className="service-modal-header">
          <div className="service-modal-title">
            <i className="fa-solid fa-calendar-plus"></i>
            Request Service
          </div>
          <button className="service-modal-close" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-times"></i>
          </button>
        </div>

        <div className="service-modal-body">
          {loading && (
            <div className="service-loading">
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <p>Loading services...</p>
            </div>
          )}

          {error && (
            <div className="service-error">
              <i className="fa-solid fa-triangle-exclamation"></i>
              <p>{error}</p>
              <button className="btn btn-outline" onClick={fetchServices}>Try Again</button>
            </div>
          )}

          {!loading && !error && services.length === 0 && (
            <div className="service-empty">
              <i className="fa-solid fa-concierge-bell"></i>
              <p>No services available in your area.</p>
              <p className="muted">Contact your chef to discuss custom service options.</p>
            </div>
          )}

          {!loading && !error && services.length > 0 && (
            <div className="service-booking-flow">
              {/* Step 1: Select Service */}
              <div className="booking-step">
                <h3 className="step-title">
                  <span className="step-number">1</span>
                  Select a Service
                </h3>
                <div className="service-options">
                  {services.map(service => (
                    <button
                      key={service.id}
                      className={`service-option ${selectedService?.id === service.id ? 'selected' : ''}`}
                      onClick={() => handleServiceSelect(service)}
                    >
                      <div className="service-option-icon">
                        <i className={`fa-solid ${service.service_type === 'home_chef' ? 'fa-house-user' : 'fa-bowl-food'}`}></i>
                      </div>
                      <div className="service-option-info">
                        <div className="service-option-type">{service.service_type_display}</div>
                        <div className="service-option-title">{service.title}</div>
                        {service.is_personalized && (
                          <span className="personalized-tag">
                            <i className="fa-solid fa-star"></i> Personalized for you
                          </span>
                        )}
                      </div>
                      <i className={`fa-solid ${selectedService?.id === service.id ? 'fa-check-circle' : 'fa-circle'} service-option-check`}></i>
                    </button>
                  ))}
                </div>
              </div>

              {/* Step 2: Select Tier */}
              {selectedService && (
                <div className="booking-step">
                  <h3 className="step-title">
                    <span className="step-number">2</span>
                    Choose a Pricing Tier
                  </h3>
                  {selectedService.description && (
                    <p className="step-description">{selectedService.description}</p>
                  )}
                  <div className="tier-options">
                    {selectedService.tiers.map(tier => (
                      <button
                        key={tier.id}
                        className={`tier-option ${selectedTier?.id === tier.id ? 'selected' : ''}${tier.ready_for_checkout === false ? ' tier-unavailable' : ''}`}
                        onClick={() => handleTierSelect(tier)}
                        disabled={tier.ready_for_checkout === false}
                        title={tier.ready_for_checkout === false ? 'This option is being set up' : ''}
                      >
                        <div className="tier-option-main">
                          <div className="tier-option-name">{tier.name}</div>
                          <div className="tier-option-details">
                            {tier.household_min}-{tier.household_max || '∞'} people
                            {tier.ready_for_checkout === false && (
                              <span className="tier-pending-badge">Setting up...</span>
                            )}
                          </div>
                        </div>
                        <div className="tier-option-price">
                          {formatPrice(tier.price_cents)}
                          {tier.is_recurring && (
                            <span className="tier-frequency">/{tier.recurrence_interval}</span>
                          )}
                        </div>
                        <i className={`fa-solid ${selectedTier?.id === tier.id ? 'fa-check-circle' : 'fa-circle'} tier-option-check`}></i>
                      </button>
                    ))}
                  </div>
                  {formErrors.tier && <p className="field-error">{formErrors.tier}</p>}
                </div>
              )}

              {/* Step 3: Booking Details */}
              {selectedTier && (
                <div className="booking-step">
                  <h3 className="step-title">
                    <span className="step-number">3</span>
                    Booking Details
                  </h3>
                  
                  <div className="booking-form">
                    {/* Household Size */}
                    <div className="form-field">
                      <label htmlFor="householdSize">Household Size</label>
                      <input
                        id="householdSize"
                        type="number"
                        min={selectedTier.household_min}
                        max={selectedTier.household_max || 99}
                        value={formData.householdSize}
                        onChange={(e) => handleFormChange('householdSize', parseInt(e.target.value) || 1)}
                        className={formErrors.householdSize ? 'error' : ''}
                      />
                      {formErrors.householdSize && <span className="field-error">{formErrors.householdSize}</span>}
                    </div>

                    {/* Date & Time (for home_chef or one-time services) */}
                    {(selectedService.service_type === 'home_chef' || !selectedTier.is_recurring) && (
                      <div className="form-row">
                        <div className="form-field">
                          <label htmlFor="serviceDate">
                            Service Date
                            {selectedService.service_type === 'home_chef' && <span className="required">*</span>}
                          </label>
                          <input
                            id="serviceDate"
                            type="date"
                            min={getMinDate()}
                            value={formData.serviceDate}
                            onChange={(e) => handleFormChange('serviceDate', e.target.value)}
                            className={formErrors.serviceDate ? 'error' : ''}
                          />
                          {formErrors.serviceDate && <span className="field-error">{formErrors.serviceDate}</span>}
                        </div>
                        
                        <div className="form-field">
                          <label htmlFor="serviceStartTime">
                            Start Time
                            {selectedService.service_type === 'home_chef' && <span className="required">*</span>}
                          </label>
                          <input
                            id="serviceStartTime"
                            type="time"
                            step="1800"
                            value={formData.serviceStartTime}
                            onChange={(e) => handleFormChange('serviceStartTime', e.target.value)}
                            className={formErrors.serviceStartTime ? 'error' : ''}
                          />
                          {formErrors.serviceStartTime && <span className="field-error">{formErrors.serviceStartTime}</span>}
                        </div>
                      </div>
                    )}

                    {/* Schedule Notes (for recurring services) */}
                    {selectedTier.is_recurring && (
                      <div className="form-field">
                        <label htmlFor="scheduleNotes">
                          Scheduling Preferences
                          <span className="label-hint">When would you like service each {selectedTier.recurrence_interval}?</span>
                        </label>
                        <textarea
                          id="scheduleNotes"
                          rows={3}
                          placeholder="e.g., Mondays at 6pm, or flexible weekday evenings"
                          value={formData.scheduleNotes}
                          onChange={(e) => handleFormChange('scheduleNotes', e.target.value)}
                          className={formErrors.scheduleNotes ? 'error' : ''}
                        />
                        {formErrors.scheduleNotes && <span className="field-error">{formErrors.scheduleNotes}</span>}
                      </div>
                    )}

                    {/* Special Requests */}
                    <div className="form-field">
                      <label htmlFor="specialRequests">
                        Special Requests
                        <span className="label-hint">Optional dietary needs, preferences, or notes</span>
                      </label>
                      <textarea
                        id="specialRequests"
                        rows={3}
                        placeholder="Any special requirements or preferences..."
                        value={formData.specialRequests}
                        onChange={(e) => handleFormChange('specialRequests', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer with pricing summary and submit */}
        {selectedTier && (
          <div className="service-modal-footer">
            <div className="booking-summary">
              <div className="summary-service">{selectedService.title}</div>
              <div className="summary-tier">{selectedTier.name}</div>
              <div className="summary-price">
                {formatPrice(selectedTier.price_cents)}
                {selectedTier.is_recurring && <span>/{selectedTier.recurrence_interval}</span>}
              </div>
            </div>
            <button
              className="btn btn-primary btn-block"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <><span className="spinner-sm"></span> Adding to Cart...</>
              ) : (
                <><i className="fa-solid fa-cart-plus"></i> Add to Cart</>
              )}
            </button>
          </div>
        )}
      </aside>
    </>
  )
}

