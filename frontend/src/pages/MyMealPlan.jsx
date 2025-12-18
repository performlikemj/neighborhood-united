import React, { useState, useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import SuggestionForm from '../components/SuggestionForm.jsx'

/**
 * MyMealPlan - Customer view of their chef-created meal plan
 * 
 * Shows the full meal plan with all days and items.
 * Allows customers to suggest changes via the suggestion form.
 */
export default function MyMealPlan() {
  const { chefId } = useParams()
  const [searchParams] = useSearchParams()
  
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Suggestion form state
  const [showSuggestionForm, setShowSuggestionForm] = useState(
    searchParams.get('suggest') === 'true'
  )
  const [suggestionTarget, setSuggestionTarget] = useState(null)
  
  useEffect(() => {
    fetchPlan()
  }, [chefId])
  
  const fetchPlan = async () => {
    setLoading(true)
    setError(null)
    try {
      // Get current plan for this chef
      const resp = await api.get(`/meals/api/my-plans/current/?chef_id=${chefId}`)
      setPlan(resp.data.plan)
    } catch (e) {
      console.error('Failed to fetch meal plan:', e)
      setError('Failed to load meal plan.')
    } finally {
      setLoading(false)
    }
  }
  
  const openSuggestionForm = (item = null, day = null) => {
    setSuggestionTarget({ item, day })
    setShowSuggestionForm(true)
  }
  
  const closeSuggestionForm = () => {
    setShowSuggestionForm(false)
    setSuggestionTarget(null)
  }
  
  const handleSuggestionSubmitted = () => {
    closeSuggestionForm()
    // Could refresh plan or show success message
  }
  
  if (loading) {
    return (
      <div className="page-meal-plan container">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading meal plan...</p>
        </div>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="page-meal-plan container">
        <div className="error-state">
          <h2>Oops!</h2>
          <p>{error}</p>
          <Link to={`/my-chefs/${chefId}`} className="btn btn-primary">
            Back to Chef Hub
          </Link>
        </div>
      </div>
    )
  }
  
  if (!plan) {
    return (
      <div className="page-meal-plan container">
        <div className="empty-state-professional">
          <div className="empty-icon">📋</div>
          <h2>No Active Meal Plan</h2>
          <p>Your chef hasn't created a meal plan for you yet.</p>
          <Link to={`/my-chefs/${chefId}`} className="btn btn-primary">
            Back to Chef Hub
          </Link>
        </div>
      </div>
    )
  }
  
  return (
    <div className="page-meal-plan container">
      <Link to={`/my-chefs/${chefId}`} className="back-link">
        ← Back to Chef Hub
      </Link>
      
      {/* Plan Header */}
      <header className="plan-header">
        <div className="plan-title-row">
          <h1>{plan.title}</h1>
          <span className="plan-status">{plan.status}</span>
        </div>
        <p className="plan-dates">
          {formatDate(plan.start_date)} - {formatDate(plan.end_date)}
        </p>
        {plan.notes && (
          <div className="plan-notes">
            <strong>Chef's Notes:</strong>
            <p>{plan.notes}</p>
          </div>
        )}
        
        <div className="plan-actions">
          <button 
            className="btn btn-outline"
            onClick={() => openSuggestionForm()}
          >
            Suggest Changes
          </button>
          <Link 
            to={`/my-chefs/${chefId}/meal-plan/suggestions`}
            className="btn btn-outline"
          >
            View My Suggestions
            {plan.pending_suggestions > 0 && (
              <span className="badge">{plan.pending_suggestions}</span>
            )}
          </Link>
        </div>
      </header>
      
      {/* Days List */}
      <div className="plan-days">
        {plan.days && plan.days.map(day => (
          <DayCard 
            key={day.id} 
            day={day}
            onSuggestChange={(item) => openSuggestionForm(item, day)}
          />
        ))}
        
        {(!plan.days || plan.days.length === 0) && (
          <div className="empty-section">
            <p>No days have been added to this plan yet.</p>
          </div>
        )}
      </div>
      
      {/* Suggestion Form Modal */}
      {showSuggestionForm && (
        <SuggestionForm
          planId={plan.id}
          targetItem={suggestionTarget?.item}
          targetDay={suggestionTarget?.day}
          onClose={closeSuggestionForm}
          onSubmitted={handleSuggestionSubmitted}
        />
      )}
    </div>
  )
}

/**
 * Day card component
 */
function DayCard({ day, onSuggestChange }) {
  const dayOfWeek = new Date(day.date).toLocaleDateString('en-US', { weekday: 'long' })
  
  if (day.is_skipped) {
    return (
      <div className="day-card skipped">
        <div className="day-header">
          <h3>{dayOfWeek}</h3>
          <span className="day-date">{formatDate(day.date)}</span>
        </div>
        <div className="skipped-content">
          <span className="skip-icon">⏭️</span>
          <span className="skip-text">
            {day.skip_reason || 'Day skipped'}
          </span>
        </div>
      </div>
    )
  }
  
  // Group items by meal type
  const mealTypes = ['breakfast', 'lunch', 'dinner', 'snack']
  const itemsByType = {}
  mealTypes.forEach(type => {
    itemsByType[type] = day.items?.filter(item => item.meal_type === type) || []
  })
  
  return (
    <div className="day-card">
      <div className="day-header">
        <h3>{dayOfWeek}</h3>
        <span className="day-date">{formatDate(day.date)}</span>
      </div>
      
      {day.notes && (
        <p className="day-notes">{day.notes}</p>
      )}
      
      <div className="meals-grid">
        {mealTypes.map(type => {
          const items = itemsByType[type]
          if (items.length === 0) return null
          
          return (
            <div key={type} className="meal-type-section">
              <h4 className="meal-type-label">
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </h4>
              {items.map(item => (
                <MealItem 
                  key={item.id} 
                  item={item}
                  onSuggestChange={() => onSuggestChange(item)}
                />
              ))}
            </div>
          )
        })}
      </div>
      
      {(!day.items || day.items.length === 0) && (
        <p className="no-meals">No meals planned for this day.</p>
      )}
    </div>
  )
}

/**
 * Meal item component
 */
function MealItem({ item, onSuggestChange }) {
  return (
    <div className="meal-item">
      <div className="meal-info">
        <h5 className="meal-name">{item.name}</h5>
        {item.description && (
          <p className="meal-description">{item.description}</p>
        )}
        {item.servings > 1 && (
          <span className="servings">{item.servings} servings</span>
        )}
        {item.notes && (
          <p className="meal-notes"><em>{item.notes}</em></p>
        )}
      </div>
      <button 
        className="suggest-btn"
        onClick={onSuggestChange}
        title="Suggest a change"
      >
        ✏️
      </button>
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
    day: 'numeric'
  })
}






