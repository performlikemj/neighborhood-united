import React, { useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function ProtectedRoute({ children, requiredRole }){
  const { user, loading, switchRole } = useAuth()
  const [busyRole, setBusyRole] = useState(null)
  const [switchError, setSwitchError] = useState(null)

  const roleOptions = useMemo(()=>{
    if (!user) return []
    const options = [{ role:'customer', label:'Customer mode', blurb:'Browse sautai as a customer and explore meal plans.' }]
    if (user.is_chef){
      options.unshift({ role:'chef', label:'Chef mode', blurb:'Manage your chef profile, events, and services.' })
    }
    return options
  }, [user])

  async function handleSwitch(targetRole){
    if (!targetRole || busyRole === targetRole) return
    setSwitchError(null)
    setBusyRole(targetRole)
    try{
      await switchRole(targetRole)
    }catch(err){
      console.warn('[ProtectedRoute] switch role failed', err?.response?.status)
      setSwitchError('Unable to switch modes right now. Please try again in a moment.')
    } finally {
      setBusyRole(null)
    }
  }

  if (loading) return <div className="container"><p>Loading…</p></div>
  if (!user) {
    const next = typeof window !== 'undefined' ? window.location.pathname + window.location.search : '/'
    console.warn('[ProtectedRoute] No user → redirect to /login', { next })
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  const currentRole = user?.current_role || 'customer'

  // If user not verified, restrict access to most protected pages
  try{
    const path = typeof window !== 'undefined' ? (window.location.pathname || '') : ''
    const allowUnverifiedPaths = new Set(['/verify-email','/profile'])
    const isAllowed = allowUnverifiedPaths.has(path)
    const isVerified = Boolean(user?.email_confirmed)
    if (!isVerified && !isAllowed){
      return <Navigate to="/verify-email" replace />
    }
  }catch{}

  if (requiredRole){
    const isChef = Boolean(user?.is_chef)
    const roleAllowed = (
      (requiredRole === 'chef' && isChef && currentRole === 'chef') ||
      (requiredRole === 'customer' && currentRole === 'customer')
    )
    if (!roleAllowed){
      const canChooseMode = (requiredRole === 'customer') || (requiredRole === 'chef' && isChef)
      if (!canChooseMode){
        return <Navigate to="/403" replace />
      }
      return (
        <div className="container">
          <div className="card" style={{maxWidth:'520px', margin:'0 auto', padding:'1.4rem 1.6rem', borderRadius:'var(--radius-xl)', boxShadow:'var(--shadow-sm)'}}>
            <h2 style={{margin:'0 0 .25rem 0'}}>Pick your mode</h2>
            <p className="muted" style={{marginTop:'.35rem'}}>
              You’re currently in <strong>{formatRoleLabel(currentRole)}</strong>. This Meal Plans page is meant for <strong>{formatRoleLabel(requiredRole)}</strong>.
              Choose where you’d like to continue.
            </p>
            {switchError && (
              <div style={{marginTop:'.6rem', color:'#b94a48'}}>{switchError}</div>
            )}
            <div style={{display:'grid', gap:'.65rem', marginTop:'.9rem'}}>
              {roleOptions.map(opt => {
                const isCurrent = opt.role === currentRole
                const isTarget = opt.role === requiredRole
                return (
                  <button
                    key={opt.role}
                    type="button"
                    className={`mode-option ${isTarget ? 'active' : ''} ${isCurrent ? 'current' : ''}`.trim()}
                    disabled={busyRole === opt.role || isCurrent}
                    onClick={()=> handleSwitch(opt.role)}
                  >
                    <span className="mode-option__title">{busyRole === opt.role ? 'Switching…' : opt.label}</span>
                    <span className="mode-option__desc">{opt.blurb}</span>
                  </button>
                )
              })}
            </div>
            <Link
              to={currentRole === 'chef' ? '/chefs/dashboard' : '/meal-plans'}
              className="mode-option secondary"
              style={{marginTop:'1rem'}}
            >
              <span className="mode-option__title">Stay in {formatRoleLabel(currentRole)}</span>
              <span className="mode-option__desc">Return to your current workspace instead.</span>
            </Link>
          </div>
        </div>
      )
    }
  }

  return children
}

function formatRoleLabel(role){
  return role === 'chef' ? 'Chef mode' : 'Customer mode'
}
