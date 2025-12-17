import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, stripe } from '../api'
import { createOffering } from '../api/servicesClient.js'
import { useConnections } from '../hooks/useConnections.js'

import ChefAllClients from '../components/ChefAllClients.jsx'
import ChefPrepPlanning from '../components/ChefPrepPlanning.jsx'
import ChefPaymentLinks from '../components/ChefPaymentLinks.jsx'
import SousChefWidget from '../components/SousChefWidget.jsx'
import ServiceAreaPicker from '../components/ServiceAreaPicker.jsx'
import ChatPanel from '../components/ChatPanel.jsx'
import { SousChefNotificationProvider } from '../contexts/SousChefNotificationContext.jsx'
import { useMessaging } from '../context/MessagingContext.jsx'

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
  notes: '',
  targetCustomerIds: []
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

function parseServiceDate(dateStr = '', timeStr = ''){
  if (!dateStr) return null
  try{
    let normalizedTime = timeStr
    if (normalizedTime && normalizedTime.length === 5) normalizedTime += ':00'
    const iso = `${dateStr}T${normalizedTime || '00:00:00'}`
    const dt = new Date(iso)
    if (Number.isNaN(dt.valueOf())) return null
    return dt
  }catch{
    return null
  }
}

function formatServiceSchedule(order = {}){
  const dt = parseServiceDate(order.service_date, order.service_start_time)
  if (dt){
    try{
      const dateFormatter = new Intl.DateTimeFormat(undefined, { month:'short', day:'numeric', year:'numeric' })
      const timeFormatter = new Intl.DateTimeFormat(undefined, { hour:'numeric', minute:'2-digit' })
      const dateLabel = dateFormatter.format(dt)
      const timeLabel = order.service_start_time ? timeFormatter.format(dt) : null
      return timeLabel ? `${dateLabel} · ${timeLabel}` : dateLabel
    }catch{}
  }
  if (order.service_date){
    return order.service_start_time ? `${order.service_date} · ${order.service_start_time}` : order.service_date
  }
  const prefs = order.schedule_preferences
  if (prefs && typeof prefs === 'object'){
    const note = prefs.notes || prefs.preferred_weekday || prefs.preferred_time || ''
    if (note) return String(note)
  }
  return 'Schedule to be arranged'
}

function toCurrencyDisplay(amount, currency = 'USD'){
  if (amount == null) return ''
  let value = amount
  if (typeof value === 'string'){
    const numeric = Number(value)
    if (!Number.isNaN(numeric)) value = numeric
  }
  if (typeof value === 'number' && !Number.isNaN(value)){
    try{
      return new Intl.NumberFormat(undefined, { style:'currency', currency: String(currency||'USD').toUpperCase(), maximumFractionDigits:2 }).format(value)
    }catch{}
    return `$${value.toFixed(2)}`
  }
  return String(amount)
}

function serviceStatusTone(status){
  const normalized = String(status || '').toLowerCase()
  if (['paid','completed','confirmed','active'].includes(normalized)){
    return { label: normalized === 'paid' ? 'Paid' : normalized.charAt(0).toUpperCase()+normalized.slice(1), style: { background:'rgba(24,180,24,.15)', color:'#168516' } }
  }
  if (['awaiting_payment','pending','draft','open'].includes(normalized)){
    return { label: normalized.replace('_',' '), style: { background:'rgba(60,100,200,.16)', color:'#1b3a72' } }
  }
  if (['cancelled','canceled','refund_pending','failed'].includes(normalized)){
    return { label: normalized.charAt(0).toUpperCase()+normalized.slice(1).replace('_',' '), style: { background:'rgba(200,40,40,.18)', color:'#a11919' } }
  }
  return { label: status || 'Unknown', style: { background:'rgba(60,60,60,.12)', color:'#2f2f2f' } }
}

function extractTierLabel(order = {}){
  const tier = order.tier || {}
  return tier.display_label || order.tier_display_label || order.tier_label || order.tier_name || ''
}

function serviceCustomerName(order = {}, detail = null){
  const customer = detail || order.customer_details || order.customer_profile || {}

  const candidate = (...values)=>{
    for (const value of values){
      if (!value) continue
      if (typeof value === 'string'){
        const trimmed = value.trim()
        if (trimmed) return trimmed
      } else if (typeof value === 'number'){
        return String(value)
      } else if (Array.isArray(value)){
        const joined = value.filter(Boolean).map(v=> String(v).trim()).filter(Boolean).join(' ')
        if (joined) return joined
      }
    }
    return ''
  }

  const fullName = candidate(
    order.customer_display_name,
    order.customer_name,
    order.customer_full_name,
    candidate(order.customer_first_name, order.customer_last_name),
    customer.full_name,
    customer.display_name,
    candidate(customer.first_name, customer.last_name)
  )

  const secondary = candidate(
    order.customer_username,
    customer.username,
    order.customer_email,
    customer.email,
    order.customer || order.customer_id || customer.id
  )

  if (fullName && secondary){
    const lowered = fullName.toLowerCase()
    const secondaryStr = String(secondary)
    if (!lowered.includes(secondaryStr.toLowerCase())){
      return `${fullName} (${secondaryStr})`
    }
    return fullName
  }
  if (fullName) return fullName
  if (secondary){
    return typeof secondary === 'number' ? `Customer #${secondary}` : String(secondary)
  }
  return 'Customer'
}

function serviceOfferingTitle(order = {}){
  return order.offering_title || order.offering?.title || order.service_title || 'Service'
}


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

function pickFirstString(...values){
  for (const value of values){
    if (typeof value === 'string'){
      const trimmed = value.trim()
      if (trimmed) return trimmed
    }
  }
  return null
}

function joinNames(first, last){
  const parts = []
  if (typeof first === 'string' && first.trim()) parts.push(first.trim())
  if (typeof last === 'string' && last.trim()) parts.push(last.trim())
  if (parts.length === 0) return null
  return parts.join(' ')
}

function connectionPartnerDetails(connection = {}, viewerRole = 'chef'){
  if (viewerRole === 'chef'){
    return connection.customer || connection.customer_profile || connection.customer_details || connection.customer_user || {}
  }
  return connection.chef || connection.chef_profile || connection.chef_details || connection.chef_user || {}
}

function connectionDisplayName(connection = {}, viewerRole = 'chef'){
  const normalizedRole = viewerRole === 'chef' ? 'chef' : 'customer'
  const partner = connectionPartnerDetails(connection, normalizedRole)
  const nameFromRecord = normalizedRole === 'chef'
    ? pickFirstString(
      connection.customer_display_name,
      connection.customer_full_name,
      connection.customer_name,
      joinNames(connection.customer_first_name, connection.customer_last_name),
      partner.full_name,
      partner.display_name,
      joinNames(partner.first_name, partner.last_name),
      partner.public_name,
      partner.name
    )
    : pickFirstString(
      connection.chef_display_name,
      connection.chef_full_name,
      connection.chef_name,
      joinNames(connection.chef_first_name, connection.chef_last_name),
      partner.full_name,
      partner.display_name,
      joinNames(partner.first_name, partner.last_name),
      partner.public_name,
      partner.name
    )

  if (nameFromRecord) return nameFromRecord

  const usernameFallback = normalizedRole === 'chef'
    ? pickFirstString(connection.customer_username, partner.username, connection.customer_email, partner.email)
    : pickFirstString(connection.chef_username, partner.username, connection.chef_email, partner.email)
  if (usernameFallback) return usernameFallback

  const fallbackId = normalizedRole === 'chef'
    ? (connection.customerId ?? connection.customer_id ?? partner?.id)
    : (connection.chefId ?? connection.chef_id ?? partner?.id)

  if (fallbackId != null){
    return normalizedRole === 'chef' ? `Customer #${fallbackId}` : `Chef #${fallbackId}`
  }
  return 'Connection'
}

function connectionInitiatedCopy(connection = {}){
  if (connection.viewerInitiated) return 'You sent this invitation'
  const role = String(connection?.initiated_by || '').toLowerCase()
  if (role === 'chef') return 'Chef sent the invitation'
  if (role === 'customer') return 'Customer sent the invitation'
  return ''
}

