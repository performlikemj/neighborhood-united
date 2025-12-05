import React, { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../api'
import { COUNTRIES } from '../utils/geo.js'
import { 
  SAMPLE_MEALS, 
  filterMealsForUser, 
  generateWeeklyPlan,
  DAYS_OF_WEEK,
  MEAL_TYPES 
} from '../data/sampleMeals.js'

// Reuse options from Profile
const FALLBACK_DIETS = ['Everything','Vegetarian','Vegan','Halal','Kosher','Gluten-Free','Pescatarian','Keto','Paleo','Low-Calorie','Low-Sodium','High-Protein','Dairy-Free','Nut-Free']
const FALLBACK_ALLERGENS = ['Peanuts','Tree nuts','Milk','Egg','Wheat','Soy','Fish','Shellfish','Sesame','Mustard','Celery','Lupin','Sulfites','Molluscs','Corn','Gluten','Kiwi','Pine Nuts','Sunflower Seeds']

// Reduced to 3 steps - Preview is now combined with Preferences
const STEPS = [
  { id: 'welcome', title: 'Welcome', icon: '👋' },
  { id: 'preferences', title: 'Preferences', icon: '🥗' },
  { id: 'waitlist', title: 'Stay Updated', icon: '🔔' }
]

function notify(text, tone = 'info') {
  try {
    window.dispatchEvent(new CustomEvent('global-toast', { detail: { text, tone } }))
  } catch {}
}

export default function GetReady() {
  const { user, refreshUser, hasChefAccess, checkChefAvailability } = useAuth()
  const navigate = useNavigate()
  
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [editingLocation, setEditingLocation] = useState(false) // Bypass auto-advance when user explicitly wants to edit
  
  // Location form
  const [location, setLocation] = useState({
    postal_code: '',
    country: ''
  })
  
  // Preferences form
  const [preferences, setPreferences] = useState({
    dietary_preferences: [],
    allergies: [],
    custom_allergies: '',
    household_size: 1
  })
  
  // Waitlist
  const [waitlistStatus, setWaitlistStatus] = useState(null)
  const [joiningWaitlist, setJoiningWaitlist] = useState(false)
  
  // Chef found celebration state
  const [chefFound, setChefFound] = useState(false)

  // Client-side meal plan generation - updates instantly as preferences change
  const { liveMealPlan, matchCount, totalMeals } = useMemo(() => {
    // Combine standard allergies with custom ones
    const customAllergiesArray = preferences.custom_allergies
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
    
    const allAllergies = [...preferences.allergies, ...customAllergiesArray]
    
    const filteredMeals = filterMealsForUser(
      SAMPLE_MEALS, 
      preferences.dietary_preferences, 
      allAllergies
    )
    
    return {
      liveMealPlan: generateWeeklyPlan(filteredMeals, preferences.household_size),
      matchCount: filteredMeals.length,
      totalMeals: SAMPLE_MEALS.length
    }
  }, [preferences.dietary_preferences, preferences.allergies, preferences.custom_allergies, preferences.household_size])
  
  // Show reassurance message when few matches
  const showLimitedMatchesMessage = matchCount < 15

  // Auto-advance step based on user's existing data
  // Skip if user explicitly clicked "Update Location" (editingLocation flag)
  useEffect(() => {
    if (!user || editingLocation) return
    
    // Check if user already has location saved
    const hasLocation = Boolean(
      (user?.address?.postalcode || user?.address?.input_postalcode || user?.postal_code) &&
      user?.address?.country
    )
    
    // If they have location saved, skip to step 1 (preferences)
    if (hasLocation && step === 0) {
      setStep(1)
    }
  }, [user, step, editingLocation])

  // Organize meals by day for display
  const mealsByDay = useMemo(() => {
    return liveMealPlan.meals.reduce((acc, meal) => {
      const day = meal.day
      if (!acc[day]) acc[day] = {}
      acc[day][meal.meal_type] = meal
      return acc
    }, {})
  }, [liveMealPlan.meals])

  // Initialize from user data
  useEffect(() => {
    if (user) {
      // Set location from user's address
      const postal = user?.address?.postalcode || user?.address?.input_postalcode || user?.postal_code || ''
      const country = user?.address?.country || ''
      setLocation({
        postal_code: postal,
        country: typeof country === 'string' ? country : (country?.code || '')
      })
      
      // Set preferences from user data
      const dietPrefs = user?.dietary_preferences || []
      const allergies = user?.allergies || []
      const customAllergies = Array.isArray(user?.custom_allergies) ? user.custom_allergies.join(', ') : ''
      const householdSize = user?.household_member_count || 1
      
      setPreferences({
        dietary_preferences: Array.isArray(dietPrefs) ? dietPrefs : [],
        allergies: Array.isArray(allergies) ? allergies.filter(a => a && a !== 'None') : [],
        custom_allergies: customAllergies,
        household_size: Math.max(1, householdSize)
      })
    }
  }, [user])

  // Check if user already has chef access (redirect them)
  useEffect(() => {
    if (hasChefAccess === true && !user?.is_chef) {
      // User has chef access, redirect to appropriate page
      navigate('/orders', { replace: true })
    }
  }, [hasChefAccess, user?.is_chef, navigate])

  // Load waitlist status
  useEffect(() => {
    if (user && location.postal_code) {
      api.get('/chefs/api/area-waitlist/status/')
        .then(res => setWaitlistStatus(res?.data || null))
        .catch(() => {})
    }
  }, [user, location.postal_code])

  const saveLocation = async () => {
    if (!location.postal_code || !location.country) {
      notify('Please enter both postal code and country', 'error')
      return false
    }
    
    setLoading(true)
    try {
      await api.post('/auth/api/update_profile/', {
        address: {
          input_postalcode: location.postal_code,
          postalcode: location.postal_code,
          country: location.country
        }
      })
      await refreshUser()
      // Re-check chef availability
      const hasAccess = await checkChefAvailability(true)
      if (hasAccess) {
        // Show celebration screen instead of immediately redirecting
        setChefFound(true)
        return false // Don't proceed to next step - show celebration instead
      }
      return true
    } catch (e) {
      const msg = e?.response?.data?.error || 'Failed to save location'
      notify(msg, 'error')
      return false
    } finally {
      setLoading(false)
    }
  }

  const savePreferences = async () => {
    setLoading(true)
    try {
      const customAllergiesArray = preferences.custom_allergies
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
      
      await api.post('/auth/api/update_profile/', {
        dietary_preferences: preferences.dietary_preferences,
        allergies: preferences.allergies,
        custom_allergies: customAllergiesArray,
        household_member_count: preferences.household_size
      })
      await refreshUser()
      return true
    } catch (e) {
      notify('Failed to save preferences', 'error')
      return false
    } finally {
      setLoading(false)
    }
  }

  const joinWaitlist = async () => {
    setJoiningWaitlist(true)
    try {
      const res = await api.post('/chefs/api/area-waitlist/join/')
      if (res?.data?.success) {
        setWaitlistStatus(res.data)
        notify("You're on the waitlist! We'll notify you when a chef is available.", 'success')
      }
    } catch (e) {
      const msg = e?.response?.data?.error || 'Failed to join waitlist'
      notify(msg, 'error')
    } finally {
      setJoiningWaitlist(false)
    }
  }

  const leaveWaitlist = async () => {
    setJoiningWaitlist(true)
    try {
      const res = await api.delete('/chefs/api/area-waitlist/leave/')
      if (res?.data?.removed) {
        setWaitlistStatus({ ...waitlistStatus, on_waitlist: false, position: null })
        notify("You've been removed from the waitlist.", 'info')
      }
    } catch (e) {
      const msg = e?.response?.data?.error || 'Failed to leave waitlist'
      notify(msg, 'error')
    } finally {
      setJoiningWaitlist(false)
    }
  }

  const handleNext = async () => {
    let canProceed = true
    
    if (step === 0) {
      canProceed = await saveLocation()
      if (canProceed) {
        setEditingLocation(false) // Clear flag after saving location
      }
    } else if (step === 1) {
      canProceed = await savePreferences()
    }
    
    if (canProceed && step < STEPS.length - 1) {
      setStep(step + 1)
    }
  }

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1)
    }
  }

  const toggleDiet = (diet) => {
    setPreferences(prev => {
      const current = new Set(prev.dietary_preferences)
      if (current.has(diet)) {
        current.delete(diet)
      } else {
        current.add(diet)
      }
      return { ...prev, dietary_preferences: Array.from(current) }
    })
  }

  const toggleAllergy = (allergy) => {
    setPreferences(prev => {
      const current = new Set(prev.allergies)
      if (current.has(allergy)) {
        current.delete(allergy)
      } else {
        current.add(allergy)
      }
      return { ...prev, allergies: Array.from(current) }
    })
  }

  return (
    <div className="page-get-ready">
      {/* Progress Steps */}
      <div className="get-ready-progress">
        {STEPS.map((s, idx) => (
          <div
            key={s.id}
            className={`progress-step ${idx === step ? 'active' : ''} ${idx < step ? 'completed' : ''}`}
          >
            <div className="step-icon">{idx < step ? '✓' : s.icon}</div>
            <div className="step-title">{s.title}</div>
          </div>
        ))}
      </div>

      <div className="get-ready-content">
        {/* Chef Found Celebration - shown when chef is available in user's area */}
        {chefFound && (
          <div className="get-ready-step step-chef-found">
            <div className="chef-found-celebration">
              <div className="celebration-icon">🎉</div>
              <h1>Great News!</h1>
              <p className="celebration-subtitle">
                Chefs are already serving your area in <strong>{location.postal_code}</strong>!
              </p>
              <p className="celebration-message">
                You can start browsing available chefs right away, or take a moment to 
                set up your dietary preferences so they know exactly what you like.
              </p>
              
              <div className="celebration-actions">
                <Link to="/chefs" className="btn btn-primary btn-large">
                  Browse Available Chefs
                </Link>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => {
                    setChefFound(false)
                    setStep(1) // Go to preferences step
                  }}
                >
                  Set Up Preferences First
                </button>
              </div>
              
              <div className="celebration-note">
                <p className="muted">
                  Don't worry — your preferences can be updated anytime from your profile.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Step 0: Welcome */}
        {step === 0 && !chefFound && (
          <div className="get-ready-step step-welcome">
            <div className="step-header">
              <h1>Get Ready for Your Personal Chef</h1>
              <p className="subtitle">
                We're bringing talented chefs to your neighborhood. 
                Let's get you set up so you'll be first in line when they arrive.
              </p>
            </div>

            <div className="card welcome-card">
              <div className="welcome-icon">🍳</div>
              <h2>First, confirm your location</h2>
              <p className="muted">This helps us match you with chefs in your area.</p>
              
              <div className="form-group">
                <label className="label">Postal Code</label>
                <input
                  type="text"
                  className="input"
                  value={location.postal_code}
                  onChange={e => setLocation({ ...location, postal_code: e.target.value })}
                  placeholder="e.g., 90210"
                />
              </div>
              
              <div className="form-group">
                <label className="label">Country</label>
                <select
                  className="select"
                  value={location.country}
                  onChange={e => setLocation({ ...location, country: e.target.value })}
                >
                  <option value="">Select country</option>
                  {COUNTRIES.map(c => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Step 1: Preferences + Live Preview */}
        {step === 1 && !chefFound && (
          <div className="get-ready-step step-preferences-preview">
            <div className="step-header">
              <h1>Personalize Your Experience</h1>
              <p className="subtitle">
                Set your preferences and see your personalized meal plan update in real-time.
              </p>
            </div>

            <div className="preferences-preview-layout">
              {/* Left side: Preferences */}
              <div className="preferences-panel">
                <div className="card preferences-card">
                  <h3>Dietary Preferences</h3>
                  <p className="muted">Select all that apply</p>
                  <div className="chip-grid">
                    {FALLBACK_DIETS.map(diet => (
                      <button
                        key={diet}
                        type="button"
                        className={`chip ${preferences.dietary_preferences.includes(diet) ? 'selected' : ''}`}
                        onClick={() => toggleDiet(diet)}
                      >
                        {diet}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="card preferences-card">
                  <h3>Allergies</h3>
                  <p className="muted">Select any foods you're allergic to</p>
                  <div className="chip-grid">
                    {FALLBACK_ALLERGENS.map(allergy => (
                      <button
                        key={allergy}
                        type="button"
                        className={`chip chip-allergy ${preferences.allergies.includes(allergy) ? 'selected' : ''}`}
                        onClick={() => toggleAllergy(allergy)}
                      >
                        {allergy}
                      </button>
                    ))}
                  </div>
                  
                  <div className="form-group" style={{ marginTop: '1rem' }}>
                    <label className="label">Other allergies (comma-separated)</label>
                    <input
                      type="text"
                      className="input"
                      value={preferences.custom_allergies}
                      onChange={e => setPreferences({ ...preferences, custom_allergies: e.target.value })}
                      placeholder="e.g., Mango, Papaya"
                    />
                  </div>
                </div>

                <div className="card preferences-card">
                  <h3>Household Size</h3>
                  <p className="muted">How many people will you be cooking for?</p>
                  <div className="household-selector">
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() => setPreferences(p => ({ ...p, household_size: Math.max(1, p.household_size - 1) }))}
                      disabled={preferences.household_size <= 1}
                    >
                      −
                    </button>
                    <span className="household-count">{preferences.household_size}</span>
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() => setPreferences(p => ({ ...p, household_size: p.household_size + 1 }))}
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>

              {/* Right side: Live Preview */}
              <div className="preview-panel">
                <div className="preview-panel-header">
                  <h3>Your Personalized Week Preview</h3>
                  <div className="summary-badge">Updates Live</div>
                </div>
                
                <div className="preview-summary-inline">
                  <p>{liveMealPlan.week_summary}</p>
                </div>

                {showLimitedMatchesMessage && (
                  <div className="limited-matches-notice">
                    <p>
                      <strong>This is an interactive preview.</strong> Your preferences are unique, 
                      and that's great! Your personal chef will work directly with you to create 
                      custom meals that perfectly match your dietary needs and tastes.
                    </p>
                  </div>
                )}

                <div className="meal-preview-grid">
                  {DAYS_OF_WEEK.map(day => (
                    <div key={day} className="day-column">
                      <div className="day-header">{day}</div>
                      {MEAL_TYPES.map(mealType => {
                        const meal = mealsByDay[day]?.[mealType]
                        return (
                          <div key={mealType} className="meal-card">
                            <div className="meal-type">{mealType}</div>
                            {meal ? (
                              <>
                                <div className="meal-name">{meal.meal_name}</div>
                                <div className="meal-desc">{meal.meal_description}</div>
                                <div className="meal-servings">{meal.servings} serving{meal.servings > 1 ? 's' : ''}</div>
                              </>
                            ) : (
                              <div className="meal-empty">—</div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ))}
                </div>

                <div className="preview-cta-inline">
                  <p>This could be yours when a chef joins your area!</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Waitlist */}
        {step === 2 && !chefFound && (
          <div className="get-ready-step step-waitlist">
            <div className="step-header">
              <h1>You're All Set!</h1>
              <p className="subtitle">
                Join the waitlist to be first in line when a chef starts serving your area.
              </p>
            </div>

            <div className="card waitlist-card">
              {waitlistStatus?.on_waitlist ? (
                <>
                  <div className="waitlist-status">
                    <div className="status-icon">🔔</div>
                    <h2>You're on the list!</h2>
                    <p className="position">Position #{waitlistStatus.position} in {waitlistStatus.postal_code}</p>
                    <p className="muted">
                      {waitlistStatus.total_waiting} {waitlistStatus.total_waiting === 1 ? 'person' : 'people'} waiting in your area
                    </p>
                  </div>
                  <p className="waitlist-info">
                    We'll email you as soon as a chef starts serving your neighborhood.
                    In the meantime, your preferences are saved and ready to go!
                  </p>
                  <div className="waitlist-actions" style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-outline btn-small"
                      onClick={() => {
                        setEditingLocation(true)
                        setStep(0)
                      }}
                    >
                      Update Location
                    </button>
                    <button
                      className="btn btn-outline btn-small"
                      onClick={leaveWaitlist}
                      disabled={joiningWaitlist}
                      style={{ color: 'var(--danger, #dc3545)', borderColor: 'var(--danger, #dc3545)' }}
                    >
                      {joiningWaitlist ? 'Leaving...' : 'Leave Waitlist'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="waitlist-status">
                    <div className="status-icon">📬</div>
                    <h2>Get notified when chefs arrive</h2>
                    <p className="muted">
                      Be the first to know when a personal chef starts serving {location.postal_code}
                    </p>
                  </div>
                  <button
                    className="btn btn-primary btn-large"
                    onClick={joinWaitlist}
                    disabled={joiningWaitlist}
                  >
                    {joiningWaitlist ? 'Joining...' : 'Join the Waitlist'}
                  </button>
                </>
              )}
            </div>

            <div className="next-steps card">
              <h3>What's Next?</h3>
              <ul className="next-steps-list">
                <li>
                  <span className="step-num">1</span>
                  <span>Your preferences are saved and ready for when a chef joins</span>
                </li>
                <li>
                  <span className="step-num">2</span>
                  <span>We'll email you when a chef starts serving your area</span>
                </li>
                <li>
                  <span className="step-num">3</span>
                  <span>Connect with your chef and start enjoying personalized meals</span>
                </li>
              </ul>
            </div>

            <div className="engagement-links">
              <Link to="/profile" className="btn btn-outline">
                Update Your Profile
              </Link>
              <Link to="/chefs" className="btn btn-outline">
                Browse Chefs Directory
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      {/* Navigation - hidden during celebration */}
      {!chefFound && (
        <div className="get-ready-nav">
          {step > 0 && step < 2 && (
            <button className="btn btn-outline" onClick={handleBack} disabled={loading}>
              Back
            </button>
          )}
          {step < STEPS.length - 1 && (
            <button className="btn btn-primary" onClick={handleNext} disabled={loading}>
              {loading ? 'Please wait...' : 'Continue'}
            </button>
          )}
          {step === STEPS.length - 1 && (
            <Link to="/" className="btn btn-primary">
              Back to Home
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
