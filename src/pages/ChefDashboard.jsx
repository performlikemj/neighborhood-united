import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, stripe } from '../api'

function toArray(payload){
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.details?.results)) return payload.details.results
  if (Array.isArray(payload?.details)) return payload.details
  if (Array.isArray(payload?.data?.results)) return payload.data.results
  if (Array.isArray(payload?.data)) return payload.data
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.events)) return payload.events
  if (Array.isArray(payload?.orders)) return payload.orders
  return []
}

function renderAreas(areas){
  if (!Array.isArray(areas) || areas.length === 0) return ''
  const names = areas
    .map(p => (p?.postal_code || p?.postalcode || p?.code || p?.name || ''))
    .filter(Boolean)
  return names.join(', ')
}

const SERVICE_TYPES = [
  { value: 'home_chef', label: 'In-Home Chef' },
  { value: 'weekly_prep', label: 'Weekly Meal Prep' }
]

const INITIAL_SERVICE_FORM = {
  id: null,
  service_type: 'home_chef',
  title: '',
  description: '',
  default_duration_minutes: '',
  max_travel_miles: '',
  notes: ''
}

const INITIAL_TIER_FORM = {
  id: null,
  offeringId: null,
  household_min: '',
  household_max: '',
  currency: 'usd',
  price: '',
  is_recurring: false,
  recurrence_interval: 'week',
  active: true,
  display_label: ''
}

const SERVICES_ROOT = '/services'

function flattenErrors(errors){
  if (!errors) return []
  if (typeof errors === 'string') return [errors]
  if (Array.isArray(errors)){
    return errors.flatMap(item => flattenErrors(item)).filter(Boolean)
  }
  if (typeof errors === 'object'){
    const entries = Object.entries(errors)
    return entries.flatMap(([key, value]) => {
      const prefix = key && key !== 'non_field_errors' ? `${key}: ` : ''
      return flattenErrors(value).map(msg => `${prefix}${msg}`)
    })
  }
  return [String(errors)]
}

function FileSelect({ label, accept, onChange }){
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState('')
  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        style={{display:'none'}}
        onChange={(e)=>{
          const f = (e.target.files||[])[0] || null
          setFileName(f ? f.name : '')
          onChange && onChange(f)
        }}
      />
      <button type="button" className="btn btn-outline btn-sm" onClick={()=> inputRef.current?.click()}>{label}</button>
      {fileName && <div className="muted" style={{marginTop:'.25rem'}}>{fileName}</div>}
    </div>
  )
}

