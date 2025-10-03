import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, buildErrorMessage } from '../api'
import { OrdersTab } from './MealPlans.jsx'
import { getStoredServiceOrderIds, rememberServiceOrderId, removeServiceOrderId, replaceServiceOrderIds, SERVICE_ORDER_STORAGE_KEY } from '../utils/serviceOrdersStorage.js'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import '../components/ConfirmDialog.css'

const SERVICE_STATUS_LABELS = {
  draft: 'Draft',
  awaiting_payment: 'Awaiting payment',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
  refunded: 'Refunded',
  completed: 'Completed'
}

const PAYABLE_STATUSES = new Set(['draft', 'awaiting_payment'])
const CONFIRMED_STATUSES = new Set(['confirmed', 'completed'])

const SERVICE_POLL_ATTEMPTS = 20
const SERVICE_POLL_DELAY_MS = 1500

function notify(text, tone = 'info'){
  try{
    window.dispatchEvent(new CustomEvent('global-toast', { detail: { text, tone } }))
  }catch{}
}

function toCurrency(amount, currency = 'USD'){
  if (amount == null) return ''
  const numeric = Number(amount)
  if (!Number.isFinite(numeric)) return String(amount)
  try{
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: String(currency || 'USD').toUpperCase(), maximumFractionDigits: 2 }).format(numeric)
  }catch{
    return `$${numeric.toFixed(2)}`
  }
}

function parseServiceDate(dateStr = '', timeStr = ''){
  if (!dateStr) return null
  try{
    let time = timeStr
    if (time && time.length === 5) time = `${time}:00`
    const iso = `${dateStr}T${time || '00:00:00'}Z`
    const dt = new Date(iso)
    if (Number.isNaN(dt.valueOf())){
      const fallback = new Date(`${dateStr}T${time || '00:00:00'}`)
      return Number.isNaN(fallback.valueOf()) ? null : fallback
    }
    return dt
  }catch{
    return null
  }
}

function formatServiceSchedule(order){
  const dt = parseServiceDate(order?.service_date, order?.service_start_time)
  if (dt){
    try{
      const dateLabel = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(dt)
      const timeLabel = order?.service_start_time ? new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(dt) : null
      return timeLabel ? `${dateLabel} · ${timeLabel}` : dateLabel
    }catch{}
  }
  if (order?.service_date){
    return order.service_start_time ? `${order.service_date} · ${order.service_start_time}` : order.service_date
  }
  const prefs = order?.schedule_preferences
  if (prefs && typeof prefs === 'object'){
    const note = prefs.notes || prefs.preferred_weekday || prefs.preferred_time
    if (note) return String(note)
  }
  return 'Schedule pending'
}

function serviceStatusLabel(status){
  return SERVICE_STATUS_LABELS[status] || (status ? status.replace(/_/g, ' ') : 'Unknown')
}

function normalizeIdentifier(value){
  if (value == null) return null
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (typeof value === 'string'){
    const trimmed = value.trim()
    if (trimmed) return trimmed
  }
  return null
}

function getChefId(order){
  if (!order || typeof order !== 'object') return null
  const candidates = [
    order.chef_id,
    order.chef,
    order.chef_user_id,
    order.chef_user,
    order.chef_details?.id,
    order.chef?.id,
    order.chef?.chef_id,
    order.chef?.user?.id
  ]
  for (const candidate of candidates){
    const normalized = normalizeIdentifier(candidate)
    if (normalized) return normalized
  }
  return null
}

function deriveChefName(order, profile){
  const nameCandidates = [
    order?.chef_name,
    order?.chef_display_name,
    order?.chef_full_name,
    order?.chef_details?.display_name,
    order?.chef_details?.name,
    order?.chef?.display_name,
    order?.chef?.name,
    order?.chef?.user?.username,
    profile?.display_name,
    profile?.name,
    profile?.public_name,
    profile?.user?.display_name,
    profile?.user?.username,
    profile?.user?.full_name,
    profile?.user?.name
  ]
  for (const candidate of nameCandidates){
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }
  if (profile?.user?.first_name || profile?.user?.last_name){
    const first = profile?.user?.first_name ? profile.user.first_name.trim() : ''
    const last = profile?.user?.last_name ? profile.user.last_name.trim() : ''
    const combined = `${first} ${last}`.trim()
    if (combined) return combined
  }
  return null
}

function getChefUsername(order, profile){
  const candidates = [
    order?.chef_username,
    order?.chef_user_username,
    order?.chef_public_username,
    order?.chef_details?.username,
    order?.chef_user?.username,
    order?.chef?.username,
    order?.chef?.user?.username,
    profile?.username,
    profile?.public_username,
    profile?.user?.username
  ]
  for (const candidate of candidates){
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  }
  return null
}

