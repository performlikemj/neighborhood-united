/**
 * MealDetailSlideout Component
 * 
 * Responsive slide-out panel for viewing and editing chef meals.
 * - Desktop: 480px side panel
 * - Tablet: 85% width overlay (max 500px)
 * - Mobile: Full screen modal
 */

import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import './MealDetailSlideout.css'

const MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner']

export default function MealDetailSlideout({
  open,
  onClose,
  meal,
  dishes = [],
  onSave,
  onDelete
}) {
  const [editMode, setEditMode] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  
  // Expandable dish cards state
  const [expandedDishes, setExpandedDishes] = useState(new Set())
  
  const toggleDishExpand = (dishId) => {
    setExpandedDishes(prev => {
      const next = new Set(prev)
      if (next.has(dishId)) {
        next.delete(dishId)
      } else {
        next.add(dishId)
      }
      return next
    })
  }
  
  // Edit form state
  const [form, setForm] = useState({
    name: '',
    description: '',
    meal_type: 'Dinner',
    price: '',
    dishes: []
  })
  
  // Initialize form when meal changes
  useEffect(() => {
    if (meal) {
      setForm({
        name: meal.name || '',
        description: meal.description || '',
        meal_type: meal.meal_type || 'Dinner',
        price: meal.price?.toString() || '',
        dishes: Array.isArray(meal.dishes) 
          ? meal.dishes.map(d => typeof d === 'object' ? d.id : d) 
          : []
      })
      setEditMode(false)
      setError(null)
      setExpandedDishes(new Set()) // Reset expanded dishes when viewing new meal
    }
  }, [meal])
  
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && open) {
        if (editMode) {
          setEditMode(false)
        } else {
          onClose()
        }
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open, editMode, onClose])
  
  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])
  
  const handleSave = async () => {
    if (!meal?.id) return
    
    // Validation
    const trimmedName = form.name.trim()
    if (!trimmedName) {
      setError('Meal name is required')
      return
    }
    if (form.dishes.length === 0) {
      setError('At least one dish is required')
      return
    }
    
    setSaving(true)
    setError(null)
    
    try {
      const payload = {
        name: trimmedName,
        description: form.description.trim(),
        meal_type: form.meal_type,
        price: parseFloat(form.price) || 0,
        dish_ids: form.dishes.map(d => Number(d))
      }
      
      await api.put(`/meals/api/chef/meals/${meal.id}/`, payload)
      
      // Notify parent of successful save
      if (onSave) {
        onSave({
          ...meal,
          ...payload
        })
      }
      
      setEditMode(false)
      
      // Show success toast
      try {
        window.dispatchEvent(new CustomEvent('global-toast', {
          detail: { text: 'Meal updated successfully', tone: 'success' }
        }))
      } catch {}
      
    } catch (err) {
      console.error('Failed to update meal:', err)
      const errorMessage = err.response?.data?.message || err.response?.data?.error || 'Failed to update meal'
      setError(errorMessage)
    } finally {
      setSaving(false)
    }
  }
  
  const handleDelete = async () => {
    if (!meal?.id) return
    if (!confirm(`Delete "${meal.name}"? This cannot be undone.`)) return
    
    try {
      await api.delete(`/meals/api/chef/meals/${meal.id}/`)
      
      if (onDelete) {
        onDelete(meal.id)
      }
      
      onClose()
      
      try {
        window.dispatchEvent(new CustomEvent('global-toast', {
          detail: { text: 'Meal deleted', tone: 'success' }
        }))
      } catch {}
      
    } catch (err) {
      console.error('Failed to delete meal:', err)
      setError('Failed to delete meal')
    }
  }
  
  const toggleDish = (dishId) => {
    setForm(prev => ({
      ...prev,
      dishes: prev.dishes.includes(dishId)
        ? prev.dishes.filter(id => id !== dishId)
        : [...prev.dishes, dishId]
    }))
  }
  
  const cancelEdit = () => {
    // Reset form to original meal values
    if (meal) {
      setForm({
        name: meal.name || '',
        description: meal.description || '',
        meal_type: meal.meal_type || 'Dinner',
        price: meal.price?.toString() || '',
        dishes: Array.isArray(meal.dishes) 
          ? meal.dishes.map(d => typeof d === 'object' ? d.id : d) 
          : []
      })
    }
    setEditMode(false)
    setError(null)
  }
  
  // Format price for display
  const formatPrice = (price) => {
    if (price == null) return '$0.00'
    const num = typeof price === 'string' ? parseFloat(price) : price
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(num || 0)
  }
  
  // Format date for display
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A'
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      })
    } catch {
      return dateStr
    }
  }
  
  // Get dishes that are part of this meal
  const getMealDishes = () => {
    if (!meal?.dishes) return []
    return meal.dishes.map(d => {
      if (typeof d === 'object') return d
      // Find dish in dishes array
      const found = dishes.find(dish => dish.id === d)
      return found || { id: d, name: `Dish #${d}` }
    })
  }
  
  if (!open) return null
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className={`meal-slideout-backdrop ${open ? 'open' : ''}`}
        onClick={onClose}
        aria-hidden="true"
      />
      
      {/* Slideout Panel */}
      <aside 
        className={`meal-slideout ${open ? 'open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={`Meal details: ${meal?.name || 'Meal'}`}
      >
        {/* Header */}
        <header className="meal-slideout-header">
          <div className="header-content">
            <button 
              className="back-btn"
              onClick={onClose}
              aria-label="Close"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M19 12H5M12 19l-7-7 7-7"/>
              </svg>
            </button>
            <div className="header-text">
              <h2>{editMode ? 'Edit Meal' : (meal?.name || 'Meal Details')}</h2>
              {!editMode && meal?.meal_type && (
                <span className="meal-type-badge">{meal.meal_type}</span>
              )}
            </div>
          </div>
          <div className="header-actions">
            {!editMode ? (
              <>
                <button 
                  className="btn btn-outline btn-sm"
                  onClick={() => setEditMode(true)}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                  Edit
                </button>
              </>
            ) : (
              <button 
                className="btn btn-outline btn-sm"
                onClick={cancelEdit}
              >
                Cancel
              </button>
            )}
          </div>
        </header>
        
        {/* Error Banner */}
        {error && (
          <div className="meal-slideout-error">
            <span>{error}</span>
            <button onClick={() => setError(null)} aria-label="Dismiss error">×</button>
          </div>
        )}
        
        {/* Content */}
        <div className="meal-slideout-content">
          {editMode ? (
            /* Edit Mode */
            <div className="edit-form">
              <div className="form-group">
                <label className="form-label">Meal Name *</label>
                <input
                  type="text"
                  className="form-input"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g., Sunday Roast Dinner"
                />
              </div>
              
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Meal Type</label>
                  <select
                    className="form-select"
                    value={form.meal_type}
                    onChange={e => setForm(f => ({ ...f, meal_type: e.target.value }))}
                  >
                    {MEAL_TYPES.map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </select>
                </div>
                
                <div className="form-group">
                  <label className="form-label">Price ($)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={form.price}
                    onChange={e => setForm(f => ({ ...f, price: e.target.value }))}
                    placeholder="0.00"
                    min="0"
                    step="0.01"
                  />
                </div>
              </div>
              
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-textarea"
                  value={form.description}
                  onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                  placeholder="Describe your meal..."
                  rows={4}
                />
              </div>
              
              <div className="form-group">
                <label className="form-label">Dishes *</label>
                <p className="form-hint">Select dishes to include in this meal</p>
                <div className="dish-selector">
                  {dishes.length === 0 ? (
                    <p className="muted">No dishes available. Create dishes first.</p>
                  ) : (
                    dishes.map(dish => (
                      <label 
                        key={dish.id} 
                        className={`dish-option ${form.dishes.includes(dish.id) ? 'selected' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={form.dishes.includes(dish.id)}
                          onChange={() => toggleDish(dish.id)}
                        />
                        <span className="dish-name">{dish.name}</span>
                        {dish.ingredients?.length > 0 && (
                          <span className="dish-ingredients">
                            {dish.ingredients.slice(0, 3).map(i => i.name || i).join(', ')}
                            {dish.ingredients.length > 3 && '...'}
                          </span>
                        )}
                      </label>
                    ))
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* View Mode */
            <>
              {/* Meal Image */}
              {meal?.image && (
                <div className="meal-image-container">
                  <img 
                    src={meal.image} 
                    alt={meal.name}
                    className="meal-image"
                  />
                </div>
              )}
              
              {/* Quick Stats */}
              <div className="meal-stats">
                <div className="stat-item">
                  <span className="stat-label">Price</span>
                  <span className="stat-value price">{formatPrice(meal?.price)}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Type</span>
                  <span className="stat-value">{meal?.meal_type || 'Dinner'}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Created</span>
                  <span className="stat-value">{formatDate(meal?.created_date)}</span>
                </div>
              </div>
              
              {/* Description */}
              {meal?.description && (
                <section className="meal-section">
                  <h3 className="section-title">Description</h3>
                  <p className="meal-description">{meal.description}</p>
                </section>
              )}
              
              {/* Dishes */}
              <section className="meal-section">
                <h3 className="section-title">
                  Dishes Included
                  <span className="count-badge">{getMealDishes().length}</span>
                </h3>
                <div className="dishes-list">
                  {getMealDishes().length === 0 ? (
                    <p className="muted">No dishes linked to this meal.</p>
                  ) : (
                    getMealDishes().map((dish, idx) => {
                      const isExpanded = expandedDishes.has(dish.id)
                      const hasIngredients = dish.ingredients?.length > 0
                      const hasNotes = dish.notes || dish.description
                      const hasExpandableContent = hasIngredients || hasNotes
                      
                      return (
                        <div 
                          key={dish.id || idx} 
                          className={`dish-card ${isExpanded ? 'expanded' : ''} ${hasExpandableContent ? 'expandable' : ''}`}
                        >
                          <button 
                            className="dish-card-header"
                            onClick={() => hasExpandableContent && toggleDishExpand(dish.id)}
                            type="button"
                            aria-expanded={isExpanded}
                          >
                            <span className="dish-icon">🍽️</span>
                            <span className="dish-name">{dish.name}</span>
                            {hasExpandableContent && (
                              <span className={`dish-expand-icon ${isExpanded ? 'expanded' : ''}`}>
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="6 9 12 15 18 9"></polyline>
                                </svg>
                              </span>
                            )}
                          </button>
                          
                          {/* Collapsed preview - show first few ingredients */}
                          {!isExpanded && hasIngredients && (
                            <div className="dish-ingredients-preview">
                              {dish.ingredients.slice(0, 3).map((ing, i) => (
                                <span key={i} className="ingredient-tag">
                                  {typeof ing === 'string' ? ing : ing.name}
                                </span>
                              ))}
                              {dish.ingredients.length > 3 && (
                                <span className="ingredient-more">+{dish.ingredients.length - 3} more</span>
                              )}
                            </div>
                          )}
                          
                          {/* Expanded details */}
                          {isExpanded && (
                            <div className="dish-details">
                              {hasIngredients && (
                                <div className="dish-details-section">
                                  <span className="dish-details-label">Ingredients</span>
                                  <div className="dish-ingredients">
                                    {dish.ingredients.map((ing, i) => (
                                      <span key={i} className="ingredient-tag">
                                        {typeof ing === 'string' ? ing : ing.name}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {hasNotes && (
                                <div className="dish-details-section">
                                  <span className="dish-details-label">Notes</span>
                                  <p className="dish-notes">{dish.notes || dish.description}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })
                  )}
                </div>
              </section>
              
              {/* Dietary Preferences */}
              {meal?.dietary_preferences?.length > 0 && (
                <section className="meal-section">
                  <h3 className="section-title">Dietary Tags</h3>
                  <div className="dietary-tags">
                    {meal.dietary_preferences.map((pref, idx) => (
                      <span key={idx} className="dietary-tag">
                        {typeof pref === 'string' ? pref : pref.name}
                      </span>
                    ))}
                  </div>
                </section>
              )}
              
              {/* Events count */}
              {meal?.events?.length > 0 && (
                <section className="meal-section">
                  <h3 className="section-title">
                    Scheduled Events
                    <span className="count-badge">{meal.events.length}</span>
                  </h3>
                  <p className="muted">
                    This meal is scheduled for {meal.events.length} event{meal.events.length !== 1 ? 's' : ''}.
                  </p>
                </section>
              )}
            </>
          )}
        </div>
        
        {/* Footer */}
        <footer className="meal-slideout-footer">
          {editMode ? (
            <div className="footer-actions">
              <button 
                className="btn btn-danger"
                onClick={handleDelete}
              >
                Delete Meal
              </button>
              <button 
                className="btn btn-primary"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          ) : (
            <div className="footer-actions">
              <button 
                className="btn btn-danger-outline"
                onClick={handleDelete}
              >
                Delete
              </button>
              <button 
                className="btn btn-primary"
                onClick={() => setEditMode(true)}
              >
                Edit Meal
              </button>
            </div>
          )}
        </footer>
      </aside>
    </>
  )
}

