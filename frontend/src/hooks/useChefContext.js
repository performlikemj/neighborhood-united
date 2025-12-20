/**
 * useChefContext Hook
 * 
 * Tracks chef activity in the dashboard for contextual AI suggestions.
 * Monitors: current tab, open forms, recent actions, idle state, validation errors.
 */

import { useState, useCallback, useRef, useEffect } from 'react'

// Idle detection threshold (30 seconds - triggers proactive suggestions)
const IDLE_THRESHOLD_MS = 30 * 1000

// Debounce delay for context updates
const DEBOUNCE_DELAY_MS = 500

// Maximum recent actions to track
const MAX_RECENT_ACTIONS = 5

/**
 * Creates the initial context state
 */
function createInitialContext() {
  return {
    currentTab: 'dashboard',
    openForms: [],  // [{ type: 'dish', fields: {...}, completion: 0.5, openedAt: timestamp }]
    recentActions: [],  // ['created_ingredient', 'viewed_events', ...]
    timeOnScreen: 0,
    validationErrors: [],
    lastActivity: Date.now(),
    sessionStart: Date.now()
  }
}

/**
 * Calculate form completion percentage based on filled fields
 */
function calculateCompletion(fields, requiredFields = []) {
  if (!fields || typeof fields !== 'object') return 0
  
  const fieldEntries = Object.entries(fields)
  if (fieldEntries.length === 0) return 0
  
  // Count non-empty fields
  const filledCount = fieldEntries.filter(([key, value]) => {
    if (value === null || value === undefined || value === '') return false
    if (Array.isArray(value) && value.length === 0) return false
    return true
  }).length
  
  return Math.round((filledCount / fieldEntries.length) * 100) / 100
}

/**
 * useChefContext Hook
 * 
 * @returns {Object} context - Current chef context state
 * @returns {Function} setTab - Update current tab
 * @returns {Function} openForm - Register a form as open
 * @returns {Function} closeForm - Register a form as closed
 * @returns {Function} updateFormFields - Update form field values
 * @returns {Function} reportAction - Record a chef action
 * @returns {Function} reportError - Record a validation error
 * @returns {Function} clearErrors - Clear validation errors
 * @returns {boolean} isIdle - Whether chef has been idle for threshold duration
 */