function appendChefIdParam(path, chefId){
  if (!path || !chefId) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}chef_id=${encodeURIComponent(chefId)}`
}

function getChefProfilePath(order, profile, fallbackId){
  if (!order || typeof order !== 'object') return null

  const usernameCandidates = [
    order.chef_public_username,
    order.chef_username,
    order.chef_user_username,
    order.chefUserUsername,
    order.chef_public_profile?.username,
    order.chef_profile?.username,
    order.chef_details?.username,
    order.chef_user?.username,
    order.chef?.public_username,
    order.chef?.username,
    order.chef?.user?.username,
    profile?.public_username,
    profile?.username,
    profile?.user?.username
  ]

  const slugCandidates = [
    order.chef_public_slug,
    order.chef_slug,
    order.chef?.slug,
    order.chef?.user?.slug,
    profile?.public_slug,
    profile?.slug,
    profile?.user?.slug
  ]

  const idCandidates = [
    order.chef_id,
    order.chef?.id,
    order.chef_user?.id,
    fallbackId
  ]

  const directPathCandidates = [
    order.chef_profile_path,
    order.chef_public_profile_path,
    order.chef_profile_url,
    order.chef_public_profile_url,
    order.chef_profile_link,
    order.chef_public_profile_link
  ]

  const sanitizeDirectPath = (candidate)=>{
    if (!candidate) return null
    const value = String(candidate).trim()
    if (!value) return null
    try{
      if (value.startsWith('http')){
        const url = new URL(value)
        if (url.pathname && url.pathname.startsWith('/c/')) return url.pathname
        if (url.pathname) return url.pathname
        return null
      }
    }catch{}
    if (value.startsWith('/')){
      if (value.startsWith('/c/')) return value
      if (value.length > 1) return value
    }
    return null
  }

  const directPath = directPathCandidates.map(sanitizeDirectPath).find(Boolean) || null

  const pickValue = (candidates)=>{
    for (const candidate of candidates){
      if (candidate == null) continue
      const str = typeof candidate === 'number' && Number.isFinite(candidate)
        ? String(candidate)
        : (typeof candidate === 'string' ? candidate.trim() : null)
      if (str) return str
    }
    return null
  }

  const username = pickValue(usernameCandidates)
  if (username){
    return appendChefIdParam(`/c/${encodeURIComponent(username)}`, fallbackId)
  }

  const slug = pickValue(slugCandidates)
  if (slug){
    return appendChefIdParam(`/c/${encodeURIComponent(slug)}`, fallbackId)
  }

  const identifier = pickValue(idCandidates)
  if (identifier){
    return appendChefIdParam(`/c/${encodeURIComponent(identifier)}`, fallbackId)
  }

  if (directPath){
    return appendChefIdParam(directPath, fallbackId)
  }

  return null
}

export default function CustomerOrders(){
  const [tab, setTab] = useState('services')
  const [serviceOrders, setServiceOrders] = useState([])
  const [serviceLoading, setServiceLoading] = useState(true)
  const [serviceError, setServiceError] = useState(null)
  const [verifyingServiceId, setVerifyingServiceId] = useState(null)
  const [cancellingOrder, setCancellingOrder] = useState(null)
  const [searchParams] = useSearchParams()

  const [verifyingMealOrderId, setVerifyingMealOrderId] = useState(null)
  const [chefDetails, setChefDetails] = useState({})
  const chefDetailsPending = useRef(new Set())
  const isMountedRef = useRef(true)

  useEffect(()=>{
    isMountedRef.current = true
    return ()=> { isMountedRef.current = false }
  }, [])

  const loadServiceOrders = async ()=>{
    setServiceLoading(true)
    setServiceError(null)
    try{
      let ids = getStoredServiceOrderIds()
      // Fallback: try to hydrate from lastServiceOrderId if storage is empty
      if (ids.length === 0){
        try{
          const last = localStorage.getItem('lastServiceOrderId')
          if (last){
            ids = [last]
            replaceServiceOrderIds(ids)
          }
        }catch{}
      }
      if (ids.length === 0){
        setServiceOrders([])
        return
      }
      const results = await Promise.all(ids.map(async id => {
        try{
          const resp = await api.get(`/services/orders/${id}/`)
          const order = resp?.data
          if (order && order.id != null){
            rememberServiceOrderId(order.id)
            return order
          }
        }catch(e){
          if (e?.response?.status === 404){
            removeServiceOrderId(id)
          }
        }
        return null
      }))
      const cleaned = results.filter(Boolean)
      setServiceOrders(cleaned)
    }catch{
      setServiceOrders([])
      setServiceError('Unable to load service orders right now.')
    }finally{
      setServiceLoading(false)
    }
  }

  useEffect(()=>{ loadServiceOrders() }, [])

  useEffect(()=>{
    let alive = true
    if (!Array.isArray(serviceOrders) || serviceOrders.length === 0) return ()=> { alive = false }
    const ids = Array.from(new Set(serviceOrders.map(getChefId).filter(Boolean)))
    const missing = ids.filter(id => !(id in chefDetails) && !chefDetailsPending.current.has(id))
    if (missing.length === 0) return ()=> { alive = false }
    missing.forEach(async id => {
      chefDetailsPending.current.add(id)
      try{
        const resp = await api.get(`/chefs/api/public/${encodeURIComponent(id)}/`, { skipUserId: true })
        const detail = resp?.data || null
        const safe = alive && isMountedRef.current
        if (safe){
          setChefDetails(prev => {
            if (prev[id] === detail) return prev
            return { ...prev, [id]: detail }
          })
          if (detail && detail.user && detail.user.username){
            setServiceOrders(prev => prev.map(order => {
              const currentId = getChefId(order)
              if (currentId && String(currentId) === String(id)){
                const username = String(detail.user.username || '').trim()
                if (!username) return order
                return {
                  ...order,
                  chef_username: username,
                  chef_user_username: username,
                  chef_name: username
                }
              }
              return order
            }))
          }
        }
      }catch(e){
        if (alive && isMountedRef.current){
          setChefDetails(prev => {
            if (prev[id] === null) return prev
            return { ...prev, [id]: null }
          })
        }
      }finally{
        chefDetailsPending.current.delete(id)
      }
    })
    return ()=> { alive = false }
  }, [serviceOrders, chefDetails])

  useEffect(()=>{
    const onStorage = (event)=>{
      if (event?.key === SERVICE_ORDER_STORAGE_KEY){
        loadServiceOrders()
      }
    }
    window.addEventListener('storage', onStorage)
    return ()=> window.removeEventListener('storage', onStorage)
  }, [])

  useEffect(()=>{
    try{
      const last = localStorage.getItem('lastServiceOrderId')
      if (last){
        setVerifyingServiceId(last)
        pollServiceOrderStatus(last)
      }
    }catch{}
  }, [])

  const pollServiceOrderStatus = async (orderId)=>{
    try{
      for (let attempt = 0; attempt < SERVICE_POLL_ATTEMPTS; attempt++){
        try{
          const resp = await api.get(`/services/orders/${orderId}/`)
          const order = resp?.data
          const status = String(order?.status || '').toLowerCase()
          if (CONFIRMED_STATUSES.has(status)){
            notify('Service order confirmed.', 'success')
            setVerifyingServiceId(null)
            try{ localStorage.removeItem('lastServiceOrderId') }catch{}
            rememberServiceOrderId(order?.id || orderId)
            loadServiceOrders()
            return
          }
          if (!PAYABLE_STATUSES.has(status)){
            setVerifyingServiceId(null)
            loadServiceOrders()
            return
          }
        }catch{}
        await new Promise(resolve => setTimeout(resolve, SERVICE_POLL_DELAY_MS))
      }
      notify('Payment not confirmed yet. You may need to try again.', 'error')
    }finally{
      setVerifyingServiceId(null)
    }
  }

  const startServiceCheckout = async (order)=>{
    try{
      setVerifyingServiceId(order.id)
      try{ localStorage.setItem('lastServiceOrderId', String(order.id)) }catch{}
      const resp = await api.post(`/services/orders/${order.id}/checkout`, {})
      const url = resp?.data?.session_url
      const sessionId = resp?.data?.session_id
      if (sessionId){ try{ localStorage.setItem('lastServiceCheckoutSessionId', String(sessionId)) }catch{} }
      if (url){
        window.location.href = url
        return
      }
      throw new Error('Missing session_url')
    }catch(e){
      setVerifyingServiceId(null)
      console.error('[CustomerOrders] startServiceCheckout failed', { id: order?.id, status: e?.response?.status, data: e?.response?.data, message: e?.message })
      let message = 'We couldn\'t start checkout. Please try again shortly or contact support.'
      if (e?.response){
        try{
          message = buildErrorMessage(e.response.data, message, e.response.status)
        }catch{}
      }
      notify(message, 'error')
      try{ localStorage.removeItem('lastServiceOrderId') }catch{}
    }
  }

  const cancelServiceOrder = async (order)=>{
    if (!order?.id) return
    setCancellingOrder(order)
  }

  const confirmCancel = async ()=>{
    if (!cancellingOrder?.id) return
    const orderId = cancellingOrder.id
    try{
      await api.post(`/services/orders/${orderId}/cancel`, {})
      notify('Service order cancelled.', 'success')
      removeServiceOrderId(orderId)
      setCancellingOrder(null)
      loadServiceOrders()
    }catch(e){
      console.error('[CustomerOrders] cancelServiceOrder failed', { id: orderId, status: e?.response?.status, data: e?.response?.data })
      let message = 'Unable to cancel this order right now.'
      if (e?.response){
        try{ message = buildErrorMessage(e.response.data, message, e.response.status) }catch{}
      }
      notify(message, 'error')
      setCancellingOrder(null)
    }
  }

  const cancelDialog = (
    <ConfirmDialog
      open={Boolean(cancellingOrder)}
      title="Cancel service order?"
      message="This will notify the chef and stop any pending payments for this booking."
      confirmLabel="Cancel order"
      cancelLabel="Keep order"
      onConfirm={confirmCancel}
      onCancel={()=> setCancellingOrder(null)}
    />
  )

  const serviceActionLabel = (status)=>{
    return status === 'draft' ? 'Complete checkout' : 'Pay now'
  }

  const serviceOrdersView = useMemo(()=>{
    if (serviceLoading) return <div className="card">Loading service orders…</div>
    if (serviceError) return <div className="card" style={{ borderColor:'#d9534f' }}>{serviceError} <button className="btn btn-link" onClick={()=> loadServiceOrders()}>Retry</button></div>
    if (!serviceOrders || serviceOrders.length === 0){
      return (
        <div className="card">
          <div className="muted">No service orders yet.</div>
          <button className="btn btn-link" onClick={()=> loadServiceOrders()} style={{marginTop:'.5rem'}}>Refresh</button>
        </div>
      )
    }
    return (
      <div style={{display:'flex', flexDirection:'column', gap:'.85rem'}}>
        {serviceOrders.map(order => {
          const status = String(order?.status || '').toLowerCase()
          const actionable = PAYABLE_STATUSES.has(status)
          const verifying = verifyingServiceId && String(verifyingServiceId) === String(order.id)
          const chefId = getChefId(order)
          const chefProfile = chefDetails[chefId] || null
          const chefProfilePath = getChefProfilePath(order, chefProfile, chefId)
          const chefUsername = (chefProfile && chefProfile.user && chefProfile.user.username)
            ? String(chefProfile.user.username).trim()
            : getChefUsername(order, chefProfile)
          const chefName = chefUsername || deriveChefName(order, chefProfile) || (chefId ? 'Chef' : null)
          const canLinkToProfile = Boolean(chefProfilePath)
          const chefLinkStyle = { fontSize: '.9rem', color: 'var(--primary-700)', fontWeight: 600 }
          return (
            <div key={order.id} className="card" style={{border:'1px solid var(--border)', borderRadius:'12px', padding:'0.85rem'}}>
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.75rem', flexWrap:'wrap'}}>
                <div>
                  <div style={{fontWeight:700}}>{order.offering_title || 'Service'}</div>
                  {chefName && (
                    canLinkToProfile ? (
                      <Link to={chefProfilePath} style={{ ...chefLinkStyle, textDecoration:'none' }}>
                        {chefName}
                      </Link>
                    ) : (
                      <div style={chefLinkStyle}>{chefName}</div>
                    )
                  )}
                  <div className="muted" style={{marginTop:'.35rem'}}>{formatServiceSchedule(order)}</div>
                </div>
                <span className="status-text status-text--blue">{serviceStatusLabel(status)}</span>
              </div>
              {order.special_requests && (
                <div className="muted" style={{marginTop:'.45rem', fontSize:'.85rem'}}>{order.special_requests}</div>
              )}
              <div style={{display:'flex', gap:'.5rem', alignItems:'center', flexWrap:'wrap', marginTop:'.6rem'}}>
                <span className="muted" style={{fontSize:'.85rem'}}>{toCurrency(order.total_value_for_chef, order.currency)}</span>
                {order.household_size ? <span className="muted" style={{fontSize:'.8rem'}}>Household: {order.household_size}</span> : null}
                {order.is_subscription ? <span className="muted" style={{fontSize:'.8rem'}}>Recurring billing</span> : null}
              </div>
              {actionable && (
                <div style={{marginTop:'.7rem', display:'flex', gap:'.5rem'}}>
                  <button className="btn btn-primary btn-sm" onClick={()=> startServiceCheckout(order)} disabled={verifying}>
                    {verifying ? 'Opening checkout…' : serviceActionLabel(status)}
                  </button>
                  <button className="btn btn-outline btn-sm" onClick={()=> cancelServiceOrder(order)} disabled={verifying}>Cancel order</button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }, [serviceOrders, serviceLoading, serviceError, verifyingServiceId, chefDetails])

  const pollMealOrderPayment = async (orderId, sessionId=null)=>{
    try{
      const maxAttempts = 20
      for (let i = 0; i < maxAttempts; i++){
        try{
          const params = (i === 0 && sessionId) ? { session_id: sessionId } : {}
          const resp = await api.get(`/meals/api/order-payment-status/${orderId}/`, { params })
          const payload = resp?.data || {}
          const paid = Boolean(payload?.is_paid)
          const status = String(payload?.status || '').toLowerCase()
          const sessionStatus = String(payload?.session_status || '').toLowerCase()
          if (paid || ['confirmed','completed'].includes(status)){
            notify('Payment confirmed.', 'success')
            try{
              localStorage.removeItem('lastPaymentOrderId')
              localStorage.removeItem('lastCheckoutSessionId')
            }catch{}
            setVerifyingMealOrderId(null)
            window.dispatchEvent(new CustomEvent('orders-reload'))
            return
          }
          if (sessionStatus && sessionStatus !== 'open') break
        }catch{}
        await new Promise(resolve => setTimeout(resolve, 1500))
      }
      notify('Payment not confirmed yet. You may need to try again.', 'error')
    }finally{
      setVerifyingMealOrderId(null)
    }
  }

  useEffect(()=>{
    try{
      const sid = searchParams.get('session_id')
      const paid = searchParams.get('payment') === 'success'
      if (sid || paid){
        notify('Payment completed. Updating orders…', 'success')
        try{ if (sid) localStorage.setItem('lastCheckoutSessionId', String(sid)) }catch{}
        const lastId = localStorage.getItem('lastPaymentOrderId')
        if (lastId){
          setVerifyingMealOrderId(lastId)
          pollMealOrderPayment(lastId, sid)
        }
      }
    }catch{}
  }, [searchParams])

  useEffect(()=>{
    try{
      const last = localStorage.getItem('lastPaymentOrderId')
      const sid = localStorage.getItem('lastCheckoutSessionId') || null
      if (last){
        setVerifyingMealOrderId(last)
        pollMealOrderPayment(last, sid)
      }
    }catch{}
  }, [])

  return (
    <div className="page-orders" style={{display:'flex', flexDirection:'column', gap:'1.25rem'}}>
      <header>
        <h1>Your orders</h1>
        <p className="muted" style={{marginTop:'.35rem'}}>Track your chef-service bookings and meal-plan orders in one place.</p>
      </header>
      <div className="seg-control" role="tablist" aria-label="Order types">
        <button className={`seg ${tab==='services'?'active':''}`} onClick={()=> setTab('services')} role="tab" aria-selected={tab==='services'}>Chef services</button>
        <button className={`seg ${tab==='meals'?'active':''}`} onClick={()=> setTab('meals')} role="tab" aria-selected={tab==='meals'}>Meal orders</button>
      </div>
      {tab === 'services' ? (
        <div>
          <div className="card" style={{marginBottom:'1rem', display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:'.5rem'}}>
            <div>
              <h2 style={{margin:'0 0 .35rem 0'}}>Service orders</h2>
              <div className="muted">These are bookings you’ve made directly with chefs.</div>
            </div>
            <div style={{display:'flex', gap:'.5rem'}}>
              <button className="btn btn-outline btn-sm" onClick={()=> loadServiceOrders()} disabled={serviceLoading}>Refresh</button>
            </div>
          </div>
          {serviceOrdersView}
        </div>
      ) : (
        <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
          <div className="card" style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:'.5rem'}}>
            <div>
              <h2 style={{margin:'0 0 .35rem 0'}}>Meal orders</h2>
              <div className="muted">Chef-prepared meals you’ve planned through sautai.</div>
            </div>
          </div>
          <OrdersTab
            onNotify={notify}
            verifyingOrderId={verifyingMealOrderId}
            setVerifyingOrderId={setVerifyingMealOrderId}
            onPollRequest={pollMealOrderPayment}
          />
        </div>
      )}
      {cancelDialog}
    </div>
  )
}
