import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { rememberServiceOrderId } from '../utils/serviceOrdersStorage.js'

const CartContext = createContext()

export function useCart() {
  const context = useContext(CartContext)
  if (!context) {
    throw new Error('useCart must be used within CartProvider')
  }
  return context
}

const CART_STORAGE_KEY = 'sautai_chef_cart'

export function CartProvider({ children }) {
  const [cart, setCart] = useState({ items: [], chefUsername: null, chefId: null })
  const [isOpen, setIsOpen] = useState(false)

  // Load cart from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(CART_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        setCart(parsed)
      }
    } catch (err) {
      console.error('Failed to load cart:', err)
    }
  }, [])

  // Save cart to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart))
    } catch (err) {
      console.error('Failed to save cart:', err)
    }
  }, [cart])

  const deriveServiceCartKey = (entry) => {
    if (!entry) return null
    if (entry.type === 'service_tier') {
      return `${entry.offering_id ?? ''}:${entry.tier_id ?? ''}`
    }
    if (entry.type === 'meal_event') {
      return `meal:${entry.event_id ?? ''}`
    }
    if (entry.type === 'quote_request') {
      return `quote:${entry.id ?? ''}`
    }
    return null
  }

  function normalizeHouseholdSize(value){
    const numeric = Number(value)
    if (!Number.isFinite(numeric) || numeric < 1) return 1
    return Math.floor(numeric)
  }

  async function ensureServiceOrder(item){
    const orderPayload = {
      offering_id: item.offering_id,
      household_size: normalizeHouseholdSize(item.householdSize || item.household_size || 1)
    }
    if (item.tier_id != null) orderPayload.tier_id = item.tier_id
    if (item.specialRequests) orderPayload.special_requests = item.specialRequests
    if (item.scheduleNotes) orderPayload.schedule_preferences = { notes: item.scheduleNotes }
    if (item.durationMinutes) orderPayload.duration_minutes = item.durationMinutes
    if (item.serviceDate) orderPayload.service_date = item.serviceDate
    if (item.serviceStartTime) orderPayload.service_start_time = item.serviceStartTime
    const resp = await api.post('/services/orders/', orderPayload)
    const order = resp?.data || {}
    if (order?.id == null) {
      throw new Error('Order created but missing id from response.')
    }
    rememberServiceOrderId(order.id)
    return {
      orderId: order.id,
      orderStatus: order.status || 'draft',
      serviceDate: order.service_date || '',
      serviceStartTime: order.service_start_time || '',
      durationMinutes: order.duration_minutes ?? null,
      specialRequests: order.special_requests || '',
      scheduleNotes: order.schedule_preferences?.notes || '',
      schedulePreferences: order.schedule_preferences || null,
      householdSize: normalizeHouseholdSize(order.household_size || item.householdSize || 1),
      addressId: order.address_id ?? order.address ?? item.addressId ?? null
    }
  }

  // Add item to cart (service tier, meal event, or custom item)
  const addToCart = useCallback(async (item, chefInfo) => {
    const { username, id: chefId } = chefInfo || {}
    const normalizedUsername = username ? String(username).trim() : null

    // If cart has items from different chef, ask to clear first (compare by ID, not username)
    const shouldResetCart = cart.items.length > 0 && cart.chefId != null && chefId != null && cart.chefId !== chefId
    if (shouldResetCart) {
      const otherChef = cart.chefUsername || 'another chef'
      const confirmed = typeof window !== 'undefined'
        ? window.confirm(`Your cart contains items from ${otherChef}. Clear the cart and add this item from ${normalizedUsername || 'this chef'}?`)
        : false
      if (!confirmed) {
        return false
      }
      setCart({ items: [], chefUsername: null, chefId: null })
    }

    const activeItems = shouldResetCart ? [] : cart.items
    const cartKey = deriveServiceCartKey(item)
    const existingIndex = activeItems.findIndex(entry => deriveServiceCartKey(entry) === cartKey)
    const existingItem = existingIndex >= 0 ? activeItems[existingIndex] : null

    let enrichedItem = { ...item }
    if (item.type === 'service_tier') {
      // Preserve existing order info when updating the same tier
      if (existingItem?.orderId) {
        enrichedItem = { ...existingItem, ...enrichedItem, orderId: existingItem.orderId, orderStatus: existingItem.orderStatus }
      }
      if (!enrichedItem.orderId) {
        const ensured = await ensureServiceOrder(enrichedItem)
        enrichedItem = { ...enrichedItem, ...ensured }
      } else {
        enrichedItem.householdSize = normalizeHouseholdSize(enrichedItem.householdSize || enrichedItem.household_size || 1)
      }
      if (!enrichedItem.price) enrichedItem.price = item.price || 0
      if (!enrichedItem.serviceDate) enrichedItem.serviceDate = ''
      if (!enrichedItem.serviceStartTime) enrichedItem.serviceStartTime = ''
      if (!enrichedItem.specialRequests) enrichedItem.specialRequests = ''
      if (!enrichedItem.scheduleNotes) enrichedItem.scheduleNotes = ''
      if (!enrichedItem.requiresDateTime) enrichedItem.requiresDateTime = Boolean(item.requiresDateTime)
      if (!enrichedItem.needsScheduleNotes) enrichedItem.needsScheduleNotes = Boolean(item.needsScheduleNotes)
      if (!enrichedItem.serviceType) enrichedItem.serviceType = item.serviceType || null
      if (!enrichedItem.tierRecurring) enrichedItem.tierRecurring = Boolean(item.tierRecurring)
      if (!enrichedItem.orderStatus) enrichedItem.orderStatus = 'draft'
    }

    setCart(prev => {
      const shouldReset = prev.items.length > 0 && prev.chefId != null && chefId != null && prev.chefId !== chefId
      const baseItems = shouldReset ? [] : prev.items.slice()
      const baseChefUsername = shouldReset ? null : prev.chefUsername
      const baseChefId = shouldReset ? null : prev.chefId
      const index = baseItems.findIndex(entry => deriveServiceCartKey(entry) === cartKey)
      let nextItems
      if (index >= 0) {
        nextItems = [...baseItems]
        nextItems[index] = { ...baseItems[index], ...enrichedItem }
      } else {
        nextItems = [...baseItems, enrichedItem]
      }
      return {
        items: nextItems,
        chefUsername: normalizedUsername ?? baseChefUsername,
        chefId: chefId ?? baseChefId
      }
    })

    return true
  }, [cart.items, cart.chefUsername, cart.chefId])

  const updateCartItem = useCallback((index, updates) => {
    setCart(prev => {
      if (!Array.isArray(prev.items) || !prev.items[index]) return prev
      const nextItems = prev.items.map((item, idx) => (idx === index ? { ...item, ...updates } : item))
      return { ...prev, items: nextItems }
    })
  }, [])

  // Load an existing service order into the cart (from CustomerOrders page)
  const loadExistingOrder = useCallback((order, chefInfo) => {
    console.log('[CartContext] loadExistingOrder called', { order, chefInfo })
    
    const { username, id: chefId } = chefInfo || {}
    const normalizedUsername = username ? String(username).trim() : null
    console.log('[CartContext] Normalized username', normalizedUsername)

    // Skip the different-chef check if this exact order is already in the cart
    const orderAlreadyInCart = cart.items.some(item => item.orderId === order.id)
    if (orderAlreadyInCart) {
      console.log('[CartContext] Order already in cart, skipping add - just return true to open cart')
      return true
    }

    // If cart has items from different chef, ask to clear first (compare by ID, not username)
    const shouldResetCart = cart.items.length > 0 && cart.chefId != null && chefId != null && cart.chefId !== chefId
    console.log('[CartContext] Should reset cart?', { shouldResetCart, currentCartChefId: cart.chefId, newChefId: chefId, cartItemsCount: cart.items.length })
    
    if (shouldResetCart) {
      const otherChef = cart.chefUsername || 'another chef'
      const confirmed = typeof window !== 'undefined'
        ? window.confirm(`Your cart contains items from ${otherChef}. Clear the cart and add this order from ${normalizedUsername || 'this chef'}?`)
        : false
      console.log('[CartContext] User confirmation result', confirmed)
      if (!confirmed) {
        return false
      }
      setCart({ items: [], chefUsername: null, chefId: null })
    }

    // Convert order to cart item format
    const cartItem = {
      type: 'service_tier',
      orderId: order.id,
      offering_id: order.offering_id,
      tier_id: order.tier_id,
      offeringTitle: order.offering_title || 'Service',
      tierLabel: order.tier_label || order.tier_name || '',
      price: order.total_value_for_chef || order.price || 0,
      orderStatus: order.status || 'draft',
      householdSize: normalizeHouseholdSize(order.household_size),
      serviceDate: order.service_date || '',
      serviceStartTime: order.service_start_time || '',
      durationMinutes: order.duration_minutes ?? null,
      addressId: order.address_id ?? order.address ?? null,
      specialRequests: order.special_requests || '',
      scheduleNotes: order.schedule_preferences?.notes || '',
      schedulePreferences: order.schedule_preferences || null,
      requiresDateTime: Boolean(order.requires_datetime || order.requiresDateTime),
      needsScheduleNotes: Boolean(order.needs_schedule_notes || order.needsScheduleNotes),
      tierRecurring: Boolean(order.is_subscription || order.tierRecurring),
      serviceType: order.service_type || null
    }
    console.log('[CartContext] Converted order to cart item', cartItem)

    setCart(prev => {
      console.log('[CartContext] Previous cart state', prev)
      
      const shouldReset = prev.items.length > 0 && prev.chefId != null && chefId != null && prev.chefId !== chefId
      const baseItems = shouldReset ? [] : prev.items.slice()
      
      // Check if this order is already in the cart
      const existingIndex = baseItems.findIndex(item => item.orderId === order.id)
      console.log('[CartContext] Existing index in cart', existingIndex)
      
      let nextItems
      if (existingIndex >= 0) {
        // Update existing
        nextItems = [...baseItems]
        nextItems[existingIndex] = { ...baseItems[existingIndex], ...cartItem }
        console.log('[CartContext] Updated existing item at index', existingIndex)
      } else {
        // Add new
        nextItems = [...baseItems, cartItem]
        console.log('[CartContext] Added new item to cart')
      }

      const newCart = {
        items: nextItems,
        chefUsername: normalizedUsername ?? prev.chefUsername,
        chefId: chefId ?? prev.chefId
      }
      console.log('[CartContext] New cart state', newCart)
      return newCart
    })

    console.log('[CartContext] loadExistingOrder returning true')
    return true
  }, [cart.items, cart.chefUsername, cart.chefId])

  // Remove item from cart
  const removeFromCart = useCallback((index) => {
    const updatedItems = cart.items.filter((_, i) => i !== index)
    setCart({ ...cart, items: updatedItems })
    
    // Clear chef info if cart is now empty
    if (updatedItems.length === 0) {
      setCart({ items: [], chefUsername: null, chefId: null })
    }
  }, [cart])

  // Update item quantity
  const updateQuantity = useCallback((index, quantity) => {
    const updatedItems = [...cart.items]
    if (quantity <= 0) {
      removeFromCart(index)
      return
    }
    updatedItems[index] = { ...updatedItems[index], quantity }
    setCart({ ...cart, items: updatedItems })
  }, [cart, removeFromCart])

  // Clear entire cart
  const clearCart = useCallback(() => {
    setCart({ items: [], chefUsername: null, chefId: null })
  }, [])

  // Calculate cart total
  const getCartTotal = useCallback(() => {
    return cart.items.reduce((total, item) => {
      const price = item.price || 0
      const quantity = item.quantity || 1
      return total + (price * quantity)
    }, 0)
  }, [cart.items])

  // Get item count
  const getItemCount = useCallback(() => {
    return cart.items.reduce((count, item) => {
      return count + (item.quantity || 1)
    }, 0)
  }, [cart.items])

  // Toggle cart sidebar
  const toggleCart = useCallback(() => {
    setIsOpen(prev => {
      console.log('[CartContext] toggleCart - prev:', prev, 'new:', !prev)
      return !prev
    })
  }, [])
  const openCart = useCallback(() => {
    console.log('[CartContext] openCart called')
    setIsOpen(true)
  }, [])
  const closeCart = useCallback(() => {
    console.log('[CartContext] closeCart called')
    setIsOpen(false)
  }, [])

  const value = {
    cart,
    isOpen,
    addToCart,
    loadExistingOrder,
    updateCartItem,
    removeFromCart,
    updateQuantity,
    clearCart,
    getCartTotal,
    getItemCount,
    toggleCart,
    openCart,
    closeCart
  }

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}

