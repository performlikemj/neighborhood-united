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
      const resp = await api.get(`/customer_dashboard/api/my-chefs/${chefId}/`)
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
      <div className="page-chef-hub">
        <div className="chef-hub-loading">
          <div className="spinner" style={{width: 40, height: 40, borderWidth: 4}} />
          <p>Loading your chef...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="page-chef-hub">
        <div className="chef-hub-error">
          <div className="error-icon">😕</div>
          <h2>Oops!</h2>
          <p>{error}</p>
          <Link to="/my-chefs" className="btn btn-primary">Back to My Chefs</Link>
        </div>
      </div>
    )
  }
  
  const { chef, connected_since, current_plan, upcoming_orders, pending_suggestions } = hubData
  
  return (
    <div className="page-chef-hub">
      {/* Back link for multi-chef users */}
      {hasMultipleChefs && (
        <div className="chef-hub-back">
          <Link to="/my-chefs" className="back-link">
            <i className="fa-solid fa-arrow-left"></i>
            Back to My Chefs
          </Link>
        </div>
      )}
      
      {/* Chef Header - Hero Style */}
      <header className="chef-hub-hero">
        <div className="chef-hub-hero-content">
          <div className="chef-hub-avatar">
            {chef.photo ? (
              <img src={chef.photo} alt={chef.display_name} className="chef-hub-photo" />
            ) : (
              <div className="chef-hub-photo-placeholder">
                {getSeededChefEmoji(chef.id)}
              </div>
            )}
            <div className="chef-hub-status-badge">
              <i className="fa-solid fa-check"></i>
              Connected
            </div>
          </div>
          
          <div className="chef-hub-info">
            <h1 className="chef-hub-name">{chef.display_name}</h1>
            
            {chef.specialty && (
              <p className="chef-hub-specialty">{chef.specialty}</p>
            )}
            
            {chef.rating && (
              <div className="chef-hub-rating">
                <div className="stars">
                  {[1,2,3,4,5].map(star => (
                    <i 
                      key={star}
                      className={`fa-solid fa-star ${star <= Math.round(chef.rating) ? 'filled' : 'empty'}`}
                    ></i>
                  ))}
                </div>
                {chef.review_count > 0 && (
                  <span className="rating-text">
                    {chef.rating.toFixed(1)} ({chef.review_count} {chef.review_count === 1 ? 'review' : 'reviews'})
                  </span>
                )}
              </div>
            )}
            
            <p className="chef-hub-connected">
              <i className="fa-regular fa-calendar-check"></i>
              Connected since {formatDate(connected_since)}
            </p>
            
            <div className="chef-hub-actions">
              <button className="btn btn-outline btn-icon" onClick={() => {/* TODO: Message chef */}}>
                <i className="fa-regular fa-comment"></i>
                Message Chef
              </button>
              <Link to={`/chefs/${chef.username}`} className="btn btn-outline btn-icon">
                <i className="fa-regular fa-user"></i>
                View Profile
              </Link>
            </div>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <div className="chef-hub-content">
        {/* Current Meal Plan */}
        <section className="hub-card">
          <div className="hub-card-header">
            <div className="hub-card-title">
              <i className="fa-solid fa-utensils"></i>
              <h2>Current Meal Plan</h2>
            </div>
            {current_plan && (
              <Link to={`/my-chefs/${chefId}/meal-plan`} className="view-all-link">
                View All <i className="fa-solid fa-arrow-right"></i>
              </Link>
            )}
          </div>
          
          <div className="hub-card-body">
            {current_plan ? (
              <MealPlanSummary plan={current_plan} chefId={chefId} />
            ) : (
              <div className="hub-empty-state">
                <div className="empty-icon">🍽️</div>
                <p className="empty-title">No active meal plan yet</p>
                <p className="empty-hint">Your chef will create a personalized plan for you.</p>
              </div>
            )}
            
            {pending_suggestions > 0 && (
              <div className="pending-badge">
                <i className="fa-solid fa-bell"></i>
                {pending_suggestions} suggestion{pending_suggestions > 1 ? 's' : ''} pending review
              </div>
            )}
          </div>
        </section>
        
        {/* Upcoming Orders */}
        <section className="hub-card">
          <div className="hub-card-header">
            <div className="hub-card-title">
              <i className="fa-solid fa-clock"></i>
              <h2>Upcoming Orders</h2>
            </div>
            <Link to={`/my-chefs/${chefId}/orders`} className="view-all-link">
              View All <i className="fa-solid fa-arrow-right"></i>
            </Link>
          </div>
          
          <div className="hub-card-body">
            {upcoming_orders && upcoming_orders.length > 0 ? (
              <div className="orders-list">
                {upcoming_orders.map(order => (
                  <OrderCard key={order.id} order={order} />
                ))}
              </div>
            ) : (
              <div className="hub-empty-state">
                <div className="empty-icon">📦</div>
                <p className="empty-title">No upcoming orders</p>
                <p className="empty-hint">Your orders will appear here when placed.</p>
              </div>
            )}
          </div>
        </section>
        
        {/* Quick Actions */}
        <section className="hub-card hub-actions-card">
          <div className="hub-card-header">
            <div className="hub-card-title">
              <i className="fa-solid fa-bolt"></i>
              <h2>Quick Actions</h2>
            </div>
          </div>
          
          <div className="hub-card-body">
            <div className="quick-actions-grid">
              <Link to={`/chefs/${chef.username}`} className="quick-action-item">
                <div className="quick-action-icon">
                  <i className="fa-solid fa-book-open"></i>
                </div>
                <span className="quick-action-label">Browse Menu</span>
                <i className="fa-solid fa-chevron-right quick-action-arrow"></i>
              </Link>
              
              <Link to="/profile" className="quick-action-item">
                <div className="quick-action-icon">
                  <i className="fa-solid fa-sliders"></i>
                </div>
                <span className="quick-action-label">Update Preferences</span>
                <i className="fa-solid fa-chevron-right quick-action-arrow"></i>
              </Link>
              
              <button className="quick-action-item" onClick={() => {/* TODO: Request service */}}>
                <div className="quick-action-icon">
                  <i className="fa-solid fa-calendar-plus"></i>
                </div>
                <span className="quick-action-label">Request Service</span>
                <i className="fa-solid fa-chevron-right quick-action-arrow"></i>
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

/**
 * Meal plan summary component
 */
function MealPlanSummary({ plan, chefId }) {
  return (
    <div className="meal-plan-summary">
      <div className="plan-info">
        <h3 className="plan-title">{plan.title}</h3>
        <div className="plan-dates">
          <i className="fa-regular fa-calendar"></i>
          {formatDate(plan.start_date)} - {formatDate(plan.end_date)}
        </div>
        {plan.notes && (
          <p className="plan-notes">{plan.notes}</p>
        )}
      </div>
      
      <div className="plan-actions">
        <Link to={`/my-chefs/${chefId}/meal-plan`} className="btn btn-primary">
          <i className="fa-solid fa-eye"></i>
          View Full Plan
        </Link>
        <Link to={`/my-chefs/${chefId}/meal-plan?suggest=true`} className="btn btn-outline">
          <i className="fa-solid fa-lightbulb"></i>
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
  const statusConfig = {
    placed: { color: 'status-pending', icon: 'fa-clock', label: 'Placed' },
    confirmed: { color: 'status-confirmed', icon: 'fa-check-circle', label: 'Confirmed' },
    completed: { color: 'status-completed', icon: 'fa-check-double', label: 'Completed' },
    cancelled: { color: 'status-cancelled', icon: 'fa-times-circle', label: 'Cancelled' },
  }
  
  const status = statusConfig[order.status] || statusConfig.placed
  
  return (
    <div className="order-card-item">
      <div className="order-main">
        <h4 className="order-name">{order.meal_name}</h4>
        <div className="order-date">
          <i className="fa-regular fa-calendar"></i>
          {formatDate(order.event_date)}
        </div>
      </div>
      <div className="order-meta">
        <span className={`order-status ${status.color}`}>
          <i className={`fa-solid ${status.icon}`}></i>
          {status.label}
        </span>
        {order.price && (
          <span className="order-price">${parseFloat(order.price).toFixed(2)}</span>
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
