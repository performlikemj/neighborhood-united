import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom'
import { api } from '../api.js'

export default function ChefGallery(){
  const { username } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  
  // Chef & Stats
  const [chef, setChef] = useState(null)
  const [stats, setStats] = useState(null)
  const [loadingChef, setLoadingChef] = useState(true)
  const [loadingStats, setLoadingStats] = useState(true)
  
  // Photos & Pagination
  const [photos, setPhotos] = useState([])
  const [loadingPhotos, setLoadingPhotos] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [totalCount, setTotalCount] = useState(0)
  
  // Filters
  const [activeTags, setActiveTags] = useState([])
  const [sortNewest, setSortNewest] = useState(true) // true = newest first, false = oldest first
  
  // Lightbox
  const [lightboxIndex, setLightboxIndex] = useState(-1)
  
  // Refs
  const galleryRef = useRef(null)
  const bodyScrollRestoreRef = useRef('')
  const observerTarget = useRef(null)
  
  // Error
  const [error, setError] = useState(null)
  
  // Active photo for lightbox
  const activePhoto = useMemo(()=>{
    if (lightboxIndex < 0 || !photos.length) return null
    return photos[lightboxIndex] || null
  }, [lightboxIndex, photos])
  
  const activePhotoDateLabel = useMemo(()=>{
    if (!activePhoto?.created_at) return ''
    const parsed = new Date(activePhoto.created_at)
    if (Number.isNaN(parsed.getTime())) return ''
    try{
      return parsed.toLocaleDateString(undefined, { month:'long', day:'numeric', year:'numeric' })
    }catch{
      return parsed.toISOString().split('T')[0]
    }
  }, [activePhoto?.created_at])

  const updatePhotoQuery = useCallback((value)=>{
    const params = new URLSearchParams(location.search)
    if (value === null || value === undefined || value === ''){
      params.delete('photo')
    } else {
      params.set('photo', String(value))
    }
    const search = params.toString()
    navigate({ search: search ? `?${search}` : '' }, { replace: true })
  }, [location.search, navigate])

  const openPhotoAt = useCallback((index)=>{
    if (index < 0 || index >= photos.length) return
    setLightboxIndex(index)
    const target = photos[index]
    const token = target?.id != null ? target.id : index
    updatePhotoQuery(token)
  }, [photos, updatePhotoQuery])

  const closeLightbox = useCallback(()=>{
    setLightboxIndex(-1)
    updatePhotoQuery(null)
  }, [updatePhotoQuery])

  useEffect(()=>{
    const params = new URLSearchParams(location.search)
    const photoParam = params.get('photo')
    if (!photoParam){
      if (lightboxIndex !== -1){
        setLightboxIndex(-1)
      }
      return
    }
    if (!photos.length) return
    let nextIndex = photos.findIndex(p => String(p.id) === photoParam)
    if (nextIndex < 0){
      const numeric = Number(photoParam)
      if (Number.isInteger(numeric) && numeric >= 0 && numeric < photos.length){
        nextIndex = numeric
      }
    }
    if (nextIndex < 0){
      if (lightboxIndex !== -1){
        setLightboxIndex(-1)
      }
      return
    }
    if (nextIndex !== lightboxIndex){
      setLightboxIndex(nextIndex)
    }
  }, [location.search, photos, lightboxIndex])

  // Fetch chef profile (using existing endpoint structure)
  useEffect(()=>{
    let cancelled = false
    setLoadingChef(true)
    setError(null)
    
    const fetchChef = async () => {
      try {
        // Try public endpoint first (existing structure)
        const isNumeric = /^\d+$/.test(username)
        let response
        
        if (!isNumeric) {
          // Try by-username endpoint
          try {
            response = await api.get(`/chefs/api/public/by-username/${encodeURIComponent(username)}/`, { skipUserId: true })
          } catch(e) {
            // Fallback to lookup
            const lookup = await api.get(`/chefs/api/lookup/by-username/${encodeURIComponent(username)}/`, { skipUserId: true })
            const chefId = lookup?.data?.chef_id || lookup?.data?.id
            if (chefId) {
              response = await api.get(`/chefs/api/public/${chefId}/`, { skipUserId: true })
            }
          }
        } else {
          // Numeric username maps directly to chef ID
          response = await api.get(`/chefs/api/public/${username}/`, { skipUserId: true })
        }
        
        if (cancelled) return
        if (response?.data) {
          setChef(response.data)
          // If photos exist, use them directly
          if (response.data.photos && Array.isArray(response.data.photos)) {
            setPhotos(response.data.photos)
            setTotalCount(response.data.photos.length)
            setHasMore(false)
            setLoadingPhotos(false)
          }
        } else {
          setError('Chef not found')
        }
      } catch(err) {
        if (cancelled) return
        console.error('Failed to load chef:', err)
        setError(err.response?.status === 404 ? 'Chef not found' : 'Failed to load chef profile')
      } finally {
        if (!cancelled) setLoadingChef(false)
      }
    }
    
    fetchChef()
    return ()=> { cancelled = true }
  }, [username])
  
  // Fetch gallery stats (optional - falls back to client-side computation)
  useEffect(()=>{
    let cancelled = false
    setLoadingStats(true)
    
    // Try new endpoint if available, otherwise compute from photos
    api.get(`/chefs/api/${username}/gallery/stats/`)
      .then(res => {
        if (cancelled) return
        setStats(res.data)
      })
      .catch(err => {
        if (cancelled) return
        // Endpoint doesn't exist yet - compute stats from chef.photos if available
        if (chef?.photos && Array.isArray(chef.photos)) {
          const categories = {}
          const tagsMap = {}
          
          chef.photos.forEach(photo => {
            if (photo.category) {
              categories[photo.category] = (categories[photo.category] || 0) + 1
            }
            if (photo.tags && Array.isArray(photo.tags)) {
              photo.tags.forEach(tag => {
                tagsMap[tag] = (tagsMap[tag] || 0) + 1
              })
            }
          })
          
          const tags = Object.entries(tagsMap)
            .map(([name, count]) => ({ name, count }))
            .sort((a, b) => b.count - a.count)
          
          setStats({
            total_photos: chef.photos.length,
            categories,
            tags
          })
        }
      })
      .finally(()=> {
        if (!cancelled) setLoadingStats(false)
      })
    return ()=> { cancelled = true }
  }, [username, chef])
  
  // Client-side filtering (until backend endpoints are ready)
  const allPhotos = useMemo(()=> {
    if (!chef?.photos || !Array.isArray(chef.photos)) return []
    return chef.photos
  }, [chef])
  
  const filteredPhotos = useMemo(()=> {
    let result = [...allPhotos]
    
    // Filter by tags
    if (activeTags.length > 0) {
      result = result.filter(p => {
        if (!p.tags || !Array.isArray(p.tags)) return false
        return activeTags.every(tag => p.tags.includes(tag))
      })
    }
    
    // Sort by date
    result.sort((a, b) => {
      const dateA = new Date(a.created_at || 0).getTime()
      const dateB = new Date(b.created_at || 0).getTime()
      return sortNewest ? (dateB - dateA) : (dateA - dateB)
    })
    
    return result
  }, [allPhotos, activeTags, sortNewest])
  
  // Update photos and pagination when filters change
  useEffect(()=> {
    setPhotos(filteredPhotos)
    setTotalCount(filteredPhotos.length)
    setHasMore(false) // No pagination needed for client-side filtering
    setLoadingPhotos(false)
    setPage(1)
  }, [filteredPhotos])
  
  // Infinite scroll observer (disabled for client-side filtering, will be enabled when backend is ready)
  // useEffect(()=>{
  //   if (!observerTarget.current || loadingPhotos || loadingMore || !hasMore) return
  //   const observer = new IntersectionObserver(
  //     (entries) => {
  //       if (entries[0].isIntersecting && hasMore && !loadingMore){
  //         const nextPage = page + 1
  //         setPage(nextPage)
  //         // fetchPhotos would be called here when backend pagination is ready
  //       }
  //     },
  //     { threshold: 0.1, rootMargin: '200px' }
  //   )
  //   observer.observe(observerTarget.current)
  //   return ()=> observer.disconnect()
  // }, [page, hasMore, loadingPhotos, loadingMore])
  
  // Body scroll lock for lightbox
  useEffect(()=>{
    if (typeof document === 'undefined') return undefined
    const className = 'chef-gallery-modal-open'
    if (lightboxIndex >= 0){
      const previous = document.body.style.overflow
      bodyScrollRestoreRef.current = previous
      document.body.classList.add(className)
      document.body.style.overflow = 'hidden'
      document.body.style.paddingRight = 'var(--scrollbar-width, 0px)'
      return ()=>{
        document.body.classList.remove(className)
        document.body.style.overflow = previous
        document.body.style.paddingRight = ''
      }
    }
    document.body.classList.remove(className)
    document.body.style.overflow = bodyScrollRestoreRef.current || ''
    return undefined
  }, [lightboxIndex])
  
  // Keyboard navigation for lightbox
  useEffect(()=>{
    const handleKeyDown = (e)=>{
      if (lightboxIndex < 0) return
      if (e.key === 'Escape'){
        closeLightbox()
      } else if (e.key === 'ArrowLeft' && lightboxIndex > 0){
        openPhotoAt(lightboxIndex - 1)
      } else if (e.key === 'ArrowRight' && lightboxIndex < photos.length - 1){
        openPhotoAt(lightboxIndex + 1)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return ()=> window.removeEventListener('keydown', handleKeyDown)
  }, [lightboxIndex, photos.length, closeLightbox, openPhotoAt])
  
  // Toggle tag filter
  const toggleTag = (tag) => {
    setActiveTags(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    )
  }
  
  // Toggle sort order
  const toggleSort = () => {
    setSortNewest(prev => !prev)
  }
  
  if (loadingChef){
    return (
      <div className="page-chef-gallery">
        <div className="chef-gallery-loading">
          <div className="spinner"></div>
          <p>Loading gallery...</p>
        </div>
      </div>
    )
  }
  
  if (error || !chef){
    return (
      <div className="page-chef-gallery">
        <div className="chef-gallery-error">
          <i className="fa-solid fa-triangle-exclamation" style={{fontSize:48,opacity:0.3,marginBottom:'1rem'}}></i>
          <h2>{error || 'Gallery not available'}</h2>
          <button className="btn btn-primary" onClick={()=> navigate('/chefs')}>
            <i className="fa-solid fa-arrow-left" style={{marginRight:'.5rem'}}></i>
            Browse Chefs
          </button>
        </div>
      </div>
    )
  }
  
  const topTags = (stats?.tags || []).slice(0, 10)
  
  return (
    <div className="page-chef-gallery">
      {/* Hero Section */}
      <div className="gallery-hero">
        <div className="gallery-hero-content">
          <button className="gallery-back-btn" onClick={()=> navigate(`/c/${username}`)}>
            <i className="fa-solid fa-arrow-left"></i>
            <span>Back to Profile</span>
          </button>
          
          <div className="gallery-hero-main">
            {chef.profile_pic_url && (
              <img 
                src={chef.profile_pic_url} 
                alt={chef.user?.username || 'Chef'} 
                className="gallery-hero-avatar"
              />
            )}
            <div className="gallery-hero-info">
              <h1 className="gallery-hero-title">
                {chef.user?.username || chef.name || 'Chef'}'s Gallery
              </h1>
              <div className="gallery-hero-meta">
                <span className="gallery-hero-count">
                  <i className="fa-solid fa-camera"></i>
                  {loadingStats ? '...' : totalCount} {totalCount === 1 ? 'photo' : 'photos'}
                </span>
                {chef.city && (
                  <span className="gallery-hero-location">
                    <i className="fa-solid fa-location-dot"></i>
                    {chef.city}{chef.country ? `, ${chef.country}` : ''}
                  </span>
                )}
              </div>
              {chef.bio && (
                <p className="gallery-hero-bio">{chef.bio}</p>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Filter Bar */}
      <div className="gallery-filters">
        <div className="gallery-filters-content">
          {/* Tag Filters */}
          {topTags.length > 0 && (
            <div className="gallery-filter-group">
              <label className="gallery-filter-label">Filter by Tags</label>
              <div className="gallery-filter-chips">
                {topTags.map(tag => (
                  <button
                    key={tag.name}
                    className={`filter-chip ${activeTags.includes(tag.name) ? 'active' : ''}`}
                    onClick={()=> toggleTag(tag.name)}
                  >
                    #{tag.name} ({tag.count})
                  </button>
                ))}
              </div>
            </div>
          )}
          
          {/* Sort Toggle */}
          <div className="gallery-sort-group">
            <button 
              className="gallery-sort-toggle"
              onClick={toggleSort}
              aria-label={sortNewest ? 'Sorted newest first, click for oldest first' : 'Sorted oldest first, click for newest first'}
              title={sortNewest ? 'Newest First' : 'Oldest First'}
            >
              <svg 
                width="20" 
                height="20" 
                viewBox="0 0 20 20" 
                fill="none" 
                xmlns="http://www.w3.org/2000/svg"
                className={sortNewest ? '' : 'flipped'}
              >
                <path d="M3 4h14M3 10h10M3 16h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <span className="sort-label">{sortNewest ? 'Newest' : 'Oldest'}</span>
            </button>
          </div>
        </div>
        
        {/* Active Filters Summary */}
        {activeTags.length > 0 && (
          <div className="gallery-active-filters">
            <span className="active-filters-label">Active filters:</span>
            {activeTags.map(tag => (
              <span key={tag} className="active-filter-tag">
                #{tag}
                <button onClick={()=> toggleTag(tag)} aria-label="Remove filter">×</button>
              </span>
            ))}
            <button 
              className="clear-filters-btn"
              onClick={()=> setActiveTags([])}
            >
              Clear all
            </button>
          </div>
        )}
      </div>
      
      {/* Gallery Grid */}
      <div className="gallery-container" ref={galleryRef}>
        {loadingPhotos ? (
          <div className="gallery-loading">
            <div className="spinner"></div>
            <p>Loading photos...</p>
          </div>
        ) : photos.length === 0 ? (
          <div className="gallery-empty">
            <i className="fa-solid fa-images" style={{fontSize:64,opacity:0.2,marginBottom:'1rem'}}></i>
            <h3>No photos found</h3>
            <p className="muted">
              {activeTags.length > 0 
                ? 'Try adjusting your filters' 
                : 'This chef hasn\'t uploaded any photos yet'}
            </p>
            {activeTags.length > 0 && (
              <button 
                className="btn btn-outline"
                onClick={()=> setActiveTags([])}
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="gallery-grid">
              {photos.map((photo, idx) => (
                <div
                  key={photo.id}
                  className="gallery-grid-item"
                  onClick={() => openPhotoAt(idx)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') openPhotoAt(idx) }}
                  aria-label={photo.title || `Photo ${idx + 1}`}
                >
                  <div className="gallery-grid-image">
                    <img 
                      src={photo.thumbnail_url || photo.image_url} 
                      alt={photo.title || 'Gallery photo'} 
                      loading="lazy" 
                      decoding="async"
                    />
                    <div className="gallery-grid-overlay">
                      <i className="fa-solid fa-expand"></i>
                      {photo.title && (
                        <span className="gallery-grid-title">{photo.title}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Infinite Scroll Trigger - Will be enabled when backend pagination is ready */}
            {/* {hasMore && (
              <div ref={observerTarget} className="gallery-load-more">
                {loadingMore && (
                  <>
                    <div className="spinner" style={{width:24,height:24,borderWidth:3}}></div>
                    <span>Loading more photos...</span>
                  </>
                )}
              </div>
            )} */}
            
            {photos.length > 0 && (
              <div className="gallery-end">
                <i className="fa-solid fa-check-circle"></i>
                Showing all {photos.length} {photos.length === 1 ? 'photo' : 'photos'}
              </div>
            )}
          </>
        )}
      </div>
      
      {/* Lightbox Modal */}
      {lightboxIndex >= 0 && activePhoto && (
        <div 
          className="lightbox" 
          role="dialog" 
          aria-modal="true" 
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              closeLightbox()
            }
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) {
              e.preventDefault()
            }
          }}
        >
          <div
            className="chef-gallery-modal"
            role="document"
            aria-labelledby="chef-gallery-modal-heading"
          >
            <header className="chef-gallery-modal__header">
              <button
                className="chef-gallery-modal__back"
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  closeLightbox()
                }}
                aria-label="Close gallery modal"
              >
                <span aria-hidden="true">‹</span>
                <span>Back to gallery</span>
              </button>
              <div className="chef-gallery-modal__heading" id="chef-gallery-modal-heading">
                <span className="chef-gallery-modal__heading-label">Photo {lightboxIndex + 1} of {photos.length}</span>
                <span className="chef-gallery-modal__heading-name">{chef?.user?.username || chef?.name || 'Chef'}</span>
              </div>
              <button
                className="chef-gallery-modal__close"
                type="button"
                aria-label="Close photo"
                onClick={(e) => {
                  e.stopPropagation()
                  closeLightbox()
                }}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5 5L15 15M15 5L5 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </header>
            <div className="chef-gallery-modal__body">
              <div className="chef-gallery-modal__media">
                {photos.length > 1 && lightboxIndex > 0 && (
                  <button
                    className="chef-gallery-modal__nav prev"
                    type="button"
                    aria-label="Previous photo"
                    onClick={(e) => {
                      e.stopPropagation()
                      openPhotoAt(lightboxIndex - 1)
                    }}
                  >
                    ‹
                  </button>
                )}
                <img
                  src={activePhoto?.image_url}
                  alt={activePhoto?.title || 'Chef gallery photo'}
                  loading="lazy"
                  draggable="false"
                />
                {photos.length > 1 && lightboxIndex < photos.length - 1 && (
                  <button
                    className="chef-gallery-modal__nav next"
                    type="button"
                    aria-label="Next photo"
                    onClick={(e) => {
                      e.stopPropagation()
                      openPhotoAt(lightboxIndex + 1)
                    }}
                  >
                    ›
                  </button>
                )}
              </div>
              <aside className="chef-gallery-modal__meta">
                <div className="chef-gallery-modal__meta-header">
                  {chef?.profile_pic_url && (
                    <img src={chef.profile_pic_url} alt="Chef avatar" className="chef-gallery-modal__avatar" loading="lazy" />
                  )}
                  <div>
                    <div className="chef-gallery-modal__chef-name">{chef?.user?.username || chef?.name || 'Chef'}</div>
                    {chef?.city && (
                      <div className="chef-gallery-modal__chef-loc">{chef.city}{chef?.country ? ` · ${chef.country}` : ''}</div>
                    )}
                  </div>
                </div>
                {(activePhoto?.title || activePhoto?.caption || activePhoto?.description) && (
                  <div className="chef-gallery-modal__meta-copy">
                    {activePhoto?.title && <h2 className="chef-gallery-modal__title">{activePhoto.title}</h2>}
                    {activePhoto?.caption && <p className="chef-gallery-modal__caption">{activePhoto.caption}</p>}
                    {activePhoto?.description && (!activePhoto.caption || activePhoto.description !== activePhoto.caption) && (
                      <p className="chef-gallery-modal__description">{activePhoto.description}</p>
                    )}
                  </div>
                )}
                {activePhoto?.tags && Array.isArray(activePhoto.tags) && activePhoto.tags.length > 0 && (
                  <ul className="chef-gallery-modal__tags">
                    {activePhoto.tags.map((tag, idx)=>(
                      <li key={idx}>#{String(tag).replace(/^#+/, '')}</li>
                    ))}
                  </ul>
                )}
                {activePhoto?.dish && (
                  <div className="chef-gallery-modal__related">
                    <i className="fa-solid fa-bowl-food"></i>
                    <div>
                      <div className="label">Dish</div>
                      <div className="value">{activePhoto.dish.name}</div>
                    </div>
                  </div>
                )}
                {activePhoto?.meal && (
                  <div className="chef-gallery-modal__related">
                    <i className="fa-solid fa-utensils"></i>
                    <div>
                      <div className="label">Meal</div>
                      <div className="value">{activePhoto.meal.name}</div>
                    </div>
                  </div>
                )}
                {activePhoto?.created_at && activePhotoDateLabel && (
                  <time className="chef-gallery-modal__timestamp" dateTime={activePhoto.created_at}>
                    <i className="fa-regular fa-calendar"></i>
                    {activePhotoDateLabel}
                  </time>
                )}
              </aside>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
