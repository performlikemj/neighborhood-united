import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext.jsx'
import { api, buildErrorMessage } from '../api'
import { rememberServiceOrderId } from '../utils/serviceOrdersStorage.js'

function formatPrice(cents, currency = 'USD') {
  if (typeof cents !== 'number') {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(0)
  }
  // Zero-decimal currencies like JPY don't divide by 100
  const zeroDecimal = ['JPY', 'KRW', 'VND', 'BIF', 'CLP', 'DJF', 'GNF', 'KMF', 'PYG', 'RWF', 'UGX', 'VUV', 'XAF', 'XOF', 'XPF']
  const divisor = zeroDecimal.includes(currency.toUpperCase()) ? 1 : 100
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(cents / divisor)
}

function normalizeInteger(value, fallback = 1) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric < 1) return fallback
  return Math.floor(numeric)
}

export default function CartSidebar() {
  const { cart, isOpen, closeCart, removeFromCart, updateQuantity, getCartTotal, clearCart, updateCartItem } = useCart()
  const { user: authUser } = useAuth()
  const [checkingOut, setCheckingOut] = useState(false)
  const [error, setError] = useState('')
  const [itemErrors, setItemErrors] = useState({})
  const [validationDetails, setValidationDetails] = useState(null)
  const isDev = Boolean(import.meta?.env?.DEV)

  // Get user's profile address (single address per user)
  const userAddress = useMemo(() => {
    const addr = authUser?.address || null
    if (isDev) {
      console.log('[CartSidebar] User address from profile:', {
        hasAddress: Boolean(addr),
        addressId: addr?.id,
        street: addr?.street,
        city: addr?.city,
        postal: addr?.postal_code || addr?.postalcode || addr?.input_postalcode,
        country: addr?.country
      })
    }
    return addr
  }, [authUser?.address, isDev])

  const addressId = useMemo(() => {
    const id = userAddress?.id ?? userAddress?.address_id ?? null
    return id != null ? String(id) : null
  }, [userAddress])

  // Check if address is complete enough for checkout (needs street)
  const addressComplete = useMemo(() => {
    if (!userAddress) return false
    const hasStreet = Boolean(userAddress.street)
    const hasCity = Boolean(userAddress.city)
    const hasPostal = Boolean(userAddress.postal_code || userAddress.postalcode || userAddress.input_postalcode)
    const complete = hasStreet && hasCity && hasPostal
    if (isDev) {
      console.log('[CartSidebar] Address completeness check:', { hasStreet, hasCity, hasPostal, complete })
    }
    return complete
  }, [userAddress, isDev])

  // Format address for display
  const addressDisplay = useMemo(() => {
    if (!userAddress) return null
    const parts = []
    if (userAddress.street) parts.push(userAddress.street)
    if (userAddress.city) parts.push(userAddress.city)
    const postal = userAddress.postal_code || userAddress.postalcode || userAddress.input_postalcode
    if (postal) parts.push(postal)
    if (userAddress.country) parts.push(String(userAddress.country).toUpperCase())
    return parts.length > 0 ? parts.join(', ') : null
  }, [userAddress])
  
  if (isDev) {
    console.debug('[CartSidebar] Render', {
      isOpen,
      cartCount: Array.isArray(cart?.items) ? cart.items.length : 0,
      addressId,
      addressComplete
    })
  }

  // Auto-fill addressId for service items when cart opens
  useEffect(() => {
    if (!Array.isArray(cart.items)) return
    if (!addressId) return
    cart.items.forEach((item, index) => {
      if (item?.type !== 'service_tier') return
      const updates = {}
      if (!item.householdSize || normalizeInteger(item.householdSize) !== Number(item.householdSize)) {
        updates.householdSize = normalizeInteger(item.householdSize)
      }
      if (!item.addressId && addressId) {
        updates.addressId = addressId
      }
      if (Object.keys(updates).length > 0) {
        updateCartItem(index, updates)
      }
    })
  }, [cart.items, addressId, updateCartItem])

  if (!isOpen) return null

  function clearFieldError(index, field) {
    setItemErrors(prev => {
      if (!prev[index]) return prev
      const { [field]: _discard, ...rest } = prev[index]
      if (Object.keys(rest).length === 0) {
        const next = { ...prev }
        delete next[index]
        return next
      }
      return { ...prev, [index]: rest }
    })
  }

  function fieldError(index, field) {
    return itemErrors[index]?.[field] || validationDetails?.[field] || null
  }

  const handleServiceFieldChange = (index, field, value) => {
    updateCartItem(index, { [field]: value })
    clearFieldError(index, field)
    if (validationDetails) setValidationDetails(null)
  }

  const handleScheduleNotesChange = (index, value) => {
    updateCartItem(index, { scheduleNotes: value })
    clearFieldError(index, 'schedule_preferences')
    if (validationDetails) setValidationDetails(null)
  }

  // Check if service datetime is at least 24 hours from now
  function isServiceDateTimeValid(dateStr, timeStr) {
    if (!dateStr || !timeStr) return true // Let required validation handle empty fields
    const serviceDateTime = new Date(`${dateStr}T${timeStr}`)
    const minDateTime = new Date()
    minDateTime.setHours(minDateTime.getHours() + 24)
    return serviceDateTime >= minDateTime
  }

  function validateServiceItem(item) {
    const errors = {}
    const requiresDateTime = Boolean(item.requiresDateTime)
    const needsScheduleNotes = Boolean(item.needsScheduleNotes)
    const size = normalizeInteger(item.householdSize)
    if (!size || size < 1) {
      errors.household_size = 'Enter how many people this booking covers.'
    }
    if (requiresDateTime && !item.serviceDate) {
      errors.service_date = 'Select a service date before checkout.'
    }
    if (requiresDateTime && !item.serviceStartTime) {
      errors.service_start_time = 'Select a service start time before checkout.'
    }
    // Check minimum notice (24 hours)
    if (requiresDateTime && item.serviceDate && item.serviceStartTime && !isServiceDateTimeValid(item.serviceDate, item.serviceStartTime)) {
      errors.service_date = 'Service must be scheduled at least 24 hours in advance.'
    }
    if (needsScheduleNotes && !item.scheduleNotes) {
      errors.schedule_preferences = 'Add scheduling preferences for this recurring service.'
    }
    // Check address - need both addressId AND complete address (with street)
    if (!item.addressId) {
      errors.address_id = 'Add your address in Profile to continue.'
    } else if (!addressComplete) {
      errors.address_id = 'Complete your address (including street) in Profile to continue.'
    }
    return errors
  }

  const handleCheckout = async () => {
    setError('')
    setValidationDetails(null)
    setItemErrors({})
    setCheckingOut(true)

    try {
      const serviceItems = cart.items.filter(item => item.type === 'service_tier')
      const mealItems = cart.items.filter(item => item.type === 'meal_event')
      const quoteItems = cart.items.filter(item => item.type === 'quote_request')

      if (serviceItems.length > 0) {
        const localErrors = {}
        serviceItems.forEach(serviceItem => {
          const indexInCart = cart.items.indexOf(serviceItem)
          const errors = validateServiceItem(serviceItem)
          if (Object.keys(errors).length > 0) {
            localErrors[indexInCart] = errors
          }
        })
        if (Object.keys(localErrors).length > 0) {
          setItemErrors(localErrors)
          throw new Error('Add the missing service details before checkout.')
        }

        let redirectUrl = null

        for (const serviceItem of serviceItems) {
          const indexInCart = cart.items.indexOf(serviceItem)
          
          // Lazy order creation: create the order now if it doesn't exist
          let orderId = serviceItem.orderId
          if (!orderId) {
            try {
              const createPayload = {
                offering_id: serviceItem.offering_id,
                tier_id: serviceItem.tier_id,
                household_size: normalizeInteger(serviceItem.householdSize)
              }
              if (serviceItem.addressId) {
                const addrNumeric = Number(serviceItem.addressId)
                createPayload.address_id = Number.isFinite(addrNumeric) ? addrNumeric : serviceItem.addressId
              }
              if (serviceItem.serviceDate) createPayload.service_date = serviceItem.serviceDate
              if (serviceItem.serviceStartTime) createPayload.service_start_time = serviceItem.serviceStartTime
              if (serviceItem.durationMinutes) createPayload.duration_minutes = Number(serviceItem.durationMinutes)
              if (serviceItem.specialRequests) createPayload.special_requests = serviceItem.specialRequests
              if (serviceItem.scheduleNotes) {
                createPayload.schedule_preferences = { notes: serviceItem.scheduleNotes }
              }
              
              const createResp = await api.post('/services/orders/', createPayload)
              const createdOrder = createResp?.data || {}
              orderId = createdOrder?.id
              
              if (!orderId) {
                const err = new Error('Failed to create order. Please try again.')
                err._cartItemIndex = indexInCart
                throw err
              }
              
              // Update cart item with the new orderId for potential retry
              updateCartItem(indexInCart, { 
                orderId, 
                orderStatus: createdOrder.status || 'draft' 
              })
              rememberServiceOrderId(orderId)
            } catch (err) {
              err._cartItemIndex = indexInCart
              throw err
            }
          }

          const payload = {
            household_size: normalizeInteger(serviceItem.householdSize)
          }

          if (serviceItem.serviceDate) payload.service_date = serviceItem.serviceDate
          if (serviceItem.serviceStartTime) payload.service_start_time = serviceItem.serviceStartTime
          if (serviceItem.durationMinutes) payload.duration_minutes = Number(serviceItem.durationMinutes)
          if (serviceItem.addressId){
            const addrNumeric = Number(serviceItem.addressId)
            payload.address_id = Number.isFinite(addrNumeric) ? addrNumeric : serviceItem.addressId
          }
          if (serviceItem.specialRequests) payload.special_requests = serviceItem.specialRequests
          if (serviceItem.scheduleNotes) {
            const basePrefs = serviceItem.schedulePreferences && typeof serviceItem.schedulePreferences === 'object'
              ? { ...serviceItem.schedulePreferences }
              : {}
            payload.schedule_preferences = { ...basePrefs, notes: serviceItem.scheduleNotes }
          }

          let updatedOrder = null
          try{
            const updateResp = await api.patch(`/services/orders/${orderId}/update/`, payload)
            updatedOrder = updateResp?.data || null
            if (updatedOrder) {
              updateCartItem(indexInCart, {
                orderId,
                serviceDate: updatedOrder.service_date ?? serviceItem.serviceDate,
                serviceStartTime: updatedOrder.service_start_time ?? serviceItem.serviceStartTime,
                durationMinutes: updatedOrder.duration_minutes ?? serviceItem.durationMinutes,
                specialRequests: updatedOrder.special_requests ?? serviceItem.specialRequests,
                scheduleNotes: updatedOrder.schedule_preferences?.notes ?? serviceItem.scheduleNotes,
                schedulePreferences: updatedOrder.schedule_preferences ?? serviceItem.schedulePreferences,
                householdSize: updatedOrder.household_size ?? serviceItem.householdSize,
                addressId: updatedOrder.address_id != null ? String(updatedOrder.address_id) : (updatedOrder.address ?? serviceItem.addressId),
                orderStatus: updatedOrder.status || serviceItem.orderStatus || 'draft'
              })
            }
            rememberServiceOrderId(orderId)
          }catch(err){
            err._cartItemIndex = indexInCart
            throw err
          }

          try{
            const checkoutResp = await api.post(`/services/orders/${orderId}/checkout/`, {})
            const checkoutData = checkoutResp?.data || {}
            if (checkoutData?.validation_errors) {
              setValidationDetails(checkoutData.validation_errors)
              setItemErrors(prev => ({
                ...prev,
                [indexInCart]: { ...(prev[indexInCart] || {}), ...checkoutData.validation_errors }
              }))
              const err = new Error('Add the missing details highlighted below, then try checkout again.')
              err._cartItemIndex = indexInCart
              throw err
            }
            if (checkoutData?.session_id) {
              try { localStorage.setItem('lastServiceCheckoutSessionId', String(checkoutData.session_id)) } catch {}
            }
            // Save order ID so CustomerOrders page can verify payment after redirect
            try { localStorage.setItem('lastServiceOrderId', String(orderId)) } catch {}
            const sessionUrl = checkoutData?.session_url || checkoutData?.url
            if (sessionUrl) {
              redirectUrl = sessionUrl
            } else {
              const err = new Error('Payment link not available')
              err._cartItemIndex = indexInCart
              throw err
            }
          } catch (err) {
            if (err?.response?.data?.validation_errors) {
              const backendErrors = err.response.data.validation_errors
              setValidationDetails(backendErrors)
              setItemErrors(prev => ({
                ...prev,
                [indexInCart]: { ...(prev[indexInCart] || {}), ...backendErrors }
              }))
            }
            err._cartItemIndex = indexInCart
            throw err
          }
        }

        if (redirectUrl) {
          clearCart()
          window.location.href = redirectUrl
        }
      } else if (mealItems.length > 0) {
        setError('Meal ordering coming soon! Please use "Add to my plan" for now.')
      } else if (quoteItems.length > 0) {
        setError('Quote requests will be sent to the chef. Feature coming soon!')
      } else {
        setError('Your cart is empty')
      }
    } catch (err) {
      let message = 'Unable to start checkout. Please review your details and try again.'
      const failedIndex = err?._cartItemIndex
      if (typeof failedIndex === 'number') {
        setItemErrors(prev => ({
          ...prev,
          [failedIndex]: prev[failedIndex] || {}
        }))
      }
      if (err?.response) {
        const data = err.response.data || {}
        if (data.validation_errors) {
          setValidationDetails(data.validation_errors)
          if (typeof failedIndex === 'number') {
            setItemErrors(prev => ({
              ...prev,
              [failedIndex]: { ...(prev[failedIndex] || {}), ...data.validation_errors }
            }))
          }
          message = 'Add the missing details highlighted below, then try checkout again.'
        } else {
          message = buildErrorMessage(data, message, err.response.status)
        }
      } else if (err?.message) {
        message = err.message
      }
      setError(message)
    } finally {
      setCheckingOut(false)
    }
  }

  const renderCartItem = (item, index) => {
    if (isDev) {
      console.log('[CartSidebar] Rendering cart item', { index, type: item.type, addressId: item.addressId })
    }
    
    if (item.type === 'service_tier') {
      return (
        <div key={index} className="cart-item">
          <div className="cart-item-header">
            <div className="cart-item-title">{item.offeringTitle}</div>
            <button
              className="cart-item-remove"
              onClick={() => removeFromCart(index)}
              aria-label="Remove item"
            >
              <i className="fa-solid fa-times"></i>
            </button>
          </div>
          <div className="cart-item-details">
            <div className="muted">{item.tierLabel}</div>
            {item.orderStatus && (
              <div className="muted" style={{ fontSize: '.8rem', textTransform: 'capitalize' }}>
                Status: {String(item.orderStatus).replace(/_/g, ' ')}
              </div>
            )}
          </div>
          <div className="cart-item-price">{formatPrice(item.price)}</div>
          <div className="cart-item-form" style={{ marginTop: '.75rem', display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
              <span>Household size</span>
              <input
                type="number"
                min="1"
                value={item.householdSize ?? ''}
                onChange={(e) => handleServiceFieldChange(index, 'householdSize', e.target.value)}
                style={{ padding: '.45rem', borderRadius: '6px', border: fieldError(index, 'household_size') ? '1px solid #c0392b' : '1px solid var(--border-subtle)' }}
              />
              {fieldError(index, 'household_size') && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'household_size')}</span>}
            </label>
            {item.requiresDateTime ? (
              <div style={{ display: 'flex', gap: '.6rem', flexWrap: 'wrap' }}>
                <label style={{ flex: '1 1 150px', display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
                  <span>Service date</span>
                  <input
                    type="date"
                    value={item.serviceDate ?? ''}
                    onChange={(e) => handleServiceFieldChange(index, 'serviceDate', e.target.value)}
                    style={{ padding: '.45rem', borderRadius: '6px', border: fieldError(index, 'service_date') ? '1px solid #c0392b' : '1px solid var(--border-subtle)' }}
                  />
                  {fieldError(index, 'service_date') && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'service_date')}</span>}
                </label>
                <label style={{ flex: '1 1 150px', display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
                  <span>Start time</span>
                  <input
                    type="time"
                    step="1800"
                    value={item.serviceStartTime ?? ''}
                    onChange={(e) => handleServiceFieldChange(index, 'serviceStartTime', e.target.value)}
                    style={{ padding: '.45rem', borderRadius: '6px', border: fieldError(index, 'service_start_time') ? '1px solid #c0392b' : '1px solid var(--border-subtle)' }}
                  />
                  {fieldError(index, 'service_start_time') && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'service_start_time')}</span>}
                </label>
              </div>
            ) : null}
            
            {/* Service Address - Read-only display with link to Profile */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
              <span>Service address</span>
              {addressDisplay ? (
                <div style={{ 
                  padding: '.45rem .6rem', 
                  borderRadius: '6px', 
                  border: fieldError(index, 'address_id') ? '1px solid #c0392b' : '1px solid var(--border-subtle)',
                  background: 'var(--surface-2, #f5f5f5)',
                  fontSize: '.85rem'
                }}>
                  {addressDisplay}
                  {!addressComplete && (
                    <div style={{ marginTop: '.35rem', color: '#c0392b', fontSize: '.75rem' }}>
                      Missing street address for checkout
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ 
                  padding: '.45rem .6rem', 
                  borderRadius: '6px', 
                  border: '1px solid #c0392b',
                  background: 'var(--surface-2, #f5f5f5)',
                  color: '#666',
                  fontSize: '.85rem'
                }}>
                  No address saved
                </div>
              )}
              {fieldError(index, 'address_id') && (
                <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'address_id')}</span>
              )}
              <Link 
                to="/profile" 
                onClick={closeCart}
                style={{ alignSelf: 'flex-start', fontSize: '.8rem', color: 'var(--primary, #16a34a)' }}
              >
                {addressDisplay ? 'Edit address in Profile' : 'Add address in Profile'} →
              </Link>
            </div>
            
            <label style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
              <span>Special requests (optional)</span>
              <textarea
                rows="2"
                value={item.specialRequests ?? ''}
                onChange={(e) => handleServiceFieldChange(index, 'specialRequests', e.target.value)}
                style={{ padding: '.45rem', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}
              />
            </label>
            {item.tierRecurring ? (
              <label style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
                <span>Scheduling preferences</span>
                <textarea
                  rows="2"
                  value={item.scheduleNotes ?? ''}
                  onChange={(e) => handleScheduleNotesChange(index, e.target.value)}
                  placeholder="Share preferred weekdays, time windows, or rotation notes."
                  style={{ padding: '.45rem', borderRadius: '6px', border: fieldError(index, 'schedule_preferences') ? '1px solid #c0392b' : '1px solid var(--border-subtle)' }}
                />
                {fieldError(index, 'schedule_preferences') && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'schedule_preferences')}</span>}
              </label>
            ) : null}
          </div>
        </div>
      )
    }

    if (item.type === 'meal_event') {
      return (
        <div key={index} className="cart-item">
          <div className="cart-item-header">
            <div className="cart-item-title">{item.mealName}</div>
            <button
              className="cart-item-remove"
              onClick={() => removeFromCart(index)}
              aria-label="Remove item"
            >
              <i className="fa-solid fa-times"></i>
            </button>
          </div>
          <div className="cart-item-details">
            <div className="muted">{item.eventDate} {item.eventTime}</div>
          </div>
          <div className="cart-item-footer">
            <div className="cart-item-quantity">
              <button onClick={() => updateQuantity(index, (item.quantity || 1) - 1)}>-</button>
              <span>{item.quantity || 1}</span>
              <button onClick={() => updateQuantity(index, (item.quantity || 1) + 1)}>+</button>
            </div>
            <div className="cart-item-price">{formatPrice(item.price * (item.quantity || 1))}</div>
          </div>
        </div>
      )
    }

    if (item.type === 'quote_request') {
      return (
        <div key={index} className="cart-item">
          <div className="cart-item-header">
            <div className="cart-item-title">
              <i className="fa-solid fa-file-invoice" style={{ marginRight: '.35rem' }}></i>
              Quote Request
            </div>
            <button
              className="cart-item-remove"
              onClick={() => removeFromCart(index)}
              aria-label="Remove item"
            >
              <i className="fa-solid fa-times"></i>
            </button>
          </div>
          <div className="cart-item-details">
            <div className="muted">{item.description}</div>
          </div>
          <div className="cart-item-price">Custom Quote</div>
        </div>
      )
    }

    return null
  }

  return (
    <>
      <div className="cart-overlay" onClick={closeCart} />
      <aside className="cart-sidebar" role="dialog" aria-label="Shopping Cart">
        <div className="cart-header">
          <div className="cart-title">
            <i className="fa-solid fa-shopping-cart"></i>
            Your Cart
            {cart.chefUsername && <span className="muted"> · {cart.chefUsername}</span>}
          </div>
          <button className="cart-close" onClick={closeCart} aria-label="Close cart">
            <i className="fa-solid fa-times"></i>
          </button>
        </div>

        <div className="cart-body">
          {cart.items.length === 0 ? (
            <div className="cart-empty">
              <i className="fa-solid fa-shopping-cart" style={{ fontSize: 48, opacity: 0.3 }}></i>
              <p className="muted">Your cart is empty</p>
              <p className="muted" style={{ fontSize: '.9rem' }}>Browse services and meals to get started!</p>
            </div>
          ) : (
            <div className="cart-items">
              {cart.items.map(renderCartItem)}
            </div>
          )}
        </div>

        {cart.items.length > 0 && (
          <div className="cart-footer">
            <div className="cart-total">
              <span className="cart-total-label">Total</span>
              <span className="cart-total-amount">{formatPrice(getCartTotal())}</span>
            </div>
            {error && (
              <div className="cart-error" role="alert" style={{ color: '#c0392b', marginTop: '.5rem', fontSize: '.85rem' }}>
                {error}
              </div>
            )}
            <button type="button" className="btn btn-outline btn-block" onClick={clearCart} style={{ marginTop: '.5rem' }}>
              Clear Cart
            </button>
            {checkingOut ? (
              <button type="button" className="btn btn-primary btn-block" disabled style={{ marginTop: '.5rem' }}>
                Processing…
              </button>
            ) : (
              <button type="button" className="btn btn-primary btn-block" onClick={handleCheckout} style={{ marginTop: '.5rem' }}>
                Proceed to Checkout
              </button>
            )}
            {validationDetails ? (
              <div className="muted" style={{ marginTop: '.75rem', fontSize: '.8rem', color: '#c0392b' }}>
                Some required details are missing. Update the highlighted fields above, then try again.
              </div>
            ) : null}
          </div>
        )}
      </aside>
    </>
  )
}