export default function ChefDashboard(){
  const [tab, setTab] = useState('dashboard')
  const [notice, setNotice] = useState(null)

  // Stripe Connect status
  const [payouts, setPayouts] = useState({ loading: true, has_account:false, is_active:false, needs_onboarding:false, account_id:null, continue_onboarding_url:null, disabled_reason:null, diagnostic:null })
  const [onboardingBusy, setOnboardingBusy] = useState(false)

  // Chef profile
  const [chef, setChef] = useState(null)
  const [profileForm, setProfileForm] = useState({ experience:'', bio:'', profile_pic:null, banner_image:null })
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileInit, setProfileInit] = useState(false)
  const [bannerUpdating, setBannerUpdating] = useState(false)
  const [bannerJustUpdated, setBannerJustUpdated] = useState(false)
  const [profilePicPreview, setProfilePicPreview] = useState(null)
  const [bannerPreview, setBannerPreview] = useState(null)
  // Break state
  const [isOnBreak, setIsOnBreak] = useState(false)
  const [breakBusy, setBreakBusy] = useState(false)
  const [breakReason, setBreakReason] = useState('')

  // Chef photos
  const [photoForm, setPhotoForm] = useState({ image:null, title:'', caption:'', is_featured:false })
  const [photoUploading, setPhotoUploading] = useState(false)

  // Ingredients
  const [ingredients, setIngredients] = useState([])
  const [ingForm, setIngForm] = useState({ name:'', calories:'', fat:'', carbohydrates:'', protein:'' })
  const [ingLoading, setIngLoading] = useState(false)
  const duplicateIngredient = useMemo(()=>{
    const a = String(ingForm.name||'').trim().toLowerCase()
    if (!a) return false
    return ingredients.some(i => String(i?.name||'').trim().toLowerCase() === a)
  }, [ingredients, ingForm.name])

  // Dishes
  const [dishes, setDishes] = useState([])
  const [dishForm, setDishForm] = useState({ name:'', featured:false, ingredient_ids:[] })

  // Meals
  const [meals, setMeals] = useState([])
  const [mealForm, setMealForm] = useState({ name:'', description:'', meal_type:'Dinner', price:'', start_date:'', dishes:[], dietary_preferences:[] })

  // Events
  const [events, setEvents] = useState([])
  const [eventForm, setEventForm] = useState({ meal:null, event_date:'', event_time:'18:00', order_cutoff_date:'', order_cutoff_time:'12:00', base_price:'', min_price:'', max_orders:10, min_orders:1, description:'', special_instructions:'' })
  const [showPastEvents, setShowPastEvents] = useState(false)

  // Orders
  const [orders, setOrders] = useState([])

  // Chef services
  const [serviceOfferings, setServiceOfferings] = useState([])
  const [serviceLoading, setServiceLoading] = useState(false)
  const [serviceForm, setServiceForm] = useState(()=>({ ...INITIAL_SERVICE_FORM }))
  const [serviceSaving, setServiceSaving] = useState(false)
  const [serviceErrors, setServiceErrors] = useState(null)
  const [tierForm, setTierForm] = useState(()=>({ ...INITIAL_TIER_FORM }))
  const [tierSaving, setTierSaving] = useState(false)
  const [tierErrors, setTierErrors] = useState(null)
  const [serviceOrderForm, setServiceOrderForm] = useState({ offeringId:'', household_size:'', tier_id:'', service_date:'', service_start_time:'', duration_minutes:'', address_id:'', special_requests:'', schedule_preferences:'' })
  const [serviceOrderSaving, setServiceOrderSaving] = useState(false)
  const [serviceOrder, setServiceOrder] = useState(null)
  const [serviceOrderErrors, setServiceOrderErrors] = useState(null)
  const [serviceOrderLoading, setServiceOrderLoading] = useState(false)
  const [serviceCheckoutBusy, setServiceCheckoutBusy] = useState(false)
  const [serviceCancelBusy, setServiceCancelBusy] = useState(false)

  const serviceErrorMessages = useMemo(()=> flattenErrors(serviceErrors), [serviceErrors])
  const tierErrorMessages = useMemo(()=> flattenErrors(tierErrors), [tierErrors])
  const serviceOrderErrorMessages = useMemo(()=> flattenErrors(serviceOrderErrors), [serviceOrderErrors])
  const serviceOrderSessionId = useMemo(()=> pickFirst(serviceOrder, ['stripe_session_id','stripe_checkout_session_id']), [serviceOrder])
  const serviceOrderCheckoutUrl = useMemo(()=> pickFirst(serviceOrder, ['stripe_checkout_url','checkout_url','session_url']), [serviceOrder])
  const selectedServiceOffering = useMemo(()=> serviceOfferings.find(o => String(o.id) === String(serviceOrderForm.offeringId)), [serviceOfferings, serviceOrderForm.offeringId])

  const todayISO = useMemo(()=> new Date().toISOString().slice(0,10), [])

  const loadIngredients = async ()=>{
    setIngLoading(true)
    try{
      const resp = await api.get('/meals/api/ingredients/', { params: { chef_ingredients: 'true' } })
      setIngredients(toArray(resp.data))
    }catch{ setIngredients([]) } finally { setIngLoading(false) }
  }

  async function loadStripeStatus(){
    try{
      const resp = await stripe.getStatus()
      const data = resp?.data || {}
      setPayouts({ loading:false, ...data })
    }catch(e){
      setPayouts(prev => ({ ...(prev || {}), loading:false }))
    }
  }

  const loadChefProfile = async (retries = 2)=>{
    try{
      const resp = await api.get('/chefs/api/me/chef/profile/', { skipUserId: true })
      const data = resp.data || null
      setChef(data)
      setIsOnBreak(Boolean(data?.is_on_break))
      setProfileForm({ experience: data?.experience || '', bio: data?.bio || '', profile_pic: null, banner_image: null })
    }catch(e){
      const status = e?.response?.status
      // Handle token/role propagation races: retry once after nudging user_details
      if ((status === 401 || status === 403) && retries > 0){
        try{ await api.get('/auth/api/user_details/', { skipUserId: true }) }catch{}
        await new Promise(r => setTimeout(r, 400))
        return loadChefProfile(retries - 1)
      }
      if (status === 403){ setNotice('You are not in Chef mode. Switch role to Chef to manage your profile.') }
      else if (status === 404){ setNotice('Chef profile not found. Your account may not be approved yet.') }
      setChef(null)
    } finally {
      setProfileInit(true)
    }
  }

  const toggleBreak = async (nextState)=>{
    if (breakBusy) return
    // Confirm enabling
    if (nextState && !window.confirm('This will cancel upcoming events and refund paid orders. Continue?')){
      return
    }
    setBreakBusy(true)
    try{
      const payload = nextState ? { is_on_break: true, reason: breakReason || 'Chef is going on break' } : { is_on_break: false }
      const resp = await api.post('/chefs/api/me/chef/break/', payload, { timeout: 60000 })
      const data = resp?.data || {}
      setIsOnBreak(Boolean(data?.is_on_break))
      if (nextState){
        const cancelled = Number(data?.cancelled_events||0)
        const refunded = Number(data?.refunds_processed||0)
        const failed = Number(data?.refunds_failed||0)
        const hasErrors = Array.isArray(data?.errors) && data.errors.length>0
        const summary = `You're now on break. Cancelled ${cancelled} events; refunds processed ${refunded}.`
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: summary, tone: failed>0||hasErrors?'error':'success' } })) }catch{}
      } else {
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: `Break disabled. You can create new events now.`, tone:'success' } })) }catch{}
      }
      // Refresh profile in background
      loadChefProfile()
    }catch(e){
      const status = e?.response?.status
      if (status === 403){
        const ok = window.confirm('You are not in Chef mode. Switch role to Chef?')
        if (ok){ try{ await switchToChef() }catch{} }
      } else {
        try{
          const { buildErrorMessage } = await import('../api')
          const msg = buildErrorMessage(e?.response?.data, 'Unable to update break status', status)
          window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
        }catch{
          window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: 'Unable to update break status', tone:'error' } }))
        }
      }
    } finally { setBreakBusy(false) }
  }

  const switchToChef = async ()=>{
    try{ await api.post('/auth/api/switch_role/', { role:'chef' }); setNotice(null); await loadChefProfile() }catch{ setNotice('Unable to switch role to Chef.') }
  }

  const loadDishes = async ()=>{
    try{ const resp = await api.get('/meals/api/dishes/', { params: { chef_dishes:'true' } }); setDishes(toArray(resp.data)) }catch{ setDishes([]) }
  }

  const loadMeals = async ()=>{
    try{ const resp = await api.get('/meals/api/meals/'); setMeals(toArray(resp.data)) }catch{ setMeals([]) }
  }

  const loadEvents = async ()=>{
    try{ 
      console.log('[ChefDashboard] Loading my events')
      const resp = await api.get('/meals/api/chef-meal-events/', { params: { my_events:'true' } }); 
      const list = toArray(resp.data)
      console.log('[ChefDashboard] Loaded my events', { count: list.length, sample: list.slice(0,3).map(e=>e.id) })
      setEvents(list) 
    }catch(e){ console.warn('[ChefDashboard] Load my events failed', { status: e?.response?.status, data: e?.response?.data }); setEvents([]) }
  }

  const loadOrders = async ()=>{
    try{ const resp = await api.get('/meals/api/chef-meal-orders/', { params: { as_chef: 'true' } }); setOrders(toArray(resp.data)) }catch{ setOrders([]) }
  }

  const loadServiceOfferings = async ()=>{
    setServiceLoading(true)
    try{
      const resp = await api.get(`${SERVICES_ROOT}/my/offerings/`)
      setServiceOfferings(toArray(resp.data))
    }catch{
      setServiceOfferings([])
    } finally {
      setServiceLoading(false)
    }
  }

  const loadAll = async ()=>{
    setNotice(null)
    try{ await api.get('/auth/api/user_details/') }catch{}
    const tasks = [loadChefProfile(), loadIngredients(), loadDishes(), loadMeals(), loadEvents(), loadOrders(), loadStripeStatus(), loadServiceOfferings()]
    await Promise.all(tasks.map(p => p.catch(()=>undefined)))
  }

  // Derive upcoming vs past events
  const upcomingEvents = useMemo(()=>{
    const now = Date.now()
    const items = Array.isArray(events) ? events.slice() : []
    const toTs = (e)=>{
      const cutoff = e?.order_cutoff_time ? Date.parse(e.order_cutoff_time) : null
      if (cutoff != null && !Number.isNaN(cutoff)) return cutoff
      const date = e?.event_date || ''
      let time = e?.event_time || '00:00'
      if (typeof time === 'string' && time.length === 5) time = time + ':00'
      const dt = Date.parse(`${date}T${time}`)
      return Number.isNaN(dt) ? 0 : dt
    }
    return items.filter(e => toTs(e) >= now).sort((a,b)=> toTs(a) - toTs(b))
  }, [events])

  const pastEvents = useMemo(()=>{
    const now = Date.now()
    const items = Array.isArray(events) ? events.slice() : []
    const toTs = (e)=>{
      const cutoff = e?.order_cutoff_time ? Date.parse(e.order_cutoff_time) : null
      if (cutoff != null && !Number.isNaN(cutoff)) return cutoff
      const date = e?.event_date || ''
      let time = e?.event_time || '00:00'
      if (typeof time === 'string' && time.length === 5) time = time + ':00'
      const dt = Date.parse(`${date}T${time}`)
      return Number.isNaN(dt) ? 0 : dt
    }
    return items.filter(e => toTs(e) < now).sort((a,b)=> toTs(b) - toTs(a))
  }, [events])

  // Preview URLs for unsaved uploads
  useEffect(()=>{
    let url
    if (profileForm.profile_pic){ try{ url = URL.createObjectURL(profileForm.profile_pic); setProfilePicPreview(url) }catch{}
    } else { setProfilePicPreview(null) }
    return ()=>{ if (url) URL.revokeObjectURL(url) }
  }, [profileForm.profile_pic])

  useEffect(()=>{
    let url
    if (profileForm.banner_image){ try{ url = URL.createObjectURL(profileForm.banner_image); setBannerPreview(url) }catch{}
    } else { setBannerPreview(null) }
    return ()=>{ if (url) URL.revokeObjectURL(url) }
  }, [profileForm.banner_image])

  useEffect(()=>{ loadAll() }, [])

  useEffect(()=>{
    // Poll while onboarding is incomplete
    if (!payouts || payouts.loading) return
    if (payouts.is_active) return
    const id = setInterval(()=>{ loadStripeStatus().catch(()=>{}) }, 7000)
    return ()=> clearInterval(id)
  }, [payouts.loading, payouts.is_active])

  const startOrContinueOnboarding = async ()=>{
    setOnboardingBusy(true)
    try{
      const resp = await stripe.createOrContinue()
      const url = resp?.data?.url
      if (url){ window.location.href = url; return }
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'No onboarding URL returned', tone:'error' } })) }catch{}
    }catch(e){
      try{
        const { buildErrorMessage } = await import('../api')
        const msg = buildErrorMessage(e?.response?.data, 'Unable to start onboarding', e?.response?.status)
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
      }catch{}
    }finally{ setOnboardingBusy(false) }
  }

  const regenerateOnboarding = async ()=>{
    setOnboardingBusy(true)
    try{
      const resp = await stripe.regenerate()
      const url = resp?.data?.onboarding_url
      if (url){ window.location.href = url; return }
      await loadStripeStatus()
    }catch{ } finally { setOnboardingBusy(false) }
  }

  const fixRestrictedAccount = async ()=>{
    setOnboardingBusy(true)
    try{
      const resp = await stripe.fixRestricted()
      const url = resp?.data?.onboarding_url
      await loadStripeStatus()
      if (url){ window.location.href = url }
    }catch(e){
      try{
        const { buildErrorMessage } = await import('../api')
        const msg = buildErrorMessage(e?.response?.data, 'Unable to fix account', e?.response?.status)
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
      }catch{}
    } finally { setOnboardingBusy(false) }
  }

  // Actions
  const createIngredient = async (e)=>{
    e.preventDefault()
    try{
      const payload = { ...ingForm, calories:Number(ingForm.calories||0), fat:Number(ingForm.fat||0), carbohydrates:Number(ingForm.carbohydrates||0), protein:Number(ingForm.protein||0) }
      const resp = await api.post('/meals/api/chef/ingredients/', payload)
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: (resp?.data?.message || 'Ingredient created successfully'), tone:'success' } })) }catch{}
      setIngForm({ name:'', calories:'', fat:'', carbohydrates:'', protein:'' })
      loadIngredients()
    }catch(e){ console.error('createIngredient failed', e); }
  }

  const deleteIngredient = async (id)=>{ try{ await api.delete(`/meals/api/chef/ingredients/${id}/delete/`); loadIngredients() }catch{} }

  const createDish = async (e)=>{
    e.preventDefault()
    try{
      const payload = { name:dishForm.name, featured:Boolean(dishForm.featured), ingredients: (dishForm.ingredient_ids||[]).map(x=> Number(x)) }
      const resp = await api.post('/meals/api/create-chef-dish/', payload)
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: (resp?.data?.message || 'Dish created successfully'), tone:'success' } })) }catch{}
      setDishForm({ name:'', featured:false, ingredient_ids:[] }); loadDishes()
    }catch(e){ console.error('createDish failed', e); }
  }

  const deleteDish = async (id)=>{ try{ await api.delete(`/meals/api/dishes/${id}/delete/`); loadDishes() }catch{} }

  const createMeal = async (e)=>{
    e.preventDefault()
    try{
      const payload = { ...mealForm, price: Number(mealForm.price||0), start_date: mealForm.start_date || todayISO, dishes: (mealForm.dishes||[]).map(x=> Number(x)) }
      const resp = await api.post('/meals/api/chef/meals/', payload)
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: (resp?.data?.message || 'Meal created successfully'), tone:'success' } })) }catch{}
      setMealForm({ name:'', description:'', meal_type:'Dinner', price:'', start_date:'', dishes:[], dietary_preferences:[] })
      loadMeals()
    }catch(e){ console.error('createMeal failed', e); }
  }

  const deleteMeal = async (id)=>{ try{ await api.delete(`/meals/api/chef/meals/${id}/`); loadMeals() }catch{} }

  const createEvent = async (e)=>{
    e.preventDefault()
    try{
      const cutoff = `${eventForm.order_cutoff_date||eventForm.event_date} ${eventForm.order_cutoff_time}`
      const payload = {
        meal: eventForm.meal ? Number(eventForm.meal) : null,
        event_date: eventForm.event_date,
        event_time: eventForm.event_time,
        order_cutoff_time: cutoff,
        base_price: Number(eventForm.base_price||0),
        min_price: Number(eventForm.min_price||0),
        max_orders: Number(eventForm.max_orders||0),
        min_orders: Number(eventForm.min_orders||0),
        description: eventForm.description,
        special_instructions: eventForm.special_instructions
      }
      console.log('[ChefDashboard] Creating event', payload)
      const resp = await api.post('/meals/api/chef-meal-events/', payload)
      console.log('[ChefDashboard] Event created', { id: resp?.data?.id })
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: (resp?.data?.message || 'Event created successfully'), tone:'success' } })) }catch{}
      setEventForm({ meal:null, event_date:'', event_time:'18:00', order_cutoff_date:'', order_cutoff_time:'12:00', base_price:'', min_price:'', max_orders:10, min_orders:1, description:'', special_instructions:'' })
      loadEvents()
    }catch(e){
      console.error('createEvent failed', e)
      try{
        const { buildErrorMessage } = await import('../api')
        const msg = buildErrorMessage(e?.response?.data, 'Failed to create event', e?.response?.status)
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
      }catch{}
    }
  }

  const toServiceTypeLabel = (value)=>{
    const found = SERVICE_TYPES.find(t => t.value === value)
    return found ? found.label : (value || '')
  }

  function pickFirst(obj, keys){
    if (!obj || !Array.isArray(keys)) return null
    for (const key of keys){
      if (key == null) continue
      if (Object.prototype.hasOwnProperty.call(obj, key) && obj[key]) return obj[key]
    }
    return null
  }

  const submitServiceOrder = async (e)=>{
    e.preventDefault()
    if (serviceOrderSaving) return
    setServiceOrderSaving(true)
    setServiceOrderErrors(null)
    const toNumber = (val)=>{
      if (val === '' || val == null) return null
      const num = Number(val)
      return Number.isFinite(num) ? num : null
    }
    const payload = {
      offering_id: serviceOrderForm.offeringId ? Number(serviceOrderForm.offeringId) : null,
      household_size: toNumber(serviceOrderForm.household_size),
      tier_id: serviceOrderForm.tier_id ? Number(serviceOrderForm.tier_id) : undefined,
      service_date: serviceOrderForm.service_date || null,
      service_start_time: serviceOrderForm.service_start_time || null,
      duration_minutes: toNumber(serviceOrderForm.duration_minutes),
      address_id: toNumber(serviceOrderForm.address_id),
      special_requests: serviceOrderForm.special_requests || ''
    }
    if (serviceOrderForm.schedule_preferences){
      try{
        payload.schedule_preferences = JSON.parse(serviceOrderForm.schedule_preferences)
      }catch{
        setServiceOrderErrors({ schedule_preferences: 'Invalid JSON' })
        setServiceOrderSaving(false)
        return
      }
    }
    if (!payload.offering_id){
      setServiceOrderErrors({ offering_id: 'Select an offering' })
      setServiceOrderSaving(false)
      return
    }
    if (!payload.household_size){
      setServiceOrderErrors({ household_size: 'Enter household size' })
      setServiceOrderSaving(false)
      return
    }
    if (payload.tier_id == null) delete payload.tier_id
    if (!payload.service_date) delete payload.service_date
    if (!payload.service_start_time) delete payload.service_start_time
    if (payload.duration_minutes == null) delete payload.duration_minutes
    if (payload.address_id == null) delete payload.address_id
    if (!payload.special_requests) delete payload.special_requests
    if (payload.schedule_preferences == null) delete payload.schedule_preferences
    try{
      const resp = await api.post(`${SERVICES_ROOT}/orders/`, payload)
      setServiceOrder(resp?.data || null)
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Service order created', tone:'success' } })) }catch{}
    }catch(err){
      const data = err?.response?.data || null
      setServiceOrderErrors(data || { detail:'Unable to create order' })
    } finally {
      setServiceOrderSaving(false)
    }
  }

  const refreshServiceOrder = async ()=>{
    if (!serviceOrder) return
    const id = serviceOrder.id || serviceOrder.order_id
    if (!id){ setServiceOrderErrors({ detail:'Order id missing' }); return }
    setServiceOrderLoading(true)
    setServiceOrderErrors(null)
    try{
      const resp = await api.get(`${SERVICES_ROOT}/orders/${id}/`)
      setServiceOrder(resp?.data || null)
    }catch(err){
      const data = err?.response?.data || null
      setServiceOrderErrors(data || { detail:'Unable to load order' })
    } finally {
      setServiceOrderLoading(false)
    }
  }

  const startServiceCheckout = async ()=>{
    if (!serviceOrder) return
    const id = serviceOrder.id || serviceOrder.order_id
    if (!id){ setServiceOrderErrors({ detail:'Order id missing' }); return }
    setServiceCheckoutBusy(true)
    setServiceOrderErrors(null)
    try{
      const resp = await api.post(`${SERVICES_ROOT}/orders/${id}/checkout`, {})
      const directUrl = pickFirst(resp?.data || {}, ['session_url','checkout_url','stripe_session_url'])
      if (directUrl){ window.location.href = directUrl; return }
      setServiceOrderErrors(resp?.data || { detail:'No checkout URL returned' })
    }catch(err){
      const data = err?.response?.data || null
      setServiceOrderErrors(data || { detail:'Unable to start checkout' })
    } finally {
      setServiceCheckoutBusy(false)
    }
  }

  const cancelServiceOrder = async ()=>{
    if (!serviceOrder) return
    const id = serviceOrder.id || serviceOrder.order_id
    if (!id){ setServiceOrderErrors({ detail:'Order id missing' }); return }
    setServiceCancelBusy(true)
    setServiceOrderErrors(null)
    try{
      await api.post(`${SERVICES_ROOT}/orders/${id}/cancel`, {})
      await refreshServiceOrder()
    }catch(err){
      const data = err?.response?.data || null
      setServiceOrderErrors(data || { detail:'Unable to cancel order' })
    } finally {
      setServiceCancelBusy(false)
    }
  }

  const resetServiceForm = ()=>{
    setServiceForm(()=>({ ...INITIAL_SERVICE_FORM }))
    setServiceErrors(null)
  }

  const editServiceOffering = (offering)=>{
    if (!offering) return
    setServiceForm({
      id: offering.id || null,
      service_type: offering.service_type || 'home_chef',
      title: offering.title || '',
      description: offering.description || '',
      default_duration_minutes: offering.default_duration_minutes != null ? String(offering.default_duration_minutes) : '',
      max_travel_miles: offering.max_travel_miles != null ? String(offering.max_travel_miles) : '',
      notes: offering.notes || ''
    })
    setServiceErrors(null)
  }

  const submitServiceOffering = async (e)=>{
    e.preventDefault()
    if (serviceSaving) return
    setServiceSaving(true)
    setServiceErrors(null)
    const toNumber = (val)=>{
      if (val === '' || val == null) return null
      const num = Number(val)
      return Number.isFinite(num) ? num : null
    }
    const payload = {
      service_type: serviceForm.service_type || 'home_chef',
      title: serviceForm.title || '',
      description: serviceForm.description || '',
      default_duration_minutes: toNumber(serviceForm.default_duration_minutes),
      max_travel_miles: toNumber(serviceForm.max_travel_miles),
      notes: serviceForm.notes || ''
    }
    try{
      if (serviceForm.id){
        await api.patch(`${SERVICES_ROOT}/offerings/${serviceForm.id}/`, payload)
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Service offering updated', tone:'success' } })) }catch{}
      }else{
        await api.post(`${SERVICES_ROOT}/offerings/`, payload)
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Service offering created', tone:'success' } })) }catch{}
      }
      resetServiceForm()
      await loadServiceOfferings()
    }catch(err){
      const data = err?.response?.data || null
      setServiceErrors(data || { detail:'Unable to save offering' })
    } finally {
      setServiceSaving(false)
    }
  }

  const resetTierForm = ()=>{
    setTierForm(()=>({ ...INITIAL_TIER_FORM }))
    setTierErrors(null)
  }

  const startTierForm = (offering, tier = null)=>{
    if (!offering) return
    if (tier){
      setTierForm({
        id: tier.id || null,
        offeringId: offering.id || null,
        household_min: tier.household_min != null ? String(tier.household_min) : '',
        household_max: tier.household_max != null ? String(tier.household_max) : '',
        currency: tier.currency || 'usd',
        price: tier.desired_unit_amount_cents != null ? String((Number(tier.desired_unit_amount_cents)||0)/100) : '',
        is_recurring: Boolean(tier.is_recurring),
        recurrence_interval: tier.recurrence_interval || 'week',
        active: Boolean(tier.active),
        display_label: tier.display_label || ''
      })
    } else {
      setTierForm({ ...INITIAL_TIER_FORM, offeringId: offering.id || null })
    }
    setTierErrors(null)
  }

  const submitTierForm = async (e)=>{
    e.preventDefault()
    if (tierSaving || !tierForm.offeringId) return
    setTierSaving(true)
    setTierErrors(null)
    const toNumber = (val)=>{
      if (val === '' || val == null) return null
      const num = Number(val)
      return Number.isFinite(num) ? num : null
    }
    const parsedPrice = tierForm.price === '' || tierForm.price == null ? null : Number(tierForm.price)
    const priceCents = parsedPrice == null ? null : (Number.isFinite(parsedPrice) ? Math.round(parsedPrice*100) : null)
    const payload = {
      household_min: toNumber(tierForm.household_min),
      household_max: toNumber(tierForm.household_max),
      currency: tierForm.currency || 'usd',
      desired_unit_amount_cents: priceCents,
      is_recurring: Boolean(tierForm.is_recurring),
      recurrence_interval: tierForm.is_recurring ? (tierForm.recurrence_interval || 'week') : null,
      active: Boolean(tierForm.active),
      display_label: tierForm.display_label || ''
    }
    try{
      if (tierForm.id){
        await api.patch(`${SERVICES_ROOT}/tiers/${tierForm.id}/`, payload)
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Tier updated', tone:'success' } })) }catch{}
      } else {
        await api.post(`${SERVICES_ROOT}/offerings/${tierForm.offeringId}/tiers/`, payload)
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Tier created', tone:'success' } })) }catch{}
      }
      resetTierForm()
      await loadServiceOfferings()
    }catch(err){
      const data = err?.response?.data || null
      setTierErrors(data || { detail:'Unable to save tier' })
    } finally {
      setTierSaving(false)
    }
  }

  const Seg = ({ value, label })=> (
    <button className={`seg ${tab===value?'active':''}`} onClick={()=> setTab(value)}>{label}</button>
  )

  return (
    <div>
      <h2>Chef Dashboard</h2>
      {notice && <div className="card" style={{borderColor:'#f0d000'}}>{notice}</div>}

      {/* Payouts status banner (compact when active) */}
      {payouts.loading ? (
        <div className="card">
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:'.75rem'}}>
            <div>
              <h3 style={{margin:'0 0 .25rem 0'}}>Payouts</h3>
              <div className="muted">Checking Stripe status…</div>
            </div>
            <button className="btn btn-outline" disabled={onboardingBusy} onClick={loadStripeStatus}>Refresh</button>
          </div>
        </div>
      ) : payouts.is_active ? (
        <div className="card" style={{padding:'.5rem .75rem'}}>
          <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'.75rem'}}>
            <span className="chip" style={{background:'var(--gradient-brand)', color:'#fff'}}>Stripe payouts active</span>
            <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={loadStripeStatus}>Refresh</button>
          </div>
        </div>
      ) : (
        <div className="card" style={{borderColor:'#f0a000', background:'rgba(240,160,0,.05)'}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:'.75rem'}}>
            <div>
              <h3 style={{margin:'0 0 .25rem 0'}}>Payouts</h3>
              <div className="muted" style={{marginBottom:'.35rem'}}>Action needed to enable payouts. Set up or continue onboarding with Stripe.</div>
              {payouts?.disabled_reason && <div className="muted" style={{marginBottom:'.35rem'}}>Reason: {payouts.disabled_reason}</div>}
            </div>
            <div style={{display:'flex', flexWrap:'wrap', gap:'.5rem'}}>
              <button className="btn btn-primary" disabled={onboardingBusy} onClick={startOrContinueOnboarding}>{onboardingBusy?'Opening…':(payouts.has_account?'Continue onboarding':'Set up payouts')}</button>
              <button className="btn btn-outline" disabled={onboardingBusy} onClick={regenerateOnboarding}>Regenerate link</button>
              <button className="btn btn-outline" disabled={onboardingBusy} onClick={loadStripeStatus}>Refresh status</button>
              {payouts.disabled_reason && (
                <button className="btn btn-outline" disabled={onboardingBusy} onClick={fixRestrictedAccount}>Fix account</button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="seg-control seg-scroll" style={{margin:'0 0 1rem 0'}} role="tablist" aria-label="Chef sections">
        <button className={`seg ${tab==='profile'?'active':''}`} onClick={()=> setTab('profile')}>Profile</button>
        <button className={`seg ${tab==='photos'?'active':''}`} onClick={()=> setTab('photos')}>Photos</button>
        <Seg value="dashboard" label="Dashboard" />
        <Seg value="ingredients" label="Ingredients" />
        <Seg value="dishes" label="Dishes" />
        <Seg value="meals" label="Meals" />
        <Seg value="services" label="Services" />
        <Seg value="events" label="Events" />
        <Seg value="orders" label="Orders" />
      </div>

      {tab==='profile' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Chef profile</h3>
            {!profileInit && <div className="muted" style={{marginBottom:'.35rem'}}>Loading…</div>}
            {chef?.profile_pic_url && (
              <div style={{marginBottom:'.5rem'}}>
                <img src={chef.profile_pic_url} alt="Profile" style={{height:72, width:72, objectFit:'cover', borderRadius:'999px', border:'1px solid var(--border)'}} />
              </div>
            )}
            <div className="label">Experience</div>
            <textarea className="textarea" rows={3} value={profileForm.experience} onChange={e=> setProfileForm(f=>({ ...f, experience:e.target.value }))} placeholder="Share your culinary experience…" />
            <div className="label">Bio</div>
            <textarea className="textarea" rows={3} value={profileForm.bio} onChange={e=> setProfileForm(f=>({ ...f, bio:e.target.value }))} placeholder="Tell customers about your style and specialties…" />
            <div className="label">Profile picture</div>
            <FileSelect label="Choose file" accept="image/*" onChange={(f)=> setProfileForm(p=>({ ...p, profile_pic: f }))} />
            {!profileForm.profile_pic && chef?.profile_pic_url && (
              <div className="muted" style={{marginTop:'.25rem'}}>Current: {(()=>{ try{ const u=new URL(chef.profile_pic_url); return decodeURIComponent(u.pathname.split('/').pop()||''); }catch{ const parts=String(chef.profile_pic_url).split('/'); return decodeURIComponent(parts[parts.length-1]||''); } })()}</div>
            )}
            <div className="label" style={{marginTop:'.6rem'}}>Banner image</div>
            <FileSelect label="Choose file" accept="image/*" onChange={(f)=> setProfileForm(p=>({ ...p, banner_image: f }))} />
            {!profileForm.banner_image && chef?.banner_url && (
              <div className="muted" style={{marginTop:'.25rem'}}>Current: {(()=>{ try{ const u=new URL(chef.banner_url); return decodeURIComponent(u.pathname.split('/').pop()||''); }catch{ const parts=String(chef.banner_url).split('/'); return decodeURIComponent(parts[parts.length-1]||''); } })()}</div>
            )}
            {bannerUpdating && (
              <div className="updating-banner" style={{marginTop:'.4rem'}}>
                <span className="spinner" aria-hidden /> Uploading banner…
              </div>
            )}
            {bannerJustUpdated && (
              <div style={{marginTop:'.4rem'}}>
                <span className="updated-chip">Banner updated</span>
              </div>
            )}
            <div style={{marginTop:'.6rem'}}>
              <button className="btn btn-primary" disabled={profileSaving} onClick={async ()=>{
                setProfileSaving(true)
                try{
                  const hasBanner = Boolean(profileForm.banner_image)
                  if (profileForm.profile_pic || hasBanner){
                    if (hasBanner) setBannerUpdating(true)
                    const fd = new FormData(); fd.append('experience', profileForm.experience||''); fd.append('bio', profileForm.bio||''); if (profileForm.profile_pic) fd.append('profile_pic', profileForm.profile_pic); if (profileForm.banner_image) fd.append('banner_image', profileForm.banner_image)
                    await api.patch('/chefs/api/me/chef/profile/update/', fd, { headers: { 'Content-Type':'multipart/form-data' } })
                  } else {
                    await api.patch('/chefs/api/me/chef/profile/update/', { experience: profileForm.experience, bio: profileForm.bio })
                  }
                  await loadChefProfile()
                  if (hasBanner){
                    setBannerJustUpdated(true)
                    try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text:'Banner updated', tone:'success' } })) }catch{}
                    setTimeout(()=> setBannerJustUpdated(false), 2200)
                  }
                }catch(e){ console.error('update profile failed', e) }
                finally {
                  setProfileSaving(false)
                  if (bannerUpdating) setBannerUpdating(false)
                  setProfileForm(p=>({ ...p, banner_image: null }))
                }
              }}>{profileSaving?'Saving…':'Save changes'}</button>
            </div>
          </div>
          <div className="card">
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
              <h3 style={{margin:0}}>Public preview</h3>
              {chef?.user?.username && (
                <Link className="btn btn-outline" to={`/c/${encodeURIComponent(chef.user.username)}`} target="_blank" rel="noreferrer">View public profile ↗</Link>
              )}
            </div>
            {chef ? (
              <div className="page-public-chef" style={{marginTop:'.5rem'}}>
                {/* Banner */}
                {(()=>{
                  const banner = bannerPreview || chef.banner_url
                  if (!banner) return null
                  return (
                    <div className={`cover has-bg`} style={{ backgroundImage:`linear-gradient(180deg, rgba(0,0,0,.35), rgba(0,0,0,.35)), url(${banner})` }}>
                      <div className="cover-inner">
                        <div className="cover-center">
                          <div className="eyebrow inv">Chef Profile</div>
                          <h1 className="title inv">{chef?.user?.username || 'Chef'}</h1>
                          {renderAreas(chef.serving_postalcodes) && (
                            <div className="loc-chip inv"><span>Serving <strong>{renderAreas(chef.serving_postalcodes)}</strong></span></div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })()}
                {/* Identity row */}
                <div className="profile-card card" style={{marginTop: bannerPreview||chef.banner_url?'-20px':'0'}}>
                  <div className="profile-card-inner">
                    <div className="avatar-wrap">
                      { (profilePicPreview || chef.profile_pic_url) && (
                        <img className="avatar-xl" src={profilePicPreview || chef.profile_pic_url} alt="Profile" />
                      )}
                    </div>
                    <div className="profile-main">
                      <h2 style={{margin:'0 0 .25rem 0'}}>{chef?.user?.username || 'Chef'}</h2>
                      {chef?.review_summary && <div className="muted" style={{marginBottom:'.35rem'}}>{chef.review_summary}</div>}
                    </div>
                  </div>
                </div>
                {/* Experience / About */}
                {(profileForm.experience || profileForm.bio || chef.experience || chef.bio) && (
                  <div className="grid grid-2 section">
                    <div className="card">
                      <h3>Experience</h3>
                      <div>{profileForm.experience || chef.experience || '—'}</div>
                    </div>
                    <div className="card">
                      <h3>About</h3>
                      <div>{profileForm.bio || chef.bio || '—'}</div>
                    </div>
                  </div>
                )}
                {/* Gallery thumbnails */}
                {Array.isArray(chef.photos) && chef.photos.length>0 && (
                  <div className="section">
                    <h3 className="sig-title" style={{textAlign:'left'}}>Gallery</h3>
                    <div className="thumb-grid">
                      {chef.photos.slice(0,6).map(p => (
                        <div key={p.id} className="thumb-card"><div className="thumb-img-wrap"><img src={p.image_url} alt={p.title||'Photo'} /></div></div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (<div className="muted">No profile loaded.</div>)}
          </div>
        </div>
      )}

      {tab==='photos' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Upload photo</h3>
            <div className="label">Image</div>
            <FileSelect label="Choose file" accept="image/jpeg,image/png,image/webp" onChange={(f)=> setPhotoForm(p=>({ ...p, image: f }))} />
            <div className="label">Title</div>
            <input className="input" value={photoForm.title} onChange={e=> setPhotoForm(f=>({ ...f, title:e.target.value }))} />
            <div className="label">Caption</div>
            <input className="input" value={photoForm.caption} onChange={e=> setPhotoForm(f=>({ ...f, caption:e.target.value }))} />
            <div style={{marginTop:'.35rem'}}>
              <label style={{display:'inline-flex', alignItems:'center', gap:'.35rem'}}>
                <input type="checkbox" checked={photoForm.is_featured} onChange={e=> setPhotoForm(f=>({ ...f, is_featured:e.target.checked }))} />
                <span>Featured</span>
              </label>
            </div>
            <div style={{marginTop:'.6rem'}}>
              <button className="btn btn-primary" disabled={photoUploading || !photoForm.image} onClick={async ()=>{
                setPhotoUploading(true)
                try{
                  const f = photoForm.image
                  const mime = (f && f.type) ? f.type.toLowerCase() : ''
                  const name = (f && f.name) ? f.name.toLowerCase() : ''
                  const isHeic = mime.includes('heic') || mime.includes('heif') || name.endsWith('.heic') || name.endsWith('.heif')
                  if (isHeic){
                    try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'HEIC images are not supported. Please upload JPG, PNG, or WEBP.', tone:'error' } })) }catch{}
                    setPhotoUploading(false)
                    return
                  }
                  const fd = new FormData(); fd.append('image', f); if (photoForm.title) fd.append('title', photoForm.title); if (photoForm.caption) fd.append('caption', photoForm.caption); if (photoForm.is_featured) fd.append('is_featured','true')
                  // Let axios set the multipart boundary automatically
                  await api.post('/chefs/api/me/chef/photos/', fd)
                  setPhotoForm({ image:null, title:'', caption:'', is_featured:false })
                  await loadChefProfile()
                  try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Photo uploaded', tone:'success' } })) }catch{}
                }catch(e){
                  // Build a richer message (HTML safe) using the global helper
                  try{
                    const { buildErrorMessage } = await import('../api')
                    const msg = buildErrorMessage(e?.response?.data, 'Failed to upload photo', e?.response?.status)
                    window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
                  }catch{
                    const msg = e?.response?.data?.error || e?.response?.data?.detail || 'Failed to upload photo'
                    window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
                  }
                } finally { setPhotoUploading(false) }
              }}>{photoUploading?'Uploading…':'Upload'}</button>
            </div>
          </div>
          <div className="card">
            <h3>Your gallery</h3>
            {!chef?.photos || chef.photos.length===0 ? <div className="muted">No photos yet.</div> : (
              <div className="thumb-grid">
                {chef.photos.map(p => (
                  <div key={p.id} className="card thumb-card" style={{padding:'.5rem'}}>
                    <div className="thumb-img-wrap"><img src={p.image_url} alt={p.title||'Photo'} /></div>
                    <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:'.35rem'}}>
                      <div style={{fontWeight:700}}>{p.title || 'Untitled'}</div>
                      {p.is_featured && <span className="chip">Featured</span>}
                    </div>
                    {p.caption && <div className="muted" style={{marginTop:'.15rem'}}>{p.caption}</div>}
                   <div style={{marginTop:'.4rem'}}>
                      <button className="btn btn-outline btn-sm" onClick={async ()=>{ try{ await api.delete(`/chefs/api/me/chef/photos/${p.id}/`); await loadChefProfile() }catch(e){ console.error('delete photo failed', e) } }}>Delete</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab==='dashboard' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Quick create meal</h3>
            <form onSubmit={createMeal}>
              <div className="label">Name</div>
              <input className="input" value={mealForm.name} onChange={e=> setMealForm(f=>({ ...f, name:e.target.value }))} required />
              <div className="label">Description</div>
              <textarea className="textarea" value={mealForm.description} onChange={e=> setMealForm(f=>({ ...f, description:e.target.value }))} required />
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                <div>
                  <div className="label">Meal type</div>
                  <select className="select" value={mealForm.meal_type} onChange={e=> setMealForm(f=>({ ...f, meal_type:e.target.value }))}>
                    {['Breakfast','Lunch','Dinner'].map(x=> <option key={x} value={x}>{x}</option>)}
                  </select>
                </div>
                <div>
                  <div className="label">Price (USD)</div>
                  <input className="input" type="number" min="1" step="0.5" value={mealForm.price} onChange={e=> setMealForm(f=>({ ...f, price:e.target.value }))} required />
                </div>
              </div>
              <div className="label" style={{marginTop:'.35rem'}}>Dishes</div>
              <select
                className="select"
                multiple
                value={mealForm.dishes}
                onChange={e=> setMealForm(f=>({ ...f, dishes: Array.from(e.target.selectedOptions).map(o=> o.value) }))}
                style={{minHeight:120}}
              >
                {dishes.map(d => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
              </select>
              <div style={{marginTop:'.6rem'}}>
                {!payouts.is_active && <div className="muted" style={{marginBottom:'.25rem'}}>Complete payouts setup to create meals.</div>}
                <button className="btn btn-primary" disabled={!payouts.is_active || !mealForm.name || !mealForm.description || !mealForm.price || (mealForm.dishes||[]).length===0}>Create</button>
              </div>
            </form>
          </div>
          <div className="card">
            <h3>Upcoming events</h3>
            <div style={{maxHeight: 260, overflowY:'auto'}}>
              {upcomingEvents.length===0 ? <div className="muted">No upcoming events.</div> : (
                <ul>
                  {upcomingEvents.map(e => (
                    <li key={e.id}><strong>{e.meal?.name || e.meal_name || 'Meal'}</strong> — {e.event_date} {e.event_time} ({e.orders_count || 0}/{e.max_orders || 0})</li>
                  ))}
                </ul>
              )}
            </div>
            {pastEvents.length>0 && (
              <div style={{marginTop:'.6rem'}}>
                <div className="label">Past</div>
                {!showPastEvents && (
                  <button className="btn btn-outline btn-sm" type="button" onClick={()=> setShowPastEvents(true)}>Show past</button>
                )}
                {showPastEvents && (
                  <>
                    <div style={{maxHeight: 220, overflowY:'auto', marginTop:'.35rem'}}>
                      <ul>
                        {pastEvents.map(e => (
                          <li key={e.id}><span className="muted">{e.event_date} {e.event_time}</span> — <strong>{e.meal?.name || e.meal_name || 'Meal'}</strong></li>
                        ))}
                      </ul>
                    </div>
                    <div style={{marginTop:'.25rem'}}>
                      <button className="btn btn-outline btn-sm" type="button" onClick={()=> setShowPastEvents(false)}>Hide past</button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {tab==='ingredients' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Create ingredient</h3>
            <form onSubmit={createIngredient}>
              <div className="label">Name</div>
              <input className="input" value={ingForm.name} onChange={e=> setIngForm(f=>({ ...f, name:e.target.value }))} required />
              {duplicateIngredient && <div className="muted" style={{marginTop:'.25rem'}}>Ingredient already exists.</div>}
              <div className="grid" style={{gridTemplateColumns:'repeat(4, 1fr)', gap:'.5rem'}}>
                {['calories','fat','carbohydrates','protein'].map(k => (
                  <div key={k}>
                    <div className="label" style={{textTransform:'capitalize'}}>{k.replace('_',' ')}</div>
                    <input className="input" type="number" step="0.1" value={ingForm[k]} onChange={e=> setIngForm(f=>({ ...f, [k]: e.target.value }))} />
                  </div>
                ))}
              </div>
              {!payouts.is_active && <div className="muted" style={{marginTop:'.35rem'}}>Complete payouts setup to add ingredients.</div>}
              <div style={{marginTop:'.6rem'}}><button className="btn btn-primary" disabled={!payouts.is_active || ingLoading || duplicateIngredient}>{ingLoading?'Saving…':'Add Ingredient'}</button></div>
            </form>
          </div>
          <div className="card">
            <h3>Your ingredients</h3>
            {ingredients.length===0 ? <div className="muted">No ingredients yet.</div> : (
              <ul>
                {ingredients.map(i => (
                  <li key={i.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <span><strong>{i.name}</strong>{' '}<span className="muted">{Number(i.calories||0).toFixed(0)} cal</span></span>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteIngredient(i.id)}>Delete</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {tab==='dishes' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Create dish</h3>
            <form onSubmit={createDish}>
              <div className="label">Name</div>
              <input className="input" value={dishForm.name} onChange={e=> setDishForm(f=>({ ...f, name:e.target.value }))} required />
              <div className="label">Ingredients</div>
              <select className="select" multiple value={dishForm.ingredient_ids} onChange={e=> {
                const opts = Array.from(e.target.selectedOptions).map(o=>o.value); setDishForm(f=>({ ...f, ingredient_ids: opts }))
              }} style={{minHeight:120}}>
                {ingredients.map(i => <option key={i.id} value={String(i.id)}>{i.name}</option>)}
              </select>
              {!payouts.is_active && <div className="muted" style={{marginTop:'.35rem'}}>Complete payouts setup to create dishes.</div>}
              <div style={{marginTop:'.6rem'}}><button className="btn btn-primary" disabled={!payouts.is_active}>Create Dish</button></div>
            </form>
          </div>
          <div className="card">
            <h3>Your dishes</h3>
            {dishes.length===0 ? <div className="muted">No dishes yet.</div> : (
              <ul>
                {dishes.map(d => (
                  <li key={d.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <span><strong>{d.name}</strong>{d.ingredients && d.ingredients.length>0 && <span className="muted"> — {d.ingredients.map(x=>x.name||x).slice(0,3).join(', ')}{d.ingredients.length>3?'…':''}</span>}</span>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteDish(d.id)}>Delete</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {tab==='meals' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Create meal</h3>
            <form onSubmit={createMeal}>
              <div className="label">Name</div>
              <input className="input" value={mealForm.name} onChange={e=> setMealForm(f=>({ ...f, name:e.target.value }))} required />
              <div className="label">Description</div>
              <textarea className="textarea" value={mealForm.description} onChange={e=> setMealForm(f=>({ ...f, description:e.target.value }))} />
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                <div>
                  <div className="label">Meal type</div>
                  <select className="select" value={mealForm.meal_type} onChange={e=> setMealForm(f=>({ ...f, meal_type:e.target.value }))}>
                    {['Breakfast','Lunch','Dinner'].map(x=> <option key={x} value={x}>{x}</option>)}
                  </select>
                </div>
                <div>
                  <div className="label">Price</div>
                  <input className="input" type="number" min="1" step="0.5" value={mealForm.price} onChange={e=> setMealForm(f=>({ ...f, price:e.target.value }))} />
                </div>
              </div>
              <div className="label" style={{marginTop:'.35rem'}}>Dishes</div>
              <select className="select" multiple value={mealForm.dishes} onChange={e=> setMealForm(f=>({ ...f, dishes: Array.from(e.target.selectedOptions).map(o=>o.value) }))} style={{minHeight:120}}>
                {dishes.map(d => <option key={d.id} value={String(d.id)}>{d.name}</option>)}
              </select>
              {!payouts.is_active && <div className="muted" style={{marginTop:'.35rem'}}>Complete payouts setup to create meals.</div>}
              <div style={{marginTop:'.6rem'}}><button className="btn btn-primary" disabled={!payouts.is_active}>Create Meal</button></div>
            </form>
          </div>
          <div className="card">
            <h3>Your meals</h3>
            {meals.length===0 ? <div className="muted">No meals yet.</div> : (
              <ul>
                {meals.map(m => (
                  <li key={m.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                    <span><strong>{m.name}</strong>{m.meal_type && <span className="muted"> — {m.meal_type}</span>}</span>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteMeal(m.id)}>Delete</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {tab==='services' && (
        <div className="grid grid-2">
          <div className="card">
            <h3 style={{marginTop:0}}>{serviceForm.id ? 'Edit service offering' : 'Create service offering'}</h3>
            <form onSubmit={submitServiceOffering}>
              <div className="label">Service type</div>
              <select className="select" value={serviceForm.service_type} onChange={e=> setServiceForm(f=>({ ...f, service_type: e.target.value }))}>
                {SERVICE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <div className="label">Title</div>
              <input className="input" value={serviceForm.title} onChange={e=> setServiceForm(f=>({ ...f, title:e.target.value }))} required />
              <div className="label">Description</div>
              <textarea className="textarea" rows={3} value={serviceForm.description} onChange={e=> setServiceForm(f=>({ ...f, description:e.target.value }))} placeholder="What does this service include?" />
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                <div>
                  <div className="label">Default duration (minutes)</div>
                  <input className="input" type="number" min="30" step="15" value={serviceForm.default_duration_minutes} onChange={e=> setServiceForm(f=>({ ...f, default_duration_minutes: e.target.value }))} />
                </div>
                <div>
                  <div className="label">Max travel miles</div>
                  <input className="input" type="number" min="0" step="1" value={serviceForm.max_travel_miles} onChange={e=> setServiceForm(f=>({ ...f, max_travel_miles: e.target.value }))} />
                </div>
              </div>
              <div className="label">Notes</div>
              <textarea className="textarea" rows={2} value={serviceForm.notes} onChange={e=> setServiceForm(f=>({ ...f, notes:e.target.value }))} placeholder="Special requirements, supplies, etc." />
              {serviceErrorMessages.length>0 && (
                <div style={{marginTop:'.5rem', color:'#b00020'}}>
                  <ul style={{margin:0, paddingLeft:'1rem'}}>
                    {serviceErrorMessages.map((msg, idx)=>(<li key={idx}>{msg}</li>))}
                  </ul>
                </div>
              )}
              {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to publish services.</div>}
              <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem', flexWrap:'wrap'}}>
                <button className="btn btn-primary" disabled={serviceSaving || !payouts.is_active}>{serviceSaving ? 'Saving…' : (serviceForm.id ? 'Save changes' : 'Create offering')}</button>
                {serviceForm.id && (
                  <button type="button" className="btn btn-outline" onClick={resetServiceForm} disabled={serviceSaving}>Cancel edit</button>
                )}
              </div>
            </form>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
            <div className="card">
              <h3>Your services</h3>
              {serviceLoading ? (
                <div className="muted">Loading…</div>
              ) : serviceOfferings.length===0 ? (
                <div className="muted">No services yet.</div>
              ) : (
                <div style={{display:'flex', flexDirection:'column', gap:'.75rem'}}>
                  {serviceOfferings.map(offering => {
                    const tiers = Array.isArray(offering.tiers) ? offering.tiers : []
                    const isEditingTier = tierForm.offeringId === offering.id
                    return (
                      <div key={offering.id} className="card" style={{padding:'.75rem'}}>
                      <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.75rem', flexWrap:'wrap'}}>
                        <div>
                          <h4 style={{margin:'0 0 .25rem 0'}}>{offering.title || 'Untitled service'}</h4>
                          <div className="muted" style={{marginBottom:'.25rem'}}>{toServiceTypeLabel(offering.service_type)}</div>
                          <div className="muted" style={{fontSize:'.85rem'}}>
                            {offering.default_duration_minutes ? `${offering.default_duration_minutes} min · ` : ''}
                            {offering.max_travel_miles ? `${offering.max_travel_miles} mi radius` : 'Travel radius not set'}
                          </div>
                        </div>
                        <div style={{display:'flex', flexDirection:'column', gap:'.35rem'}}>
                          <span className="chip" style={{background: offering.active ? 'var(--gradient-brand)' : '#ddd', color: offering.active ? '#fff' : '#333'}}>{offering.active ? 'Active' : 'Inactive'}</span>
                          <button className="btn btn-outline btn-sm" type="button" onClick={()=> editServiceOffering(offering)}>Edit</button>
                        </div>
                      </div>
                      {offering.description && <div style={{marginTop:'.35rem'}}>{offering.description}</div>}
                      {offering.notes && <div className="muted" style={{marginTop:'.35rem'}}>{offering.notes}</div>}
                      <div style={{marginTop:'.75rem'}}>
                        <div className="label" style={{marginTop:0}}>Tiers</div>
                        {tiers.length===0 ? (
                          <div className="muted">No tiers yet.</div>
                        ) : (
                          <div style={{display:'flex', flexDirection:'column', gap:'.5rem'}}>
                            {tiers.map(tier => {
                              const priceDollars = tier.desired_unit_amount_cents != null ? (Number(tier.desired_unit_amount_cents)/100).toFixed(2) : '0.00'
                              const syncError = tier.price_sync_error || tier.sync_error || tier.price_sync_message || tier.last_error || ''
                              const syncAt = tier.price_synced_at ? new Date(tier.price_synced_at) : null
                              const syncText = syncAt && !Number.isNaN(syncAt.valueOf()) ? syncAt.toLocaleString() : (tier.price_synced_at || '')
                              return (
                                <div key={tier.id} className="card" style={{padding:'.5rem'}}>
                                  <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.5rem'}}>
                                    <div>
                                      <strong>{tier.display_label || `${tier.household_min || 0}${tier.household_max ? `-${tier.household_max}` : '+'} people`}</strong>
                                      <div className="muted" style={{fontSize:'.85rem'}}>
                                        ${priceDollars} {tier.currency ? tier.currency.toUpperCase() : ''}{tier.is_recurring ? ` · Recurring ${tier.recurrence_interval || ''}` : ''}
                                      </div>
                                      <div className="muted" style={{fontSize:'.8rem'}}>
                                        Range: {tier.household_min || 0}{tier.household_max ? `-${tier.household_max}` : '+'}
                                      </div>
                                      <div style={{marginTop:'.25rem'}}>
                                        <span className="chip" style={{background: tier.price_sync_status === 'success' ? 'rgba(24,180,24,.15)' : tier.price_sync_status === 'error' ? 'rgba(200,40,40,.15)' : 'rgba(60,100,200,.15)', color: tier.price_sync_status === 'success' ? '#168516' : tier.price_sync_status === 'error' ? '#a11919' : '#1b3a72'}}>{tier.price_sync_status || 'pending'}</span>
                                        {!tier.active && <span className="chip" style={{marginLeft:'.35rem'}}>Inactive</span>}
                                      </div>
                                      {syncError && <div style={{marginTop:'.25rem', color:'#a11919', fontSize:'.85rem'}}>{syncError}</div>}
                                      {syncText && <div className="muted" style={{marginTop:'.25rem', fontSize:'.75rem'}}>Last sync: {syncText}</div>}
                                    </div>
                                    <button className="btn btn-outline btn-sm" type="button" onClick={()=> startTierForm(offering, tier)}>Edit</button>
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        )}
                        <div style={{marginTop:'.5rem'}}>
                          <button className="btn btn-outline btn-sm" type="button" onClick={()=> startTierForm(offering)}>Add tier</button>
                        </div>
                      </div>
                      {isEditingTier && (
                        <form onSubmit={submitTierForm} style={{marginTop:'.75rem', padding:'.75rem', border:'1px solid var(--border)', borderRadius:'8px', background:'rgba(0,0,0,.02)'}}>
                          <h4 style={{margin:'0 0 .5rem 0'}}>{tierForm.id ? 'Edit tier' : 'Create tier'}</h4>
                          <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                            <div>
                              <div className="label">Household min</div>
                              <input className="input" type="number" min="1" step="1" value={tierForm.household_min} onChange={e=> setTierForm(f=>({ ...f, household_min: e.target.value }))} />
                            </div>
                            <div>
                              <div className="label">Household max</div>
                              <input className="input" type="number" min="1" step="1" value={tierForm.household_max} onChange={e=> setTierForm(f=>({ ...f, household_max: e.target.value }))} placeholder="Unlimited" />
                            </div>
                          </div>
                          <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                            <div>
                              <div className="label">Currency</div>
                              <input className="input" value={tierForm.currency} onChange={e=> setTierForm(f=>({ ...f, currency: e.target.value.toLowerCase() }))} />
                            </div>
                            <div>
                              <div className="label">Price</div>
                              <input className="input" type="number" min="0.5" step="0.5" value={tierForm.price} onChange={e=> setTierForm(f=>({ ...f, price: e.target.value }))} required />
                            </div>
                          </div>
                          <div style={{marginTop:'.35rem'}}>
                            <label style={{display:'inline-flex', alignItems:'center', gap:'.35rem'}}>
                              <input type="checkbox" checked={tierForm.is_recurring} onChange={e=> setTierForm(f=>({ ...f, is_recurring: e.target.checked }))} />
                              <span>Recurring</span>
                            </label>
                          </div>
                          {tierForm.is_recurring && (
                            <div style={{marginTop:'.35rem'}}>
                              <div className="label">Recurrence interval</div>
                              <select className="select" value={tierForm.recurrence_interval} onChange={e=> setTierForm(f=>({ ...f, recurrence_interval: e.target.value }))}>
                                <option value="week">Week</option>
                                <option value="month">Month</option>
                              </select>
                            </div>
                          )}
                          <div style={{marginTop:'.35rem'}}>
                            <label style={{display:'inline-flex', alignItems:'center', gap:'.35rem'}}>
                              <input type="checkbox" checked={tierForm.active} onChange={e=> setTierForm(f=>({ ...f, active: e.target.checked }))} />
                              <span>Active</span>
                            </label>
                          </div>
                          <div className="label">Display label</div>
                          <input className="input" value={tierForm.display_label} onChange={e=> setTierForm(f=>({ ...f, display_label: e.target.value }))} placeholder="Optional label shown to customers" />
                          {tierErrorMessages.length>0 && (
                            <div style={{marginTop:'.5rem', color:'#b00020'}}>
                              <ul style={{margin:0, paddingLeft:'1rem'}}>
                                {tierErrorMessages.map((msg, idx)=>(<li key={idx}>{msg}</li>))}
                              </ul>
                            </div>
                          )}
                          {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to activate tiers.</div>}
                          <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem', flexWrap:'wrap'}}>
                            <button className="btn btn-primary" disabled={tierSaving || !payouts.is_active}>{tierSaving ? 'Saving…' : (tierForm.id ? 'Save tier' : 'Create tier')}</button>
                            <button type="button" className="btn btn-outline" onClick={resetTierForm} disabled={tierSaving}>Cancel</button>
                          </div>
                        </form>
                      )}
                    </div>
                  )
                  })}
                </div>
              )}
            </div>
            <div className="card">
              <h3>Service order tester</h3>
              <form onSubmit={submitServiceOrder}>
                <div className="label">Offering</div>
                <select className="select" value={serviceOrderForm.offeringId} onChange={e=> setServiceOrderForm(f=>({ ...f, offeringId:e.target.value, tier_id:'' }))} required>
                  <option value="">Select offering…</option>
                  {serviceOfferings.map(o => <option key={o.id} value={String(o.id)}>{o.title || `Offering #${o.id}`}</option>)}
                </select>
                <div className="label">Household size</div>
                <input className="input" type="number" min="1" step="1" value={serviceOrderForm.household_size} onChange={e=> setServiceOrderForm(f=>({ ...f, household_size: e.target.value }))} required />
                <div className="label">Tier (optional)</div>
                <select className="select" value={serviceOrderForm.tier_id} onChange={e=> setServiceOrderForm(f=>({ ...f, tier_id: e.target.value }))}>
                  <option value="">Auto-select based on household size</option>
                  {(selectedServiceOffering?.tiers || []).map(t => {
                    const title = t.display_label || `Tier #${t.id}`
                    return (
                      <option key={t.id} value={String(t.id)}>{title}{t.active ? '' : ' (inactive)'}</option>
                    )
                  })}
                </select>
                <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                  <div>
                    <div className="label">Service date</div>
                    <input className="input" type="date" value={serviceOrderForm.service_date} onChange={e=> setServiceOrderForm(f=>({ ...f, service_date:e.target.value }))} />
                  </div>
                  <div>
                    <div className="label">Start time</div>
                    <input className="input" type="time" value={serviceOrderForm.service_start_time} onChange={e=> setServiceOrderForm(f=>({ ...f, service_start_time:e.target.value }))} />
                  </div>
                </div>
                <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                  <div>
                    <div className="label">Duration (minutes)</div>
                    <input className="input" type="number" min="30" step="15" value={serviceOrderForm.duration_minutes} onChange={e=> setServiceOrderForm(f=>({ ...f, duration_minutes:e.target.value }))} />
                  </div>
                  <div>
                    <div className="label">Address ID</div>
                    <input className="input" type="number" min="1" step="1" value={serviceOrderForm.address_id} onChange={e=> setServiceOrderForm(f=>({ ...f, address_id:e.target.value }))} />
                  </div>
                </div>
                <div className="label">Special requests</div>
                <textarea className="textarea" rows={2} value={serviceOrderForm.special_requests} onChange={e=> setServiceOrderForm(f=>({ ...f, special_requests:e.target.value }))} />
                <div className="label">Schedule preferences (JSON)</div>
                <textarea className="textarea" rows={2} value={serviceOrderForm.schedule_preferences} onChange={e=> setServiceOrderForm(f=>({ ...f, schedule_preferences:e.target.value }))} placeholder='e.g. {"days":["Tue"]}' />
                {serviceOrderErrorMessages.length>0 && (
                  <div style={{marginTop:'.5rem', color:'#b00020'}}>
                    <ul style={{margin:0, paddingLeft:'1rem'}}>
                      {serviceOrderErrorMessages.map((msg, idx)=>(<li key={idx}>{msg}</li>))}
                    </ul>
                  </div>
                )}
                {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup before testing service checkout.</div>}
                <div style={{marginTop:'.75rem'}}>
                  <button className="btn btn-primary" disabled={serviceOrderSaving || !payouts.is_active}>{serviceOrderSaving ? 'Creating…' : 'Create draft order'}</button>
                </div>
              </form>
              {serviceOrder && (
                <div style={{marginTop:'1rem'}}>
                  <h4 style={{margin:'0 0 .35rem 0'}}>Latest order</h4>
                  <div className="muted" style={{fontSize:'.85rem', marginBottom:'.35rem'}}>Order #{serviceOrder.id || serviceOrder.order_id}</div>
                  <div><strong>Status:</strong> {serviceOrder.status || serviceOrder.state || 'unknown'}</div>
                  <div className="muted" style={{fontSize:'.85rem', marginTop:'.25rem'}}>
                    Household size: {serviceOrder.household_size || '—'}{serviceOrder.tier_id ? ` · Tier ${serviceOrder.tier_id}` : ''}
                  </div>
                  {serviceOrderSessionId && (
                    <div style={{marginTop:'.35rem'}}><strong>Stripe session:</strong> {serviceOrderSessionId}</div>
                  )}
                  {serviceOrderCheckoutUrl && (
                    <div className="muted" style={{marginTop:'.25rem', wordBreak:'break-all'}}>Checkout URL: {serviceOrderCheckoutUrl}</div>
                  )}
                  <div style={{marginTop:'.6rem', display:'flex', gap:'.5rem', flexWrap:'wrap'}}>
                    <button className="btn btn-outline btn-sm" type="button" onClick={refreshServiceOrder} disabled={serviceOrderLoading}>{serviceOrderLoading ? 'Refreshing…' : 'Refresh status'}</button>
                    <button className="btn btn-primary btn-sm" type="button" onClick={startServiceCheckout} disabled={serviceCheckoutBusy || !payouts.is_active}>{serviceCheckoutBusy ? 'Starting…' : 'Start checkout'}</button>
                    <button className="btn btn-outline btn-sm" type="button" onClick={cancelServiceOrder} disabled={serviceCancelBusy}>{serviceCancelBusy ? 'Cancelling…' : 'Cancel order'}</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab==='events' && (
        <div className="grid grid-2">
          <div className="card">
            <h3>Create event</h3>
            <form onSubmit={createEvent}>
              <div className="label">Meal</div>
              <select className="select" value={eventForm.meal||''} onChange={e=> setEventForm(f=>({ ...f, meal: e.target.value }))}>
                <option value="">Select meal…</option>
                {meals.map(m => <option key={m.id} value={String(m.id)}>{m.name}</option>)}
              </select>
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem', marginTop:'.35rem'}}>
                <div>
                  <div className="label">Event date</div>
                  <input className="input" type="date" value={eventForm.event_date} min={todayISO} onChange={e=> setEventForm(f=>({ ...f, event_date:e.target.value, order_cutoff_date:e.target.value }))} />
                </div>
                <div>
                  <div className="label">Event time</div>
                  <input className="input" type="time" value={eventForm.event_time} onChange={e=> setEventForm(f=>({ ...f, event_time:e.target.value }))} />
                </div>
              </div>
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                <div>
                  <div className="label">Cutoff date</div>
                  <input className="input" type="date" value={eventForm.order_cutoff_date} min={todayISO} onChange={e=> setEventForm(f=>({ ...f, order_cutoff_date:e.target.value }))} />
                </div>
                <div>
                  <div className="label">Cutoff time</div>
                  <input className="input" type="time" value={eventForm.order_cutoff_time} onChange={e=> setEventForm(f=>({ ...f, order_cutoff_time:e.target.value }))} />
                </div>
              </div>
              <div className="grid" style={{gridTemplateColumns:'repeat(3, 1fr)', gap:'.5rem'}}>
                <div>
                  <div className="label">Base price</div>
                  <input className="input" type="number" step="0.5" value={eventForm.base_price} onChange={e=> setEventForm(f=>({ ...f, base_price:e.target.value }))} />
                </div>
                <div>
                  <div className="label">Min price</div>
                  <input className="input" type="number" step="0.5" value={eventForm.min_price} onChange={e=> setEventForm(f=>({ ...f, min_price:e.target.value }))} />
                </div>
                <div>
                  <div className="label">Max orders</div>
                  <input className="input" type="number" min="1" step="1" value={eventForm.max_orders} onChange={e=> setEventForm(f=>({ ...f, max_orders:e.target.value }))} />
                </div>
              </div>
              <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem'}}>
                <div>
                  <div className="label">Min orders</div>
                  <input className="input" type="number" min="1" step="1" value={eventForm.min_orders} onChange={e=> setEventForm(f=>({ ...f, min_orders:e.target.value }))} />
                </div>
                <div>
                  <div className="label">Description</div>
                  <input className="input" value={eventForm.description} onChange={e=> setEventForm(f=>({ ...f, description:e.target.value }))} />
                </div>
              </div>
              <div className="label">Special instructions (optional)</div>
              <textarea className="textarea" value={eventForm.special_instructions} onChange={e=> setEventForm(f=>({ ...f, special_instructions:e.target.value }))} />
              {!payouts.is_active && <div className="muted" style={{marginTop:'.35rem'}}>Complete payouts setup to create events.</div>}
              <div style={{marginTop:'.6rem'}}><button className="btn btn-primary" disabled={!payouts.is_active}>Create Event</button></div>
            </form>
          </div>
          <div className="card">
            <h3>Your events</h3>
            {upcomingEvents.length===0 && pastEvents.length===0 ? (
              <div className="muted">No events yet.</div>
            ) : (
              <>
                <div>
                  <div className="label" style={{marginTop:0}}>Upcoming</div>
                  {upcomingEvents.length===0 ? <div className="muted">None</div> : (
                    <ul>
                      {upcomingEvents.map(e => (
                        <li key={e.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                          <span><strong>{e.meal?.name || e.meal_name || 'Meal'}</strong> — {e.event_date} {e.event_time} ({e.orders_count || 0}/{e.max_orders || 0})</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                {pastEvents.length>0 && (
                  <div style={{marginTop:'.6rem'}}>
                    <div className="label">Past</div>
                    {!showPastEvents && (
                      <button className="btn btn-outline btn-sm" type="button" onClick={()=> setShowPastEvents(true)}>Show past</button>
                    )}
                    {showPastEvents && (
                      <>
                        <div style={{maxHeight: 320, overflowY:'auto', marginTop:'.35rem'}}>
                          <ul>
                            {pastEvents.map(e => (
                              <li key={e.id} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                                <span><span className="muted">{e.event_date} {e.event_time}</span> — <strong>{e.meal?.name || e.meal_name || 'Meal'}</strong></span>
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div style={{marginTop:'.25rem'}}>
                          <button className="btn btn-outline btn-sm" type="button" onClick={()=> setShowPastEvents(false)}>Hide past</button>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {tab==='orders' && (
        <div className="card">
          <h3>Orders</h3>
          {orders.length===0 ? <div className="muted">No orders yet.</div> : (
            <ul>
              {orders.map(o => (
                <li key={o.id || o.order_id}>
                  <strong>{o.customer_username || o.customer_name || 'Customer'}</strong> — {o.status || 'pending'} — {o.total_value_for_chef ? `$${o.total_value_for_chef}` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="card" style={{marginTop:'2.5rem', background:'var(--surface-2)'}}>
        <div style={{display:'flex', flexWrap:'wrap', gap:'1.4rem', alignItems:'flex-start'}}>
          <div style={{flex:'1 1 260px'}}>
            <h3 style={{marginTop:0}}>Need a breather?</h3>
            <p className="muted" style={{marginTop:'.35rem'}}>
              Turning on break pauses new bookings, cancels upcoming events, and issues refunds automatically.
              Use it whenever you need to step back, focus on personal matters, or simply recharge.
            </p>
            <p className="muted" style={{marginTop:'.35rem'}}>
              A rested chef creates the best experiences. Pause with confidence and come back when you’re ready—your guests will understand.
            </p>
          </div>
          <div style={{flex:'1 1 240px', maxWidth:360}}>
            <div style={{display:'flex', alignItems:'center', gap:'.6rem'}}>
              <span style={{fontWeight:700}}>Break status</span>
              <label style={{display:'inline-flex', alignItems:'center', gap:'.35rem'}}>
                <input type="checkbox" checked={isOnBreak} disabled={breakBusy} onChange={e=> toggleBreak(e.target.checked)} />
                <span>{isOnBreak ? 'On' : 'Off'}</span>
              </label>
              {breakBusy && <span className="spinner" aria-hidden />}
            </div>
            <input
              className="input"
              style={{marginTop:'.7rem'}}
              placeholder="Optional note for your guests"
              value={breakReason}
              disabled={breakBusy}
              onChange={e=> setBreakReason(e.target.value)}
            />
            <div className="muted" style={{fontSize:'.85rem', marginTop:'.45rem'}}>
              We display this note on your profile so people know when to expect you back.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
