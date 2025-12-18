import React, { useState } from 'react'
import { api } from '../api'

/**
 * SuggestionForm - Modal for submitting meal plan suggestions
 * 
 * Allows customers to suggest changes to their chef-created meal plan.
 */
export default function SuggestionForm({ 
  planId, 
  targetItem = null, 
  targetDay = null,
  onClose,
  onSubmitted 
}) {
  const [suggestionType, setSuggestionType] = useState(
    targetItem ? 'swap_meal' : targetDay ? 'skip_day' : 'general'
  )
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  
  const suggestionTypes = [
    { value: 'swap_meal', label: 'Swap this meal for something else', needsItem: true },
    { value: 'skip_day', label: 'Skip this day', needsDay: true },
    { value: 'add_day', label: 'Add a day to the plan', needsNothing: true },
    { value: 'dietary_note', label: 'Dietary concern/note', needsNothing: true },
    { value: 'general', label: 'General feedback', needsNothing: true },
  ]
  
  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!description.trim()) {
      setError('Please describe your suggestion.')
      return
    }
    
    setSubmitting(true)
    setError(null)
    
    try {
      const payload = {
        suggestion_type: suggestionType,
        description: description.trim(),
      }
      
      if (targetItem) {
        payload.target_item_id = targetItem.id
      }
      if (targetDay) {
        payload.target_day_id = targetDay.id
      }
      
      await api.post(`/meals/api/my-plans/${planId}/suggest/`, payload)
      
      if (onSubmitted) {
        onSubmitted()
      }
    } catch (e) {
      console.error('Failed to submit suggestion:', e)
      setError(e?.response?.data?.error || 'Failed to submit suggestion. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }
  
  const getContextText = () => {
    if (targetItem) {
      return `Suggesting a change for: ${targetItem.name}`
    }
    if (targetDay) {
      const dayName = new Date(targetDay.date).toLocaleDateString('en-US', { weekday: 'long' })
      return `Suggesting a change for: ${dayName}, ${targetDay.date}`
    }
    return 'Submit a suggestion for your meal plan'
  }
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content suggestion-form" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        
        <h2>Suggest a Change</h2>
        <p className="context-text">{getContextText()}</p>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="suggestion-type">Type of Suggestion</label>
            <select
              id="suggestion-type"
              value={suggestionType}
              onChange={e => setSuggestionType(e.target.value)}
              disabled={submitting}
            >
              {suggestionTypes.map(type => {
                // Only show relevant types based on target
                if (type.needsItem && !targetItem) return null
                if (type.needsDay && !targetDay && !targetItem) return null
                return (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                )
              })}
            </select>
          </div>
          
          <div className="form-group">
            <label htmlFor="description">
              {suggestionType === 'swap_meal' && 'What would you prefer instead?'}
              {suggestionType === 'skip_day' && 'Why would you like to skip this day?'}
              {suggestionType === 'add_day' && 'Which day would you like to add?'}
              {suggestionType === 'dietary_note' && 'What dietary concern do you have?'}
              {suggestionType === 'general' && 'What feedback do you have?'}
            </label>
            <textarea
              id="description"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder={getPlaceholder(suggestionType)}
              rows={4}
              disabled={submitting}
              required
            />
          </div>
          
          {error && (
            <div className="error-message">{error}</div>
          )}
          
          <div className="form-actions">
            <button 
              type="button" 
              className="btn btn-outline"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="btn btn-primary"
              disabled={submitting || !description.trim()}
            >
              {submitting ? 'Submitting...' : 'Submit Suggestion'}
            </button>
          </div>
        </form>
        
        <p className="form-note">
          Your chef will review your suggestion and respond. You'll see the status
          in your suggestions list.
        </p>
      </div>
    </div>
  )
}

function getPlaceholder(type) {
  switch (type) {
    case 'swap_meal':
      return "I'd prefer something lighter, like a salad or soup..."
    case 'skip_day':
      return "We have dinner plans that evening..."
    case 'add_day':
      return "Could we add Saturday to the plan? We'd like..."
    case 'dietary_note':
      return "I recently discovered I'm sensitive to..."
    case 'general':
      return "I really enjoyed last week's plan! Could we..."
    default:
      return "Describe your suggestion..."
  }
}






