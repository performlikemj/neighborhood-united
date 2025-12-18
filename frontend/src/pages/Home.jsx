import React, { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../api'

// Random chef emojis for placeholder
const CHEF_EMOJIS = ['👨‍🍳', '👩‍🍳', '🧑‍🍳', '🍳', '🥘', '🍲', '🥗', '🍝']
function getRandomChefEmoji() {
  return CHEF_EMOJIS[Math.floor(Math.random() * CHEF_EMOJIS.length)]
}

// Animated counter hook for trust metrics
function useAnimatedCounter(targetValue, duration = 2000) {
  const [count, setCount] = useState(0)
  const [animationKey, setAnimationKey] = useState(0)
  const ref = useRef(null)

  // Trigger animation when target value changes
  useEffect(() => {
    if (targetValue > 0) {
      setAnimationKey(k => k + 1)
    }
  }, [targetValue])

  useEffect(() => {
    if (targetValue === 0) {
      setCount(0)
      return
    }
    
    let startTime = null
    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp
      const progress = Math.min((timestamp - startTime) / duration, 1)
      setCount(Math.floor(progress * targetValue))
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [animationKey, targetValue, duration])

  return { count, ref }
}

// Featured chef card component
function ChefCard({ chef }) {
  const username = chef?.user?.username || 'Chef'
  const profilePic = chef?.profile_pic_url
  const bio = chef?.bio || ''
  const location = chef?.city || chef?.location_city || ''
  const country = chef?.country || ''
  const photoCount = chef?.photos?.length || 0
  // Use chef's chosen emoji, or fall back to a random chef emoji
  const chefEmoji = chef?.sous_chef_emoji || getRandomChefEmoji()

  return (
    <Link to={`/c/${encodeURIComponent(username)}`} className="home-chef-card">
      <div className="home-chef-avatar">
        {profilePic ? (
          <img src={profilePic} alt={username} />
        ) : (
          <div className="home-chef-avatar-emoji">
            <span role="img" aria-label="chef">{chefEmoji}</span>
          </div>
        )}
      </div>
      <div className="home-chef-info">
        <h4 className="home-chef-name">{username}</h4>
        {(location || country) && (
          <p className="home-chef-location">
            <i className="fa-solid fa-location-dot"></i>
            {[location, country].filter(Boolean).join(', ')}
          </p>
        )}
        {bio && <p className="home-chef-bio">{bio.slice(0, 80)}{bio.length > 80 ? '...' : ''}</p>}
      </div>
      {photoCount > 0 && (
        <div className="home-chef-photos">
          <i className="fa-solid fa-images"></i> {photoCount}
        </div>
      )}
    </Link>
  )
}

export default function Home() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [locationQuery, setLocationQuery] = useState('')
  const [featuredChefs, setFeaturedChefs] = useState([])
  const [loadingChefs, setLoadingChefs] = useState(true)
  const [activeAudience, setActiveAudience] = useState('customer') // 'customer' or 'chef'

  // Application modal state (for logged-in non-chef users)
  const [applyOpen, setApplyOpen] = useState(false)
  const [chefForm, setChefForm] = useState({ experience: '', bio: '', serving_areas: '', profile_pic: null })
  const [submitting, setSubmitting] = useState(false)
  const [applyMsg, setApplyMsg] = useState(null)

  // Platform stats from real data
  const [platformStats, setPlatformStats] = useState({ chefCount: 0, cityCount: 0 })

  // Animated counters for trust metrics - using real data
  const chefsCounter = useAnimatedCounter(platformStats.chefCount, 2000)
  const citiesCounter = useAnimatedCounter(platformStats.cityCount, 1800)

  // Fetch featured chefs and derive real stats
  useEffect(() => {
    let mounted = true
    api.get('/chefs/api/public/', { params: { page_size: 100 }, skipUserId: true })
      .then(res => {
        if (!mounted) return
        const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
        
        // Set featured chefs (first 8)
        setFeaturedChefs(list.slice(0, 8))
        
        // Calculate real stats from chef data
        const chefCount = res.data?.count || list.length
        
        // Count unique cities from chef serving areas
        const cities = new Set()
        list.forEach(chef => {
          const postalCodes = chef?.serving_postalcodes || []
          postalCodes.forEach(pc => {
            const city = pc?.city || ''
            if (city.trim()) cities.add(city.toLowerCase())
          })
          // Also check chef's direct city field
          const chefCity = chef?.city || chef?.location_city || ''
          if (chefCity.trim()) cities.add(chefCity.toLowerCase())
        })
        
        setPlatformStats({
          chefCount: chefCount,
          cityCount: Math.max(cities.size, 1) // At least 1 if we have chefs
        })
      })
      .catch(() => {})
      .finally(() => { if (mounted) setLoadingChefs(false) })
    return () => { mounted = false }
  }, [])

  const handleLocationSearch = (e) => {
    e.preventDefault()
    if (locationQuery.trim()) {
      navigate(`/chefs?q=${encodeURIComponent(locationQuery.trim())}`)
    } else {
      navigate('/chefs')
    }
  }

  const handleChefApplication = async () => {
    setSubmitting(true)
    setApplyMsg(null)
    try {
      const fd = new FormData()
      fd.append('experience', chefForm.experience)
      fd.append('bio', chefForm.bio)
      fd.append('serving_areas', chefForm.serving_areas)
      if (user?.address?.city) fd.append('city', user.address.city)
      if (user?.address?.country) fd.append('country', user.address.country)
      if (chefForm.profile_pic) fd.append('profile_pic', chefForm.profile_pic)
      
      const resp = await api.post('/chefs/api/submit-chef-request/', fd, { 
        headers: { 'Content-Type': 'multipart/form-data' } 
      })
      if (resp.status === 200 || resp.status === 201) {
        setApplyMsg('Application submitted! We\'ll notify you when approved.')
      } else {
        setApplyMsg('Submission failed. Please try again later.')
      }
    } catch (e) {
      setApplyMsg(e?.response?.data?.error || 'Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-home-v2">
      {/* ============================================ */}
      {/* HERO SECTION - Split Audience Design */}
      {/* ============================================ */}
      <section className="home-hero">
        <div className="home-hero-bg"></div>
        <div className="home-hero-content">
          {/* Audience Toggle */}
          <div className="home-audience-toggle">
            <button 
              className={`audience-btn ${activeAudience === 'customer' ? 'active' : ''}`}
              onClick={() => setActiveAudience('customer')}
            >
              I'm looking for a chef
            </button>
            <button 
              className={`audience-btn ${activeAudience === 'chef' ? 'active' : ''}`}
              onClick={() => setActiveAudience('chef')}
            >
              I'm a chef
            </button>
          </div>

          {/* Customer-focused hero */}
          {activeAudience === 'customer' && (
            <div className="home-hero-main">
              <h1 className="home-hero-title">
                Discover Your Perfect <span className="text-gradient">Personal Chef</span>
              </h1>
              <p className="home-hero-subtitle">
                Connect with talented local chefs for meal prep, private dinners, cooking classes, and more. 
                Home cooking, elevated.
              </p>
              
              {/* Location Search */}
              <form className="home-search-form" onSubmit={handleLocationSearch}>
                <div className="home-search-input-wrap">
                  <i className="fa-solid fa-location-dot"></i>
                  <input
                    type="text"
                    placeholder="Enter your city or postal code..."
                    value={locationQuery}
                    onChange={(e) => setLocationQuery(e.target.value)}
                    className="home-search-input"
                  />
                </div>
                <button type="submit" className="btn btn-primary home-search-btn">
                  Find Chefs
                </button>
              </form>

              <div className="home-hero-links">
                <Link to="/chefs" className="home-hero-link">
                  <i className="fa-solid fa-globe"></i>
                  Browse all chefs
                </Link>
                {!user && (
                  <Link to="/register" className="home-hero-link">
                    <i className="fa-solid fa-user-plus"></i>
                    Create free account
                  </Link>
                )}
              </div>
            </div>
          )}

          {/* Chef-focused hero */}
          {activeAudience === 'chef' && (
            <div className="home-hero-main">
              <h1 className="home-hero-title">
                Grow Your <span className="text-gradient">Culinary Business</span>
              </h1>
              <p className="home-hero-subtitle">
                The all-in-one platform for independent chefs. Manage clients, services, and bookings — 
                focus on cooking while we handle the business.
              </p>
              
              <div className="home-hero-actions">
                {!user && (
                  <Link to="/register" className="btn btn-primary btn-lg">
                    Start Your Chef Profile
                  </Link>
                )}
                {user?.is_chef && (
                  <Link to="/chefs/dashboard" className="btn btn-primary btn-lg">
                    Go to Chef Hub
                  </Link>
                )}
                {user && !user?.is_chef && (
                  <button className="btn btn-primary btn-lg" onClick={() => setApplyOpen(true)}>
                    Apply to Become a Chef
                  </button>
                )}
              </div>

              <div className="home-chef-features">
                <div className="home-chef-feature">
                  <i className="fa-solid fa-users"></i>
                  <span>Client Management</span>
                </div>
                <div className="home-chef-feature">
                  <i className="fa-solid fa-calendar-check"></i>
                  <span>Easy Booking</span>
                </div>
                <div className="home-chef-feature">
                  <i className="fa-solid fa-credit-card"></i>
                  <span>Stripe Payments</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Hero Image */}
        <div className="home-hero-image">
          <img 
            src={activeAudience === 'customer' 
              ? 'https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=800&q=80' 
              : 'https://images.unsplash.com/photo-1577219491135-ce391730fb2c?w=800&q=80'
            } 
            alt={activeAudience === 'customer' ? 'Delicious home-cooked meal' : 'Professional chef at work'}
          />
        </div>
      </section>

      {/* ============================================ */}
      {/* TRUST METRICS BAR */}
      {/* ============================================ */}
      {platformStats.chefCount > 0 && (
        <section className="home-trust-bar" ref={chefsCounter.ref}>
          <div className="home-trust-content">
            <div className="home-trust-item">
              <span className="home-trust-number">{chefsCounter.count}</span>
              <span className="home-trust-label">Active {chefsCounter.count === 1 ? 'Chef' : 'Chefs'}</span>
            </div>
            {platformStats.cityCount > 0 && (
              <>
                <div className="home-trust-divider"></div>
                <div className="home-trust-item">
                  <span className="home-trust-number">{citiesCounter.count}</span>
                  <span className="home-trust-label">{citiesCounter.count === 1 ? 'City' : 'Cities'}</span>
                </div>
              </>
            )}
            <div className="home-trust-divider"></div>
            <div className="home-trust-item">
              <span className="home-trust-number">
                <i className="fa-solid fa-globe" style={{ fontSize: '1.5rem' }}></i>
              </span>
              <span className="home-trust-label">Worldwide</span>
            </div>
          </div>
        </section>
      )}

      {/* ============================================ */}
      {/* FEATURED CHEFS SECTION */}
      {/* ============================================ */}
      <section className="home-section home-featured-chefs">
        <div className="home-section-header">
          <h2 className="home-section-title">Meet Our Chefs</h2>
          <p className="home-section-subtitle">
            Talented culinary professionals ready to bring restaurant-quality food to your home
          </p>
        </div>

        <div className="home-chefs-grid">
          {loadingChefs ? (
            <div className="home-chefs-loading">
              <div className="spinner"></div>
            </div>
          ) : featuredChefs.length > 0 ? (
            featuredChefs.map(chef => (
              <ChefCard key={chef.id} chef={chef} />
            ))
          ) : (
            <p className="home-chefs-empty">Chefs are joining every day. Check back soon!</p>
          )}
        </div>

        <div className="home-section-cta">
          <Link to="/chefs" className="btn btn-outline btn-lg">
            <i className="fa-solid fa-utensils"></i>
            View All Chefs
          </Link>
        </div>
      </section>

      {/* ============================================ */}
      {/* SERVICE CATEGORIES */}
      {/* ============================================ */}
      <section className="home-section home-services">
        <div className="home-section-header">
          <h2 className="home-section-title">What Can a Chef Do for You?</h2>
          <p className="home-section-subtitle">
            From weekly meal prep to special occasions — find the perfect service
          </p>
        </div>

        <div className="home-services-grid">
          <Link to="/chefs?service=meal-prep" className="home-service-card">
            <div className="home-service-image">
              <img src="https://images.unsplash.com/photo-1498837167922-ddd27525d352?w=400&q=80" alt="Meal Prep" />
            </div>
            <div className="home-service-content">
              <h3>Weekly Meal Prep</h3>
              <p>Healthy, portioned meals ready for your week. Save time and eat better.</p>
            </div>
          </Link>

          <Link to="/chefs?service=private-dining" className="home-service-card">
            <div className="home-service-image">
              <img src="https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&q=80" alt="Private Dining" />
            </div>
            <div className="home-service-content">
              <h3>Private Dinners</h3>
              <p>Restaurant-quality dining in your home. Perfect for special occasions.</p>
            </div>
          </Link>

          <Link to="/chefs?service=cooking-class" className="home-service-card">
            <div className="home-service-image">
              <img src="https://images.unsplash.com/photo-1507048331197-7d4ac70811cf?w=400&q=80" alt="Cooking Class" />
            </div>
            <div className="home-service-content">
              <h3>Cooking Classes</h3>
              <p>Learn new techniques and recipes from professional chefs.</p>
            </div>
          </Link>

          <Link to="/chefs?service=events" className="home-service-card">
            <div className="home-service-image">
              <img src="https://images.unsplash.com/photo-1555244162-803834f70033?w=400&q=80" alt="Events" />
            </div>
            <div className="home-service-content">
              <h3>Events & Catering</h3>
              <p>From intimate gatherings to larger celebrations — we've got you covered.</p>
            </div>
          </Link>
        </div>
      </section>

      {/* ============================================ */}
      {/* HOW IT WORKS */}
      {/* ============================================ */}
      <section className="home-section home-how-it-works">
        <div className="home-section-header">
          <h2 className="home-section-title">How It Works</h2>
          <p className="home-section-subtitle">Three simple steps to amazing food</p>
        </div>

        <div className="home-steps">
          <div className="home-step">
            <div className="home-step-number">1</div>
            <div className="home-step-icon">
              <i className="fa-solid fa-magnifying-glass"></i>
            </div>
            <h3>Discover</h3>
            <p>Browse local chefs, explore their menus, and find your perfect match.</p>
          </div>

          <div className="home-step-arrow">
            <i className="fa-solid fa-arrow-right"></i>
          </div>

          <div className="home-step">
            <div className="home-step-number">2</div>
            <div className="home-step-icon">
              <i className="fa-solid fa-handshake"></i>
            </div>
            <h3>Connect</h3>
            <p>Request services, discuss your preferences, and book your chef.</p>
          </div>

          <div className="home-step-arrow">
            <i className="fa-solid fa-arrow-right"></i>
          </div>

          <div className="home-step">
            <div className="home-step-number">3</div>
            <div className="home-step-icon">
              <i className="fa-solid fa-heart"></i>
            </div>
            <h3>Enjoy</h3>
            <p>Sit back and enjoy delicious, personalized meals made just for you.</p>
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* WHY SAUTAI - Value Props instead of fake testimonials */}
      {/* ============================================ */}
      <section className="home-section home-testimonials">
        <div className="home-section-header">
          <h2 className="home-section-title">Why Choose sautai?</h2>
          <p className="home-section-subtitle">
            Built by food lovers, for food lovers
          </p>
        </div>

        <div className="home-testimonials-grid">
          <div className="home-testimonial">
            <div className="home-testimonial-icon">
              <i className="fa-solid fa-user-check"></i>
            </div>
            <h3>Verified Chefs</h3>
            <p>
              Every chef on our platform goes through a verification process. 
              Browse real profiles, see their work, and connect with confidence.
            </p>
          </div>

          <div className="home-testimonial">
            <div className="home-testimonial-icon">
              <i className="fa-solid fa-hand-holding-dollar"></i>
            </div>
            <h3>Fair & Transparent</h3>
            <p>
              Chefs set their own prices. No hidden fees. Secure payments through Stripe 
              protect both chefs and customers.
            </p>
          </div>

          <div className="home-testimonial">
            <div className="home-testimonial-icon">
              <i className="fa-solid fa-users"></i>
            </div>
            <h3>Community First</h3>
            <p>
              We're building a global community of independent chefs and food lovers. 
              Support local talent and discover amazing home-cooked meals.
            </p>
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* FINAL CTA */}
      {/* ============================================ */}
      <section className="home-section home-final-cta">
        <div className="home-final-cta-content">
          <h2>Ready to Transform Your Meals?</h2>
          <p>
            Whether you're seeking delicious home-cooked meals or looking to grow your culinary career — 
            sautai connects you with your community.
          </p>
          <div className="home-final-cta-actions">
            <Link to="/chefs" className="btn btn-primary btn-lg">
              <i className="fa-solid fa-search"></i>
              Find a Chef
            </Link>
            {!user && (
              <Link to="/register" className="btn btn-outline btn-lg">
                <i className="fa-solid fa-user-plus"></i>
                Create Chef Profile
              </Link>
            )}
            {user && !user?.is_chef && (
              <button className="btn btn-outline btn-lg" onClick={() => setApplyOpen(true)}>
                <i className="fa-solid fa-hat-chef"></i>
                Become a Chef
              </button>
            )}
            {user?.is_chef && (
              <Link to="/chefs/dashboard" className="btn btn-outline btn-lg">
                <i className="fa-solid fa-chart-line"></i>
                Chef Dashboard
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* ============================================ */}
      {/* CHEF APPLICATION MODAL */}
      {/* ============================================ */}
      {applyOpen && (
        <>
          <div className="modal-overlay" onClick={() => setApplyOpen(false)} />
          <aside className="right-panel" role="dialog" aria-label="Become a Chef">
            <div className="right-panel-head">
              <div className="slot-title">Become a Community Chef</div>
              <button className="icon-btn" onClick={() => setApplyOpen(false)}>
                <i className="fa-solid fa-times"></i>
              </button>
            </div>
            <div className="right-panel-body">
              {applyMsg && (
                <div className="card" style={{ marginBottom: '.75rem', padding: '.75rem' }}>
                  {applyMsg}
                </div>
              )}
              <p className="muted">Share your experience and where you can serve. You can complete your profile later.</p>
              
              <div className="label">Experience</div>
              <textarea 
                className="textarea" 
                rows={3} 
                placeholder="Tell us about your culinary background..."
                value={chefForm.experience} 
                onChange={e => setChefForm({ ...chefForm, experience: e.target.value })} 
              />
              
              <div className="label">Bio</div>
              <textarea 
                className="textarea" 
                rows={3} 
                placeholder="What makes your cooking special?"
                value={chefForm.bio} 
                onChange={e => setChefForm({ ...chefForm, bio: e.target.value })} 
              />
              
              <div className="label">Serving areas (postal codes)</div>
              <input 
                className="input" 
                placeholder="e.g., 90210, 90211"
                value={chefForm.serving_areas} 
                onChange={e => setChefForm({ ...chefForm, serving_areas: e.target.value })} 
              />
              
              <div className="label">Profile picture (optional)</div>
              <div>
                <input 
                  id="homeProfilePic" 
                  type="file" 
                  accept="image/jpeg,image/png,image/webp" 
                  style={{ display: 'none' }} 
                  onChange={e => setChefForm({ ...chefForm, profile_pic: e.target.files?.[0] || null })} 
                />
                <label htmlFor="homeProfilePic" className="btn btn-outline">Choose file</label>
                {chefForm.profile_pic && (
                  <span className="muted" style={{ marginLeft: '.5rem' }}>{chefForm.profile_pic.name}</span>
                )}
              </div>
              
              <div className="actions-row" style={{ marginTop: '.75rem' }}>
                <button 
                  className="btn btn-primary" 
                  disabled={submitting} 
                  onClick={handleChefApplication}
                >
                  {submitting ? 'Submitting...' : 'Submit Application'}
                </button>
                <button className="btn btn-outline" onClick={() => setApplyOpen(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </aside>
        </>
      )}
    </div>
  )
}
