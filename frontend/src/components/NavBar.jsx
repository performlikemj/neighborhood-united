import React, { useState, useCallback, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { useMessaging } from '../context/MessagingContext.jsx'
import { FEATURES } from '../config/features.js'
import SautaiLogo from './SautaiLogo.jsx'
import ChatPanel from './ChatPanel.jsx'


export default function NavBar(){
  const { user, logout, switchRole, hasChefAccess, connectedChefs, hasChefConnection } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { totalUnread, getOrCreateConversation } = useMessaging()
  const nav = useNavigate()
  const location = useLocation()
  const [switching, setSwitching] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const accountMenuRef = useRef(null)
  
  // Chat panel state for customers
  const [chatOpen, setChatOpen] = useState(false)
  const [chatLoading, setChatLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [chatRecipient, setChatRecipient] = useState({ name: '', photo: null })
  const [chefPickerOpen, setChefPickerOpen] = useState(false)
  
  const isAuthed = Boolean(user)
  const inChef = user?.current_role === 'chef'
  
  // Detect if we're in the Chef Dashboard context for streamlined navbar
  const isChefDashboard = inChef && (
    location.pathname.startsWith('/chefs/dashboard') || 
    location.pathname.startsWith('/chefs/')
  )
  
  // Use connected chefs from AuthContext (no separate API call needed)
  const connectedChefCount = connectedChefs?.length || 0

  const doLogout = () => {
    logout()
    setMenuOpen(false)
    setAccountMenuOpen(false)
    nav('/login')
  }

  // Close account menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target)) {
        setAccountMenuOpen(false)
      }
    }
    if (accountMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [accountMenuOpen])

  // Get user initials for avatar
  const userInitials = (() => {
    if (user?.first_name && user?.last_name) {
      return `${user.first_name[0]}${user.last_name[0]}`.toUpperCase()
    }
    if (user?.username) {
      return user.username.slice(0, 2).toUpperCase()
    }
    return '?'
  })()

  const userDisplayName = user?.first_name && user?.last_name 
    ? `${user.first_name} ${user.last_name}`
    : user?.username || 'User'

  const closeMenu = () => { setMenuOpen(false); setAccountMenuOpen(false); setChefPickerOpen(false) }
  
  // Handle opening chat for a customer
  const handleCustomerMessageClick = useCallback(async (e) => {
    e.preventDefault()
    closeMenu()
    
    // If only one connected chef, open chat directly
    if (connectedChefs.length === 1) {
      const chef = connectedChefs[0]
      setChatLoading(true)
      try {
        const conversation = await getOrCreateConversation(chef.id)
        setConversationId(conversation.id)
        setChatRecipient({ name: chef.display_name || chef.username, photo: chef.photo })
        setChatOpen(true)
      } catch (err) {
        console.error('Failed to open chat:', err)
        try {
          window.dispatchEvent(new CustomEvent('global-toast', { 
            detail: { text: 'Unable to open chat. Please try again.', tone: 'error' } 
          }))
        } catch {}
      } finally {
        setChatLoading(false)
      }
    } else {
      // Multiple chefs - show picker
      setChefPickerOpen(v => !v)
    }
  }, [connectedChefs, getOrCreateConversation])
  
  // Handle selecting a chef from the picker
  const handleSelectChef = useCallback(async (chef) => {
    setChefPickerOpen(false)
    setChatLoading(true)
    try {
      const conversation = await getOrCreateConversation(chef.id)
      setConversationId(conversation.id)
      setChatRecipient({ name: chef.display_name || chef.username, photo: chef.photo })
      setChatOpen(true)
    } catch (err) {
      console.error('Failed to open chat:', err)
      try {
        window.dispatchEvent(new CustomEvent('global-toast', { 
          detail: { text: 'Unable to open chat. Please try again.', tone: 'error' } 
        }))
      } catch {}
    } finally {
      setChatLoading(false)
    }
  }, [getOrCreateConversation])

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
    <div className={`navbar${isChefDashboard ? ' navbar--chef-context' : ''}${isAuthed ? ' navbar--logged-in' : ''}`}>
      <div className="navbar-inner container">
        <div className="brand">
          <Link to="/" onClick={closeMenu} style={{display:'inline-flex', alignItems:'center', gap:'.5rem', textDecoration:'none'}}>
            <SautaiLogo size={40} />
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
          <i className={`fa-solid ${menuOpen ? 'fa-xmark' : 'fa-bars'}`}></i>
        </button>

        <div id="site-menu" className={"nav-links" + (menuOpen ? " open" : "") }>
          {/* Home link - subtle text style in chef context */}
          <Link to="/" onClick={closeMenu} className={isChefDashboard ? "nav-text-link" : "btn btn-outline"}>Home</Link>
          
          {/* Chef Dashboard link for chefs - hidden when already in chef dashboard */}
          {(inChef && isAuthed && !isChefDashboard) && (
            <Link to="/chefs/dashboard" onClick={closeMenu} className="btn btn-outline">Chef Dashboard</Link>
          )}
          
          
          {/* Messages notification for chefs - goes to dashboard messages tab */}
          {(inChef && isAuthed) && (
            <Link 
              to="/chefs/dashboard" 
              state={{ tab: 'messages' }}
              onClick={closeMenu} 
              className="nav-icon-link"
              title="Messages"
            >
              <i className="fa-regular fa-comment"></i>
              {totalUnread > 0 && (
                <span className="nav-unread-badge">{totalUnread > 9 ? '9+' : totalUnread}</span>
              )}
            </Link>
          )}
          
          {/* Messages notification for customers with chef connections */}
          {(!inChef && isAuthed && hasChefConnection) && (
            <div className="menu-wrap">
              <button 
                type="button"
                onClick={handleCustomerMessageClick}
                className="nav-icon-link"
                title="Messages"
                disabled={chatLoading}
              >
                {chatLoading ? (
                  <span className="spinner-sm"></span>
                ) : (
                  <i className="fa-regular fa-comment"></i>
                )}
                {totalUnread > 0 && (
                  <span className="nav-unread-badge">{totalUnread > 9 ? '9+' : totalUnread}</span>
                )}
              </button>
              {/* Chef picker for multiple chefs */}
              {chefPickerOpen && connectedChefs.length > 1 && (
                <div className="menu-pop chef-picker" role="menu" aria-label="Select Chef">
                  <div className="chef-picker-header">Message a Chef</div>
                  {connectedChefs.map(chef => (
                    <button
                      key={chef.id}
                      type="button"
                      className="menu-item chef-picker-item"
                      role="menuitem"
                      onClick={() => handleSelectChef(chef)}
                    >
                      {chef.photo ? (
                        <img src={chef.photo} alt="" className="chef-picker-photo" />
                      ) : (
                        <div className="chef-picker-photo-placeholder">
                          <i className="fa-solid fa-user"></i>
                        </div>
                      )}
                      <span>{chef.display_name || chef.username}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          
          {/* Legacy Meal Plans link (only if feature enabled and no chef connection) */}
          {(!inChef && isAuthed && FEATURES.CUSTOMER_STANDALONE_MEAL_PLANS && !hasChefConnection) && (
            <Link to="/meal-plans" onClick={closeMenu} className="btn btn-outline">Meal Plans</Link>
          )}
          
          {/* Public chefs directory for non-authenticated users */}
          {!isAuthed && (
            <Link to="/chefs" onClick={closeMenu} className="btn btn-outline">Chefs</Link>
          )}
          
          {/* Account menu with avatar trigger */}
          {isAuthed && !isChefDashboard && (
            <div className="account-menu-wrap" ref={accountMenuRef}>
              <button 
                type="button" 
                className="account-trigger"
                aria-haspopup="menu" 
                aria-expanded={accountMenuOpen} 
                onClick={() => setAccountMenuOpen(v => !v)}
                title="Account menu"
              >
                <span className="account-avatar">{userInitials}</span>
                <i className={`fa-solid fa-chevron-down account-chevron ${accountMenuOpen ? 'open' : ''}`}></i>
              </button>
              
              {accountMenuOpen && (
                <div className="account-menu" role="menu" aria-label="Account">
                  {/* User info header */}
                  <div className="account-menu-header">
                    <span className="account-avatar account-avatar--lg">{userInitials}</span>
                    <div className="account-menu-user">
                      <div className="account-menu-name">{userDisplayName}</div>
                      {user?.email && <div className="account-menu-email">{user.email}</div>}
                    </div>
                  </div>
                  
                  <div className="account-menu-divider" />
                  
                  {/* Navigation section - visible on mobile, hidden on desktop */}
                  <div className="account-menu-nav-section">
                    <Link to="/" onClick={closeMenu} className="account-menu-item" role="menuitem">
                      <span className="account-menu-emoji">🏠</span>
                      <span>Home</span>
                    </Link>
                    
                    {hasChefConnection && (
                      <button 
                        type="button" 
                        onClick={(e) => { closeMenu(); handleCustomerMessageClick(e); }}
                        className="account-menu-item"
                        role="menuitem"
                      >
                        <span className="account-menu-emoji">💬</span>
                        <span>Messages</span>
                        {totalUnread > 0 && <span className="account-menu-badge">{totalUnread > 9 ? '9+' : totalUnread}</span>}
                      </button>
                    )}
                    
                    <div className="account-menu-divider" />
                  </div>
                  
                  {/* Activity section for customers */}
                  {!inChef && (
                    <>
                      {/* Primary chef action - changes based on connection status */}
                      {hasChefConnection ? (
                        <Link to="/my-chefs" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">👨‍🍳</span>
                          <span>{connectedChefCount === 1 ? 'My Chef' : 'My Chefs'}</span>
                        </Link>
                      ) : hasChefAccess ? (
                        <Link to="/chefs" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">🔍</span>
                          <span>Find a Chef</span>
                        </Link>
                      ) : (
                        <Link to="/get-ready" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">🚀</span>
                          <span>Get Started</span>
                        </Link>
                      )}
                      
                      <Link to="/orders" onClick={closeMenu} className="account-menu-item" role="menuitem">
                        <span className="account-menu-emoji">📦</span>
                        <span>My Orders</span>
                      </Link>
                      
                      {FEATURES.CUSTOMER_AI_CHAT && (
                        <Link to="/chat" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">🤖</span>
                          <span>AI Chat</span>
                        </Link>
                      )}
                      {FEATURES.CUSTOMER_HEALTH_TRACKING && (
                        <Link to="/health" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">❤️</span>
                          <span>Health</span>
                        </Link>
                      )}
                      
                      {/* Discovery - only show if already connected (otherwise the primary action handles it) */}
                      {hasChefConnection && (
                        <Link to="/chefs" onClick={closeMenu} className="account-menu-item" role="menuitem">
                          <span className="account-menu-emoji">🍽️</span>
                          <span>Find More Chefs</span>
                        </Link>
                      )}
                      
                      <div className="account-menu-divider" />
                    </>
                  )}
                  
                  {/* Account section */}
                  <Link to="/profile" onClick={closeMenu} className="account-menu-item" role="menuitem">
                    <span className="account-menu-emoji">⚙️</span>
                    <span>Profile Settings</span>
                  </Link>
                  
                  {/* Theme toggle - shown for mobile in dropdown */}
                  <button 
                    type="button" 
                    onClick={() => { toggleTheme(); closeMenu(); }}
                    className="account-menu-item account-menu-theme-toggle" 
                    role="menuitem"
                  >
                    <span className="account-menu-emoji">{theme === 'dark' ? '☀️' : '🌙'}</span>
                    <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
                  </button>
                  
                  {/* Role toggle for chefs - mobile only in dropdown */}
                  {user?.is_chef && (
                    <div className="account-menu-role-section">
                      <div className="account-menu-divider" />
                      <div className="account-menu-role-label">Switch Role</div>
                      <div className="account-menu-role-toggle">
                        <button
                          type="button"
                          className={`account-menu-role-btn ${user?.current_role !== 'chef' ? 'active' : ''}`}
                          disabled={switching}
                          onClick={() => { selectRole('customer'); closeMenu(); }}
                        >
                          🥣 Customer
                        </button>
                        <button
                          type="button"
                          className={`account-menu-role-btn ${user?.current_role === 'chef' ? 'active' : ''}`}
                          disabled={switching}
                          onClick={() => { selectRole('chef'); closeMenu(); }}
                        >
                          👨‍🍳 Chef
                        </button>
                      </div>
                    </div>
                  )}
                  
                  <div className="account-menu-divider" />
                  
                  {/* Logout */}
                  <button type="button" onClick={doLogout} className="account-menu-item account-menu-item--danger" role="menuitem">
                    <span className="account-menu-emoji">🚪</span>
                    <span>Log Out</span>
                  </button>
                </div>
              )}
            </div>
          )}
          {/* Role toggle - compact in chef dashboard context */}
          {user?.is_chef && (
            <div className={`role-toggle${isChefDashboard ? ' role-toggle--compact' : ''}`} role="group" aria-label="Select role">
              <button
                type="button"
                className={`seg ${user?.current_role !== 'chef' ? 'active' : ''}`}
                aria-pressed={user?.current_role !== 'chef'}
                disabled={switching}
                title="Use app as Customer"
                onClick={()=>selectRole('customer')}
              >
                {switching && user?.current_role === 'chef' ? '…' : (isChefDashboard ? '🥣' : '🥣 Customer')}
              </button>
              <button
                type="button"
                className={`seg ${user?.current_role === 'chef' ? 'active' : ''}`}
                aria-pressed={user?.current_role === 'chef'}
                disabled={switching}
                title="Use app as Chef"
                onClick={()=>selectRole('chef')}
              >
                {switching && user?.current_role !== 'chef' ? '…' : (isChefDashboard ? '👨‍🍳' : '👨‍🍳 Chef')}
              </button>
            </div>
          )}
          {!user && <Link to="/login" onClick={closeMenu} className="btn btn-primary">Login</Link>}
          {!user && <Link to="/register" onClick={closeMenu} className="btn btn-outline">Register</Link>}
          
          {/* Compact account menu for chef dashboard */}
          {user && isChefDashboard && (
            <div className="account-menu-wrap account-menu-wrap--compact" ref={accountMenuRef}>
              <button 
                type="button" 
                className="account-trigger account-trigger--compact"
                aria-haspopup="menu" 
                aria-expanded={accountMenuOpen} 
                onClick={() => setAccountMenuOpen(v => !v)}
                title="Account menu"
              >
                <span className="account-avatar account-avatar--sm">{userInitials}</span>
              </button>
              
              {accountMenuOpen && (
                <div className="account-menu" role="menu" aria-label="Account">
                  <div className="account-menu-header">
                    <span className="account-avatar">{userInitials}</span>
                    <div className="account-menu-user">
                      <div className="account-menu-name">{userDisplayName}</div>
                      {user?.email && <div className="account-menu-email">{user.email}</div>}
                    </div>
                  </div>
                  
                  {/* Navigation section - mobile only */}
                  <div className="account-menu-nav-section">
                    <div className="account-menu-divider" />
                    <Link to="/" onClick={closeMenu} className="account-menu-item" role="menuitem">
                      <span className="account-menu-emoji">🏠</span>
                      <span>Home</span>
                    </Link>
                    <Link to="/chefs/dashboard" onClick={closeMenu} className="account-menu-item" role="menuitem">
                      <span className="account-menu-emoji">📊</span>
                      <span>Dashboard</span>
                    </Link>
                    <Link 
                      to="/chefs/dashboard" 
                      state={{ tab: 'messages' }}
                      onClick={closeMenu} 
                      className="account-menu-item" 
                      role="menuitem"
                    >
                      <span className="account-menu-emoji">💬</span>
                      <span>Messages</span>
                      {totalUnread > 0 && <span className="account-menu-badge">{totalUnread > 9 ? '9+' : totalUnread}</span>}
                    </Link>
                  </div>
                  
                  <div className="account-menu-divider" />
                  <Link to="/profile" onClick={closeMenu} className="account-menu-item" role="menuitem">
                    <span className="account-menu-emoji">⚙️</span>
                    <span>Profile Settings</span>
                  </Link>
                  
                  {/* Theme toggle - mobile only */}
                  <button 
                    type="button" 
                    onClick={() => { toggleTheme(); closeMenu(); }}
                    className="account-menu-item account-menu-theme-toggle" 
                    role="menuitem"
                  >
                    <span className="account-menu-emoji">{theme === 'dark' ? '☀️' : '🌙'}</span>
                    <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
                  </button>
                  
                  {/* Role toggle - mobile only */}
                  <div className="account-menu-role-section">
                    <div className="account-menu-divider" />
                    <div className="account-menu-role-label">Switch Role</div>
                    <div className="account-menu-role-toggle">
                      <button
                        type="button"
                        className={`account-menu-role-btn ${user?.current_role !== 'chef' ? 'active' : ''}`}
                        disabled={switching}
                        onClick={() => { selectRole('customer'); closeMenu(); }}
                      >
                        🥣 Customer
                      </button>
                      <button
                        type="button"
                        className={`account-menu-role-btn ${user?.current_role === 'chef' ? 'active' : ''}`}
                        disabled={switching}
                        onClick={() => { selectRole('chef'); closeMenu(); }}
                      >
                        👨‍🍳 Chef
                      </button>
                    </div>
                  </div>
                  
                  <div className="account-menu-divider" />
                  <button type="button" onClick={doLogout} className="account-menu-item account-menu-item--danger" role="menuitem">
                    <span className="account-menu-emoji">🚪</span>
                    <span>Log Out</span>
                  </button>
                </div>
              )}
            </div>
          )}
          <button
            type="button"
            className={isChefDashboard ? "theme-toggle-icon" : "btn btn-outline"}
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
            aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          >
            {isChefDashboard 
              ? (theme === 'dark' ? '☀️' : '🌙')
              : (theme === 'dark' ? '☀️ Light' : '🌙 Dark')
            }
          </button>
        </div>
      </div>
      
      {/* Chat Panel for customers - rendered via portal to avoid navbar stacking context issues */}
      {!inChef && chatOpen && typeof document !== 'undefined' && document.body && createPortal(
        <ChatPanel
          isOpen={chatOpen}
          onClose={() => {
            setChatOpen(false)
            setConversationId(null)
          }}
          conversationId={conversationId}
          recipientName={chatRecipient.name}
          recipientPhoto={chatRecipient.photo}
          onSwitchConversation={(newConvId, name, photo) => {
            setConversationId(newConvId)
            setChatRecipient({ name, photo })
          }}
        />,
        document.body
      )}
    </div>
  )
}
