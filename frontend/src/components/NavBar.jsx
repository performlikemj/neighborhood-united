import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { FEATURES } from '../config/features.js'
import { api } from '../api'

function PlateStackIcon(){
  const stroke = 'currentColor'
  return (
    <svg width="24" height="20" viewBox="0 0 24 20" aria-hidden focusable="false">
      <g fill="none" stroke={stroke} strokeWidth="1.8">
        <ellipse cx="12" cy="5" rx="8.5" ry="2.4" />
        <ellipse cx="12" cy="10" rx="8.5" ry="2.4" />
        <ellipse cx="12" cy="15" rx="8.5" ry="2.4" />
      </g>
    </svg>
  )
}

export default function NavBar(){
  const { user, logout, switchRole, hasChefAccess } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const nav = useNavigate()
  const [switching, setSwitching] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [brandSrc, setBrandSrc] = useState('/sautai_logo_web.png')
  const onBrandError = ()=> setBrandSrc('/sautai_logo_transparent_800.png')
  const isAuthed = Boolean(user)
  const inChef = user?.current_role === 'chef'
  
  // Track connected chefs for adaptive nav text
  const [connectedChefCount, setConnectedChefCount] = useState(0)
  
  // Fetch connected chef count for customers
  useEffect(() => {
    if (isAuthed && !inChef && FEATURES.CLIENT_PORTAL_MY_CHEFS) {
      api.get('/customer-dashboard/api/my-chefs/')
        .then(resp => setConnectedChefCount(resp?.data?.count || 0))
        .catch(() => setConnectedChefCount(0))
    }
  }, [isAuthed, inChef])
  
  // Determine if user has chef connection(s)
  const hasChefConnection = connectedChefCount > 0

  const doLogout = () => {
    logout()
    setMenuOpen(false)
    nav('/login')
  }

  const closeMenu = () => { setMenuOpen(false); setMoreOpen(false) }

  const selectRole = async (target)=>{
    const access = localStorage.getItem('accessToken')
    const refresh = localStorage.getItem('refreshToken')
    try{
      setSwitching(true)
      await switchRole(target)
      if (target === 'chef') nav('/chefs/dashboard')
      else nav('/meal-plans')
    }catch(e){
      const status = e?.response?.status
      const msg = e?.message || 'Failed to switch role'
      console.error('[NavBar] switchRole() failed', { status, url: e?.config?.url, err: e })
      // Non-blocking slide-in toast via window event (handled by page-level overlays)
      try{
        const ev = new CustomEvent('global-toast', { detail: { text: msg, tone: 'error' } })
        window.dispatchEvent(ev)
      }catch{}
    }finally{
      setSwitching(false)
      setMenuOpen(false)
    }
  }

  return (
    <div className="navbar">
      <div className="navbar-inner container">
        <div className="brand">
          <Link to="/" onClick={closeMenu} style={{display:'inline-flex', alignItems:'center', gap:'.5rem', textDecoration:'none'}}>
            <img src={brandSrc} onError={onBrandError} alt="sautai" style={{height:32, width:'auto', borderRadius:6}} />
            <span style={{color:'inherit', textDecoration:'none'}}>sautai</span>
          </Link>
        </div>

        <button
          className={`btn btn-outline menu-toggle${menuOpen ? ' open' : ''}`}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="site-menu"
          onClick={()=>setMenuOpen(v=>!v)}
          title="Menu"
          type="button"
        >
          <PlateStackIcon />
        </button>

        <div id="site-menu" className={"nav-links" + (menuOpen ? " open" : "") }>
          <Link to="/" onClick={closeMenu} className="btn btn-outline">Home</Link>
          
          {/* Chef Dashboard link for chefs */}
          {(inChef && isAuthed) && (
            <Link to="/chefs/dashboard" onClick={closeMenu} className="btn btn-outline">Chef Dashboard</Link>
          )}
          
          {/* Client Portal Navigation for customers with chef connections */}
          {(!inChef && isAuthed && hasChefConnection && FEATURES.CLIENT_PORTAL_MY_CHEFS) && (
            <Link to="/my-chefs" onClick={closeMenu} className="btn btn-outline">
              {connectedChefCount === 1 ? 'My Chef' : 'My Chefs'}
            </Link>
          )}
          
          {/* Legacy Meal Plans link (only if feature enabled and no chef connection) */}
          {(!inChef && isAuthed && FEATURES.CUSTOMER_STANDALONE_MEAL_PLANS && !hasChefConnection) && (
            <Link to="/meal-plans" onClick={closeMenu} className="btn btn-outline">Meal Plans</Link>
          )}
          
          {/* Get Started link for customers without chef access */}
          {(!inChef && isAuthed && !hasChefAccess && !hasChefConnection) && (
            <Link to="/get-ready" onClick={closeMenu} className="btn btn-outline">Get Started</Link>
          )}
          
          {/* Discover Chefs for customers with area access but no connection */}
          {(!inChef && isAuthed && hasChefAccess && !hasChefConnection) && (
            <Link to="/chefs" onClick={closeMenu} className="btn btn-outline">Find a Chef</Link>
          )}
          
          {/* Public chefs directory for non-authenticated users */}
          {!isAuthed && (
            <Link to="/chefs" onClick={closeMenu} className="btn btn-outline">Chefs</Link>
          )}
          
          {isAuthed && (
            (()=>{
              const items = []
              
              // Customer navigation items
              if (!inChef) {
                // Orders always visible for customers
                items.push({ to: '/orders', label: 'Orders' })
                
                // Legacy features (behind feature flags)
                if (FEATURES.CUSTOMER_AI_CHAT) {
                  items.push({ to: '/chat', label: 'Chat' })
                }
                if (FEATURES.CUSTOMER_HEALTH_TRACKING) {
                  items.push({ to: '/health', label: 'Health' })
                }
                
                // Chefs directory for discovery (if not in primary nav)
                if (hasChefConnection) {
                  items.push({ to: '/chefs', label: 'Find More Chefs' })
                }
              }
              
              // Profile always visible
              items.push({ to: '/profile', label: 'Profile' })
              
              if (items.length === 0) return null
              return (
                <div className="menu-wrap">
                  <button type="button" className="btn btn-outline" aria-haspopup="menu" aria-expanded={moreOpen} onClick={()=> setMoreOpen(v=>!v)}>More ▾</button>
                  {moreOpen && (
                    <div className="menu-pop" role="menu" aria-label="More">
                      {items.map(i => (
                        <Link key={i.to} to={i.to} onClick={closeMenu} className="menu-item" role="menuitem">{i.label}</Link>
                      ))}
                    </div>
                  )}
                </div>
              )
            })()
          )}
          {/* History removed */}
          {user?.is_chef && (
            <div className="role-toggle" role="group" aria-label="Select role">
              <button
                type="button"
                className={`seg ${user?.current_role !== 'chef' ? 'active' : ''}`}
                aria-pressed={user?.current_role !== 'chef'}
                disabled={switching}
                title="Use app as Customer"
                onClick={()=>selectRole('customer')}
              >
                {switching && user?.current_role === 'chef' ? '…' : '🥣 Customer'}
              </button>
              <button
                type="button"
                className={`seg ${user?.current_role === 'chef' ? 'active' : ''}`}
                aria-pressed={user?.current_role === 'chef'}
                disabled={switching}
                title="Use app as Chef"
                onClick={()=>selectRole('chef')}
              >
                {switching && user?.current_role !== 'chef' ? '…' : '👨‍🍳 Chef'}
              </button>
            </div>
          )}
          {!user && <Link to="/login" onClick={closeMenu} className="btn btn-primary">Login</Link>}
          {!user && <Link to="/register" onClick={closeMenu} className="btn btn-outline">Register</Link>}
          {user && <button onClick={doLogout} className="btn btn-primary">Logout</button>}
          <button
            type="button"
            className="btn btn-outline"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          >
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </div>
    </div>
  )
}
