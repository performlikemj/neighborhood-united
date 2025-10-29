import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext.jsx'
import { api, buildErrorMessage } from '../api'
import { rememberServiceOrderId } from '../utils/serviceOrdersStorage.js'

function formatPrice(cents) {
  if (typeof cents !== 'number') return '$0.00'
  return `$${(cents / 100).toFixed(2)}`
}

function normalizeInteger(value, fallback = 1) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric < 1) return fallback
  return Math.floor(numeric)
}

function normalizeAddressList(payload){
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.data?.results)) return payload.data.results
  if (Array.isArray(payload?.addresses)) return payload.addresses
  if (Array.isArray(payload?.data?.addresses)) return payload.data.addresses
  if (payload?.address && typeof payload.address === 'object') return [payload.address]
  if (payload?.id != null) return [payload]
  return []
}

function formatAddressSummary(address){
  if (!address || typeof address !== 'object') return ''
  const parts = []
  const nickname = address.nickname || address.label || ''
  const line1 = address.street || address.address_line1 || address.address1 || ''
  const line2 = address.address_line2 || address.address2 || ''
  const city = address.city || address.locality || ''
  const state = address.state || address.region || address.province || ''
  const postal = address.postal_code || address.postalcode || address.zip || address.zip_code || ''
  const country = address.country_code || address.country || ''
  if (nickname) parts.push(nickname)
  const location = [line1, line2, city].filter(Boolean).join(', ')
  if (location) parts.push(location)
  const region = [state, postal].filter(Boolean).join(' ')
  if (region) parts.push(region)
  if (country) parts.push(String(country).toUpperCase())
  if (!parts.length && address.id != null) return `Address #${address.id}`
  return parts.join(' • ')
}

