import React, { useState, useEffect } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import { getSeededChefEmoji } from '../utils/emojis.js'

/**
 * ChefHub - Individual chef relationship page
 * 
 * The main hub for a customer's relationship with a specific chef.
 * Shows current meal plan, upcoming orders, and quick actions.
 */
export default function ChefHub() {
  const { chefId } = useParams()
  const navigate = useNavigate()
  const { connectedChefs } = useAuth()
  
  const [hubData, setHubData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Check if we have multiple chefs (to show back button)
  const hasMultipleChefs = connectedChefs.length > 1
  
  useEffect(() => {
    fetchHubData()
  }, [chefId])
  
  const fetchHubData = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.get(`/customer-dashboard/api/my-chefs/${chefId}/`)
      setHubData(resp.data)
    } catch (e) {
      console.error('Failed to fetch chef hub data:', e)
      if (e?.response?.status === 404) {
        setError('Chef connection not found.')
      } else if (e?.response?.status === 403) {
        setError('You don\'t have access to this chef.')
      } else {
        setError('Failed to load chef information.')
      }
    } finally {
      setLoading(false)
    }
  }
  
  if (loading) {
    return (
      <div className="page-chef-hub container">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="page-chef-hub container">
        <div className="error-state">
          <h2>Oops!</h2>
          <p>{error}</p>
          <Link to="/my-chefs" className="btn btn-primary">Back to My Chefs</Link>
        </div>
      </div>
    )
  }
  
  const { chef, connected_since, current_plan, upcoming_orders, pending_suggestions } = hubData
  
  return (
    <div className="page-chef-hub container">
      {/* Back link for multi-chef users */}
      {hasMultipleChefs && (
        <Link to="/my-chefs" className="back-link">← Back to My Chefs</Link>
      )}
      
      {/* Chef Header */}
      <header className="chef-header">
        <div className="chef-photo-large">
          {chef.photo ? (
            <img src={chef.photo} alt={chef.display_name} />
          ) : (
            <div className="photo-placeholder-large">{getSeededChefEmoji(chef.id)}</div>
          )}
        </div>
        
        <div className="chef-details">
          <h1>{chef.display_name}</h1>
          {chef.rating && (
            <div className="chef-rating">
              {'★'.repeat(Math.round(chef.rating))}
              {'☆'.repeat(5 - Math.round(chef.rating))}
              <span className="rating-text">
                {chef.rating} ({chef.review_count} reviews)
              </span>
            </div>
          )}
          <p className="connected-since">
            Connected since {formatDate(connected_since)}
          </p>
          
          <div className="chef-actions">
            <button className="btn btn-outline" onClick={() => {/* TODO: Message chef */}}>
              Message Chef
            </button>
            <Link to={`/chefs/${chef.username}`} className="btn btn-outline">
              View Profile
            </Link>
          </div>
        </div>
      </header>
      
      {/* Current Meal Plan */}
      <section className="hub-section">
        <div className="section-header">
          <h2>Current Meal Plan</h2>
          {current_plan && (
            <Link to={`/my-chefs/${chefId}/meal-plan`} className="view-all-link">
              View All →
            </Link>
          )}
        </div>
        
        {current_plan ? (
          <MealPlanSummary plan={current_plan} chefId={chefId} />
        ) : (
          <div className="empty-section">
            <p>No active meal plan yet.</p>
            <p className="hint">Your chef will create a personalized plan for you.</p>
          </div>
        )}
        
        {pending_suggestions > 0 && (
          <div className="pending-badge">
            {pending_suggestions} suggestion{pending_suggestions > 1 ? 's' : ''} pending review
          </div>
        )}
      </section>
      
      {/* Upcoming Orders */}
      <section className="hub-section">
        <div className="section-header">
          <h2>Upcoming Orders</h2>
          <Link to={`/my-chefs/${chefId}/orders`} className="view-all-link">
            View All →
          </Link>
        </div>
        
        {upcoming_orders && upcoming_orders.length > 0 ? (
          <div className="orders-list">
            {upcoming_orders.map(order => (
              <OrderCard key={order.id} order={order} />
            ))}
          </div>
        ) : (
          <div className="empty-section">
            <p>No upcoming orders.</p>
          </div>
        )}
      </section>
      
      {/* Quick Actions */}
      <section className="hub-section quick-actions">
        <h2>Quick Actions</h2>
        <div className="action-buttons">
          <Link to={`/chefs/${chef.username}`} className="action-btn">
            <span className="action-icon">🍽️</span>
            <span className="action-label">Browse Menu</span>
          </Link>
          <Link to="/profile" className="action-btn">
            <span className="action-icon">⚙️</span>
            <span className="action-label">Update Preferences</span>
          </Link>
          <button className="action-btn" onClick={() => {/* TODO: Request service */}}>
            <span className="action-icon">📅</span>
            <span className="action-label">Request Service</span>
          </button>
        </div>
      </section>
    </div>
  )
}

/**
 * Meal plan summary component
 */
function MealPlanSummary({ plan, chefId }) {
  return (
    <div className="meal-plan-summary">
      <div className="plan-header">
        <h3>{plan.title}</h3>
        <span className="plan-dates">
          {formatDate(plan.start_date)} - {formatDate(plan.end_date)}
        </span>
      </div>
      
      {plan.notes && (
        <p className="plan-notes">{plan.notes}</p>
      )}
      
      <div className="plan-actions">
        <Link to={`/my-chefs/${chefId}/meal-plan`} className="btn btn-primary">
          View Full Plan
        </Link>
        <Link to={`/my-chefs/${chefId}/meal-plan?suggest=true`} className="btn btn-outline">
          Suggest Changes
        </Link>
      </div>
    </div>
  )
}

/**
 * Order card component
 */
function OrderCard({ order }) {
  const statusColors = {
    placed: 'status-pending',
    confirmed: 'status-confirmed',
    completed: 'status-completed',
    cancelled: 'status-cancelled',
  }
  
  return (
    <div className="order-card">
      <div className="order-info">
        <h4>{order.meal_name}</h4>
        <p className="order-date">{formatDate(order.event_date)}</p>
      </div>
      <div className="order-meta">
        <span className={`status-badge ${statusColors[order.status] || ''}`}>
          {order.status}
        </span>
        {order.price && (
          <span className="order-price">${order.price}</span>
        )}
      </div>
    </div>
  )
}

/**
 * Format date helper
 */
function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
  })
}