export function useChefContext() {
  const [context, setContext] = useState(createInitialContext)
  const [isIdle, setIsIdle] = useState(false)
  
  // Refs for debouncing and timers
  const debounceTimer = useRef(null)
  const idleTimer = useRef(null)
  const tabStartTime = useRef(Date.now())
  const screenTimeInterval = useRef(null)
  
  /**
   * Reset idle timer on any activity
   */
  const resetIdleTimer = useCallback(() => {
    setIsIdle(false)
    
    if (idleTimer.current) {
      clearTimeout(idleTimer.current)
    }
    
    idleTimer.current = setTimeout(() => {
      setIsIdle(true)
    }, IDLE_THRESHOLD_MS)
    
    // Update last activity timestamp
    setContext(prev => ({
      ...prev,
      lastActivity: Date.now()
    }))
  }, [])
  
  /**
   * Debounced context update
   */
  const debouncedUpdate = useCallback((updater) => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current)
    }
    
    debounceTimer.current = setTimeout(() => {
      setContext(updater)
      resetIdleTimer()
    }, DEBOUNCE_DELAY_MS)
  }, [resetIdleTimer])
  
  /**
   * Set current tab and track time on screen
   */
  const setTab = useCallback((tab) => {
    const now = Date.now()
    tabStartTime.current = now
    
    setContext(prev => ({
      ...prev,
      currentTab: tab,
      timeOnScreen: 0,
      lastActivity: now
    }))
    
    resetIdleTimer()
  }, [resetIdleTimer])
  
  /**
   * Open a form (register it as active)
   */
  const openForm = useCallback((formType, initialFields = {}) => {
    const now = Date.now()
    
    setContext(prev => {
      // Check if form already open
      const existingIndex = prev.openForms.findIndex(f => f.type === formType)
      
      const newForm = {
        type: formType,
        fields: initialFields,
        completion: calculateCompletion(initialFields),
        openedAt: now
      }
      
      let newOpenForms
      if (existingIndex >= 0) {
        // Update existing
        newOpenForms = [...prev.openForms]
        newOpenForms[existingIndex] = newForm
      } else {
        // Add new
        newOpenForms = [...prev.openForms, newForm]
      }
      
      return {
        ...prev,
        openForms: newOpenForms,
        lastActivity: now
      }
    })
    
    resetIdleTimer()
  }, [resetIdleTimer])
  
  /**
   * Close a form (remove from active)
   */
  const closeForm = useCallback((formType) => {
    setContext(prev => ({
      ...prev,
      openForms: prev.openForms.filter(f => f.type !== formType),
      lastActivity: Date.now()
    }))
    
    resetIdleTimer()
  }, [resetIdleTimer])
  
  /**
   * Update form field values (debounced)
   */
  const updateFormFields = useCallback((formType, fields) => {
    debouncedUpdate(prev => {
      const formIndex = prev.openForms.findIndex(f => f.type === formType)
      
      if (formIndex < 0) {
        // Form not tracked, add it
        return {
          ...prev,
          openForms: [...prev.openForms, {
            type: formType,
            fields,
            completion: calculateCompletion(fields),
            openedAt: Date.now()
          }],
          lastActivity: Date.now()
        }
      }
      
      // Update existing form
      const newOpenForms = [...prev.openForms]
      newOpenForms[formIndex] = {
        ...newOpenForms[formIndex],
        fields: { ...newOpenForms[formIndex].fields, ...fields },
        completion: calculateCompletion({ ...newOpenForms[formIndex].fields, ...fields })
      }
      
      return {
        ...prev,
        openForms: newOpenForms,
        lastActivity: Date.now()
      }
    })
  }, [debouncedUpdate])
  
  /**
   * Record a chef action
   */
  const reportAction = useCallback((actionType, metadata = {}) => {
    setContext(prev => {
      const actionEntry = {
        type: actionType,
        timestamp: Date.now(),
        ...metadata
      }
      
      // Keep only last N actions
      const newActions = [actionEntry, ...prev.recentActions].slice(0, MAX_RECENT_ACTIONS)
      
      return {
        ...prev,
        recentActions: newActions,
        lastActivity: Date.now()
      }
    })
    
    resetIdleTimer()
  }, [resetIdleTimer])
  
  /**
   * Record a validation error
   */
  const reportError = useCallback((errorType, details = {}) => {
    setContext(prev => ({
      ...prev,
      validationErrors: [...prev.validationErrors, {
        type: errorType,
        timestamp: Date.now(),
        ...details
      }],
      lastActivity: Date.now()
    }))
    
    resetIdleTimer()
  }, [resetIdleTimer])
  
  /**
   * Clear validation errors
   */
  const clearErrors = useCallback((errorType = null) => {
    setContext(prev => ({
      ...prev,
      validationErrors: errorType 
        ? prev.validationErrors.filter(e => e.type !== errorType)
        : []
    }))
  }, [])
  
  /**
   * Get time spent on current form (if any)
   */
  const getFormTime = useCallback((formType) => {
    const form = context.openForms.find(f => f.type === formType)
    if (!form) return 0
    return Date.now() - form.openedAt
  }, [context.openForms])
  
  /**
   * Check if a specific form has been idle
   */
  const isFormIdle = useCallback((formType, thresholdMs = IDLE_THRESHOLD_MS) => {
    const form = context.openForms.find(f => f.type === formType)
    if (!form) return false
    
    const timeSinceActivity = Date.now() - context.lastActivity
    return timeSinceActivity >= thresholdMs
  }, [context.openForms, context.lastActivity])
  
  // Track time on screen
  useEffect(() => {
    screenTimeInterval.current = setInterval(() => {
      setContext(prev => ({
        ...prev,
        timeOnScreen: Date.now() - tabStartTime.current
      }))
    }, 1000)
    
    return () => {
      if (screenTimeInterval.current) {
        clearInterval(screenTimeInterval.current)
      }
    }
  }, [])
  
  // Initialize idle timer
  useEffect(() => {
    resetIdleTimer()
    
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current)
      if (debounceTimer.current) clearTimeout(debounceTimer.current)
    }
  }, [resetIdleTimer])
  
  return {
    context,
    setTab,
    openForm,
    closeForm,
    updateFormFields,
    reportAction,
    reportError,
    clearErrors,
    isIdle,
    getFormTime,
    isFormIdle
  }
}

export default useChefContext