export default function CartSidebar() {
  const { cart, isOpen, closeCart, removeFromCart, updateQuantity, getCartTotal, clearCart, updateCartItem } = useCart()
  const { user: authUser } = useAuth()
  const [checkingOut, setCheckingOut] = useState(false)
  const [error, setError] = useState('')
  const [itemErrors, setItemErrors] = useState({})
  const [validationDetails, setValidationDetails] = useState(null)
  const [addresses, setAddresses] = useState([])
  const [addressesLoading, setAddressesLoading] = useState(false)
  const [addressesError, setAddressesError] = useState('')
  const [addressForm, setAddressForm] = useState({ street:'', city:'', state:'', postal_code:'', country:'' })
  const [addressFormState, setAddressFormState] = useState({ open:false, targetIndex:null })
  const [addressFormError, setAddressFormError] = useState('')
  const [addressSaving, setAddressSaving] = useState(false)
  const addressesFetchedRef = useRef(false)
  
  console.log('[CartSidebar] Render - isOpen:', isOpen, 'cart items:', cart?.items?.length || 0)

  const defaultAddressId = useMemo(() => {
    const addr = authUser?.address || {}
    const id = addr.id ?? addr.address_id ?? null
    console.log('[CartSidebar] defaultAddressId from authUser:', { authUser, address: addr, id })
    return id != null ? String(id) : null
  }, [authUser])

  const primaryAddressId = useMemo(()=>{
    if (!Array.isArray(addresses) || addresses.length === 0) return null
    const preferred = addresses.find(a => a?.is_default) || addresses[0]
    return preferred?.id != null ? String(preferred.id) : null
  }, [addresses])

  const fetchAddresses = useCallback(async (force = false)=>{
    if (!force && addressesFetchedRef.current && addresses.length > 0) return
    setAddressesLoading(true)
    setAddressesError('')
    try{
      console.log('[CartSidebar] Fetching addresses...')
      const resp = await api.get('/auth/api/address_details/')
      console.log('[CartSidebar] Raw API response:', resp?.data)
      const list = normalizeAddressList(resp?.data)
      console.log('[CartSidebar] After normalization:', list)
      setAddresses(Array.isArray(list) ? list.filter(Boolean) : [])
      addressesFetchedRef.current = true
    }catch(err){
      const message = err?.response
        ? buildErrorMessage(err.response.data, 'Unable to load saved addresses. Please try again.', err.response.status)
        : (err?.message || 'Unable to load saved addresses. Please try again.')
      setAddresses([])
      setAddressesError(message)
    }finally{
      setAddressesLoading(false)
    }
  }, [addresses.length])

  useEffect(() => {
    if (!Array.isArray(cart.items)) return
    cart.items.forEach((item, index) => {
      if (item?.type !== 'service_tier') return
      const updates = {}
      if (!item.householdSize || normalizeInteger(item.householdSize) !== Number(item.householdSize)) {
        updates.householdSize = normalizeInteger(item.householdSize)
      }
      if (!item.addressId && defaultAddressId) {
        updates.addressId = defaultAddressId
      }
      if (Object.keys(updates).length > 0) {
        updateCartItem(index, updates)
      }
    })
  }, [cart.items, defaultAddressId, updateCartItem])

  useEffect(()=>{
    if (!Array.isArray(addresses) || addresses.length === 0) return
    if (!primaryAddressId) return
    cart.items.forEach((item, index)=>{
      if (item?.type !== 'service_tier') return
      if (item.addressId != null && String(item.addressId).trim() !== '') return
      updateCartItem(index, { addressId: primaryAddressId })
    })
  }, [addresses, cart.items, primaryAddressId, updateCartItem])

  useEffect(()=>{
    if (!isOpen) return
    fetchAddresses()
  }, [isOpen, fetchAddresses])

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
    if (field === 'addressId' && value === '__add__'){
      const base = authUser?.address || {}
      setAddressForm({
        street: '',
        city: '',
        state: '',
        postal_code: '',
        country: String(base.country || base.country_code || '').toUpperCase()
      })
      setAddressFormError('')
      setAddressFormState({ open:true, targetIndex:index })
      clearFieldError(index, 'address_id')
      return
    }
    updateCartItem(index, { [field]: value })
    clearFieldError(index, field)
    if (validationDetails) setValidationDetails(null)
  }

  const handleScheduleNotesChange = (index, value) => {
    updateCartItem(index, { scheduleNotes: value })
    clearFieldError(index, 'schedule_preferences')
    if (validationDetails) setValidationDetails(null)
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
    if (needsScheduleNotes && !item.scheduleNotes) {
      errors.schedule_preferences = 'Add scheduling preferences for this recurring service.'
    }
    if (!item.addressId) {
      errors.address_id = 'Choose an address for this service.'
    }
    return errors
  }

  const submitNewAddress = async (event)=>{
    if (event && typeof event.preventDefault === 'function') event.preventDefault()
    if (addressSaving) return
    setAddressFormError('')
    const normalized = {
      street: (addressForm.street || '').trim(),
      city: (addressForm.city || '').trim(),
      state: (addressForm.state || '').trim(),
      postal_code: (addressForm.postal_code || '').trim(),
      country: (addressForm.country || '').trim()
    }
    if (!normalized.street || !normalized.city || !normalized.postal_code || !normalized.country){
      setAddressFormError('Please complete street, city, postal code, and country to add a new address.')
      return
    }
    setAddressSaving(true)
    try{
      const resp = await api.post('/auth/api/address_details/', normalized)
      const created = resp?.data || null
      await fetchAddresses(true)
      const newId = created?.id ?? created?.address_id ?? null
      if (newId != null && typeof addressFormState.targetIndex === 'number'){
        updateCartItem(addressFormState.targetIndex, { addressId: String(newId) })
        clearFieldError(addressFormState.targetIndex, 'address_id')
      }
      setAddressFormState({ open:false, targetIndex:null })
      setAddressForm({ street:'', city:'', state:'', postal_code:'', country:'' })
      try{
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Address added.', tone:'success' } }))
      }catch{}
    }catch(err){
      const message = err?.response
        ? buildErrorMessage(err.response.data, 'Unable to add address.', err.response.status)
        : (err?.message || 'Unable to add address.')
      setAddressFormError(message)
    }finally{
      setAddressSaving(false)
    }
  }

  const cancelAddressForm = ()=>{
    setAddressFormState({ open:false, targetIndex:null })
    setAddressForm({ street:'', city:'', state:'', postal_code:'', country:'' })
    setAddressFormError('')
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
          if (!serviceItem.orderId) {
            const err = new Error('Service item is missing a draft order. Remove it from your cart and add it again.')
            err._cartItemIndex = indexInCart
            throw err
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
            const updateResp = await api.patch(`/chef-services/orders/${serviceItem.orderId}/update/`, payload)
            updatedOrder = updateResp?.data || null
            if (updatedOrder) {
              updateCartItem(indexInCart, {
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
            rememberServiceOrderId(serviceItem.orderId)
          }catch(err){
            err._cartItemIndex = indexInCart
            throw err
          }

          try{
            const checkoutResp = await api.post(`/chef-services/orders/${serviceItem.orderId}/checkout`, {})
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
    console.log('[CartSidebar] Rendering cart item', { index, type: item.type, addressId: item.addressId, item })
    
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
            <label style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', fontSize: '.85rem' }}>
              <span>Service address</span>
              {(() => {
                const currentAddressId = item.addressId ?? ''
                const availableIds = addresses.map(a => String(a?.id || '')).filter(Boolean)
                console.log('[CartSidebar] Address dropdown state:', { 
                  currentAddressId, 
                  availableIds, 
                  addressesCount: addresses.length,
                  addressesLoading,
                  addressesError 
                })
                return null
              })()}
              <select
                value={item.addressId ?? ''}
                onChange={(e) => handleServiceFieldChange(index, 'addressId', e.target.value)}
                style={{ padding: '.45rem', borderRadius: '6px', border: fieldError(index, 'address_id') ? '1px solid #c0392b' : '1px solid var(--border-subtle)' }}
              >
                <option value="">Select an address…</option>
                {addresses.map(addr => {
                  const id = addr?.id != null ? String(addr.id) : null
                  if (!id) return null
                  return (
                    <option key={id} value={id}>
                      {formatAddressSummary(addr)}
                    </option>
                  )
                })}
                <option value="__add__">+ Add new address</option>
              </select>
              {addressesLoading && <span className="muted" style={{ fontSize: '.75rem' }}>Loading addresses…</span>}
              {addressesError && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{addressesError}</span>}
              {fieldError(index, 'address_id') && <span style={{ color: '#c0392b', fontSize: '.75rem' }}>{fieldError(index, 'address_id')}</span>}
              {!addressesLoading && !addressesError && addresses.length === 0 && (
                <span className="muted" style={{ fontSize: '.75rem' }}>You haven’t saved any addresses yet. Add one below to keep checkout moving.</span>
              )}
              <button
                type="button"
                className="btn btn-link"
                onClick={() => {
                  const base = authUser?.address || {}
                  setAddressForm({
                    street: '',
                    city: '',
                    state: '',
                    postal_code: '',
                    country: String(base.country || base.country_code || '').toUpperCase()
                  })
                  setAddressFormError('')
                  setAddressFormState({ open:true, targetIndex:index })
                }}
                style={{ alignSelf:'flex-start', padding:0, fontSize:'.8rem' }}
              >
                Add new address
              </button>
            </label>
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
            <button className="btn btn-outline btn-block" onClick={clearCart} style={{ marginTop: '.5rem' }}>
              Clear Cart
            </button>
            {checkingOut ? (
              <button className="btn btn-primary btn-block" disabled style={{ marginTop: '.5rem' }}>
                Processing…
              </button>
            ) : (
              <button className="btn btn-primary btn-block" onClick={handleCheckout} style={{ marginTop: '.5rem' }}>
                Proceed to Checkout
              </button>
            )}
            {validationDetails ? (
              <div className="muted" style={{ marginTop: '.75rem', fontSize: '.8rem', color: '#c0392b' }}>
                Some required details are missing. Update the highlighted fields above, then try again.
              </div>
            ) : null}
            {addressFormState.open && (
              <div className="card" style={{ marginTop: '1rem', background: 'var(--surface-2)', padding: '.75rem' }}>
                <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Add a new address</h3>
                <form onSubmit={submitNewAddress} style={{ display: 'flex', flexDirection: 'column', gap: '.6rem' }}>
                  <label style={{ display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.85rem' }}>
                    <span>Street address</span>
                    <input
                      className="input"
                      value={addressForm.street}
                      onChange={(e)=> setAddressForm(prev => ({ ...prev, street: e.target.value }))}
                      placeholder="123 Main St"
                    />
                  </label>
                  <label style={{ display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.85rem' }}>
                    <span>City</span>
                    <input
                      className="input"
                      value={addressForm.city}
                      onChange={(e)=> setAddressForm(prev => ({ ...prev, city: e.target.value }))}
                      placeholder="City"
                    />
                  </label>
                  <div style={{ display:'flex', gap:'.6rem', flexWrap:'wrap' }}>
                    <label style={{ flex:'1 1 120px', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.85rem' }}>
                      <span>State / Region</span>
                      <input
                        className="input"
                        value={addressForm.state}
                        onChange={(e)=> setAddressForm(prev => ({ ...prev, state: e.target.value }))}
                        placeholder="State"
                      />
                    </label>
                    <label style={{ flex:'1 1 120px', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.85rem' }}>
                      <span>Postal code</span>
                      <input
                        className="input"
                        value={addressForm.postal_code}
                        onChange={(e)=> setAddressForm(prev => ({ ...prev, postal_code: e.target.value }))}
                        placeholder="Postal code"
                      />
                    </label>
                    <label style={{ flex:'1 1 120px', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.85rem' }}>
                      <span>Country</span>
                      <input
                        className="input"
                        value={addressForm.country}
                        onChange={(e)=> setAddressForm(prev => ({ ...prev, country: e.target.value }))}
                        placeholder="US"
                      />
                    </label>
                  </div>
                  {addressFormError && (
                    <div style={{ color:'#c0392b', fontSize:'.8rem' }}>{addressFormError}</div>
                  )}
                  <div style={{ display:'flex', gap:'.5rem', justifyContent:'flex-end' }}>
                    <button type="button" className="btn btn-outline btn-sm" onClick={cancelAddressForm} disabled={addressSaving}>
                      Cancel
                    </button>
                    <button type="submit" className="btn btn-primary btn-sm" disabled={addressSaving}>
                      {addressSaving ? 'Saving…' : 'Save address'}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </div>
        )}
      </aside>
    </>
  )
}
