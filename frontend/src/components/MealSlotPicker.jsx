/**
 * MealSlotPicker Component
 * 
 * Modal for selecting what meal to assign to a slot.
 * Options:
 * 1. Pick from chef's composed meals (multi-dish)
 * 2. Pick from chef's saved single items
 * 3. Generate AI suggestion for this slot
 * 4. Compose meal on-the-fly from dishes
 * 5. Enter custom meal name
 */

import React, { useState, useEffect } from 'react'
import { getChefDishes, getChefComposedMeals, startMealGeneration } from '../api/chefMealPlanClient.js'
import { useSousChefNotifications } from '../contexts/SousChefNotificationContext.jsx'

// Helper to format meal type for display
const MEAL_TYPE_LABELS = { breakfast: 'Breakfast', lunch: 'Lunch', dinner: 'Dinner', snack: 'Snack' }
const formatMealType = (type) => MEAL_TYPE_LABELS[type] || type

export default function MealSlotPicker({ 
  isOpen, 
  onClose, 
  slot, 
  onAssign,
  planId,
  planTitle = 'Meal Plan',
  clientName = 'Client',
  chefDishes = [] // All chef dishes for compose mode
}) {
  // Notification context for global job tracking
  let notifications = null
  try {
    notifications = useSousChefNotifications()
  } catch (e) {
    // Context not available
  }
  
  const [tab, setTab] = useState('meals')
  const [composedMeals, setComposedMeals] = useState([])
  const [singleItems, setSingleItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [generating, setGenerating] = useState(false)
  const [aiSuggestion, setAiSuggestion] = useState(null)
  
  // Compose mode state
  const [composeSelectedDishes, setComposeSelectedDishes] = useState([])
  const [composeName, setComposeName] = useState('')
  const [composeDescription, setComposeDescription] = useState('')
  const [availableDishes, setAvailableDishes] = useState([])
  
  const [customForm, setCustomForm] = useState({
    name: '',
    description: '',
    servings: 1
  })

  // Load data on open
  useEffect(() => {
    if (isOpen && slot) {
      loadMeals()
      loadAvailableDishes()
      setAiSuggestion(null)
      setCustomForm({ name: '', description: '', servings: 1 })
      setComposeSelectedDishes([])
      setComposeName('')
      setComposeDescription('')
    }
  }, [isOpen, slot])

  const loadMeals = async () => {
    setLoading(true)
    try {
      // Load composed meals (multi-dish) and single items in parallel
      const [composedRes, singleRes] = await Promise.all([
        getChefComposedMeals({ 
          meal_type: slot?.mealType,
          search: search || undefined 
        }),
        getChefDishes({ 
          meal_type: slot?.mealType,
          search: search || undefined,
          include_dishes: true
        })
      ])
      
      setComposedMeals(composedRes?.dishes?.filter(m => m.is_composed) || [])
      setSingleItems(singleRes?.dishes?.filter(m => !m.is_composed) || [])
    } catch (err) {
      console.error('Failed to load meals:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadAvailableDishes = async () => {
    try {
      // Get all meals (which represent dishes in the kitchen)
      const data = await getChefDishes({ limit: 100, include_dishes: true })
      setAvailableDishes(data?.dishes || [])
    } catch (err) {
      console.error('Failed to load available dishes:', err)
    }
  }

  // Debounced search
  useEffect(() => {
    if (!isOpen || tab === 'compose') return
    const timer = setTimeout(() => {
      loadMeals()
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  const handleSelectMeal = (meal) => {
    onAssign({
      meal_id: meal.id,
      custom_name: '',
      custom_description: '',
      servings: customForm.servings || 1,
      is_composed: meal.is_composed,
      dishes: meal.dishes // Pass dish info for display
    })
  }

  const [aiError, setAiError] = useState(null)
  const [aiStatus, setAiStatus] = useState('')
  
  const handleGenerateAI = async () => {
    if (!planId || !slot) return
    
    setGenerating(true)
    setAiSuggestion(null)
    setAiError(null)
    setAiStatus('Starting generation...')
    
    const dayName = new Date(slot.date).toLocaleDateString('en-US', { weekday: 'long' })
    
    try {
      // Start async generation
      const startData = await startMealGeneration(planId, {
        mode: 'single_slot',
        day: dayName,
        meal_type: slot.mealType
      })
      
      if (!startData?.job_id) {
        throw new Error('Failed to start generation')
      }
      
      // Use global tracking so generation continues even if modal closes
      if (notifications?.trackJob) {
        notifications.trackJob({
          jobId: startData.job_id,
          planId,
          planTitle,
          clientName,
          mode: 'single_slot',
          slot: { day: dayName, meal_type: slot.mealType },
          onComplete: (result) => {
            // If this picker is still open, update local state
            if (result?.suggestions?.length > 0) {
              setAiSuggestion(result.suggestions[0])
              setGenerating(false)
              setAiStatus('')
            }
          }
        })
        
        setAiStatus('Generating... Sous Chef will notify you when ready!')
      } else {
        // Fallback without global tracking
        setAiError('Background tracking not available')
        setGenerating(false)
      }
    } catch (err) {
      console.error('AI generation failed:', err)
      setAiError(err.message || 'Generation failed. Please try again.')
      setGenerating(false)
      setAiStatus('')
    }
  }

  const handleAcceptAI = () => {
    if (!aiSuggestion) return
    onAssign({
      meal_id: null,
      custom_name: aiSuggestion.name,
      custom_description: aiSuggestion.description,
      servings: customForm.servings || 1
    })
  }

  // Compose mode handlers
  const handleToggleDish = (dish) => {
    setComposeSelectedDishes(prev => {
      const exists = prev.find(d => d.id === dish.id)
      if (exists) {
        return prev.filter(d => d.id !== dish.id)
      }
      return [...prev, dish]
    })
  }

  const handleComposeSubmit = (e) => {
    e.preventDefault()
    if (composeSelectedDishes.length === 0) return
    
    // Create a composed meal on-the-fly
    const composedName = composeName.trim() || composeSelectedDishes.map(d => d.name).join(' + ')
    
    onAssign({
      meal_id: null,
      custom_name: composedName,
      custom_description: composeDescription || composeSelectedDishes.map(d => d.name).join(', '),
      servings: customForm.servings || 1,
      composed_dishes: composeSelectedDishes.map(d => ({
        id: d.id,
        name: d.name
      }))
    })
  }

  const handleCustomSubmit = (e) => {
    e.preventDefault()
    if (!customForm.name.trim()) return
    
    onAssign({
      meal_id: null,
      custom_name: customForm.name,
      custom_description: customForm.description,
      servings: customForm.servings || 1
    })
  }

  if (!isOpen || !slot) return null

  const dayName = new Date(slot.date).toLocaleDateString('en-US', { weekday: 'long' })
  const dateDisplay = new Date(slot.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

  return (
    <>
      <div className="msp-backdrop" onClick={onClose} />
      <div className="msp-modal">
        <header className="msp-header">
          <div>
            <h3>Add Meal</h3>
            <span className="msp-slot-info">{dayName} {dateDisplay} • {formatMealType(slot.mealType)}</span>
          </div>
          <button className="msp-close" onClick={onClose}>×</button>
        </header>

        {/* Tabs */}
        <div className="msp-tabs">
          <button 
            className={`msp-tab ${tab === 'meals' ? 'active' : ''}`}
            onClick={() => setTab('meals')}
          >
            My Meals
          </button>
          <button 
            className={`msp-tab ${tab === 'compose' ? 'active' : ''}`}
            onClick={() => setTab('compose')}
          >
            Compose
          </button>
          <button 
            className={`msp-tab ${tab === 'ai' ? 'active' : ''}`}
            onClick={() => setTab('ai')}
          >
            AI
          </button>
          <button 
            className={`msp-tab ${tab === 'custom' ? 'active' : ''}`}
            onClick={() => setTab('custom')}
          >
            Quick Add
          </button>
        </div>

        {/* Content */}
        <div className="msp-content">
          {tab === 'meals' && (
            <div className="msp-meals">
              <div className="msp-search">
                <input 
                  type="text"
                  placeholder="Search your meals..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
              
              {loading ? (
                <div className="msp-loading">Loading meals...</div>
              ) : (composedMeals.length === 0 && singleItems.length === 0) ? (
                <div className="msp-empty">
                  <p>No meals found{search ? ' matching your search' : ''}.</p>
                  <p className="msp-hint">Create meals in Kitchen, or use Compose/AI tabs.</p>
                </div>
              ) : (
                <div className="msp-meals-sections">
                  {/* Composed Meals Section */}
                  {composedMeals.length > 0 && (
                    <div className="msp-section">
                      <h4 className="msp-section-title">
                        🍽️ Composed Meals
                        <span className="msp-section-badge">{composedMeals.length}</span>
                      </h4>
                      <div className="msp-dishes-list">
                        {composedMeals.map(meal => (
                          <button 
                            key={meal.id}
                            className="msp-dish-card msp-composed"
                            onClick={() => handleSelectMeal(meal)}
                          >
                            <div className="msp-dish-info">
                              <span className="msp-dish-name">{meal.name}</span>
                              {meal.dishes?.length > 0 && (
                                <span className="msp-dish-components">
                                  {meal.dishes.map(d => d.name).join(' • ')}
                                </span>
                              )}
                              {meal.description && (
                                <span className="msp-dish-desc">{meal.description}</span>
                              )}
                            </div>
                            <div className="msp-dish-meta">
                              <span className="msp-dish-count">{meal.dish_count} dishes</span>
                              <span className="msp-dish-arrow">→</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Single Items Section */}
                  {singleItems.length > 0 && (
                    <div className="msp-section">
                      <h4 className="msp-section-title">
                        🥘 Single Items
                        <span className="msp-section-badge">{singleItems.length}</span>
                      </h4>
                      <div className="msp-dishes-list">
                        {singleItems.map(item => (
                          <button 
                            key={item.id}
                            className="msp-dish-card"
                            onClick={() => handleSelectMeal(item)}
                          >
                            <div className="msp-dish-info">
                              <span className="msp-dish-name">{item.name}</span>
                              {item.description && (
                                <span className="msp-dish-desc">{item.description}</span>
                              )}
                              {item.dietary_preferences?.length > 0 && (
                                <div className="msp-dish-tags">
                                  {item.dietary_preferences.slice(0, 3).map((tag, i) => (
                                    <span key={i} className="msp-tag">{tag}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                            <span className="msp-dish-arrow">→</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === 'compose' && (
            <div className="msp-compose">
              <p className="msp-compose-hint">
                Build a meal by selecting multiple dishes from your menu.
              </p>
              
              {/* Selected dishes */}
              {composeSelectedDishes.length > 0 && (
                <div className="msp-compose-selected">
                  <label>Selected dishes ({composeSelectedDishes.length}):</label>
                  <div className="msp-compose-chips">
                    {composeSelectedDishes.map(dish => (
                      <span key={dish.id} className="msp-compose-chip">
                        {dish.name}
                        <button onClick={() => handleToggleDish(dish)}>×</button>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Available dishes to add */}
              <div className="msp-compose-available">
                <label>Add dishes to meal:</label>
                <div className="msp-compose-grid">
                  {availableDishes.map(dish => {
                    const isSelected = composeSelectedDishes.some(d => d.id === dish.id)
                    return (
                      <button
                        key={dish.id}
                        className={`msp-compose-option ${isSelected ? 'selected' : ''}`}
                        onClick={() => handleToggleDish(dish)}
                      >
                        <span className="msp-compose-check">{isSelected ? '✓' : '+'}</span>
                        <span>{dish.name}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Meal name (optional) */}
              {composeSelectedDishes.length >= 2 && (
                <form onSubmit={handleComposeSubmit} className="msp-compose-form">
                  <div className="msp-form-row">
                    <label>Meal Name (optional)</label>
                    <input 
                      type="text"
                      placeholder={composeSelectedDishes.map(d => d.name).join(' + ')}
                      value={composeName}
                      onChange={e => setComposeName(e.target.value)}
                    />
                  </div>
                  <button 
                    type="submit" 
                    className="msp-btn msp-btn-primary msp-btn-full"
                  >
                    Add to Plan
                  </button>
                </form>
              )}

              {composeSelectedDishes.length === 1 && (
                <div className="msp-compose-hint-more">
                  Select at least one more dish to compose a meal.
                </div>
              )}
            </div>
          )}

          {tab === 'ai' && (
            <div className="msp-ai">
              {aiError && (
                <div className="msp-ai-error">
                  ⚠️ {aiError}
                </div>
              )}
              {!aiSuggestion ? (
                <div className="msp-ai-prompt">
                  <div className="msp-ai-icon">✨</div>
                  <p>Generate an AI meal suggestion tailored to this family's dietary needs.</p>
                  {aiStatus && (
                    <div className="msp-ai-status">
                      {aiStatus}
                    </div>
                  )}
                  <button 
                    className="msp-btn msp-btn-ai"
                    onClick={handleGenerateAI}
                    disabled={generating}
                  >
                    {generating ? '🔄 Generating...' : 'Generate Suggestion'}
                  </button>
                  {generating && (
                    <p className="msp-ai-hint">
                      You can close this and Sous Chef will notify you when done!
                    </p>
                  )}
                </div>
              ) : (
                <div className="msp-ai-result">
                  <div className="msp-suggestion-card">
                    <h4>{aiSuggestion.name}</h4>
                    <p className="msp-suggestion-desc">{aiSuggestion.description}</p>
                    {aiSuggestion.dietary_tags?.length > 0 && (
                      <div className="msp-dish-tags">
                        {aiSuggestion.dietary_tags.map((tag, i) => (
                          <span key={i} className="msp-tag">{tag}</span>
                        ))}
                      </div>
                    )}
                    {aiSuggestion.household_notes && (
                      <p className="msp-household-note">💡 {aiSuggestion.household_notes}</p>
                    )}
                  </div>
                  <div className="msp-ai-actions">
                    <button 
                      className="msp-btn msp-btn-primary"
                      onClick={handleAcceptAI}
                    >
                      Use This Meal
                    </button>
                    <button 
                      className="msp-btn msp-btn-outline"
                      onClick={handleGenerateAI}
                      disabled={generating}
                    >
                      {generating ? 'Generating...' : 'Try Another'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'custom' && (
            <div className="msp-custom">
              <form onSubmit={handleCustomSubmit}>
                <div className="msp-form-row">
                  <label>Meal Name *</label>
                  <input 
                    type="text"
                    placeholder="e.g., Grilled Salmon with Vegetables"
                    value={customForm.name}
                    onChange={e => setCustomForm(f => ({ ...f, name: e.target.value }))}
                    required
                  />
                </div>
                <div className="msp-form-row">
                  <label>Description</label>
                  <textarea 
                    rows={3}
                    placeholder="Brief description..."
                    value={customForm.description}
                    onChange={e => setCustomForm(f => ({ ...f, description: e.target.value }))}
                  />
                </div>
                <div className="msp-form-row">
                  <label>Servings</label>
                  <input 
                    type="number"
                    min={1}
                    value={customForm.servings}
                    onChange={e => setCustomForm(f => ({ ...f, servings: parseInt(e.target.value) || 1 }))}
                  />
                </div>
                <button 
                  type="submit" 
                  className="msp-btn msp-btn-primary msp-btn-full"
                  disabled={!customForm.name.trim()}
                >
                  Add to Plan
                </button>
              </form>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .msp-backdrop {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          z-index: 2000;
        }

        .msp-modal {
          position: fixed;
          z-index: 2001;
          background: var(--surface, #fff);
          display: flex;
          flex-direction: column;
          animation: mspSlideUp 0.2s ease;
          box-shadow: 0 18px 48px rgba(0,0,0,0.28);
        }

        /* Mobile: Bottom sheet */
        @media (max-width: 639px) {
          .msp-modal {
            bottom: 0;
            left: 0;
            right: 0;
            max-height: 85vh;
            border-radius: 16px 16px 0 0;
          }
        }

        /* Tablet+: Centered modal */
        @media (min-width: 640px) {
          .msp-modal {
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            max-width: 480px;
            max-height: 80vh;
            border-radius: 16px;
            animation: mspFadeIn 0.2s ease;
          }
        }

        @keyframes mspSlideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }

        @keyframes mspFadeIn {
          from { opacity: 0; transform: translate(-50%, -48%); }
          to { opacity: 1; transform: translate(-50%, -50%); }
        }

        .msp-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid var(--border, #e5e7eb);
        }

        .msp-header h3 {
          margin: 0;
          font-size: 1.1rem;
        }

        .msp-slot-info {
          font-size: 0.85rem;
          color: var(--muted, #666);
        }

        .msp-close {
          background: none;
          border: none;
          font-size: 1.75rem;
          line-height: 1;
          cursor: pointer;
          color: var(--muted, #666);
          padding: 0;
        }

        .msp-tabs {
          display: flex;
          border-bottom: 1px solid var(--border, #e5e7eb);
        }

        .msp-tab {
          flex: 1;
          padding: 0.75rem 0.5rem;
          background: none;
          border: none;
          border-bottom: 2px solid transparent;
          font-size: 0.8rem;
          font-weight: 500;
          color: var(--muted, #666);
          cursor: pointer;
          white-space: nowrap;
        }

        @media (min-width: 400px) {
          .msp-tab {
            font-size: 0.9rem;
            padding: 0.75rem;
          }
        }

        .msp-tab.active {
          color: var(--primary, #5cb85c);
          border-bottom-color: var(--primary, #5cb85c);
        }

        .msp-content {
          flex: 1;
          overflow-y: auto;
          padding: 1rem;
        }

        /* Meals Tab */
        .msp-search input {
          width: 100%;
          padding: 0.65rem 0.85rem;
          border: 1px solid var(--border, #ddd);
          border-radius: 8px;
          background: var(--surface, #fff);
          color: var(--text, #333);
          font-size: 0.9rem;
          margin-bottom: 0.75rem;
          caret-color: var(--primary, #5cb85c);
          transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
        }

        .msp-search input::placeholder {
          color: var(--muted, #666);
        }

        .msp-search input:focus {
          outline: none;
          border-color: color-mix(in oklab, var(--primary, #5cb85c) 55%, var(--border, #ddd));
          box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.16);
          background: var(--surface, #fff);
        }

        .msp-loading,
        .msp-empty {
          text-align: center;
          padding: 2rem 1rem;
          color: var(--muted, #666);
        }

        .msp-hint {
          font-size: 0.85rem;
          opacity: 0.8;
        }

        .msp-meals-sections {
          display: flex;
          flex-direction: column;
          gap: 1.25rem;
        }

        .msp-section {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .msp-section-title {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.9rem;
          font-weight: 600;
          margin: 0;
          color: var(--text, #333);
        }

        .msp-section-badge {
          background: var(--surface-2, #f3f4f6);
          color: var(--muted, #666);
          font-size: 0.75rem;
          font-weight: 500;
          padding: 0.1rem 0.5rem;
          border-radius: 99px;
        }

        .msp-dishes-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .msp-dish-card {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          padding: 0.85rem;
          background: var(--surface, #fff);
          border: 1px solid var(--border, #e5e7eb);
          border-radius: 10px;
          cursor: pointer;
          text-align: left;
          transition: all 0.15s;
        }

        .msp-dish-card:hover {
          border-color: var(--primary, #5cb85c);
          background: var(--surface-2, #f9fafb);
        }

        .msp-dish-card.msp-composed {
          border-left: 3px solid var(--primary, #5cb85c);
        }

        .msp-dish-components {
          font-size: 0.8rem;
          color: var(--primary-700, #4a9d4a);
          font-weight: 500;
        }

        .msp-dish-meta {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .msp-dish-count {
          font-size: 0.75rem;
          color: var(--muted, #888);
          background: var(--surface-2, #f3f4f6);
          padding: 0.2rem 0.5rem;
          border-radius: 4px;
        }

        .msp-dish-info {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
          flex: 1;
          min-width: 0;
        }

        .msp-dish-name {
          font-weight: 500;
          color: var(--text, #333);
        }

        .msp-dish-desc {
          font-size: 0.8rem;
          color: var(--muted, #666);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .msp-dish-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 0.25rem;
          margin-top: 0.25rem;
        }

        .msp-tag {
          font-size: 0.7rem;
          padding: 0.15rem 0.4rem;
          background: var(--surface-2, #f3f4f6);
          border-radius: 4px;
          color: var(--muted, #666);
        }

        .msp-dish-arrow {
          font-size: 1.25rem;
          color: var(--muted, #ccc);
          margin-left: 0.5rem;
        }

        /* AI Tab */
        .msp-ai-error {
          background: color-mix(in oklab, var(--surface, #fff) 90%, #dc2626 10%);
          border: 1px solid color-mix(in oklab, var(--border, #e5e7eb) 50%, #dc2626 50%);
          color: color-mix(in oklab, #dc2626 75%, var(--text, #333) 25%);
          padding: 0.75rem 1rem;
          border-radius: 8px;
          margin-bottom: 1rem;
          font-size: 0.9rem;
        }

        .msp-ai-prompt {
          text-align: center;
          padding: 2rem 1rem;
        }

        .msp-ai-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }

        .msp-ai-prompt p {
          color: var(--muted, #666);
          margin-bottom: 1.5rem;
        }

        .msp-ai-status {
          font-size: 0.9rem;
          color: var(--primary, #5cb85c);
          margin-bottom: 1rem;
          padding: 0.5rem 1rem;
          background: rgba(92, 184, 92, 0.1);
          border-radius: 8px;
        }

        .msp-ai-hint {
          font-size: 0.85rem;
          color: var(--muted, #888);
          margin-top: 0.75rem;
          font-style: italic;
        }

        .msp-ai-result {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .msp-suggestion-card {
          padding: 1rem;
          background: var(--surface-2, #f9fafb);
          border-radius: 10px;
        }

        .msp-suggestion-card h4 {
          margin: 0 0 0.5rem 0;
          font-size: 1.05rem;
        }

        .msp-suggestion-desc {
          font-size: 0.9rem;
          color: var(--muted, #666);
          margin: 0 0 0.5rem 0;
        }

        .msp-household-note {
          font-size: 0.85rem;
          color: var(--muted, #666);
          font-style: italic;
          margin: 0.5rem 0 0 0;
        }

        .msp-ai-actions {
          display: flex;
          gap: 0.5rem;
        }

        .msp-ai-actions .msp-btn {
          flex: 1;
        }

        /* Compose Tab */
        .msp-compose {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          background: var(--surface, #fff);
          border-radius: 12px;
          padding: 0.5rem;
        }

        .msp-compose-hint {
          text-align: center;
          color: var(--muted, #666);
          font-size: 0.9rem;
          margin: 0;
        }

        .msp-compose-selected {
          background: var(--primary-50, #f0fdf4);
          border: 1px solid var(--primary-200, #bbf7d0);
          border-radius: 10px;
          padding: 0.75rem;
        }

        .msp-compose-selected label {
          display: block;
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--primary-700, #4a9d4a);
          margin-bottom: 0.5rem;
        }

        .msp-compose-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .msp-compose-chip {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          background: var(--surface, #fff);
          border: 1px solid var(--primary, #5cb85c);
          color: var(--primary-700, #4a9d4a);
          padding: 0.3rem 0.6rem;
          border-radius: 99px;
          font-size: 0.8rem;
          font-weight: 500;
        }

        .msp-compose-chip button {
          background: none;
          border: none;
          color: var(--primary-700, #4a9d4a);
          cursor: pointer;
          padding: 0;
          font-size: 1rem;
          line-height: 1;
        }

        .msp-compose-available {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .msp-compose-available label {
          font-size: 0.85rem;
          font-weight: 500;
          color: var(--muted, #666);
        }

        .msp-compose-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
          gap: 0.5rem;
          max-height: 200px;
          overflow-y: auto;
          padding: 0.35rem;
        }

        .msp-compose-option {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.5rem 0.65rem;
          border: 1px solid color-mix(in oklab, var(--border, #e5e7eb) 70%, var(--primary, #5cb85c) 30%);
          border-radius: 8px;
          background: var(--surface-2, #f3f4f6);
          color: var(--text, #333);
          cursor: pointer;
          font-size: 0.85rem;
          text-align: left;
          transition: all 0.15s;
          box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        }

        .msp-compose-option:hover {
          border-color: var(--primary, #5cb85c);
          background: color-mix(in oklab, var(--surface-2, #f3f4f6) 70%, var(--primary, #5cb85c) 30%);
        }

        .msp-compose-option.selected {
          background: color-mix(in oklab, var(--primary, #5cb85c) 22%, var(--surface, #fff));
          border-color: var(--primary, #5cb85c);
          color: var(--text, #1a1f1a);
          box-shadow: 0 0 0 1px color-mix(in oklab, var(--primary, #5cb85c) 60%, transparent);
        }

        .msp-compose-check {
          font-size: 0.9rem;
          width: 1.1rem;
          text-align: center;
        }

        .msp-compose-form {
          margin-top: 0.5rem;
          padding-top: 1rem;
          border-top: 1px solid var(--border, #e5e7eb);
        }

        .msp-compose-hint-more {
          text-align: center;
          color: var(--muted, #999);
          font-size: 0.85rem;
          padding: 1rem;
        }

        /* Custom Tab */
        .msp-form-row {
          margin-bottom: 1rem;
        }

        .msp-form-row label {
          display: block;
          font-size: 0.85rem;
          font-weight: 500;
          margin-bottom: 0.35rem;
          color: var(--muted, #666);
        }

        .msp-form-row input,
        .msp-form-row textarea {
          width: 100%;
          padding: 0.65rem 0.85rem;
          border: 1px solid var(--border, #ddd);
          border-radius: 8px;
          font-size: 0.9rem;
          background: var(--surface, #fff);
          color: var(--text, #333);
          transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
        }

        .msp-form-row input::placeholder,
        .msp-form-row textarea::placeholder {
          color: var(--muted, #666);
        }

        .msp-form-row input:focus,
        .msp-form-row textarea:focus {
          outline: none;
          border-color: color-mix(in oklab, var(--primary, #5cb85c) 55%, var(--border, #ddd));
          box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.16);
          background: var(--surface, #fff);
        }

        /* Buttons */
        .msp-btn {
          padding: 0.7rem 1.25rem;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 500;
          cursor: pointer;
          border: 1px solid transparent;
          transition: all 0.15s;
        }

        .msp-btn-full {
          width: 100%;
        }

        .msp-btn-primary {
          background: var(--primary, #5cb85c);
          color: white;
        }

        .msp-btn-primary:hover {
          background: var(--primary-700, #4a9d4a);
        }

        .msp-btn-outline {
          background: transparent;
          border-color: var(--border, #ddd);
          color: var(--text, #333);
        }

        .msp-btn-ai {
          background: linear-gradient(135deg, var(--primary, #5cb85c), var(--primary-700, #4a9d4a));
          color: white;
        }

        .msp-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </>
  )
}
