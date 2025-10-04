import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import { countryNameFromCode } from '../utils/geo.js'

function renderAreas(areas){
  if (!Array.isArray(areas) || areas.length === 0) return []
  return areas
    .map(p => (p?.postal_code || p?.postalcode || p?.code || p?.name || ''))
    .filter(Boolean)
}

function renderAreasString(areas){
  const codes = renderAreas(areas)
  return codes.join(', ')
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
  const [loading, setLoading] = useState(true)
  const [chefs, setChefs] = useState([])
  const [error, setError] = useState(null)
  const [onlyServesMe, setOnlyServesMe] = useState(false)
  const [query, setQuery] = useState('')
  
  const [userDetailsById, setUserDetailsById] = useState({})

  const mePostal = user?.postal_code || user?.address?.postalcode || ''

  const filtered = useMemo(()=>{
    const q = (query||'').toLowerCase()
    return chefs.filter(c => {
      const name = c?.user?.username?.toLowerCase?.() || ''
      const areas = renderAreas(c?.serving_postalcodes)
      const areasStr = areas.join(', ').toLowerCase()
      const matchQ = !q || name.includes(q) || areasStr.includes(q)
      if (!matchQ) return false
      if (onlyServesMe && mePostal){
        return areas.includes(mePostal)
      }
      return true
    })
  }, [chefs, query, onlyServesMe, mePostal])

  useEffect(()=>{ document.title = 'sautai — Chefs' }, [])

  useEffect(()=>{
    let mounted = true
    setLoading(true)
    setError(null)
    
    api.get('/chefs/api/public/', { skipUserId: true })
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
  }, [])

  return (
    <div className="page-chefs-directory">
      {/* Hero Section */}
      <div className="chefs-hero">
        <div className="chefs-hero-content">
          <h1 className="chefs-hero-title">
            <i className="fa-solid fa-hat-chef" style={{marginRight: '0.5rem'}}></i>
            Find Your Chef
          </h1>
          <p className="chefs-hero-subtitle">
            Connect with talented chefs in your area for personalized meal experiences
          </p>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="chefs-search-bar">
        <div className="chefs-search-content">
          <div className="search-input-wrapper">
            <i className="fa-solid fa-search search-icon"></i>
            <input 
              className="search-input" 
              placeholder="Search by chef name or service area…" 
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
          {mePostal && (
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
        </div>
        {(query || onlyServesMe) && (
          <div className="chefs-results-summary">
            <span className="results-count">
              {filtered.length} {filtered.length === 1 ? 'chef' : 'chefs'} found
            </span>
            {(query || onlyServesMe) && (
              <button 
                className="clear-all-btn"
                onClick={() => {
                  setQuery('')
                  setOnlyServesMe(false)
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
              {query || onlyServesMe 
                ? 'Try adjusting your search or filters' 
                : 'No chefs are currently available'}
            </p>
            {(query || onlyServesMe) && (
              <button 
                className="btn btn-primary"
                onClick={() => {
                  setQuery('')
                  setOnlyServesMe(false)
                }}
              >
                Clear filters
              </button>
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
              const serviceAreas = renderAreas(c.serving_postalcodes)
              const photoCount = c?.photos?.length || 0
              const bio = c?.bio || ''
              
              return (
                <Link 
                  key={c.id} 
                  to={`/c/${encodeURIComponent(c?.user?.username || c.id)}`} 
                  className="chef-card"
                >
                  <div className="chef-card-header">
                    <div className="chef-avatar-wrapper">
                      {c.profile_pic_url ? (
                        <img 
                          src={c.profile_pic_url} 
                          alt={c?.user?.username||'Chef'} 
                          className="chef-avatar"
                        />
                      ) : (
                        <div className="chef-avatar-placeholder">
                          <i className="fa-solid fa-user"></i>
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
    </div>
  )
}