function formatConnectionStatus(status){
  const normalized = String(status || '').toLowerCase()
  if (!normalized) return 'Unknown'
  return normalized.charAt(0).toUpperCase() + normalized.slice(1)
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

// Icon components (inline SVG)
const DashboardIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
const ProfileIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
const PhotosIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
const KitchenIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/></svg>
const ClientsIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
const ServicesIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
const ConnectionsIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="5" cy="6" r="3"/><circle cx="19" cy="6" r="3"/><circle cx="12" cy="18" r="3"/><path d="M5 9v3a4 4 0 0 0 4 4h2"/><path d="M19 9v3a4 4 0 0 1-4 4h-2"/></svg>
const EventsIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
const OrdersIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
const MealsIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/></svg>
const PrepPlanIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="m9 14 2 2 4-4"/></svg>
const PaymentLinksIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/><path d="M7 15h4"/><path d="M15 15h2"/></svg>
const MessagesIcon = ()=> <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>

/**
 * ChefMessagesSection - Messages tab for chef dashboard
 */
function ChefMessagesSection() {
  const { conversations, conversationsLoading, fetchConversations, totalUnread } = useMessaging()
  const [chatOpen, setChatOpen] = useState(false)
  const [selectedConversation, setSelectedConversation] = useState(null)
  
  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])
  
  const handleOpenChat = (conversation) => {
    setSelectedConversation(conversation)
    setChatOpen(true)
  }
  
  const formatTime = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const isToday = date.toDateString() === now.toDateString()
    const yesterday = new Date(now)
    yesterday.setDate(yesterday.getDate() - 1)
    const isYesterday = date.toDateString() === yesterday.toDateString()
    
    if (isToday) {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    }
    if (isYesterday) {
      return 'Yesterday'
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  
  return (
    <div>
      <header style={{marginBottom:'1.5rem', display:'flex', alignItems:'center', justifyContent:'space-between'}}>
        <div>
          <h1 style={{margin:'0 0 .25rem 0'}}>Messages</h1>
          <p className="muted" style={{margin:0}}>Chat with your connected clients</p>
        </div>
        {totalUnread > 0 && (
          <span className="badge badge-primary">{totalUnread} unread</span>
        )}
      </header>
      
      <div className="card">
        {conversationsLoading && (
          <div style={{display:'flex', alignItems:'center', justifyContent:'center', padding:'3rem'}}>
            <div className="spinner" style={{width: 32, height: 32}} />
          </div>
        )}
        
        {!conversationsLoading && conversations.length === 0 && (
          <div className="chef-empty-state" style={{padding:'3rem', textAlign:'center'}}>
            <MessagesIcon />
            <p style={{margin:'1rem 0 0', fontWeight:600}}>No conversations yet</p>
            <p className="muted" style={{margin:'.5rem 0 0'}}>Messages from your clients will appear here</p>
          </div>
        )}
        
        {!conversationsLoading && conversations.length > 0 && (
          <div className="conversations-list">
            {conversations.map(conv => (
              <button
                key={conv.id}
                className="conversation-item"
                onClick={() => handleOpenChat(conv)}
              >
                <div className="conversation-avatar">
                  {conv.customer_photo ? (
                    <img src={conv.customer_photo} alt="" />
                  ) : (
                    <div className="conversation-avatar-placeholder">
                      <i className="fa-solid fa-user"></i>
                    </div>
                  )}
                </div>
                <div className="conversation-info">
                  <div className="conversation-header">
                    <span className="conversation-name">{conv.customer_name}</span>
                    <span className="conversation-time">{formatTime(conv.last_message_at)}</span>
                  </div>
                  <div className="conversation-preview">
                    {conv.last_message_preview || 'Start a conversation'}
                  </div>
                </div>
                {conv.unread_count > 0 && (
                  <span className="conversation-unread">{conv.unread_count}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
      
      {/* Chat Panel */}
      <ChatPanel
        isOpen={chatOpen}
        onClose={() => {
          setChatOpen(false)
          setSelectedConversation(null)
          fetchConversations() // Refresh after closing
        }}
        conversationId={selectedConversation?.id}
        recipientName={selectedConversation?.customer_name}
        recipientPhoto={selectedConversation?.customer_photo}
      />
    </div>
  )
}

export default function ChefDashboard(){
  const location = useLocation()
  const [tab, setTab] = useState(() => location.state?.tab || 'dashboard')
  const [notice, setNotice] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  
  // Handle navigation state changes (e.g., clicking messages icon from navbar)
  useEffect(() => {
    if (location.state?.tab && location.state.tab !== tab) {
      setTab(location.state.tab)
    }
  }, [location.state?.tab])

  // Stripe Connect status
  const [payouts, setPayouts] = useState({ loading: true, has_account:false, is_active:false, needs_onboarding:false, account_id:null, continue_onboarding_url:null, disabled_reason:null, diagnostic:null })
  const [onboardingBusy, setOnboardingBusy] = useState(false)

  // Chef profile
  const [chef, setChef] = useState(null)
  const [profileForm, setProfileForm] = useState({ experience:'', bio:'', profile_pic:null, banner_image:null, calendly_url:'' })
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

  // Service area management
  const [areaStatus, setAreaStatus] = useState(null) // { approved_areas, pending_requests, etc. }
  const [areaStatusLoading, setAreaStatusLoading] = useState(false)
  const [showAreaPicker, setShowAreaPicker] = useState(false)
  const [newAreaSelection, setNewAreaSelection] = useState([])
  const [areaRequestNotes, setAreaRequestNotes] = useState('')
  const [submittingAreaRequest, setSubmittingAreaRequest] = useState(false)

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
  const [dishFilter, setDishFilter] = useState('')
  
  // UI state for create panels
  const [showIngredientForm, setShowIngredientForm] = useState(false)
  const [showDishForm, setShowDishForm] = useState(false)
  const [showMealForm, setShowMealForm] = useState(false)
  const [showEventForm, setShowEventForm] = useState(false)
  const [showServiceForm, setShowServiceForm] = useState(false)

  // Meals
  const [meals, setMeals] = useState([])
  const [mealForm, setMealForm] = useState({ name:'', description:'', meal_type:'Dinner', price:'', start_date:'', dishes:[], dietary_preferences:[] })
  const [mealSaving, setMealSaving] = useState(false)

  // Events
  const [events, setEvents] = useState([])
  const [eventForm, setEventForm] = useState({ meal:null, event_date:'', event_time:'18:00', order_cutoff_date:'', order_cutoff_time:'12:00', base_price:'', min_price:'', max_orders:10, min_orders:1, description:'', special_instructions:'' })
  const [showPastEvents, setShowPastEvents] = useState(false)

  // Orders
  const [orders, setOrders] = useState([])
  const [serviceOrders, setServiceOrders] = useState([])
  const [serviceOrdersLoading, setServiceOrdersLoading] = useState(false)
  const [serviceCustomerDetails, setServiceCustomerDetails] = useState({})
  const serviceCustomerPending = useRef(new Set())

  const {
    connections,
    pendingConnections,
    acceptedConnections,
    declinedConnections,
    endedConnections,
    respondToConnection,
    refetchConnections,
    isLoading: connectionsLoading,
    requestError: connectionRequestError,
    respondError: connectionRespondError,
    respondStatus
  } = useConnections('chef')
  const [connectionActionId, setConnectionActionId] = useState(null)
  const connectionMutating = respondStatus === 'pending'

  // Chef services
  const [serviceOfferings, setServiceOfferings] = useState([])
  const [serviceLoading, setServiceLoading] = useState(false)
  const [serviceForm, setServiceForm] = useState(()=>({ ...INITIAL_SERVICE_FORM }))
  const [serviceSaving, setServiceSaving] = useState(false)
  const [serviceErrors, setServiceErrors] = useState(null)
  const [tierForm, setTierForm] = useState(()=>({ ...INITIAL_TIER_FORM }))
  const [tierSaving, setTierSaving] = useState(false)
  const [tierErrors, setTierErrors] = useState(null)
  const serviceErrorMessages = useMemo(()=> flattenErrors(serviceErrors), [serviceErrors])
  const tierErrorMessages = useMemo(()=> flattenErrors(tierErrors), [tierErrors])
  const tierSummaryExamples = useMemo(()=>{
    const summaries = []
    if (!Array.isArray(serviceOfferings)) return summaries
    for (const offering of serviceOfferings){
      const tierSummaries = Array.isArray(offering?.tier_summary) ? offering.tier_summary : []
      for (const summary of tierSummaries){
        const text = typeof summary === 'string' ? summary.trim() : String(summary || '').trim()
        if (!text) continue
        if (summaries.length < 4 && !summaries.includes(text)){
          summaries.push(text)
        }
        if (summaries.length >= 4){
          return summaries
        }
      }
    }
    return summaries
  }, [serviceOfferings])

  const todayISO = useMemo(()=> new Date().toISOString().slice(0,10), [])

  const acceptedCustomerOptions = useMemo(()=>{
    return acceptedConnections
      .map(connection => {
        const id = connection?.customerId ?? connection?.customer_id
        if (id == null) return null
        return { value: String(id), label: connectionDisplayName(connection, 'chef') }
      })
      .filter(Boolean)
  }, [acceptedConnections])

  const loadIngredients = async ()=>{
    setIngLoading(true)
    try{
      const resp = await api.get('/meals/api/ingredients/', { params: { chef_ingredients: 'true' } })
      setIngredients(toArray(resp.data))
    }catch{ setIngredients([]) } finally { setIngLoading(false) }
  }

  const toggleMealDish = (dishId)=>{
    const id = String(dishId)
    setMealForm(prev => {
      const has = prev.dishes.includes(id)
      const nextDishes = has ? prev.dishes.filter(x => x !== id) : [...prev.dishes, id]
      return { ...prev, dishes: nextDishes }
    })
  }

  const renderDishChecklist = (idPrefix = 'dish')=>{
    if (!Array.isArray(dishes) || dishes.length === 0){
      return <div className="muted">No dishes yet.</div>
    }
    const trimmed = dishFilter.trim().toLowerCase()
    const filtered = trimmed ? dishes.filter(d => String(d.name || '').toLowerCase().includes(trimmed)) : dishes
    return (
      <div>
        <input
          type="search"
          value={dishFilter}
          onChange={e => setDishFilter(e.target.value)}
          placeholder="Filter dishes…"
          aria-label="Filter dishes"
          className="input"
          style={{marginTop:'.25rem', marginBottom:'.35rem'}}
        />
        <div className="dish-checklist" role="group" aria-label="Select dishes" style={{display:'flex', flexDirection:'column', gap:'.35rem', maxHeight:'220px', overflowY:'auto', paddingRight:'.25rem'}}>
          {filtered.map(d => {
            const dishId = String(d.id)
            const inputId = `${idPrefix}-${dishId}`
            return (
              <label key={dishId} htmlFor={inputId} style={{display:'flex', alignItems:'center', gap:'.4rem'}}>
                <input
                  id={inputId}
                  type="checkbox"
                  checked={mealForm.dishes.includes(dishId)}
                  onChange={()=> toggleMealDish(dishId)}
                />
                <span>{d.name}</span>
              </label>
            )
          })}
        </div>
        {filtered.length === 0 && <div className="muted" style={{marginTop:'.35rem'}}>No dishes match your filter.</div>}
      </div>
    )
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
      setProfileForm({ experience: data?.experience || '', bio: data?.bio || '', profile_pic: null, banner_image: null, calendly_url: data?.calendly_url || '' })
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

  // Load service area status
  const loadAreaStatus = useCallback(async () => {
    setAreaStatusLoading(true)
    try {
      const resp = await api.get('/local_chefs/api/chef/area-status/')
      setAreaStatus(resp.data || null)
    } catch (e) {
      console.warn('Failed to load area status:', e)
      setAreaStatus(null)
    } finally {
      setAreaStatusLoading(false)
    }
  }, [])

  // Submit new area request
  const submitAreaRequest = useCallback(async () => {
    if (submittingAreaRequest || newAreaSelection.length === 0) return
    
    setSubmittingAreaRequest(true)
    try {
      const areaIds = newAreaSelection.map(a => a.area_id || a.id)
      await api.post('/local_chefs/api/chef/area-requests/', {
        area_ids: areaIds,
        notes: areaRequestNotes
      })
      
      // Reset form and reload status
      setNewAreaSelection([])
      setAreaRequestNotes('')
      setShowAreaPicker(false)
      await loadAreaStatus()
      
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: 'Area request submitted! An admin will review it soon.', tone: 'success' } 
      }))
    } catch (e) {
      const msg = e?.response?.data?.error || 'Failed to submit request'
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: msg, tone: 'error' } 
      }))
    } finally {
      setSubmittingAreaRequest(false)
    }
  }, [submittingAreaRequest, newAreaSelection, areaRequestNotes, loadAreaStatus])

  // Cancel pending request
  const cancelAreaRequest = useCallback(async (requestId) => {
    if (!window.confirm('Cancel this area request?')) return
    
    try {
      await api.delete(`/local_chefs/api/chef/area-requests/${requestId}/cancel/`)
      await loadAreaStatus()
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: 'Request cancelled', tone: 'success' } 
      }))
    } catch (e) {
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: 'Failed to cancel request', tone: 'error' } 
      }))
    }
  }, [loadAreaStatus])

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
      const resp = await api.get('/meals/api/chef-meal-events/', { params: { my_events:'true' } }); 
      const list = toArray(resp.data)
      setEvents(list) 
    }catch(e){ console.warn('[ChefDashboard] Load my events failed', { status: e?.response?.status, data: e?.response?.data }); setEvents([]) }
  }

  const loadOrders = async ()=>{
    try{ const resp = await api.get('/meals/api/chef-meal-orders/', { params: { as_chef: 'true' } }); setOrders(toArray(resp.data)) }catch{ setOrders([]) }
  }

  const loadServiceOrders = async ()=>{
    setServiceOrdersLoading(true)
    try{
      const resp = await api.get(`${SERVICES_ROOT}/my/orders/`)
      setServiceOrders(toArray(resp.data))
    }catch{
      setServiceOrders([])
    }finally{
      setServiceOrdersLoading(false)
    }
  }

  useEffect(()=>{
    if (!Array.isArray(serviceOrders) || serviceOrders.length === 0) return
    const ids = Array.from(new Set(serviceOrders.map(o => o?.customer).filter(id => id != null)))
    const missing = ids.filter(id => !(id in serviceCustomerDetails) && !serviceCustomerPending.current.has(id))
    if (missing.length === 0) return
    let cancelled = false
    const fetchDetails = async ()=>{
      await Promise.all(missing.map(async id => {
        serviceCustomerPending.current.add(id)
        try{
          const resp = await api.get('/auth/api/user_details/', { params: { user_id: id }, skipUserId: true })
          if (!cancelled){
            setServiceCustomerDetails(prev => ({ ...prev, [id]: resp?.data || null }))
          }
        }catch{
          if (!cancelled){
            setServiceCustomerDetails(prev => ({ ...prev, [id]: null }))
          }
        }finally{
          serviceCustomerPending.current.delete(id)
        }
      }))
    }
    fetchDetails()
    return ()=>{ cancelled = true }
  }, [serviceOrders, serviceCustomerDetails])

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
    const tasks = [loadChefProfile(), loadAreaStatus(), loadIngredients(), loadDishes(), loadMeals(), loadEvents(), loadOrders(), loadServiceOrders(), loadStripeStatus(), loadServiceOfferings()]
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
    if (mealSaving) return
    setMealSaving(true)
    const startedAt = Date.now()
    const trimmedName = String(mealForm.name || '').trim()
    const trimmedDescription = String(mealForm.description || '').trim()
    const fieldErrors = []
    if (!trimmedName) fieldErrors.push('Enter a meal name before saving.')
    if (!trimmedDescription) fieldErrors.push('Add a brief description for your meal.')
    const priceValue = Number(mealForm.price || 0)
    if (!Number.isFinite(priceValue) || priceValue <= 0) fieldErrors.push('Set a meal price greater than zero.')
    if (!Array.isArray(mealForm.dishes) || mealForm.dishes.length === 0) fieldErrors.push('Choose at least one dish to include.')
    if (fieldErrors.length > 0){
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: fieldErrors[0], tone:'error' } })) }catch{}
      setMealSaving(false)
      return
    }
    try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Creating meal…', tone:'info' } })) }catch{}
    try{
      const payload = { ...mealForm, price: Number(mealForm.price||0), start_date: mealForm.start_date || todayISO, dishes: (mealForm.dishes||[]).map(x=> Number(x)) }
      const resp = await api.post('/meals/api/chef/meals/', payload)
      const message = resp?.data?.message || 'Meal created successfully'
      try{ window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: message, tone:'success' } })) }catch{}
      setMealForm({ name:'', description:'', meal_type:'Dinner', price:'', start_date:'', dishes:[], dietary_preferences:[] })
      await loadMeals()
    }catch(err){
      console.error('createMeal failed', err)
      try{
        const { buildErrorMessage } = await import('../api')
        const msg = buildErrorMessage(err?.response?.data, 'Failed to create meal', err?.response?.status)
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
      }catch{
        const msg = err?.response?.data?.error || err?.response?.data?.detail || 'Failed to create meal'
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } })) }catch{}
      }
    } finally {
      const elapsed = Date.now() - startedAt
      if (elapsed < 350){
        await new Promise(resolve => setTimeout(resolve, 350 - elapsed))
      }
      setMealSaving(false)
    }
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
      const resp = await api.post('/meals/api/chef-meal-events/', payload)
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

  const resetServiceForm = ()=>{
    setServiceForm(()=>({ ...INITIAL_SERVICE_FORM }))
    setServiceErrors(null)
  }

  const editServiceOffering = (offering)=>{
    if (!offering) return
    const targetIds = Array.isArray(offering?.target_customer_ids)
      ? offering.target_customer_ids
      : Array.isArray(offering?.target_customers)
        ? offering.target_customers.map(t => t?.id ?? t?.customer_id ?? t)
        : []
    setServiceForm({
      id: offering.id || null,
      service_type: offering.service_type || 'home_chef',
      title: offering.title || '',
      description: offering.description || '',
      default_duration_minutes: offering.default_duration_minutes != null ? String(offering.default_duration_minutes) : '',
      max_travel_miles: offering.max_travel_miles != null ? String(offering.max_travel_miles) : '',
      notes: offering.notes || '',
      targetCustomerIds: Array.isArray(targetIds) ? targetIds.filter(id => id != null).map(String) : []
    })
    setServiceErrors(null)
  }

  const handleConnectionAction = async (connectionId, action)=>{
    if (!connectionId || !action) return
    setConnectionActionId(connectionId)
    try{
      await respondToConnection({ connectionId, action })
      await refetchConnections()
      const message = action === 'accept'
        ? 'Connection accepted'
        : action === 'decline'
          ? 'Connection declined'
          : 'Connection ended'
      try{
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: message, tone:'success' } }))
      }catch{}
    }catch(error){
      console.error('update connection failed', error)
      const msg = error?.response?.data?.detail || 'Unable to update the connection. Please try again.'
      try{
        window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text: msg, tone:'error' } }))
      }catch{}
    } finally {
      setConnectionActionId(null)
    }
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
    const targetIds = Array.isArray(serviceForm.targetCustomerIds)
      ? serviceForm.targetCustomerIds
        .map(id => {
          if (id == null) return null
          const numeric = Number(id)
          return Number.isNaN(numeric) ? String(id) : numeric
        })
        .filter(id => id != null && String(id).trim() !== '')
      : []
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
        await api.patch(`${SERVICES_ROOT}/offerings/${serviceForm.id}/`, {
          ...payload,
          target_customer_ids: targetIds
        })
        try{ window.dispatchEvent(new CustomEvent('global-toast', { detail:{ text:'Service offering updated', tone:'success' } })) }catch{}
      }else{
        await createOffering({ ...payload, targetCustomerIds: targetIds })
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

  const NavItem = ({ value, label, icon: Icon })=> (
    <button 
      className={`chef-nav-item ${tab===value?'active':''}`} 
      onClick={()=> setTab(value)}
      aria-current={tab===value?'page':undefined}
      title={sidebarCollapsed ? label : undefined}
    >
      <Icon />
      {!sidebarCollapsed && <span>{label}</span>}
    </button>
  )

  const SectionHeader = ({ title, subtitle, onAdd, addLabel, showAdd = true })=> (
    <header className="chef-section-header">
      <div className="chef-section-header-text">
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {showAdd && onAdd && (
        <button className="btn btn-primary chef-add-btn" onClick={onAdd}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          <span>{addLabel || 'Add'}</span>
        </button>
      )}
    </header>
  )

  return (
    <SousChefNotificationProvider>
    <div className={`chef-dashboard-layout ${sidebarCollapsed?'sidebar-collapsed':''}`}>
      {/* Sidebar Navigation */}
      <aside className={`chef-sidebar ${sidebarCollapsed?'collapsed':''}`}>
        <div className="chef-sidebar-header">
          <h2 style={{margin:0, fontSize:'1.25rem'}}>Chef Hub</h2>
          <button 
            className="btn btn-outline btn-sm chef-sidebar-toggle" 
            onClick={()=> setSidebarCollapsed(!sidebarCollapsed)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? '→' : '←'}
          </button>
        </div>
        <nav className="chef-nav" role="navigation" aria-label="Chef dashboard sections">
          <NavItem value="dashboard" label="Dashboard" icon={DashboardIcon} />
          <NavItem value="prep" label="Prep Planning" icon={PrepPlanIcon} />
          <NavItem value="profile" label="Profile" icon={ProfileIcon} />
          <NavItem value="photos" label="Photos" icon={PhotosIcon} />
          <NavItem value="kitchen" label="Kitchen" icon={KitchenIcon} />
          <NavItem value="connections" label="Connections" icon={ConnectionsIcon} />
          <NavItem value="clients" label="Clients" icon={ClientsIcon} />
          <NavItem value="messages" label="Messages" icon={MessagesIcon} />
          <NavItem value="payments" label="Payment Links" icon={PaymentLinksIcon} />
          <NavItem value="services" label="Services" icon={ServicesIcon} />
          <NavItem value="events" label="Events" icon={EventsIcon} />
          <NavItem value="orders" label="Orders" icon={OrdersIcon} />
          <NavItem value="meals" label="Meals" icon={MealsIcon} />
        </nav>
      </aside>

      {/* Main Content */}
      <main className="chef-main-content">
        {notice && <div className="card" style={{borderColor:'#f0d000', marginBottom:'1rem'}}>{notice}</div>}

      {/* Content Sections */}
      {tab==='dashboard' && (
        <div>
          <header style={{marginBottom:'1.5rem'}}>
            <h1 style={{margin:'0 0 .25rem 0'}}>Dashboard</h1>
            <p className="muted">Your business overview and key metrics</p>
          </header>

          {/* Stripe Payouts Status */}
          {payouts.loading ? (
            <div className="card" style={{marginBottom:'1.5rem', background:'var(--surface-2)'}}>
              <div style={{display:'flex', alignItems:'center', gap:'.75rem'}}>
                <div style={{width:40, height:40, borderRadius:8, background:'var(--surface)', display:'flex', alignItems:'center', justifyContent:'center'}}>
                  <i className="fa-brands fa-stripe" style={{fontSize:20, opacity:.5}}></i>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:600, marginBottom:'.15rem'}}>Payouts</div>
                  <div className="muted" style={{fontSize:'.9rem'}}>Checking Stripe status…</div>
                </div>
                <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={loadStripeStatus}>
                  <i className="fa-solid fa-rotate-right" style={{fontSize:14}}></i>
                </button>
              </div>
            </div>
          ) : payouts.is_active ? (
            <div className="card" style={{marginBottom:'1.5rem', background:'linear-gradient(135deg, rgba(52,211,153,.1), rgba(16,185,129,.05))', borderColor:'rgba(16,185,129,.3)'}}>
              <div style={{display:'flex', alignItems:'center', gap:'.75rem'}}>
                <div style={{width:40, height:40, borderRadius:8, background:'rgba(16,185,129,.15)', display:'flex', alignItems:'center', justifyContent:'center'}}>
                  <i className="fa-solid fa-circle-check" style={{fontSize:20, color:'var(--success)'}}></i>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:600, marginBottom:'.15rem', display:'flex', alignItems:'center', gap:'.5rem'}}>
                    Stripe Payouts Active
                    <i className="fa-brands fa-stripe" style={{fontSize:18, opacity:.6}}></i>
                  </div>
                  <div className="muted" style={{fontSize:'.9rem'}}>You're ready to receive payments</div>
                </div>
                <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={loadStripeStatus} title="Refresh status">
                  <i className="fa-solid fa-rotate-right" style={{fontSize:14}}></i>
                </button>
              </div>
            </div>
          ) : (
            <div className="card" style={{marginBottom:'1.5rem', borderColor:'#f0a000', background:'rgba(240,160,0,.08)'}}>
              <div style={{display:'flex', alignItems:'flex-start', gap:'.75rem'}}>
                <div style={{width:40, height:40, borderRadius:8, background:'rgba(240,160,0,.15)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0}}>
                  <i className="fa-solid fa-triangle-exclamation" style={{fontSize:20, color:'#f0a000'}}></i>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontWeight:600, marginBottom:'.25rem'}}>Payouts Setup Required</div>
                  <div className="muted" style={{fontSize:'.9rem', marginBottom:'.5rem'}}>Complete Stripe onboarding to receive payments and unlock all features.</div>
                  {payouts?.disabled_reason && (
                    <div className="muted" style={{fontSize:'.85rem', marginBottom:'.5rem'}}>
                      <strong>Reason:</strong> {payouts.disabled_reason}
                    </div>
                  )}
                  <div style={{display:'flex', flexWrap:'wrap', gap:'.5rem', marginTop:'.75rem'}}>
                    <button className="btn btn-primary btn-sm" disabled={onboardingBusy} onClick={startOrContinueOnboarding}>
                      <i className="fa-brands fa-stripe" style={{fontSize:14, marginRight:'.35rem'}}></i>
                      {onboardingBusy?'Opening…':(payouts.has_account?'Continue Setup':'Set Up Payouts')}
                    </button>
                    <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={regenerateOnboarding}>
                      <i className="fa-solid fa-link" style={{fontSize:12, marginRight:'.35rem'}}></i>
                      New Link
                    </button>
                    <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={loadStripeStatus}>
                      <i className="fa-solid fa-rotate-right" style={{fontSize:12, marginRight:'.35rem'}}></i>
                      Refresh
                    </button>
                    {payouts.disabled_reason && (
                      <button className="btn btn-outline btn-sm" disabled={onboardingBusy} onClick={fixRestrictedAccount}>
                        <i className="fa-solid fa-wrench" style={{fontSize:12, marginRight:'.35rem'}}></i>
                        Fix Account
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Key Metrics Cards */}
          <div className="chef-metrics-grid">
            <div className="chef-metric-card">
              <div className="metric-label">Total Revenue</div>
              <div className="metric-value">
                {toCurrencyDisplay(
                  [...serviceOrders, ...orders].reduce((sum, o)=> sum + (Number(o.total_value_for_chef)||0), 0),
                  'USD'
                )}
              </div>
              <div className="metric-change positive">+12% from last month</div>
            </div>
            <div className="chef-metric-card">
              <div className="metric-label">Active Families</div>
              <div className="metric-value">
                {new Set([...serviceOrders, ...orders].map(o=> o.customer).filter(Boolean)).size}
              </div>
              <div className="metric-change positive">+3 this month</div>
            </div>
            <div className="chef-metric-card">
              <div className="metric-label">Service Orders</div>
              <div className="metric-value">{serviceOrders.length}</div>
              <div className="metric-change">{serviceOrdersLoading ? 'Loading...' : `${serviceOrders.filter(o=> ['confirmed','completed'].includes(String(o.status||'').toLowerCase())).length} confirmed`}</div>
            </div>
            <div className="chef-metric-card">
              <div className="metric-label">Meal Orders</div>
              <div className="metric-value">{orders.length}</div>
              <div className="metric-change">{orders.filter(o=> ['paid','completed'].includes(String(o.status||'').toLowerCase())).length} completed</div>
            </div>
          </div>

          {/* Quick Actions & Upcoming */}
          <div className="grid grid-2" style={{marginTop:'1.5rem'}}>
            <div className="card">
              <h3 style={{marginTop:0}}>Upcoming Events</h3>
              <div style={{maxHeight: 300, overflowY:'auto'}}>
                {upcomingEvents.length===0 ? (
                  <div className="muted">No upcoming events.</div>
                ) : (
                  <div style={{display:'flex', flexDirection:'column', gap:'.5rem'}}>
                    {upcomingEvents.slice(0,5).map(e => (
                      <div key={e.id} className="card" style={{padding:'.6rem', background:'var(--surface-2)'}}>
                        <div style={{fontWeight:700}}>{e.meal?.name || e.meal_name || 'Meal'}</div>
                        <div className="muted" style={{fontSize:'.85rem', marginTop:'.15rem'}}>
                          {e.event_date} at {e.event_time}
                        </div>
                        <div className="muted" style={{fontSize:'.85rem'}}>
                          Orders: {e.orders_count || 0} / {e.max_orders || 0}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <h3 style={{marginTop:0}}>Recent Service Orders</h3>
              <div style={{maxHeight: 300, overflowY:'auto'}}>
                {serviceOrders.length===0 ? (
                  <div className="muted">No service orders yet.</div>
                ) : (
                  <div style={{display:'flex', flexDirection:'column', gap:'.5rem'}}>
                    {serviceOrders.slice(0,5).map(order => {
                      const statusMeta = serviceStatusTone(order.status)
                      const detail = serviceCustomerDetails?.[order.customer] || null
                      const displayName = serviceCustomerName(order, detail)
                      return (
                        <div key={order.id} className="card" style={{padding:'.6rem', background:'var(--surface-2)'}}>
                          <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.5rem'}}>
                            <div style={{fontWeight:700, fontSize:'.9rem'}}>{displayName}</div>
                            <span className="chip" style={{...statusMeta.style, fontSize:'.7rem', padding:'.1rem .4rem'}}>{statusMeta.label}</span>
                          </div>
                          <div className="muted" style={{fontSize:'.85rem', marginTop:'.15rem'}}>
                            {serviceOfferingTitle(order)}
                          </div>
                          <div className="muted" style={{fontSize:'.85rem'}}>
                            {formatServiceSchedule(order)}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="card" style={{marginTop:'1.5rem', background:'linear-gradient(135deg, var(--surface-2), var(--surface))'}}>
            <h3 style={{marginTop:0}}>Quick Stats</h3>
            <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(140px, 1fr))', gap:'1rem'}}>
              <div>
                <div className="muted" style={{fontSize:'.85rem'}}>Total Meals</div>
                <div style={{fontSize:'1.5rem', fontWeight:700, color:'var(--primary-700)'}}>{meals.length}</div>
              </div>
              <div>
                <div className="muted" style={{fontSize:'.85rem'}}>Dishes</div>
                <div style={{fontSize:'1.5rem', fontWeight:700, color:'var(--primary-700)'}}>{dishes.length}</div>
              </div>
              <div>
                <div className="muted" style={{fontSize:'.85rem'}}>Ingredients</div>
                <div style={{fontSize:'1.5rem', fontWeight:700, color:'var(--primary-700)'}}>{ingredients.length}</div>
              </div>
              <div>
                <div className="muted" style={{fontSize:'.85rem'}}>Service Offerings</div>
                <div style={{fontSize:'1.5rem', fontWeight:700, color:'var(--primary-700)'}}>{serviceOfferings.length}</div>
              </div>
            </div>
          </div>

          {/* Break Mode Banner */}
          <div className="card" style={{marginTop:'1.5rem', background:'var(--surface-2)'}}>
            <div style={{display:'flex', flexWrap:'wrap', gap:'1.4rem', alignItems:'flex-start'}}>
              <div style={{flex:'1 1 260px'}}>
                <h3 style={{marginTop:0}}>Need a breather?</h3>
                <p className="muted" style={{marginTop:'.35rem'}}>
                  Turning on break pauses new bookings, cancels upcoming events, and issues refunds automatically.
                  Use it whenever you need to step back, focus on personal matters, or simply recharge.
                </p>
                <p className="muted" style={{marginTop:'.35rem'}}>
                  A rested chef creates the best experiences. Pause with confidence and come back when you're ready—your guests will understand.
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
      )}

      {tab==='connections' && (
        <div>
          <SectionHeader
            title="Client Connections"
            subtitle="Review pending invitations and manage the customers who can access personalized offerings."
            showAdd={false}
          />
          <div className="muted" style={{marginBottom:'.75rem'}}>
            Accepted: {acceptedConnections.length} · Pending: {pendingConnections.length} · Total: {connections.length}
          </div>
          {(connectionRequestError || connectionRespondError) && (
            <div className="alert alert-error" role="alert" style={{marginBottom:'1rem'}}>
              <strong style={{display:'block', marginBottom:'.25rem'}}>We could not update one of your connections.</strong>
              <span>{connectionRespondError?.response?.data?.detail || connectionRequestError?.response?.data?.detail || connectionRespondError?.message || connectionRequestError?.message || 'Please try again.'}</span>
            </div>
          )}
          <div className="grid grid-2" style={{gap:'1.5rem'}}>
            <div className="card">
              <h3 style={{marginTop:0}}>Pending requests</h3>
              {connectionsLoading ? (
                <div className="muted">Loading connections…</div>
              ) : pendingConnections.length === 0 ? (
                <div className="muted">No pending requests right now.</div>
              ) : (
                <table className="table" style={{width:'100%', borderCollapse:'collapse'}}>
                  <thead>
                    <tr>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Customer</th>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Details</th>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingConnections.map(connection => {
                      const key = connection?.id != null ? connection.id : `pending-${connection?.customerId || connection?.customer_id}`
                      const busy = connectionMutating && String(connectionActionId) === String(connection?.id)
                      return (
                        <tr key={key}>
                          <td style={{padding:'.5rem 0', fontWeight:600}}>{connectionDisplayName(connection, 'chef')}</td>
                          <td style={{padding:'.5rem 0', fontSize:'.85rem'}}>
                            <div>{connectionInitiatedCopy(connection) || 'Awaiting your response'}</div>
                            <div className="muted">{formatConnectionStatus(connection.status)}</div>
                          </td>
                          <td style={{padding:'.5rem 0'}}>
                            <div style={{display:'flex', gap:'.5rem', flexWrap:'wrap'}}>
                              {connection.canAccept && (
                                <button
                                  type="button"
                                  className="btn btn-primary btn-sm"
                                  disabled={busy}
                                  onClick={()=> handleConnectionAction(connection.id, 'accept')}
                                >
                                  {busy ? 'Updating…' : 'Accept'}
                                  <span style={{display:'none'}}>Accept</span>
                                </button>
                              )}
                              {connection.canDecline && (
                                <button
                                  type="button"
                                  className="btn btn-outline btn-sm"
                                  disabled={busy}
                                  onClick={()=> handleConnectionAction(connection.id, 'decline')}
                                >
                                  Decline
                                  <span style={{display:'none'}}>Decline</span>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
            <div className="card">
              <h3 style={{marginTop:0}}>Accepted clients</h3>
              {connectionsLoading ? (
                <div className="muted">Loading connections…</div>
              ) : acceptedConnections.length === 0 ? (
                <div className="muted">You have not accepted any clients yet.</div>
              ) : (
                <table className="table" style={{width:'100%', borderCollapse:'collapse'}}>
                  <thead>
                    <tr>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Customer</th>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Status</th>
                      <th style={{textAlign:'left', padding:'.5rem 0'}}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {acceptedConnections.map(connection => {
                      const key = connection?.id != null ? connection.id : `accepted-${connection?.customerId || connection?.customer_id}`
                      const busy = connectionMutating && String(connectionActionId) === String(connection?.id)
                      return (
                        <tr key={key}>
                          <td style={{padding:'.5rem 0', fontWeight:600}}>{connectionDisplayName(connection, 'chef')}</td>
                          <td style={{padding:'.5rem 0'}}>
                            <span className="chip" style={{background:'rgba(16,185,129,.15)', color:'#0f7a54', fontSize:'.75rem'}}>
                              {formatConnectionStatus(connection.status)}
                            </span>
                          </td>
                          <td style={{padding:'.5rem 0'}}>
                            <button
                              type="button"
                              className="btn btn-outline btn-sm"
                              disabled={busy}
                              onClick={()=> handleConnectionAction(connection.id, 'end')}
                            >
                              {busy ? 'Ending…' : 'End'}
                              <span style={{display:'none'}}>End</span>
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
          <div className="card" style={{marginTop:'1.5rem'}}>
            <h3 style={{marginTop:0}}>Recent updates</h3>
            {connectionsLoading ? (
              <div className="muted">Loading history…</div>
            ) : declinedConnections.length === 0 && endedConnections.length === 0 ? (
              <div className="muted">You have not declined or ended any connections yet.</div>
            ) : (
              <ul style={{margin:0, padding:0, listStyle:'none', display:'flex', flexDirection:'column', gap:'.5rem'}}>
                {[...declinedConnections, ...endedConnections].slice(0,6).map(connection => {
                  const key = connection?.id != null ? connection.id : `history-${connection?.customerId || connection?.customer_id}`
                  return (
                    <li key={key} style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                      <div>
                        <div style={{fontWeight:600}}>{connectionDisplayName(connection, 'chef')}</div>
                        <div className="muted" style={{fontSize:'.85rem'}}>{formatConnectionStatus(connection.status)}</div>
                      </div>
                      <span className="muted" style={{fontSize:'.8rem'}}>{connectionInitiatedCopy(connection)}</span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>
      )}


      {tab==='clients' && <ChefAllClients />}

      {tab==='messages' && <ChefMessagesSection />}

      {tab==='payments' && <ChefPaymentLinks />}

      {tab==='prep' && <ChefPrepPlanning />}

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
            <div className="label" style={{marginTop:'.6rem'}}>Calendly Booking Link</div>
            <input 
              type="url" 
              className="input"
              placeholder="https://calendly.com/yourname/consultation"
              value={profileForm.calendly_url}
              onChange={e => setProfileForm(f => ({ ...f, calendly_url: e.target.value }))}
            />
            <div className="muted" style={{marginTop:'.25rem'}}>
              Let customers book a consultation or tasting session with you
            </div>
            <div style={{marginTop:'.6rem'}}>
              <button className="btn btn-primary" disabled={profileSaving} onClick={async ()=>{
                setProfileSaving(true)
                try{
                  const hasBanner = Boolean(profileForm.banner_image)
                  if (profileForm.profile_pic || hasBanner){
                    if (hasBanner) setBannerUpdating(true)
                    const fd = new FormData(); fd.append('experience', profileForm.experience||''); fd.append('bio', profileForm.bio||''); fd.append('calendly_url', profileForm.calendly_url||''); if (profileForm.profile_pic) fd.append('profile_pic', profileForm.profile_pic); if (profileForm.banner_image) fd.append('banner_image', profileForm.banner_image)
                    await api.patch('/chefs/api/me/chef/profile/update/', fd, { headers: { 'Content-Type':'multipart/form-data' } })
                  } else {
                    await api.patch('/chefs/api/me/chef/profile/update/', { experience: profileForm.experience, bio: profileForm.bio, calendly_url: profileForm.calendly_url || null })
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
          
          {/* Service Areas Management */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <h3 style={{ margin: 0 }}>Service Areas</h3>
              <button 
                className="btn btn-outline btn-sm" 
                onClick={() => { setShowAreaPicker(!showAreaPicker); setNewAreaSelection([]) }}
              >
                {showAreaPicker ? 'Cancel' : '+ Request New Areas'}
              </button>
            </div>
            
            {areaStatusLoading ? (
              <div className="muted">Loading service areas...</div>
            ) : areaStatus ? (
              <>
                {/* Current approved areas */}
                {(areaStatus.approved_areas?.length > 0 || areaStatus.ungrouped_postal_codes?.length > 0) ? (
                  <div style={{ marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.85em', fontWeight: 600, textTransform: 'uppercase', opacity: 0.6, marginBottom: '0.5rem' }}>
                      Approved Service Areas ({areaStatus.total_postal_codes} postal codes)
                    </div>
                    
                    {/* Areas grouped by admin region */}
                    {areaStatus.approved_areas?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        {areaStatus.approved_areas.map(area => (
                          <span 
                            key={area.area_id} 
                            style={{
                              background: 'var(--accent-green-soft, rgba(92, 184, 92, 0.15))',
                              border: '1px solid var(--accent-green, #5cb85c)',
                              borderRadius: '6px',
                              padding: '0.35rem 0.75rem',
                              fontSize: '0.9em'
                            }}
                          >
                            {area.name}
                            {area.name_local && area.name_local !== area.name && (
                              <span style={{ opacity: 0.6, marginLeft: '0.35rem' }}>{area.name_local}</span>
                            )}
                            <span style={{ opacity: 0.5, marginLeft: '0.35rem' }}>({area.postal_code_count})</span>
                          </span>
                        ))}
                      </div>
                    )}
                    
                    {/* Individual postal codes not linked to an admin area */}
                    {areaStatus.ungrouped_postal_codes?.length > 0 && (
                      <div>
                        <div style={{ fontSize: '0.8em', opacity: 0.6, marginBottom: '0.35rem' }}>
                          Individual postal codes:
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                          {areaStatus.ungrouped_postal_codes.map(pc => (
                            <span 
                              key={pc.id} 
                              style={{
                                background: 'var(--bg-muted, #f5f5f5)',
                                border: '1px solid var(--border, #ddd)',
                                borderRadius: '4px',
                                padding: '0.25rem 0.5rem',
                                fontSize: '0.85em'
                              }}
                            >
                              {pc.code}
                              {pc.place_name && <span style={{ opacity: 0.6, marginLeft: '0.25rem' }}>({pc.place_name})</span>}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="muted" style={{ marginBottom: '1rem' }}>
                    No approved service areas yet. Request areas below.
                  </div>
                )}
                
                {/* Pending requests */}
                {areaStatus.pending_requests?.length > 0 && (
                  <div style={{ 
                    marginBottom: '1rem', 
                    padding: '0.75rem', 
                    background: 'rgba(255, 193, 7, 0.15)', 
                    borderRadius: '6px', 
                    border: '1px solid rgba(255, 193, 7, 0.4)' 
                  }}>
                    <div style={{ fontSize: '0.85em', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--text-warning, #ffc107)' }}>
                      ⏳ Pending Requests
                    </div>
                    {areaStatus.pending_requests.map(req => (
                      <div key={req.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <div>
                          <span style={{ color: 'var(--text, inherit)' }}>{req.areas.map(a => a.name).join(', ') || 'Individual codes'}</span>
                          <span style={{ marginLeft: '0.5rem', opacity: 0.7 }}>({req.total_codes_requested} codes)</span>
                        </div>
                        <button 
                          className="btn btn-outline btn-sm" 
                          onClick={() => cancelAreaRequest(req.id)}
                          style={{ color: '#ff6b6b', borderColor: '#ff6b6b' }}
                        >
                          Cancel
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Request new areas form */}
                {showAreaPicker && (
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                    <div style={{ fontSize: '0.85em', fontWeight: 600, textTransform: 'uppercase', opacity: 0.6, marginBottom: '0.5rem' }}>
                      Request Additional Areas
                    </div>
                    <p className="muted" style={{ fontSize: '0.85em', marginBottom: '0.75rem' }}>
                      Select areas you want to serve. Your request will be reviewed by an admin.
                      You'll keep your existing approved areas while the request is pending.
                    </p>
                    
                    <ServiceAreaPicker
                      country={
                        // Try multiple sources for country code
                        areaStatus?.approved_areas?.[0]?.country ||
                        areaStatus?.ungrouped_postal_codes?.[0]?.country ||
                        chef?.serving_postalcodes?.[0]?.country ||
                        'US'
                      }
                      selectedAreas={newAreaSelection}
                      onChange={setNewAreaSelection}
                      maxHeight="400px"
                    />
                    
                    <div style={{ marginTop: '0.75rem' }}>
                      <div className="label">Notes (optional)</div>
                      <textarea 
                        className="textarea" 
                        rows={2} 
                        value={areaRequestNotes}
                        onChange={e => setAreaRequestNotes(e.target.value)}
                        placeholder="Why do you want to serve these areas?"
                      />
                    </div>
                    
                    <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                      <button 
                        className="btn btn-primary"
                        disabled={submittingAreaRequest || newAreaSelection.length === 0}
                        onClick={submitAreaRequest}
                      >
                        {submittingAreaRequest ? 'Submitting...' : `Request ${newAreaSelection.length} Area${newAreaSelection.length !== 1 ? 's' : ''}`}
                      </button>
                      <button 
                        className="btn btn-outline"
                        onClick={() => { setShowAreaPicker(false); setNewAreaSelection([]) }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
                
                {/* Recent history */}
                {areaStatus.request_history?.length > 0 && !showAreaPicker && (
                  <details style={{ marginTop: '1rem' }}>
                    <summary style={{ cursor: 'pointer', fontSize: '0.85em', opacity: 0.7 }}>
                      Recent request history
                    </summary>
                    <div style={{ marginTop: '0.5rem' }}>
                      {areaStatus.request_history.map(req => {
                        const statusColors = {
                          approved: { bg: 'rgba(92, 184, 92, 0.2)', color: '#5cb85c' },
                          rejected: { bg: 'rgba(217, 83, 79, 0.2)', color: '#d9534f' },
                          partially_approved: { bg: 'rgba(91, 192, 222, 0.2)', color: '#5bc0de' },
                        }
                        const style = statusColors[req.status] || { bg: 'rgba(255,255,255,0.1)', color: 'inherit' }
                        
                        return (
                          <div key={req.id} style={{ 
                            padding: '0.5rem',
                            marginBottom: '0.35rem',
                            borderRadius: '4px',
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid var(--border-light, rgba(255,255,255,0.1))',
                            fontSize: '0.9em'
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span>
                                {req.areas_count} area{req.areas_count !== 1 ? 's' : ''} requested
                                <span style={{ marginLeft: '0.5rem', opacity: 0.6 }}>
                                  {new Date(req.created_at).toLocaleDateString()}
                                </span>
                              </span>
                              <span style={{ 
                                padding: '2px 8px', 
                                borderRadius: '3px',
                                fontSize: '0.85em',
                                background: style.bg,
                                color: style.color
                              }}>
                                {req.status_display || req.status}
                              </span>
                            </div>
                            
                            {/* Show approval details for partial approvals */}
                            {req.status === 'partially_approved' && req.approval_summary && (
                              <div style={{ marginTop: '0.5rem', fontSize: '0.85em' }}>
                                <div style={{ color: '#5cb85c' }}>
                                  ✅ Approved: {req.approval_summary.approved_areas} areas ({req.approval_summary.approved_codes} codes)
                                </div>
                                <div style={{ color: '#d9534f' }}>
                                  ❌ Rejected: {req.approval_summary.rejected_areas} areas ({req.approval_summary.rejected_codes} codes)
                                </div>
                                {req.approved_areas?.length > 0 && (
                                  <div style={{ marginTop: '0.25rem', opacity: 0.8 }}>
                                    <span style={{ fontWeight: 500 }}>Approved:</span> {req.approved_areas.map(a => a.name).join(', ')}
                                  </div>
                                )}
                                {req.rejected_areas?.length > 0 && (
                                  <div style={{ opacity: 0.6 }}>
                                    <span style={{ fontWeight: 500 }}>Not approved:</span> {req.rejected_areas.map(a => a.name).join(', ')}
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {/* Show admin notes if any */}
                            {req.admin_notes && (
                              <div style={{ marginTop: '0.35rem', fontSize: '0.85em', opacity: 0.7, fontStyle: 'italic' }}>
                                "{req.admin_notes}"
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </details>
                )}
              </>
            ) : (
              <div className="muted">Unable to load service areas</div>
            )}
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


      {tab==='kitchen' && (
        <div>
          <SectionHeader 
            title="Kitchen" 
            subtitle="Manage your ingredients, dishes, and meals"
            showAdd={false}
          />

          {/* Ingredients Section */}
          <div className="chef-kitchen-section">
            <div className="chef-kitchen-section-header">
              <div>
                <h2 className="chef-kitchen-section-title">
                  <i className="fa-solid fa-carrot" style={{fontSize:'20px'}}></i>
                  Ingredients
                  <span className="chef-count-badge">{ingredients.length}</span>
                </h2>
                <p className="muted" style={{marginTop:'.25rem', fontSize:'.9rem'}}>Building blocks for your dishes</p>
              </div>
              <button className="btn btn-primary btn-sm" onClick={()=> setShowIngredientForm(!showIngredientForm)}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                {showIngredientForm ? 'Cancel' : 'Add'}
              </button>
            </div>

            {showIngredientForm && (
              <div className="card chef-create-card" style={{marginBottom:'1rem', marginTop:'.75rem'}}>
                <h3 style={{marginTop:0}}>Create ingredient</h3>
                <form onSubmit={createIngredient}>
                  <div className="label">Name</div>
                  <input className="input" value={ingForm.name} onChange={e=> setIngForm(f=>({ ...f, name:e.target.value }))} required placeholder="e.g., Chicken Breast" />
                  {duplicateIngredient && <div className="muted" style={{marginTop:'.25rem'}}>Ingredient already exists.</div>}
                  <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit, minmax(100px, 1fr))', gap:'.5rem', marginTop:'.5rem'}}>
                    {['calories','fat','carbohydrates','protein'].map(k => (
                      <div key={k}>
                        <div className="label" style={{textTransform:'capitalize'}}>{k.replace('_',' ')}</div>
                        <input className="input" type="number" step="0.1" value={ingForm[k]} onChange={e=> setIngForm(f=>({ ...f, [k]: e.target.value }))} placeholder="0" />
                      </div>
                    ))}
                  </div>
                  {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to add ingredients.</div>}
                  <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                    <button className="btn btn-primary" disabled={!payouts.is_active || ingLoading || duplicateIngredient}>
                      {ingLoading?'Saving…':'Add Ingredient'}
                    </button>
                    <button type="button" className="btn btn-outline" onClick={()=> setShowIngredientForm(false)}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            {ingredients.length===0 ? (
              <div className="chef-empty-state chef-empty-state-compact">
                <p>No ingredients yet. Click "Add" to create your first ingredient.</p>
              </div>
            ) : (
              <div className="chef-items-grid">
                {ingredients.map(i => (
                  <div key={i.id} className="chef-item-card chef-item-card-compact">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{i.name}</div>
                      <div className="chef-item-meta">{Number(i.calories||0).toFixed(0)} cal</div>
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteIngredient(i.id)}>×</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dishes Section */}
          <div className="chef-kitchen-section">
            <div className="chef-kitchen-section-header">
              <div>
                <h2 className="chef-kitchen-section-title">
                  <i className="fa-solid fa-bowl-food" style={{fontSize:'20px'}}></i>
                  Dishes
                  <span className="chef-count-badge">{dishes.length}</span>
                </h2>
                <p className="muted" style={{marginTop:'.25rem', fontSize:'.9rem'}}>Combinations of ingredients</p>
              </div>
              <button className="btn btn-primary btn-sm" onClick={()=> setShowDishForm(!showDishForm)} disabled={ingredients.length===0}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                {showDishForm ? 'Cancel' : 'Add'}
              </button>
            </div>

            {showDishForm && (
              <div className="card chef-create-card" style={{marginBottom:'1rem', marginTop:'.75rem'}}>
                <h3 style={{marginTop:0}}>Create dish</h3>
                <form onSubmit={createDish}>
                  <div className="label">Name</div>
                  <input className="input" value={dishForm.name} onChange={e=> setDishForm(f=>({ ...f, name:e.target.value }))} required placeholder="e.g., Grilled Salmon" />
                  <div className="label">Ingredients</div>
                  <select className="select" multiple value={dishForm.ingredient_ids} onChange={e=> {
                    const opts = Array.from(e.target.selectedOptions).map(o=>o.value); setDishForm(f=>({ ...f, ingredient_ids: opts }))
                  }} style={{minHeight:120}}>
                    {ingredients.map(i => <option key={i.id} value={String(i.id)}>{i.name}</option>)}
                  </select>
                  {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to create dishes.</div>}
                  <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                    <button className="btn btn-primary" disabled={!payouts.is_active}>Create Dish</button>
                    <button type="button" className="btn btn-outline" onClick={()=> setShowDishForm(false)}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            {dishes.length===0 ? (
              <div className="chef-empty-state chef-empty-state-compact">
                <p>{ingredients.length===0 ? 'Add ingredients first, then create dishes.' : 'No dishes yet. Click "Add" to create your first dish.'}</p>
              </div>
            ) : (
              <div className="chef-items-grid">
                {dishes.map(d => (
                  <div key={d.id} className="chef-item-card chef-item-card-compact">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{d.name}</div>
                      {d.ingredients && d.ingredients.length>0 && (
                        <div className="chef-item-meta">{d.ingredients.length} ingredient{d.ingredients.length!==1?'s':''}</div>
                      )}
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteDish(d.id)}>×</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Meals Section */}
          <div className="chef-kitchen-section">
            <div className="chef-kitchen-section-header">
              <div>
                <h2 className="chef-kitchen-section-title">
                  <i className="fa-solid fa-utensils" style={{fontSize:'20px'}}></i>
                  Meals
                  <span className="chef-count-badge">{meals.length}</span>
                </h2>
                <p className="muted" style={{marginTop:'.25rem', fontSize:'.9rem'}}>Complete meals made from dishes</p>
              </div>
              <button className="btn btn-primary btn-sm" onClick={()=> setShowMealForm(!showMealForm)} disabled={dishes.length===0}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
                {showMealForm ? 'Cancel' : 'Add'}
              </button>
            </div>

            {showMealForm && (
              <div className="card chef-create-card" style={{marginBottom:'1rem', marginTop:'.75rem'}}>
                <h3 style={{marginTop:0}}>Create meal</h3>
                <form onSubmit={createMeal} aria-busy={mealSaving}>
                  <div className="label">Name</div>
                  <input className="input" value={mealForm.name} onChange={e=> setMealForm(f=>({ ...f, name:e.target.value }))} required placeholder="e.g., Sunday Family Dinner" />
                  <div className="label">Description</div>
                  <textarea className="textarea" rows={2} value={mealForm.description} onChange={e=> setMealForm(f=>({ ...f, description:e.target.value }))} placeholder="Describe this meal..." />
                  <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem', marginTop:'.5rem'}}>
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
                  <div className="label" style={{marginTop:'.5rem'}}>Dishes</div>
                  {renderDishChecklist('meal-dish')}
                  {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to create meals.</div>}
                  <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                    <button className="btn btn-primary" disabled={!payouts.is_active || mealSaving}>{mealSaving ? 'Saving…' : 'Create Meal'}</button>
                    <button type="button" className="btn btn-outline" onClick={()=> setShowMealForm(false)}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            {meals.length===0 ? (
              <div className="chef-empty-state chef-empty-state-compact">
                <p>{dishes.length===0 ? 'Add dishes first, then create meals.' : 'No meals yet. Click "Add" to create your first meal.'}</p>
              </div>
            ) : (
              <div className="chef-items-list">
                {meals.map(m => (
                  <div key={m.id} className="chef-item-card">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{m.name}</div>
                      <div className="chef-item-meta">
                        {m.meal_type} • {toCurrencyDisplay(m.price, 'USD')}
                        {m.description && ` • ${m.description.slice(0,60)}${m.description.length>60?'...':''}`}
                      </div>
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteMeal(m.id)}>Delete</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Keep old tabs hidden for backward compatibility but not in nav */}
      {tab==='ingredients' && (
        <div>
          <SectionHeader 
            title="Ingredients" 
            subtitle="Manage your ingredient library for dishes and meals"
            onAdd={()=> setShowIngredientForm(!showIngredientForm)}
            addLabel={showIngredientForm ? 'Cancel' : 'Add Ingredient'}
          />

          {showIngredientForm && (
            <div className="card chef-create-card" style={{marginBottom:'1rem'}}>
              <h3 style={{marginTop:0}}>Create ingredient</h3>
              <form onSubmit={createIngredient}>
                <div className="label">Name</div>
                <input className="input" value={ingForm.name} onChange={e=> setIngForm(f=>({ ...f, name:e.target.value }))} required />
                {duplicateIngredient && <div className="muted" style={{marginTop:'.25rem'}}>Ingredient already exists.</div>}
                <div className="grid" style={{gridTemplateColumns:'repeat(auto-fit, minmax(100px, 1fr))', gap:'.5rem', marginTop:'.5rem'}}>
                  {['calories','fat','carbohydrates','protein'].map(k => (
                    <div key={k}>
                      <div className="label" style={{textTransform:'capitalize'}}>{k.replace('_',' ')}</div>
                      <input className="input" type="number" step="0.1" value={ingForm[k]} onChange={e=> setIngForm(f=>({ ...f, [k]: e.target.value }))} />
                    </div>
                  ))}
                </div>
                {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to add ingredients.</div>}
                <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                  <button className="btn btn-primary" disabled={!payouts.is_active || ingLoading || duplicateIngredient}>
                    {ingLoading?'Saving…':'Add Ingredient'}
                  </button>
                  <button type="button" className="btn btn-outline" onClick={()=> setShowIngredientForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="card">
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'1rem'}}>
              <h3 style={{margin:0}}>Your ingredients ({ingredients.length})</h3>
            </div>
            {ingredients.length===0 ? (
              <div className="chef-empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
                  <path d="M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/>
                  <line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>
                </svg>
                <p>No ingredients yet. Click "Add Ingredient" to get started.</p>
              </div>
            ) : (
              <div className="chef-items-list">
                {ingredients.map(i => (
                  <div key={i.id} className="chef-item-card">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{i.name}</div>
                      <div className="chef-item-meta">{Number(i.calories||0).toFixed(0)} cal • {Number(i.protein||0).toFixed(1)}g protein • {Number(i.carbohydrates||0).toFixed(1)}g carbs • {Number(i.fat||0).toFixed(1)}g fat</div>
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteIngredient(i.id)}>Delete</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab==='dishes' && (
        <div>
          <SectionHeader 
            title="Dishes" 
            subtitle="Create dishes from your ingredients"
            onAdd={()=> setShowDishForm(!showDishForm)}
            addLabel={showDishForm ? 'Cancel' : 'Add Dish'}
          />

          {showDishForm && (
            <div className="card chef-create-card" style={{marginBottom:'1rem'}}>
              <h3 style={{marginTop:0}}>Create dish</h3>
              <form onSubmit={createDish}>
                <div className="label">Name</div>
                <input className="input" value={dishForm.name} onChange={e=> setDishForm(f=>({ ...f, name:e.target.value }))} required placeholder="e.g., Grilled Salmon" />
                <div className="label">Ingredients</div>
                {ingredients.length === 0 ? (
                  <div className="muted">No ingredients available. Create ingredients first.</div>
                ) : (
                  <select className="select" multiple value={dishForm.ingredient_ids} onChange={e=> {
                    const opts = Array.from(e.target.selectedOptions).map(o=>o.value); setDishForm(f=>({ ...f, ingredient_ids: opts }))
                  }} style={{minHeight:120}}>
                    {ingredients.map(i => <option key={i.id} value={String(i.id)}>{i.name}</option>)}
                  </select>
                )}
                {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to create dishes.</div>}
                <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                  <button className="btn btn-primary" disabled={!payouts.is_active || ingredients.length === 0}>Create Dish</button>
                  <button type="button" className="btn btn-outline" onClick={()=> setShowDishForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="card">
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'1rem'}}>
              <h3 style={{margin:0}}>Your dishes ({dishes.length})</h3>
            </div>
            {dishes.length===0 ? (
              <div className="chef-empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
                  <circle cx="12" cy="12" r="10"/><path d="M12 6v12M6 12h12"/>
                </svg>
                <p>No dishes yet. Click "Add Dish" to get started.</p>
              </div>
            ) : (
              <div className="chef-items-list">
                {dishes.map(d => (
                  <div key={d.id} className="chef-item-card">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{d.name}</div>
                      {d.ingredients && d.ingredients.length>0 && (
                        <div className="chef-item-meta">
                          {d.ingredients.map(x=>x.name||x).slice(0,5).join(', ')}{d.ingredients.length>5?', …':''}
                        </div>
                      )}
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteDish(d.id)}>Delete</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab==='meals' && (
        <div>
      <SectionHeader 
        title="Meals" 
        subtitle="Create complete meals from your dishes"
        onAdd={()=> setShowMealForm(!showMealForm)}
        addLabel={showMealForm ? 'Cancel' : 'Add Meal'}
      />

      {!showMealForm && (
        <div style={{display:'flex', justifyContent:'flex-end', marginBottom:'1rem'}}>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={mealSaving}
            onClick={()=> setShowMealForm(true)}
          >
            {mealSaving ? 'Saving…' : 'Create'}
          </button>
        </div>
      )}

      {showMealForm && (
        <div className="card chef-create-card" style={{marginBottom:'1rem'}}>
          <h3 style={{marginTop:0}}>Create meal</h3>
          <form onSubmit={createMeal} aria-busy={mealSaving}>
            <div className="label">Name</div>
                <input className="input" value={mealForm.name} onChange={e=> setMealForm(f=>({ ...f, name:e.target.value }))} required placeholder="e.g., Sunday Family Dinner" />
                <div className="label">Description</div>
                <textarea className="textarea" rows={2} value={mealForm.description} onChange={e=> setMealForm(f=>({ ...f, description:e.target.value }))} placeholder="Describe this meal..." />
                <div className="grid" style={{gridTemplateColumns:'1fr 1fr', gap:'.5rem', marginTop:'.5rem'}}>
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
                <div className="label" style={{marginTop:'.5rem'}}>Dishes</div>
                {renderDishChecklist('meal-dish')}
                {!payouts.is_active && <div className="muted" style={{marginTop:'.5rem'}}>Complete payouts setup to create meals.</div>}
                <div style={{marginTop:'.75rem', display:'flex', gap:'.5rem'}}>
                  <button className="btn btn-primary" disabled={!payouts.is_active || mealSaving}>{mealSaving ? 'Saving…' : 'Create Meal'}</button>
                  <button type="button" className="btn btn-outline" onClick={()=> setShowMealForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="card">
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'1rem'}}>
              <h3 style={{margin:0}}>Your meals ({meals.length})</h3>
            </div>
            {meals.length===0 ? (
              <div className="chef-empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
                  <path d="M17 21v-2a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1v2M7 21v-2a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1v2M12 11V6M12 6a4 4 0 1 0 0-8"/>
                </svg>
                <p>No meals yet. Click "Add Meal" to get started.</p>
              </div>
            ) : (
              <div className="chef-items-list">
                {meals.map(m => (
                  <div key={m.id} className="chef-item-card">
                    <div className="chef-item-info">
                      <div className="chef-item-name">{m.name}</div>
                      <div className="chef-item-meta">
                        {m.meal_type} • {toCurrencyDisplay(m.price, 'USD')}
                        {m.description && ` • ${m.description.slice(0,60)}${m.description.length>60?'...':''}`}
                      </div>
                    </div>
                    <button className="btn btn-outline btn-sm" onClick={()=> deleteMeal(m.id)}>Delete</button>
                  </div>
                ))}
              </div>
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
              <div className="label">Target customers (optional)</div>
              {acceptedCustomerOptions.length === 0 ? (
                <div className="muted" style={{fontSize:'.85rem'}}>
                  You do not have accepted connections yet. Leave this multiselect empty to publish a public offering.
                </div>
              ) : (
                <select
                  className="select"
                  multiple
                  value={serviceForm.targetCustomerIds}
                  onChange={(event)=>{
                    const values = Array.from(event.target.selectedOptions || []).map(option => option.value)
                    setServiceForm(f => ({ ...f, targetCustomerIds: values }))
                  }}
                >
                  {acceptedCustomerOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              )}
              <p className="muted" style={{margin:'0.35rem 0 0', fontSize:'.82rem'}}>
                Use the multiselect to target accepted customers. Leave it blank to keep the service visible to everyone.
              </p>
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
            <div className="card" style={{background:'var(--surface-1)', padding:'1rem', display:'flex', flexDirection:'column', gap:'.6rem'}}>
              <h3 style={{margin:'0'}}>Service tier basics</h3>
              <p className="muted" style={{margin:0, fontSize:'.9rem'}}>
                Service tiers bundle household size, price, and billing frequency so guests can spot the right fit.
              </p>
              {tierSummaryExamples.length > 0 ? (
                <div>
                  <div className="label" style={{marginTop:0}}>Examples from your offerings</div>
                  <ul style={{margin:'.35rem 0 0', paddingLeft:'1.1rem', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.9rem'}}>
                    {tierSummaryExamples.map((summary, index) => (
                      <li key={index}>{summary}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="muted" style={{fontSize:'.85rem'}}>Add tiers to see quick examples of how pricing appears to guests.</div>
              )}
              <p className="muted" style={{margin:0, fontSize:'.85rem'}}>
                Household range defines who each tier covers, and recurring options handle weekly or monthly plans.
              </p>
              <p className="muted" style={{margin:0, fontSize:'.85rem'}}>
                Stripe sync runs automatically once you save a tier—check the status chips below if something looks off.
              </p>
            </div>
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
                    const tierSummaries = Array.isArray(offering?.tier_summary)
                      ? offering.tier_summary.reduce((acc, summary) => {
                          const text = typeof summary === 'string' ? summary.trim() : String(summary || '').trim()
                          if (text) acc.push(text)
                          return acc
                        }, [])
                      : []
                    const isEditingTier = tierForm.offeringId === offering.id
                    const serviceTypeLabel = offering.service_type_label || toServiceTypeLabel(offering.service_type)
                    return (
                      <div key={offering.id} className="card" style={{padding:'.75rem'}}>
                      <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'.75rem', flexWrap:'wrap'}}>
                        <div>
                          <h4 style={{margin:'0 0 .25rem 0'}}>{offering.title || 'Untitled service'}</h4>
                          <div className="muted" style={{marginBottom:'.25rem'}}>{serviceTypeLabel}</div>
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
                      {tierSummaries.length > 0 && (
                        <div style={{marginTop:'.65rem'}}>
                          <div className="label" style={{marginTop:0}}>Tier overview</div>
                          <ul style={{margin:'.3rem 0 0', paddingLeft:'1.1rem', display:'flex', flexDirection:'column', gap:'.25rem', fontSize:'.9rem'}}>
                            {tierSummaries.map((summary, idx) => (
                              <li key={idx}>{summary}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <div style={{marginTop:'.75rem'}}>
                        <div className="label" style={{marginTop:0}}>Tiers</div>
                        {tiers.length===0 ? (
                          <div className="muted">No tiers yet.</div>
                        ) : (
                          <div style={{display:'flex', flexDirection:'column', gap:'.5rem'}}>
                            {tiers.map(tier => {
                              const priceDollars = tier.desired_unit_amount_cents != null ? (Number(tier.desired_unit_amount_cents)/100).toFixed(2) : '0.00'
                              const syncError = tier.last_price_sync_error || tier.price_sync_error || tier.sync_error || tier.price_sync_message || tier.last_error || ''
                              const rawStatus = String(tier.price_sync_status || tier.price_sync_state || '').toLowerCase()
                              let syncLabel = 'Stripe sync pending'
                              let syncChipStyle = { background: 'rgba(60,100,200,.15)', color: '#1b3a72' }
                              if (['success', 'synced', 'complete', 'completed'].includes(rawStatus)){
                                syncLabel = 'Stripe sync successful'
                                syncChipStyle = { background: 'rgba(24,180,24,.15)', color: '#168516' }
                              } else if (['error', 'failed', 'failure'].includes(rawStatus)){
                                syncLabel = 'Stripe sync failed'
                                syncChipStyle = { background: 'rgba(200,40,40,.15)', color: '#a11919' }
                              } else if (['processing', 'pending', 'queued', 'running', 'updating'].includes(rawStatus) || !rawStatus){
                                syncLabel = 'Stripe sync pending'
                                syncChipStyle = { background: 'rgba(60,100,200,.15)', color: '#1b3a72' }
                              } else {
                                syncLabel = `Stripe sync ${rawStatus}`
                                syncChipStyle = { background: 'rgba(60,100,200,.15)', color: '#1b3a72' }
                              }
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
                                        <span className="chip" style={syncChipStyle}>{syncLabel}</span>
                                        {!tier.active && <span className="chip" style={{marginLeft:'.35rem'}}>Inactive</span>}
                                      </div>
                                      {syncError && <div style={{marginTop:'.25rem', color:'#a11919', fontSize:'.85rem'}}>{syncError}</div>}
                                      {syncText && <div className="muted" style={{marginTop:'.25rem', fontSize:'.75rem'}}>Last synced: {syncText}</div>}
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
                          <div className="muted" style={{marginTop:'.35rem', fontSize:'.85rem'}}>
                            Household range defines how many people each tier covers.
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
                          <div className="muted" style={{marginTop:'.25rem', fontSize:'.85rem'}}>
                            Recurring tiers automatically handle future invoices.
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
                          <div className="muted" style={{marginTop:'.35rem', fontSize:'.85rem'}}>
                            Stripe creates or updates prices after you save a tier.
                          </div>
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
        <div style={{display:'flex', flexDirection:'column', gap:'1rem'}}>
          <div className="card">
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:'.75rem'}}>
              <h3 style={{margin:0}}>Service orders</h3>
              <span className="chip" style={{background:'var(--surface-2)', color:'var(--muted)', border:'1px solid color-mix(in oklab, var(--border) 70%, transparent)'}}>
                {serviceOrdersLoading ? 'Loading…' : `${serviceOrders.length} ${serviceOrders.length===1?'order':'orders'}`}
              </span>
            </div>
            {serviceOrdersLoading ? (
              <div className="muted" style={{marginTop:'.75rem'}}>Fetching your service bookings…</div>
            ) : serviceOrders.length === 0 ? (
              <div className="muted" style={{marginTop:'.75rem'}}>No service orders yet. Share your profile to collect bookings.</div>
            ) : (
              <div style={{display:'flex', flexDirection:'column', gap:'.75rem', marginTop:'.75rem'}}>
                {serviceOrders.map(order => {
                  const statusMeta = serviceStatusTone(order.status)
                  const tierLabel = extractTierLabel(order)
                  const priceLabel = order.price_summary || order.total_display || toCurrencyDisplay(order.total_value_for_chef, order.currency || order.order_currency)
                  const scheduleLabel = formatServiceSchedule(order)
                  const recurring = order.is_subscription ? 'Recurring billing' : ''
                  const detail = serviceCustomerDetails?.[order.customer] || serviceCustomerDetails?.[String(order.customer)] || null
                  const displayName = serviceCustomerName(order, detail)
                  const contactLine = detail?.email || order.customer_email || detail?.username || order.customer_username || ''
                  return (
                    <div key={order.id || order.order_id} className="card" style={{border:'1px solid var(--border)', borderRadius:'12px', padding:'.75rem', background:'var(--surface-2)'}}>
                      <div style={{display:'flex', justifyContent:'space-between', flexWrap:'wrap', gap:'.5rem'}}>
                        <div>
                          <div style={{fontWeight:700}}>{displayName}</div>
                          {contactLine && (
                            <div className="muted" style={{fontSize:'.85rem'}}>{contactLine}</div>
                          )}
                          <div className="muted" style={{fontSize:'.9rem'}}>{serviceOfferingTitle(order)}{tierLabel ? ` · ${tierLabel}` : ''}</div>
                        </div>
                        <span className="status-text status-text--blue">{statusMeta.label}</span>
                      </div>
                      <div className="muted" style={{marginTop:'.45rem', fontSize:'.9rem'}}>{scheduleLabel}</div>
                      {(recurring || priceLabel) && (
                        <div style={{display:'flex', gap:'.4rem', flexWrap:'wrap', marginTop:'.5rem', fontSize:'.85rem'}}>
                          {priceLabel && <span className="chip small soft" style={{background:'rgba(92,184,92,.12)', color:'#1f7a3d'}}>{priceLabel}</span>}
                          {recurring && <span className="chip small soft" style={{background:'rgba(60,100,200,.12)', color:'#1b3a72'}}>{recurring}</span>}
                        </div>
                      )}
                      {order.special_requests && (
                        <div className="muted" style={{marginTop:'.5rem', fontSize:'.85rem'}}>
                          <strong style={{fontWeight:600, color:'var(--text)'}}>Notes:</strong> {order.special_requests}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="card">
            <h3>Meal orders</h3>
            {orders.length===0 ? (
              <div className="muted">No meal orders yet.</div>
            ) : (
              <ul style={{marginTop:'.5rem', display:'flex', flexDirection:'column', gap:'.4rem', paddingLeft:'1.05rem'}}>
                {orders.map(o => (
                  <li key={o.id || o.order_id}>
                    <strong>{o.customer_username || o.customer_name || 'Customer'}</strong>
                    <span className="muted"> — {o.status || 'pending'}</span>
                    {o.total_value_for_chef ? <span className="muted"> — {toCurrencyDisplay(o.total_value_for_chef, o.currency || 'USD')}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      </main>

      {/* Floating Sous Chef Widget - always visible */}
      {chef && (
        <SousChefWidget
          sousChefEmoji={chef.sous_chef_emoji || '🧑‍🍳'}
          onEmojiChange={(emoji) => {
            setChef(prev => prev ? { ...prev, sous_chef_emoji: emoji } : prev)
          }}
        />
      )}
    </div>
    </SousChefNotificationProvider>
  )
}
