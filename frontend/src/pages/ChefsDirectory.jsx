import React, { useEffect, useMemo, useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import { useConnections } from '../hooks/useConnections.js'
import { countryNameFromCode } from '../utils/geo.js'
import { getSeededChefEmoji } from '../utils/emojis.js'

// Get chef emoji - use their chosen one or a seeded random for consistency
function getChefEmoji(chef) {
  if (chef?.sous_chef_emoji) return chef.sous_chef_emoji
  return getSeededChefEmoji(chef?.id || 0)
}

// Countries with flag emojis for the discover filter
const FEATURED_COUNTRIES = [
  { code: '', label: 'All Countries', flag: '🌍' },
  { code: 'US', label: 'United States', flag: '🇺🇸' },
  { code: 'CA', label: 'Canada', flag: '🇨🇦' },
  { code: 'GB', label: 'United Kingdom', flag: '🇬🇧' },
  { code: 'AU', label: 'Australia', flag: '🇦🇺' },
  { code: 'DE', label: 'Germany', flag: '🇩🇪' },
  { code: 'FR', label: 'France', flag: '🇫🇷' },
  { code: 'IT', label: 'Italy', flag: '🇮🇹' },
  { code: 'ES', label: 'Spain', flag: '🇪🇸' },
  { code: 'JP', label: 'Japan', flag: '🇯🇵' },
  { code: 'MX', label: 'Mexico', flag: '🇲🇽' },
  { code: 'IN', label: 'India', flag: '🇮🇳' },
  { code: 'BR', label: 'Brazil', flag: '🇧🇷' },
]

// Get raw postal codes array for filtering
function getPostalCodes(areas){
  if (!Array.isArray(areas) || areas.length === 0) return []
  return areas
    .map(p => (p?.postal_code || p?.postalcode || p?.code || p?.name || ''))
    .filter(Boolean)
}

/**
 * Render service areas as an array of user-friendly summary strings
 * Groups by country and shows city names or area counts
 * Returns array for use in tag display
 */
function renderAreas(areas){
  if (!Array.isArray(areas) || areas.length === 0) return []
  
  // Group by country
  const byCountry = {}
  for (const p of areas) {
    const countryCode = p?.country?.code || p?.country || ''
    const countryName = p?.country?.name || countryCode || 'Unknown'
    const city = (p?.city || p?.place_name || '').trim()
    
    if (!byCountry[countryName]) {
      byCountry[countryName] = { cities: new Set(), count: 0 }
    }
    byCountry[countryName].count++
    if (city) byCountry[countryName].cities.add(city)
  }
  
  // Build summary strings as array
  const summaries = []
  for (const [country, data] of Object.entries(byCountry)) {
    const cities = Array.from(data.cities).slice(0, 3)
    if (cities.length > 0 && data.count <= 10) {
      // Show city names
      cities.forEach(city => summaries.push(city))
    } else if (data.count > 1) {
      // Show count for large areas
      summaries.push(`${data.count} areas in ${country}`)
    } else {
      summaries.push(cities[0] || country)
    }
  }
  
  return summaries
}

function extractCountryCode(chef) {
  const sp = Array.isArray(chef?.serving_postalcodes) ? chef.serving_postalcodes : []
  return sp.map(p => (p?.country?.code || p?.country || p?.country_code || '')).find(v => String(v||'').trim()) || ''
}

function extractCityCountry(chef, authUser){
  // Mirror the logic used on the PublicChef profile page
  
  const isSelf = authUser && (chef?.user?.id === authUser?.id || chef?.user?.username === authUser?.username)
  const sp = Array.isArray(chef?.serving_postalcodes) ? chef.serving_postalcodes : []
  const spCity = sp.map(p=> (p?.city||'').trim()).find(Boolean) || ''
  const spCountryRaw = sp.map(p=> (p?.country?.code || p?.country?.name || p?.country || p?.country_code || '')).find(v=> String(v||'').trim()) || ''
  const city = String(
    chef?.city || chef?.location_city || chef?.location?.city || chef?.address?.city || chef?.user?.address?.city || spCity ||
    (isSelf ? (authUser?.address?.city || '') : '')
  ).trim()
  let countryRaw = (
    chef?.country || chef?.location_country || chef?.location?.country || chef?.address?.country || chef?.user?.address?.country || spCountryRaw ||
    chef?.country_code || chef?.countryCode || chef?.location?.country_code || chef?.address?.country_code || chef?.user?.address?.country_code ||
    (isSelf ? (authUser?.address?.country || authUser?.address?.country_code || '') : '')
  )
  countryRaw = String(countryRaw || '').trim()
  const country = countryRaw.length === 2 ? countryNameFromCode(countryRaw) : countryRaw
  if (city && country) return `${city}, ${country}`
  return city || country || ''
}

export default function ChefsDirectory(){
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [chefs, setChefs] = useState([])
  const [error, setError] = useState(null)
  const [onlyServesMe, setOnlyServesMe] = useState(false)
  const [query, setQuery] = useState('')
  // Read initial country from URL params (e.g., /chefs?country=US)
  const [selectedCountry, setSelectedCountry] = useState(() => searchParams.get('country') || '')
  
  const [userDetailsById, setUserDetailsById] = useState({})
  const [addingChefId, setAddingChefId] = useState(null)
  
  const isGuest = !user
  
  // Connection management for quick add button
  const {
    requestConnection,
    requestStatus,
    getConnectionForChef,
    hasActiveConnectionForChef
  } = useConnections('customer')
  
  const viewerId = user?.id ?? user?.user_id ?? null
  
  // Get connection status for a chef
  const getChefConnectionState = useCallback((chefId) => {
    if (!user || !chefId) return { state: 'none', canAdd: false }
    const connection = getConnectionForChef(chefId)
    if (!connection) return { state: 'none', canAdd: true }
    if (connection.isAccepted) return { state: 'connected', canAdd: false }
    if (connection.isPending) return { state: 'pending', canAdd: false }
    return { state: 'none', canAdd: !hasActiveConnectionForChef(chefId) }
  }, [user, getConnectionForChef, hasActiveConnectionForChef])
  
  // Handle quick add chef from card
  const handleQuickAdd = useCallback(async (e, chefId) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (!user) {
      // Redirect to login
      const next = window.location.pathname + window.location.search
      window.location.href = `/login?next=${encodeURIComponent(next)}`
      return
    }
    
    if (!chefId || !viewerId) return
    
    setAddingChefId(chefId)
    try {
      await requestConnection({ chefId, customerId: viewerId })
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: 'Request sent! The chef will be notified.', tone: 'success' } 
      }))
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Unable to send request right now.'
      window.dispatchEvent(new CustomEvent('global-toast', { 
        detail: { text: msg, tone: 'error' } 
      }))
    } finally {
      setAddingChefId(null)
    }
  }, [user, viewerId, requestConnection])
  
  // Update URL when country changes
  const handleCountryChange = (code) => {
    setSelectedCountry(code)
    if (code) {
      setSearchParams({ country: code })
    } else {
      setSearchParams({})
    }
  }

  const mePostal = user?.postal_code || user?.address?.postalcode || ''

  const filtered = useMemo(()=>{
    const q = (query||'').toLowerCase()
    return chefs.filter(c => {
      const name = c?.user?.username?.toLowerCase?.() || ''
      const postalCodes = getPostalCodes(c?.serving_postalcodes)
      const areasStr = postalCodes.join(', ').toLowerCase()
      const matchQ = !q || name.includes(q) || areasStr.includes(q)
      if (!matchQ) return false
      if (onlyServesMe && mePostal){
        return postalCodes.includes(mePostal)
      }
      // Country filter (client-side backup for any chefs already loaded)
      if (selectedCountry) {
        const chefCountry = extractCountryCode(c)
        if (chefCountry !== selectedCountry) return false
      }
      return true
    })
  }, [chefs, query, onlyServesMe, mePostal, selectedCountry])

  useEffect(()=>{ document.title = 'sautai — Discover Chefs' }, [])

  useEffect(()=>{
    let mounted = true
    setLoading(true)
    setError(null)
    
    // Build API params - filter by country if selected
    const params = {}
    if (selectedCountry) {
      params.country = selectedCountry
    }
    
    api.get('/chefs/api/public/', { params, skipUserId: true })
      .then(async res => { 
        const list = Array.isArray(res.data)? res.data : (res.data?.results||[])
        
        if (!mounted) return
        setChefs(list)
        const ids = Array.from(new Set(list.map(c => c?.user?.id).filter(Boolean)))
        if (ids.length){
          try{
            const entries = await Promise.all(ids.map(async uid => {
              try{
                const r = await api.get('/auth/api/user_details/', { params: { user_id: uid }, skipUserId: true })
                return [uid, r?.data||null]
              }catch{ return [uid, null] }
            }))
            if (!mounted) return
            setUserDetailsById(Object.fromEntries(entries))
          }catch{}
        }
      })
      .catch((e)=> { if (mounted) setError('Unable to load chefs.') })
      .finally(()=> { if (mounted) setLoading(false) })
    return ()=>{ mounted = false }
  }, [selectedCountry])

  return (
    <div className="page-chefs-directory">
      {/* Hero Section */}
      <div className="chefs-hero">
        <div className="chefs-hero-content">
          <h1 className="chefs-hero-title">
            {isGuest ? (
              <>
                <span className="hero-globe">🌍</span>
                Discover Chefs Worldwide
              </>
            ) : (
              <>
                <i className="fa-solid fa-hat-chef" style={{marginRight: '0.5rem'}}></i>
                Find Your Chef
              </>
            )}
          </h1>
          <p className="chefs-hero-subtitle">
            {isGuest 
              ? 'Explore talented chefs from around the world and discover the amazing foods they create'
              : 'Connect with talented chefs in your area for personalized meal experiences'
            }
          </p>
          {isGuest && (
            <p className="chefs-hero-tagline">
              <span className="tagline-icon">✨</span>
              Browse chef profiles, see their culinary creations, and find inspiration from global cuisines
            </p>
          )}
        </div>
      </div>

      {/* Country Discovery Bar - prominent for guests */}
      {isGuest && (
        <div className="country-discover-bar">
          <div className="country-discover-label">
            <span className="discover-icon">🗺️</span>
            <span>Explore by region:</span>
          </div>
          <div className="country-pills">
            {FEATURED_COUNTRIES.map(c => (
              <button
                key={c.code}
                className={`country-pill${selectedCountry === c.code ? ' active' : ''}`}
                onClick={() => handleCountryChange(c.code)}
              >
                <span className="country-flag">{c.flag}</span>
                <span className="country-name">{c.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="chefs-search-bar">
        <div className="chefs-search-content">
          <div className="search-input-wrapper">
            <i className="fa-solid fa-search search-icon"></i>
            <input 
              className="search-input" 
              placeholder={isGuest ? "Search chefs by name or location…" : "Search by chef name or service area…"}
              value={query} 
              onChange={e=> setQuery(e.target.value)} 
            />
            {query && (
              <button 
                className="search-clear"
                onClick={() => setQuery('')}
                aria-label="Clear search"
              >
                <i className="fa-solid fa-times"></i>
              </button>
            )}
          </div>
          {/* Authenticated user filters */}
          {!isGuest && mePostal && (
            <label className="filter-checkbox">
              <input 
                type="checkbox" 
                checked={onlyServesMe} 
                onChange={e=> setOnlyServesMe(e.target.checked)} 
              />
              <span className="checkbox-label">
                <i className="fa-solid fa-location-dot"></i>
                Serves my area ({mePostal})
              </span>
            </label>
          )}
          {/* Country filter dropdown for authenticated users */}
          {!isGuest && (
            <select 
              className="country-select"
              value={selectedCountry}
              onChange={e => handleCountryChange(e.target.value)}
            >
              {FEATURED_COUNTRIES.map(c => (
                <option key={c.code} value={c.code}>{c.flag} {c.label}</option>
              ))}
            </select>
          )}
        </div>
        {(query || onlyServesMe || selectedCountry) && (
          <div className="chefs-results-summary">
            <span className="results-count">
              {filtered.length} {filtered.length === 1 ? 'chef' : 'chefs'} found
              {selectedCountry && !isGuest && (
                <span className="results-filter-tag">
                  {FEATURED_COUNTRIES.find(c => c.code === selectedCountry)?.flag} {FEATURED_COUNTRIES.find(c => c.code === selectedCountry)?.label}
                </span>
              )}
            </span>
            {(query || onlyServesMe || selectedCountry) && (
              <button 
                className="clear-all-btn"
                onClick={() => {
                  setQuery('')
                  setOnlyServesMe(false)
                  handleCountryChange('')
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="chefs-container">
        {loading && (
          <div className="chefs-loading">
            <div className="spinner" style={{width: 40, height: 40, borderWidth: 4}}></div>
            <p>Finding chefs...</p>
          </div>
        )}
        
        {!loading && error && (
          <div className="chefs-error">
            <i className="fa-solid fa-triangle-exclamation"></i>
            <h3>Unable to load chefs</h3>
            <p>{error}</p>
          </div>
        )}
        
        {!loading && !error && filtered.length === 0 && (
          <div className="chefs-empty">
            <i className="fa-solid fa-search"></i>
            <h3>No chefs found</h3>
            <p className="muted">
              {query || onlyServesMe || selectedCountry
                ? 'Try adjusting your search or filters' 
                : 'No chefs are currently available'}
            </p>
            {(query || onlyServesMe || selectedCountry) && (
              <button 
                className="btn btn-primary"
                onClick={() => {
                  setQuery('')
                  setOnlyServesMe(false)
                  handleCountryChange('')
                }}
              >
                Clear filters
              </button>
            )}
            {isGuest && !query && !selectedCountry && (
              <p className="muted" style={{marginTop: '1rem'}}>
                More chefs are joining sautai every day. Check back soon!
              </p>
            )}
          </div>
        )}
        
        {!loading && !error && filtered.length > 0 && (
          <div className="chefs-grid">
            {filtered.map(c => {
              const chefUser = {
                ...c,
                user: { ...(c?.user||{}), address: (userDetailsById?.[c?.user?.id]?.address || c?.user?.address) }
              }
              const location = extractCityCountry(chefUser, user)
              const chefCountryCode = extractCountryCode(c)
              const countryInfo = FEATURED_COUNTRIES.find(fc => fc.code === chefCountryCode)
              const serviceAreas = renderAreas(c.serving_postalcodes)
              const photoCount = c?.photos?.length || 0
              const bio = c?.bio || ''
              
              // Connection state for quick add button
              const chefId = c?.id
              const isOwnProfile = user && (c?.user?.id === user?.id)
              const connectionState = getChefConnectionState(chefId)
              const isAddingThis = addingChefId === chefId
              
              return (
                <Link 
                  key={c.id} 
                  to={`/c/${encodeURIComponent(c?.user?.username || c.id)}`} 
                  className="chef-card"
                >
                  {/* Country flag badge for global discovery */}
                  {isGuest && countryInfo && (
                    <div className="chef-country-badge" title={countryInfo.label}>
                      {countryInfo.flag}
                    </div>
                  )}
                  
                  {/* Quick Add Button - Social media style */}
                  {!isOwnProfile && (
                    <div className="chef-card-quick-add">
                      {connectionState.state === 'connected' ? (
                        <span className="quick-add-badge connected" title="Connected">
                          <i className="fa-solid fa-check"></i>
                        </span>
                      ) : connectionState.state === 'pending' ? (
                        <span className="quick-add-badge pending" title="Request pending">
                          <i className="fa-solid fa-clock"></i>
                        </span>
                      ) : (
                        <button 
                          className="quick-add-btn"
                          onClick={(e) => handleQuickAdd(e, chefId)}
                          disabled={isAddingThis}
                          title={user ? "Add this chef" : "Sign in to add chef"}
                        >
                          {isAddingThis ? (
                            <div className="quick-add-spinner"></div>
                          ) : (
                            <i className="fa-solid fa-user-plus"></i>
                          )}
                        </button>
                      )}
                    </div>
                  )}
                  
                  <div className="chef-card-header">
                    <div className="chef-avatar-wrapper">
                      {c.profile_pic_url ? (
                        <img 
                          src={c.profile_pic_url} 
                          alt={c?.user?.username||'Chef'} 
                          className="chef-avatar"
                        />
                      ) : (
                        <div className="chef-avatar-emoji">
                          <span role="img" aria-label="chef">{getChefEmoji(c)}</span>
                        </div>
                      )}
                    </div>
                    <div className="chef-card-info">
                      <h3 className="chef-name">{c?.user?.username || 'Chef'}</h3>
                      {location && (
                        <div className="chef-location">
                          <i className="fa-solid fa-location-dot"></i>
                          <span>{location}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  {bio && (
                    <p className="chef-bio">{bio}</p>
                  )}
                  
                  <div className="chef-card-footer">
                    {serviceAreas.length > 0 && (
                      <div className="chef-service-areas">
                        <i className="fa-solid fa-map-pin"></i>
                        <div className="service-area-tags">
                          {serviceAreas.slice(0, 3).map((area, idx) => (
                            <span key={idx} className="service-area-tag">{area}</span>
                          ))}
                          {serviceAreas.length > 3 && (
                            <span className="service-area-tag more">+{serviceAreas.length - 3}</span>
                          )}
                        </div>
                      </div>
                    )}
                    {photoCount > 0 && (
                      <div className="chef-stat">
                        <i className="fa-solid fa-images"></i>
                        <span>{photoCount} {photoCount === 1 ? 'photo' : 'photos'}</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="chef-card-action">
                    <span>View Profile</span>
                    <i className="fa-solid fa-arrow-right"></i>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </div>
      
      {/* Guest CTA Section */}
      {isGuest && !loading && (
        <div className="guest-cta-section">
          <div className="guest-cta-card">
            <div className="guest-cta-icon">👨‍🍳</div>
            <h3>Ready to connect with a chef?</h3>
            <p>Create a free account to contact chefs, get personalized meal plans, and discover local culinary talent in your area.</p>
            <div className="guest-cta-actions">
              <Link to="/register" className="btn btn-primary">Create Free Account</Link>
              <Link to="/login" className="btn btn-outline">Sign In</Link>
            </div>
          </div>
          <div className="guest-cta-card">
            <div className="guest-cta-icon">🍳</div>
            <h3>Are you a chef?</h3>
            <p>Join sautai to grow your culinary business, manage clients, and connect with food lovers around the world.</p>
            <div className="guest-cta-actions">
              <Link to="/register" className="btn btn-primary">Start Your Profile</Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


