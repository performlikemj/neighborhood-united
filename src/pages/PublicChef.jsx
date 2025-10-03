import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, buildErrorMessage } from '../api'
import { rememberServiceOrderId } from '../utils/serviceOrdersStorage.js'
import { useAuth } from '../context/AuthContext.jsx'
import { countryNameFromCode, codeFromCountryName } from '../utils/geo.js'
import MapPanel from '../components/MapPanel.jsx'
import Carousel from '../components/Carousel.jsx'
import MultiCarousel from '../components/MultiCarousel.jsx'

function renderAreas(areas){
  if (!Array.isArray(areas) || areas.length === 0) return null
  const names = areas
    .map(p => (p?.postal_code || p?.postalcode || p?.code || p?.name || ''))
    .filter(Boolean)
  if (names.length === 0) return null
  return names.join(', ')
}

function toServiceOfferings(payload){
  try{
    if (!payload) return []
    if (Array.isArray(payload)) return payload
    if (Array.isArray(payload?.results)) return payload.results
    if (Array.isArray(payload?.data?.results)) return payload.data.results
    if (Array.isArray(payload?.details?.results)) return payload.details.results
    if (Array.isArray(payload?.details)) return payload.details
    if (Array.isArray(payload?.items)) return payload.items
    return []
  }catch{
    return []
  }
}

const EMPTY_BOOKING_FORM = {
  householdSize: '',
  serviceDate: '',
  serviceStartTime: '',
  durationMinutes: '',
  specialRequests: '',
  scheduleNotes: ''
}

const HALF_HOUR_TIMES = Array.from({ length: 48 }, (_, index) => {
  const hours = String(Math.floor(index / 2)).padStart(2, '0')
  const minutes = index % 2 === 0 ? '00' : '30'
  return `${hours}:${minutes}`
})

function isHalfHourTime(value){
  if (typeof value !== 'string') return false
  return /^([01]\d|2[0-3]):(00|30)$/.test(value.trim())
}

function nextHalfHourTime(){
  const now = new Date()
  const totalMinutes = now.getHours() * 60 + now.getMinutes()
  const next = Math.ceil((totalMinutes + 1) / 30) * 30
  const wrapped = next % (24 * 60)
  const hours = Math.floor(wrapped / 60)
  const minutes = wrapped % 60
  return `${String(hours).padStart(2, '0')}:${minutes === 0 ? '00' : '30'}`
}

function formatHalfHourLabel(time){
  try{
    if (!isHalfHourTime(time)) return time
    const [h, m] = time.split(':')
    let hours = Number(h)
    const suffix = hours >= 12 ? 'PM' : 'AM'
    hours = hours % 12
    if (hours === 0) hours = 12
    return `${hours}:${m} ${suffix}`
  }catch{
    return time
  }
}

function getDefaultServiceTime(tier){
  const preferred = tier?.default_start_time || tier?.start_time || tier?.service_time
  if (typeof preferred === 'string'){
    const normalized = preferred.slice(0,5)
    if (isHalfHourTime(normalized)) return normalized
  }
  return nextHalfHourTime()
}

