import React, { useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { getRandomChefEmoji, getSeededChefEmoji } from '../utils/emojis.js'

/**
 * MyChefs - Client Portal chef list page
 * 
 * Shows all connected chefs for the customer, ordered by recent activity.
 * Implements smart redirect: single-chef users skip straight to ChefHub.
 */
export default function MyChefs() {
  const navigate = useNavigate()
  const { 
    connectedChefs, 
    connectedChefsLoading, 
    hasChefConnection,
    singleChef,
    hasChefAccess,
    user 
  } = useAuth()
  
  // Random chef emoji for empty state
  const emptyStateEmoji = useMemo(() => getRandomChefEmoji(), [])
  
  // Smart redirect: single chef -> skip list, go to hub
  useEffect(() => {
    if (!connectedChefsLoading && singleChef) {
      navigate(`/my-chefs/${singleChef.id}`, { replace: true })
    }
  }, [connectedChefsLoading, singleChef, navigate])
  
  // Loading state
  if (connectedChefsLoading) {
    return (
      <div className="page-my-chefs container">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading your chefs...</p>
        </div>
      </div>
    )
  }
  
  // No chefs connected
  if (!hasChefConnection) {
    return (
      <div className="page-my-chefs container">
        <div className="empty-state-professional">
          <div className="empty-icon">{emptyStateEmoji}</div>
          <h2>No Chef Connected Yet</h2>
          {hasChefAccess ? (
            <>
              <p>Connect with a chef to get personalized meal plans and services.</p>
              <Link to="/chefs" className="btn btn-primary">
                Find a Chef
              </Link>
            </>
          ) : (
            <>
              <p>Chefs aren't available in your area yet, but you can get ready!</p>
              <Link to="/get-ready" className="btn btn-primary">
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    )
  }
  
  // Multiple chefs - show list
  return (
    <div className="page-my-chefs container">
      <header className="page-header">
        <h1>My Chefs</h1>
        <p className="subtitle">Your personal chef connections</p>
      </header>
      
      <div className="chefs-list">
        {connectedChefs.map(chef => (
          <ChefCard key={chef.id} chef={chef} />
        ))}
      </div>
      
      <div className="actions-footer">
        <Link to="/chefs" className="btn btn-outline">
          Find Another Chef
        </Link>
      </div>
    </div>
  )
}

/**
 * Chef card component for the list view
 */
function ChefCard({ chef }) {
  const formatLastActivity = (dateStr) => {
    if (!dateStr) return 'No activity yet'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    return `${Math.floor(diffDays / 30)} months ago`
  }
  
  return (
    <Link to={`/my-chefs/${chef.id}`} className="chef-card">
      <div className="chef-photo">
        {chef.photo ? (
          <img src={chef.photo} alt={chef.display_name} />
        ) : (
          <div className="photo-placeholder">{getSeededChefEmoji(chef.id)}</div>
        )}
      </div>
      
      <div className="chef-info">
        <h3 className="chef-name">{chef.display_name}</h3>
        {chef.specialty && (
          <p className="chef-specialty">{chef.specialty}</p>
        )}
        {chef.rating && (
          <div className="chef-rating">
            {'★'.repeat(Math.round(chef.rating))}
            {'☆'.repeat(5 - Math.round(chef.rating))}
            <span className="rating-value">{chef.rating}</span>
          </div>
        )}
        <p className="last-activity">
          Last activity: {formatLastActivity(chef.last_activity)}
        </p>
      </div>
      
      <div className="chef-arrow">→</div>
    </Link>
  )
}