export default function PublicChef(){
  const { username } = useParams()
  const { user: authUser, loading: authLoading } = useAuth()
  const [loading, setLoading] = useState(true)
  const [chef, setChef] = useState(null)
  const [events, setEvents] = useState([])
  const [serviceOfferings, setServiceOfferings] = useState([])
  const [servicesLoading, setServicesLoading] = useState(false)
  const [servicesError, setServicesError] = useState(null)
  const [servicesOutOfArea, setServicesOutOfArea] = useState(false)
  const [serviceViewerLocation, setServiceViewerLocation] = useState({ postal:'', country:'' })
  const [error, setError] = useState(null)
  const [lightboxIndex, setLightboxIndex] = useState(-1)
  const [mapOpen, setMapOpen] = useState(false)
  const sentryRef = useRef(null)
  const [sticky, setSticky] = useState(false)
  const [servesMyArea, setServesMyArea] = useState(null)
  // Waitlist state
  const [waitlistCfg, setWaitlistCfg] = useState(null)
  const [waitlist, setWaitlist] = useState(null)
  const [waitlistLoading, setWaitlistLoading] = useState(false)
  const [subscribing, setSubscribing] = useState(false)
  const [unsubscribing, setUnsubscribing] = useState(false)
  const [bookingOffering, setBookingOffering] = useState(null)
  const [bookingTier, setBookingTier] = useState(null)
  const [bookingForm, setBookingForm] = useState({ ...EMPTY_BOOKING_FORM })
  const [bookingSubmitting, setBookingSubmitting] = useState(false)
  const [bookingError, setBookingError] = useState('')


  const placeholderMealImage = useMemo(()=>{
    const svg = `\n<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' viewBox='0 0 640 480'>\n  <defs>\n    <linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>\n      <stop offset='0' stop-color='#eaf5ec'/>\n      <stop offset='1' stop-color='#d9efe0'/>\n    </linearGradient>\n  </defs>\n  <rect width='640' height='480' fill='url(#g)'/>\n  <g fill='#5cb85c'>\n    <circle cx='320' cy='240' r='70' fill='none' stroke='#5cb85c' stroke-width='8'/>\n    <rect x='292' y='220' width='56' height='40' rx='8'/>\n  </g>\n  <text x='50%' y='80%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, Arial, sans-serif' font-size='28' fill='#5c6b5d'>Meal photo</text>\n</svg>`
    return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
  }, [])

  const bookingOpen = useMemo(()=> Boolean(bookingOffering && bookingTier), [bookingOffering, bookingTier])
  const bookingRecurringTier = useMemo(()=> Boolean(bookingTier?.is_recurring || bookingTier?.recurrence_interval), [bookingTier])
  const bookingRequiresDateTime = useMemo(()=>{
    if (!bookingOffering) return false
    const type = String(bookingOffering?.service_type || '').toLowerCase()
    if (type === 'home_chef') return true
    if (type === 'weekly_prep'){
      return !bookingRecurringTier
    }
    return false
  }, [bookingOffering, bookingRecurringTier])
  const bookingNeedsScheduleChoice = useMemo(()=>{
    if (!bookingOffering) return false
    const type = String(bookingOffering?.service_type || '').toLowerCase()
    return type === 'weekly_prep' && bookingRecurringTier
  }, [bookingOffering, bookingRecurringTier])

  function resetBooking(){
    setBookingOffering(null)
    setBookingTier(null)
    setBookingForm({ ...EMPTY_BOOKING_FORM })
    setBookingError('')
  }

  function closeBooking(){
    if (bookingSubmitting) return
    resetBooking()
  }

  function startServiceBooking(offering, tier){
    if (!offering || !tier) return
    if (bookingOffering?.id === offering?.id && bookingTier?.id === tier?.id){
      closeBooking()
      return
    }
    if (!authUser){
      if (typeof window !== 'undefined'){
        const next = `${window.location.pathname}${window.location.search}`
        window.location.href = `/login?next=${encodeURIComponent(next)}`
      }
      return
    }
    const min = Number(tier?.household_min)
    const max = Number(tier?.household_max)
    let defaultSize = Number.isFinite(min) && min > 0 ? min : 1
    if (Number.isFinite(max) && max > 0 && defaultSize > max) defaultSize = max
    const durationCandidate = Number(tier?.duration_minutes) > 0
      ? Number(tier.duration_minutes)
      : (Number(offering?.default_duration_minutes) > 0 ? Number(offering.default_duration_minutes) : '')
    const defaultStartTime = getDefaultServiceTime(tier)
    setBookingOffering(offering)
    setBookingTier(tier)
    setBookingForm({
      householdSize: defaultSize ? String(defaultSize) : '',
      serviceDate: '',
      serviceStartTime: defaultStartTime,
      durationMinutes: durationCandidate ? String(durationCandidate) : '',
      specialRequests: '',
      scheduleNotes: ''
    })
    setBookingError('')
  }

  function updateBookingField(field, value){
    setBookingForm(prev => ({ ...prev, [field]: value }))
  }

  async function submitBooking(e){
    if (e && typeof e.preventDefault === 'function') e.preventDefault()
    if (!bookingOffering || !bookingTier || bookingSubmitting) return
    setBookingError('')

    let householdSize = Number(bookingForm.householdSize)
    if (!Number.isFinite(householdSize)) householdSize = 0
    householdSize = Math.floor(householdSize)
    if (householdSize < 1){
      setBookingError('Enter a household size of at least 1.')
      return
    }
    const tierMin = Number(bookingTier?.household_min)
    const tierMax = Number(bookingTier?.household_max)
    if (Number.isFinite(tierMin) && householdSize < tierMin){
      setBookingError(`This tier starts at ${tierMin} people.`)
      return
    }
    if (Number.isFinite(tierMax) && tierMax > 0 && householdSize > tierMax){
      setBookingError(`This tier supports up to ${tierMax} people.`)
      return
    }

    const hasDate = Boolean(bookingForm.serviceDate)
    const hasTime = Boolean(bookingForm.serviceStartTime)
    const scheduleNotes = bookingForm.scheduleNotes.trim()

    if (hasTime && !isHalfHourTime(bookingForm.serviceStartTime)){
      setBookingError('Choose a start time on the half hour (for example, 12:00 or 12:30).')
      return
    }

    if (bookingRequiresDateTime && (!hasDate || !hasTime)){
      setBookingError('Select a service date and start time for this tier.')
      return
    }

    if (bookingNeedsScheduleChoice && !scheduleNotes && (!hasDate || !hasTime)){
      setBookingError('Add scheduling preferences or provide a date and start time.')
      return
    }

    const payload = {
      offering_id: bookingOffering.id,
      household_size: householdSize
    }
    if (bookingTier?.id != null) payload.tier_id = bookingTier.id
    if (hasDate) payload.service_date = bookingForm.serviceDate
    if (hasTime) payload.service_start_time = bookingForm.serviceStartTime
    const duration = Number(bookingForm.durationMinutes)
    if (Number.isFinite(duration) && duration > 0) payload.duration_minutes = Math.round(duration)
    const requests = bookingForm.specialRequests.trim()
    if (requests) payload.special_requests = requests
    if (scheduleNotes){
      payload.schedule_preferences = { notes: scheduleNotes }
    }

    setBookingSubmitting(true)
    try{
      const orderResp = await api.post('/services/orders/', payload)
      const orderData = orderResp?.data || {}
      const orderId = orderData?.id || orderData?.order_id || orderData?.order?.id || orderData?.data?.id
      if (!orderId){
        throw new Error('Order created but missing id from response.')
      }
      rememberServiceOrderId(orderId)
      const checkoutResp = await api.post(`/services/orders/${orderId}/checkout`, {})
      const checkoutData = checkoutResp?.data || {}
      const sessionUrl = checkoutData?.session_url || checkoutData?.url || checkoutData?.checkout_url
      if (typeof window !== 'undefined' && checkoutData?.session_id){
        try{ localStorage.setItem('lastServiceCheckoutSessionId', String(checkoutData.session_id)) }catch{}
      }
      if (typeof window !== 'undefined'){
        try{ localStorage.setItem('lastServiceOrderId', String(orderId)) }catch{}
      }
      if (sessionUrl && typeof window !== 'undefined'){
        window.location.href = sessionUrl
      } else {
        setBookingError('Order created but payment link was not returned. Visit your orders to complete payment.')
        if (typeof window !== 'undefined'){
          try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: 'Order created. Complete payment from your orders list.', tone: 'info' } })) }catch{}
        }
      }
    }catch(err){
      let message = 'Unable to start checkout. Please try again.'
      if (err?.response){
        message = buildErrorMessage(err.response.data, message, err.response.status)
      }else if (err?.message){
        message = err.message
      }
      setBookingError(message)
      if (typeof window !== 'undefined'){
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: message, tone: 'error' } })) }catch{}
      }
    }finally{
      setBookingSubmitting(false)
    }
  }

  function toEventsArray(payload){
    try{
      if (!payload) return []
      if (Array.isArray(payload)) return payload
      if (Array.isArray(payload?.results)) return payload.results
      if (Array.isArray(payload?.events)) return payload.events
      if (Array.isArray(payload?.data?.results)) return payload.data.results
      if (Array.isArray(payload?.data?.events)) return payload.data.events
      // Standardized response wrapper: { status, message, details }
      if (payload && typeof payload === 'object' && 'details' in payload){
        const d = payload.details
        if (Array.isArray(d)) return d
        if (d && typeof d === 'object'){
          if (Array.isArray(d.results)) return d.results
          if (Array.isArray(d.events)) return d.events
        }
      }
      if (Array.isArray(payload?.items)) return payload.items
      if (Array.isArray(payload?.details)) return payload.details
      return []
    }catch{ return [] }
  }

  function toEventTimestamp(ev){
    try{
      const cutoff = ev?.order_cutoff_time ? Date.parse(ev.order_cutoff_time) : null
      if (cutoff != null && !Number.isNaN(cutoff)) return cutoff
      const date = ev?.event_date || ''
      let time = ev?.event_time || '00:00'
      if (typeof time === 'string' && time.length === 5) time = time + ':00'
      const dt = Date.parse(`${date}T${time}`)
      return Number.isNaN(dt) ? 0 : dt
    }catch{ return 0 }
  }

  function isUpcomingEvent(ev){
    try{
      const status = String(ev?.status||'').toLowerCase()
      const statusOk = !status || status === 'scheduled' || status === 'open'
      const ts = toEventTimestamp(ev)
      return Boolean(statusOk && ts >= Date.now())
    }catch{ return false }
  }

  function belongsToChef(ev, profile){
    try{
      const chefId = profile?.id
      const evChefId = ev?.chef?.id || ev?.chef_id || ev?.chef?.chef_id
      if (chefId && evChefId && Number(evChefId) === Number(chefId)) return true
      const evChefUsername = ev?.chef?.user?.username || ev?.chef?.username || ev?.chef_username
      const profUsername = profile?.user?.username
      if (evChefUsername && profUsername && String(evChefUsername) === String(profUsername)) return true
    }catch{}
    return false
  }

  const title = useMemo(()=> chef?.user?.username ? `${chef.user.username} • Chef` : 'Chef', [chef])

  useEffect(()=>{
    document.title = `sautai — ${title}`
  }, [title])

  useEffect(()=>{
    try{
      const obs = new IntersectionObserver(([entry])=> setSticky(!entry.isIntersecting), { rootMargin: '-96px 0px 0px 0px' })
      const el = sentryRef.current
      if (el) obs.observe(el)
      return ()=> obs.disconnect()
    }catch{}
  }, [])

  useEffect(()=>{
    let mounted = true
    setLoading(true)
    setError(null)
    setChef(null)
    setEvents([])
    

    const fetchProfile = async ()=>{
      const numericUsername = /^\d+$/.test(username || '')
      console.log('[PublicChef] fetchProfile', username, numericUsername)
      if (!numericUsername){
        // Try preferred by-username endpoint first
        try{
          const r1 = await api.get(`/chefs/api/public/by-username/${encodeURIComponent(username)}/`, { skipUserId: true })
          if (!mounted) return
          setChef(r1.data || null)
          return r1.data
        }catch(e){ /* fallthrough */ }

        // Try lookup to ID (non-numeric usernames only)
        try{
          const r2 = await api.get(`/chefs/api/lookup/by-username/${encodeURIComponent(username)}/`, { skipUserId: true })
          const cid = r2?.data?.chef_id || r2?.data?.id
          if (cid){
            const r3 = await api.get(`/chefs/api/public/${cid}/`, { skipUserId: true })
            if (!mounted) return
            setChef(r3.data || null)
            return r3.data
          }
        }catch(e){ /* fallthrough */ }
      } else {
        // Numeric usernames map directly to chef id
        try{
          const r4 = await api.get(`/chefs/api/public/${username}/`, { skipUserId: true })
          if (!mounted) return
          setChef(r4.data || null)
          return r4.data
        }catch(e){ /* fallthrough */ }
      }

      throw new Error('Chef not found')
    }

    const fetchEvents = async (profile)=>{
      if (!profile) return
      const chefId = profile?.id
      try{
        // Prefer filtering by id; fallback to username
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { upcoming: 'true', chef_id: chefId, page_size: 50 } })
        const list = toEventsArray(r.data)
        setEvents(list)
        if (list.length > 0) return
      }catch(e){ }
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { upcoming: 'true', chef_username: username, page_size: 50 } })
        const list = toEventsArray(r.data)
        setEvents(list)
        if (list.length > 0) return
      }catch(e){ }
      // Fallbacks without upcoming flag in case backend param differs
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { chef_id: chefId, page_size: 50 } })
        const list = toEventsArray(r.data)
        setEvents(list)
        if (list.length > 0) return
      }catch(e){ }
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { chef_username: username, page_size: 50 } })
        const list = toEventsArray(r.data)
        setEvents(list)
        if (list.length > 0) return
      }catch(e){ }

      // Extra compatibility attempts for different parameter names
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { upcoming: 'true', chef: chefId, page_size: 50 } })
        const list = toEventsArray(r.data)
        if (list.length){ setEvents(list); return }
      }catch(e){ }
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { upcoming: 'true', username, page_size: 50 } })
        const list = toEventsArray(r.data)
        if (list.length){ setEvents(list); return }
      }catch(e){ }
      try{
        const r = await api.get('/meals/api/chef-meal-events/', { skipUserId: true, params: { page_size: 50 } })
        const all = toEventsArray(r.data)
        const mine = all.filter(ev => belongsToChef(ev, profile))
        const upcoming = mine.filter(isUpcomingEvent)
        const chosen = upcoming.length > 0 ? upcoming : mine
        setEvents(chosen)
      }catch(e){ }
    }

    async function fetchWaitlist(chefId){
      try{
        setWaitlistLoading(true)
        const [cfg, st] = await Promise.all([
          api.get('/chefs/api/waitlist/config/', { skipUserId: true }),
          api.get(`/chefs/api/public/${encodeURIComponent(chefId)}/waitlist/status/`, { skipUserId: true })
        ])
        setWaitlistCfg(cfg?.data || null)
        setWaitlist(st?.data || null)
      }catch(e){
        // If disabled or unavailable, keep cfg disabled and null status
        setWaitlistCfg(prev => (prev && typeof prev==='object') ? { ...prev, enabled:false } : { enabled:false })
        setWaitlist(null)
      }finally{
        setWaitlistLoading(false)
      }
    }

    ;(async ()=>{
      try{
        const profile = await fetchProfile()
        await fetchEvents(profile)
        if (profile?.id){ await fetchWaitlist(profile.id) }
        // Kick off serves-my-area check if auth already available
        if (!authLoading && authUser && profile?.id){
          try{
            const r = await api.get(`/chefs/api/public/${profile.id}/serves-my-area/`)
            setServesMyArea(Boolean(r?.data?.serves))
          }catch(e){ setServesMyArea(false) }
        }
      }catch(e){ if (mounted) setError('Chef not found or unavailable.') }
      finally{ if (mounted) setLoading(false) }
    })()

    return ()=>{ mounted = false }
  }, [username])

  const upcomingEvents = useMemo(()=>{
    const items = Array.isArray(events) ? events.slice() : []
    return items.filter(isUpcomingEvent).sort((a,b)=> toEventTimestamp(a) - toEventTimestamp(b))
  }, [events])

  const showWaitlist = useMemo(()=>{
    const enabled = Boolean(waitlistCfg?.enabled)
    const none = (waitlist?.upcoming_events_count ?? upcomingEvents.length ?? 0) === 0
    return enabled && none
  }, [waitlistCfg, waitlist, upcomingEvents])

  const servicesAvailableInArea = useMemo(()=> Array.isArray(serviceOfferings) && serviceOfferings.length > 0, [serviceOfferings])

  const servicesHasViewerLocation = useMemo(()=> Boolean(serviceViewerLocation?.postal), [serviceViewerLocation])

  const servicesChipLabel = useMemo(()=>{
    if (!servicesHasViewerLocation) return null
    if (servicesAvailableInArea) return 'Available in your area'
    if (servicesOutOfArea) return 'Outside your area'
    return 'No services posted yet'
  }, [servicesAvailableInArea, servicesHasViewerLocation, servicesOutOfArea])

  useEffect(()=>{
    let cancelled = false
    if (!chef?.id){
      setServiceOfferings([])
      setServicesOutOfArea(false)
      setServiceViewerLocation(prev => prev)
      return undefined
    }

    const loadServices = async ()=>{
      setServicesLoading(true)
      setServicesError(null)
      let viewerPostal = ''
      let viewerCountry = ''
      if (typeof window !== 'undefined'){
        try{
          const params = new URLSearchParams(window.location.search || '')
          viewerPostal = params.get('postal_code') || params.get('postal') || ''
          viewerCountry = params.get('country') || params.get('country_code') || ''
        }catch{}
      }
      const authPostal = authUser?.address?.postalcode || authUser?.postal_code || ''
      const authCountry = authUser?.address?.country || authUser?.address?.country_code || authUser?.country || ''
      if (!viewerPostal) viewerPostal = authPostal || ''
      if (!viewerCountry) viewerCountry = authCountry || ''
      const normalizedCountry = viewerCountry ? String(viewerCountry).toUpperCase() : ''

      const baseParams = { chef_id: chef.id, page_size: 50 }
      const params = { ...baseParams }
      if (viewerPostal){
        params.postal_code = viewerPostal
        if (normalizedCountry) params.country = normalizedCountry
      }

      try{
        const resp = await api.get('/services/offerings/', { skipUserId: true, params })
        if (cancelled) return
        const filtered = toServiceOfferings(resp.data)
        setServiceOfferings(filtered)
        setServiceViewerLocation({ postal: viewerPostal || '', country: normalizedCountry || '' })

        if (viewerPostal){
          if (filtered.length === 0){
            try{
              const allResp = await api.get('/services/offerings/', { skipUserId: true, params: baseParams })
              const unfiltered = toServiceOfferings(allResp.data)
              if (!cancelled){
                setServicesOutOfArea(unfiltered.length > 0)
              }
            }catch{
              if (!cancelled) setServicesOutOfArea(false)
            }
          } else if (!cancelled){
            setServicesOutOfArea(false)
          }
        } else if (!cancelled){
          setServicesOutOfArea(false)
        }
      }catch(err){
        if (!cancelled){
          setServiceOfferings([])
          setServicesError('Unable to load chef services right now.')
          setServicesOutOfArea(false)
          setServiceViewerLocation({ postal: viewerPostal || '', country: normalizedCountry || '' })
        }
      }finally{
        if (!cancelled){
          setServicesLoading(false)
        }
      }
    }

    loadServices()
    return ()=>{ cancelled = true }
  }, [chef?.id, authUser])

  async function doSubscribe(){
    try{
      if (!authUser){
        const next = `${window.location.pathname}${window.location.search}`
        window.location.href = `/login?next=${encodeURIComponent(next)}`
        return
      }
      if (!chef?.id) return
      setSubscribing(true)
      await api.post(`/chefs/api/public/${encodeURIComponent(chef.id)}/waitlist/subscribe`, {})
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text:'You’ll be notified for future openings.', tone:'success' } })) }catch{}
      // refresh status
      const st = await api.get(`/chefs/api/public/${encodeURIComponent(chef.id)}/waitlist/status/`, { skipUserId: true })
      setWaitlist(st?.data || null)
    } catch(e){
      if (e?.response?.status === 401){
        const next = `${window.location.pathname}${window.location.search}`
        window.location.href = `/login?next=${encodeURIComponent(next)}`
        return
      }
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text:'Unable to subscribe right now.', tone:'error' } })) }catch{}
    } finally { setSubscribing(false) }
  }

  async function doUnsubscribe(){
    try{
      if (!authUser){
        const next = `${window.location.pathname}${window.location.search}`
        window.location.href = `/login?next=${encodeURIComponent(next)}`
        return
      }
      if (!chef?.id) return
      setUnsubscribing(true)
      await api.delete(`/chefs/api/public/${encodeURIComponent(chef.id)}/waitlist/unsubscribe`)
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text:'You will no longer receive notifications.', tone:'success' } })) }catch{}
      const st = await api.get(`/chefs/api/public/${encodeURIComponent(chef.id)}/waitlist/status/`, { skipUserId: true })
      setWaitlist(st?.data || null)
    } catch(e){
      if (e?.response?.status === 401){
        const next = `${window.location.pathname}${window.location.search}`
        window.location.href = `/login?next=${encodeURIComponent(next)}`
        return
      }
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text:'Unable to unsubscribe right now.', tone:'error' } })) }catch{}
    } finally { setUnsubscribing(false) }
  }

  const coverImage = useMemo(()=>{
    if (!chef) return null
    if (chef.banner_url) return chef.banner_url
    if (chef.cover_image_url) return chef.cover_image_url
    const firstPhoto = Array.isArray(chef.photos) && chef.photos.length>0 ? chef.photos[0].image_url : null
    return firstPhoto || chef.profile_pic_url || null
  }, [chef])

  const areaText = useMemo(()=> renderAreas(chef?.serving_postalcodes) || null, [chef])
  const cityCountry = useMemo(()=>{
    if (!chef) return null
    const isSelf = authUser && (chef?.user?.id === authUser?.id || chef?.user?.username === authUser?.username)
    const pickStr = (...vals) => {
      for (const v of vals){ if (typeof v === 'string' && v.trim()) return v.trim() }
      return ''
    }
    const fromObj = (obj, keys)=>{
      try{
        if (!obj) return ''
        const entries = Object.entries(obj)
        for (const [k, v] of entries){
          const kl = String(k||'').toLowerCase()
          if (keys.some(s => kl.includes(s))){
            if (typeof v === 'string' && v.trim()) return v.trim()
          }
        }
      }catch{}
      return ''
    }
    const sp = Array.isArray(chef?.serving_postalcodes) ? chef.serving_postalcodes : []
    const spCity = sp.map(p=> (p?.city||'').trim()).find(Boolean) || ''
    const spCountryRaw = sp.map(p=> (p?.country?.code || p?.country?.name || p?.country || p?.country_code || '')).find(v=> String(v||'').trim()) || ''
    const rawCity = pickStr(
      chef?.city, chef?.location_city, chef?.location?.city,
      chef?.user?.city, chef?.address?.city, chef?.user?.address?.city,
      spCity,
      fromObj(chef?.location, ['city']), fromObj(chef?.address, ['city']), fromObj(chef?.user?.address, ['city']),
      isSelf ? authUser?.address?.city : ''
    )
    const rawCountry = pickStr(
      chef?.country, chef?.location_country, chef?.location?.country,
      chef?.user?.country, chef?.address?.country, chef?.user?.address?.country,
      chef?.country_code, chef?.countryCode, chef?.location?.country_code,
      chef?.address?.country_code, chef?.user?.address?.country_code,
      spCountryRaw,
      fromObj(chef?.location, ['country_code','countrycode','country']), fromObj(chef?.address, ['country_code','countrycode','country']), fromObj(chef?.user?.address, ['country_code','countrycode','country']),
      isSelf ? (authUser?.address?.country || authUser?.address?.country_code) : ''
    )
    let displayCountry = ''
    if (rawCountry){
      if (rawCountry.length === 2){
        const code = rawCountry.toUpperCase()
        displayCountry = countryNameFromCode(code) || code
      } else {
        const codeFromName = codeFromCountryName(rawCountry)
        displayCountry = countryNameFromCode((codeFromName||'').toUpperCase()) || rawCountry
      }
    }
    if (rawCity && displayCountry) return `${rawCity}, ${displayCountry}`
    return rawCity || displayCountry || null
  }, [chef, authUser])

  // Re-check serves-my-area whenever auth finishes or chef changes
  useEffect(()=>{
    if (!chef?.id) { setServesMyArea(null); return }
    if (authLoading) return
    if (!authUser) { setServesMyArea(false); return }
    (async ()=>{
      try{
        const r = await api.get(`/chefs/api/public/${chef.id}/serves-my-area/`)
        setServesMyArea(Boolean(r?.data?.serves))
      }catch(e){ setServesMyArea(false) }
    })()
  }, [authLoading, authUser?.postal_code, authUser?.address?.postalcode, authUser?.address?.country, authUser?.address?.country_code, chef?.id])

  const mapCountryCode = useMemo(()=>{
    const cand = (
      chef?.country || chef?.country_code || chef?.location?.country_code || chef?.location?.country ||
      chef?.address?.country_code || chef?.address?.country || authUser?.address?.country || ''
    )
    const raw = String(cand||'').trim()
    if (!raw) return ''
    if (raw.length === 2) return raw.toUpperCase()
    const mapped = codeFromCountryName(raw)
    return mapped || raw.toUpperCase()
  }, [chef, authUser])

  return (
    <div className="page-public-chef">
      {loading && <div className="muted">Loading…</div>}
      {!loading && error && (
        <div className="card" style={{borderColor:'#e66'}}>
          <div style={{fontWeight:700}}>Not available</div>
          <div className="muted">{error}</div>
          <div style={{marginTop:'.5rem'}}><Link className="btn btn-outline" to="/chefs">See chefs</Link></div>
        </div>
      )}
      {!loading && chef && (
        <div>
          <div ref={sentryRef} aria-hidden />
          <div className={`cover ${coverImage ? 'has-bg' : ''}`} style={coverImage ? { backgroundImage:`url(${coverImage})` } : undefined}>
            <div className="cover-inner">
              <div className="cover-center">
                <h1 className={`title ${coverImage?'inv':''}`}>{chef?.user?.username || 'Chef'}</h1>
                {(cityCountry || areaText) && (
                  <div className={`loc-chip ${coverImage?'inv':''}`} aria-label="Location">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                      <path d="M12 22s7-5.686 7-11a7 7 0 10-14 0c0 5.314 7 11 7 11z" stroke="currentColor" strokeWidth="1.6"/>
                      <circle cx="12" cy="11" r="2.6" stroke="currentColor" strokeWidth="1.6"/>
                    </svg>
                    <span>
                      {cityCountry ? <strong>{cityCountry}</strong> : null}
                      {cityCountry && areaText ? ' ' : ''}
                      {areaText ? <span className={coverImage? 'inv' : 'muted'}>(serves {areaText})</span> : null}
                    </span>
                  </div>
                )}
                <button className="btn btn-outline" onClick={()=> setMapOpen(true)}>View on Map</button>
              </div>
            </div>
          </div>

          {/* Overlapping profile card */}
          <div className="profile-card card">
            <div className="profile-card-inner">
              <div className="avatar-wrap">
                {chef.profile_pic_url && <img className="avatar-xl" src={chef.profile_pic_url} alt={chef?.user?.username||'Chef'} />}
              </div>
              <div className="profile-main">
                <h2 style={{margin:'0 0 .25rem 0'}}>{chef?.user?.username || 'Chef'}</h2>
                {chef?.review_summary && <div className="muted" style={{marginBottom:'.35rem'}}>{chef.review_summary}</div>}
                <div className="actions">
                  <a className="btn btn-primary" href="#upcoming">See upcoming meals</a>
                  <Link className="btn btn-outline" to="/meal-plans">Go to my meal plans</Link>
                  <Link className="btn btn-outline" to="/chefs">Back to chefs</Link>
                  <button className="btn btn-outline" onClick={()=>{ try{ navigator.clipboard.writeText(window.location.href); window.dispatchEvent(new CustomEvent('global-toast',{ detail:{ text:'Profile link copied', tone:'success' } })) }catch{} }}>Share</button>
                </div>
              </div>
            </div>
          </div>

          {(chef.experience || chef.bio) && (
            <div className="grid grid-2 section">
              <div className="card">
                <h3>Experience</h3>
                <div>{chef.experience || '—'}</div>
              </div>
              <div className="card">
                <h3>About</h3>
                <div>{chef.bio || '—'}</div>
              </div>
            </div>
          )}

          <div className="grid grid-2 section">
            <div className="card" id="upcoming">
              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'.5rem'}}>
                <h3 style={{margin:0}}>Upcoming meals</h3>
                <span className={`chip ${servesMyArea?'':'small'}`} style={{background: servesMyArea? 'var(--gradient-brand)' : '#fff', color: servesMyArea? '#fff' : 'var(--muted)', border: servesMyArea? '0' : '1px solid var(--border)'}}>
                  {servesMyArea ? 'Serves your area' : 'Outside your area'}
                </span>
              </div>
              {waitlistLoading ? (
                <div className="muted">Loading…</div>
              ) : (
                showWaitlist ? (
                  <div className="card" style={{background:'var(--surface-2)'}}>
                    <h4 style={{marginTop:0}}>Get notified</h4>
                    {!authUser ? (
                      <div>
                        <div className="muted" style={{marginBottom:'.5rem'}}>Sign in to get notified when this chef starts accepting orders.</div>
                        <Link className="btn btn-primary" to={`/login?next=${encodeURIComponent(window.location.pathname+window.location.search)}`}>Sign in</Link>
                      </div>
                    ) : (
                      <div>
                        {waitlist?.subscribed ? (
                          <>
                            <div className="muted" style={{marginBottom:'.5rem'}}>You’ll be notified when this chef opens orders.</div>
                            <button className="btn btn-outline" disabled={unsubscribing} onClick={doUnsubscribe}>{unsubscribing? 'Unsubscribing…' : 'Unsubscribe'}</button>
                          </>
                        ) : (
                          <>
                            <div className="muted" style={{marginBottom:'.5rem'}}>No upcoming meals yet. Get notified when this chef starts accepting orders.</div>
                            <button className="btn btn-primary" disabled={subscribing || waitlist?.can_subscribe===false} onClick={doSubscribe}>{subscribing? 'Subscribing…' : 'Notify me'}</button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  upcomingEvents.length===0 ? (
                    <div className="muted">No upcoming events posted.</div>
                  ) : (
                    <div className="grid">
                      {upcomingEvents.map(ev => (
                        <div key={ev.id} className="card meal-card" style={{padding:0, overflow:'hidden'}}>
                          <div className="meal-row-inner">
                            <div className="meal-thumb" style={{backgroundImage:`url(${placeholderMealImage})`}} aria-hidden />
                            <div className="meal-main">
                              <div style={{fontWeight:800}}>{ev.meal?.name || ev.meal_name || 'Meal'}</div>
                              <div className="muted">{ev.event_date} {ev.event_time}</div>
                            </div>
                            <div className="meal-actions">
                              <button className="btn btn-outline" onClick={()=> {
                                const mealName = ev.meal?.name || 'this meal'
                                const mealId = ev?.meal?.id || ev?.meal_id || ''
                                const q = `Can you tell me more about ${mealName}?`
                                const url = `/chat?chef=${encodeURIComponent(chef?.user?.username||'')}&topic=${encodeURIComponent(ev.meal?.name||'Meal')}&meal_id=${encodeURIComponent(mealId)}&q=${encodeURIComponent(q)}`
                                window.open(url,'_self')
                              }}>Ask about this meal</button>
                              {authUser && servesMyArea ? (
                                <button className="btn btn-primary" onClick={()=>{
                                  window.location.href = `/meal-plans?addFromChefEvent=${encodeURIComponent(ev.id)}`
                                }}>Add to my plan</button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                )
              )}
          </div>
        </div>

        <div className="section" id="services">
          <div className="card">
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', gap:'.5rem'}}>
              <h3 style={{margin:0}}>Chef services</h3>
              {servicesChipLabel && (
                <span
                  className={`chip ${servicesAvailableInArea ? '' : 'small'}`}
                  style={{
                    background: servicesAvailableInArea ? 'var(--gradient-brand)' : '#fff',
                    color: servicesAvailableInArea ? '#fff' : 'var(--muted)',
                    border: servicesAvailableInArea ? '0' : '1px solid var(--border)'
                  }}
                >
                  {servicesChipLabel}
                </span>
              )}
            </div>
            {servicesLoading ? (
              <div className="muted" style={{marginTop:'.5rem'}}>Loading services…</div>
            ) : servicesError ? (
              <div style={{marginTop:'.5rem', color:'#b00020'}}>{servicesError}</div>
            ) : servicesAvailableInArea ? (
              <div style={{display:'flex', flexDirection:'column', gap:'.75rem', marginTop:'.75rem'}}>
                {serviceOfferings.map(offering => {
                  const tierSummaries = Array.isArray(offering?.tier_summary)
                    ? offering.tier_summary.filter(summary => typeof summary === 'string' ? summary.trim() : Boolean(summary)).map(summary => typeof summary === 'string' ? summary.trim() : String(summary))
                    : []
                  const tiers = Array.isArray(offering?.tiers)
                    ? offering.tiers.filter(t => t && t.hidden !== true && t.soft_deleted !== true)
                    : []
                  return (
                    <div key={offering.id || offering.title} style={{border:'1px solid var(--border)', borderRadius:'8px', padding:'.75rem', background:'var(--surface-2)'}}>
                      <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.5rem'}}>
                        <div>
                          <div style={{fontWeight:700}}>{offering.title || 'Service offering'}</div>
                          <div className="muted" style={{fontSize:'.9rem'}}>{offering.service_type_label || offering.service_type || 'Service'}</div>
                        </div>
                        {offering.max_travel_miles ? (
                          <span className="chip small" style={{background:'#fff', border:'1px solid var(--border)', color:'var(--muted)'}}>{offering.max_travel_miles} mi max</span>
                        ) : null}
                      </div>
                      {offering.description && <div style={{marginTop:'.5rem'}}>{offering.description}</div>}
                      {tierSummaries.length>0 && (
                        <div style={{marginTop:'.5rem'}}>
                          <div className="label" style={{marginTop:0}}>Tier overview</div>
                          <ul style={{margin:'.3rem 0 0', paddingLeft:'1.1rem', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.9rem'}}>
                            {tierSummaries.map((summary, idx) => (
                              <li key={idx}>{summary}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {tiers.length>0 && (
                        <div style={{marginTop:'.75rem'}}>
                          <div className="label" style={{marginTop:0}}>Tier details</div>
                          <div style={{display:'flex', flexDirection:'column', gap:'.5rem'}}>
                            {tiers.map((tier, idx) => {
                              if (!tier) return null
                              const isActiveTier = bookingOpen && bookingOffering?.id === offering.id && bookingTier?.id === tier.id
                              const priceCents = tier.desired_unit_amount_cents ?? tier.unit_amount_cents ?? tier.price_cents
                              const price = Number.isFinite(Number(priceCents)) ? (Number(priceCents)/100).toFixed(2) : null
                              const currency = String(tier.currency || offering.currency || 'USD').toUpperCase()
                              const isRecurring = Boolean(tier.is_recurring || tier.recurrence_interval)
                              const householdMin = tier.household_min ?? tier.household_start ?? null
                              const householdMax = tier.household_max ?? tier.household_end ?? null
                              const recurrenceLabel = tier.recurrence_interval ? String(tier.recurrence_interval).replace(/_/g,' ') : ''
                              const recurrenceText = isRecurring
                                ? `Recurring service${recurrenceLabel ? ` · ${recurrenceLabel}` : ''}`
                                : 'One-time service'
                              return (
                                <div key={tier.id || `${offering.id || offering.title}-tier-${idx}`} className="card" style={{padding:'.65rem', background:'rgba(0,0,0,.03)', border:'1px solid var(--border)'}}>
                                  <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.75rem', flexWrap:'wrap'}}>
                                    <div>
                                      <div style={{fontWeight:600}}>{tier.display_label || tier.name || 'Tier'}</div>
                                      <div style={{display:'flex', gap:'.35rem', alignItems:'center', flexWrap:'wrap', marginTop:'.3rem'}}>
                                        <span
                                          className={`chip ${isRecurring ? 'tier-recurring-chip' : 'tier-once-chip'}`}
                                          style={{
                                            background: isRecurring ? 'rgba(40,180,80,.18)' : 'rgba(80,100,160,.18)',
                                            color: isRecurring ? '#0f6b2f' : '#1b3a72',
                                            fontWeight:600
                                          }}
                                        >
                                          {recurrenceText}
                                        </span>
                                      </div>
                                      <div className="muted" style={{fontSize:'.85rem'}}>
                                        {householdMin != null ? `${householdMin}` : '?'}
                                        {householdMax != null ? `-${householdMax}` : '+'} people
                                      </div>
                                      {price && (
                                        <div className="muted" style={{fontSize:'.85rem'}}>
                                          ${price} {currency}
                                        </div>
                                      )}
                                      {tier.description && <div style={{marginTop:'.35rem'}}>{tier.description}</div>}
                                    </div>
                                    <div style={{display:'flex', flexDirection:'column', gap:'.3rem'}}>
                                      <button
                                        className="btn btn-primary btn-sm"
                                        type="button"
                                        onClick={()=> startServiceBooking(offering, tier)}
                                        aria-expanded={isActiveTier}
                                      >
                                        Book this service tier
                                      </button>
                                    </div>
                                  </div>
                                  {isActiveTier && (
                                    <form onSubmit={submitBooking} style={{marginTop:'.75rem', display:'flex', flexDirection:'column', gap:'.5rem'}}>
                                      <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit, minmax(180px,1fr))', gap:'.5rem'}}>
                                        <div>
                                          <div className="label">Household size</div>
                                          <input
                                            className="input"
                                            type="number"
                                            min={Math.max(1, Number(householdMin)||1)}
                                            value={bookingForm.householdSize}
                                            onChange={e=> updateBookingField('householdSize', e.target.value)}
                                            required
                                          />
                                        </div>
                                        <div>
                                          <div className="label">Service date</div>
                                          <input
                                            className="input"
                                            type="date"
                                            value={bookingForm.serviceDate}
                                            onChange={e=> updateBookingField('serviceDate', e.target.value)}
                                            required={bookingRequiresDateTime}
                                          />
                                        </div>
                                        <div>
                                          <div className="label">Start time</div>
                                          <select
                                            className="select time-select"
                                            name="serviceStartTime"
                                            value={bookingForm.serviceStartTime || ''}
                                            onChange={e=> updateBookingField('serviceStartTime', e.target.value)}
                                            required={bookingRequiresDateTime}
                                          >
                                            {!bookingRequiresDateTime && (
                                              <option value="">No preference</option>
                                            )}
                                            {HALF_HOUR_TIMES.map(time => (
                                              <option key={time} value={time}>{formatHalfHourLabel(time)}</option>
                                            ))}
                                          </select>
                                        </div>
                                      </div>
                                      <div>
                                        <div className="label">Special requests</div>
                                        <textarea
                                          className="textarea"
                                          rows={3}
                                          value={bookingForm.specialRequests}
                                          onChange={e=> updateBookingField('specialRequests', e.target.value)}
                                          placeholder="Allergies, menu notes, access details…"
                                        />
                                      </div>
                                      <div>
                                        <div className="label">Scheduling preferences (optional)</div>
                                        <textarea
                                          className="textarea"
                                          rows={2}
                                          value={bookingForm.scheduleNotes}
                                          onChange={e=> updateBookingField('scheduleNotes', e.target.value)}
                                          placeholder="Preferred weekday or cadence for recurring services"
                                        />
                                      </div>
                                      {bookingNeedsScheduleChoice && (
                                        <div className="muted" style={{fontSize:'.85rem'}}>
                                          Add your preferred recurring cadence here, or provide a specific date and start time above.
                                        </div>
                                      )}
                                      {bookingError && (
                                        <div role="alert" style={{color:'#b00020', fontSize:'.9rem'}}>{bookingError}</div>
                                      )}
                                      <div style={{display:'flex', gap:'.5rem', flexWrap:'wrap'}}>
                                        <button className="btn btn-primary" type="submit" disabled={bookingSubmitting}>
                                          {bookingSubmitting ? 'Starting checkout…' : 'Continue to payment'}
                                        </button>
                                        <button className="btn btn-outline" type="button" onClick={closeBooking} disabled={bookingSubmitting}>
                                          Cancel
                                        </button>
                                      </div>
                                    </form>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : servicesOutOfArea ? (
              <div className="card" style={{background:'var(--surface-2)', marginTop:'.75rem'}}>
                <h4 style={{marginTop:0}}>Not in range</h4>
                <p className="muted" style={{marginBottom:'.35rem'}}>
                  This chef's services aren't available in your area yet. Try updating your location or message the chef to see if they can travel further.
                </p>
                {servicesHasViewerLocation && serviceViewerLocation.postal && (
                  <p className="muted" style={{fontSize:'.85rem', marginBottom:0}}>
                    Based on {serviceViewerLocation.postal}{serviceViewerLocation.country ? ` · ${serviceViewerLocation.country}` : ''}.
                  </p>
                )}
              </div>
            ) : servicesHasViewerLocation ? (
              <div className="muted" style={{marginTop:'.5rem'}}>This chef hasn't listed any services yet.</div>
            ) : (
              <div className="muted" style={{marginTop:'.5rem'}}>Add your location to check service availability.</div>
            )}
          </div>
        </div>

        {/* Signature dishes (multi-item carousel) */}
        <div className="section sig-section">
          <h3 className="sig-title">Signature Dishes</h3>
            {!chef.photos || chef.photos.length===0 ? (
              <div className="muted" style={{textAlign:'center'}}>No photos yet.</div>
            ) : (
              <div className="sig-carousel">
                <MultiCarousel
                  ariaLabel="Signature dishes"
                  autoPlay={true}
                  intervalMs={4200}
                  loop={true}
                  items={chef.photos.map((p, idx) => (
                    <figure
                      key={p.id || idx}
                      className="sig-tile"
                      onClick={()=> setLightboxIndex(idx)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e)=>{ if (e.key==='Enter') setLightboxIndex(idx) }}
                    >
                      <div className="sig-img">
                        <img src={p.image_url} alt={p.title||'Photo'} loading="lazy" decoding="async" />
                        {p.title && (
                          <div className="sig-overlay"><span className="title">{p.title}</span></div>
                        )}
                      </div>
                    </figure>
                  ))}
                />
              </div>
            )}
          </div>

          {lightboxIndex>=0 && (
            <div className="lightbox" role="dialog" aria-modal="true" onClick={()=> setLightboxIndex(-1)}>
              <div className="lightbox-inner" onClick={(e)=> e.stopPropagation()}>
                <img src={chef.photos[lightboxIndex]?.image_url} alt={chef.photos[lightboxIndex]?.title||'Photo'} />
                <div className="lightbox-caption">
                  <div className="title">{chef.photos[lightboxIndex]?.title || 'Untitled'}</div>
                  {chef.photos[lightboxIndex]?.caption && <div className="sub">{chef.photos[lightboxIndex].caption}</div>}
                </div>
                <button className="icon-btn close" aria-label="Close" onClick={()=> setLightboxIndex(-1)}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
                </button>
                {Array.isArray(chef.photos) && chef.photos.length>1 && (
                  <>
                    <button
                      className="prev"
                      aria-label="Previous photo"
                      onClick={(e)=>{ e.stopPropagation(); setLightboxIndex(i=> (i-1+chef.photos.length)%chef.photos.length) }}
                    >
                      ‹
                    </button>
                    <button
                      className="next"
                      aria-label="Next photo"
                      onClick={(e)=>{ e.stopPropagation(); setLightboxIndex(i=> (i+1)%chef.photos.length) }}
                    >
                      ›
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
          <MapPanel
            open={mapOpen}
            onClose={()=> setMapOpen(false)}
            countryCode={mapCountryCode}
            postalCodes={(chef?.serving_postalcodes||[]).map(p=> p?.postal_code || p?.postalcode || p?.code || p?.name || '').filter(Boolean)}
            city={chef?.city || chef?.location?.city || chef?.address?.city || ''}
          />
        </div>
      )}
    </div>
  )
}
