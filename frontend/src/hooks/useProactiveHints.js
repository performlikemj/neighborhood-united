/**
 * useProactiveHints Hook
 * 
 * Detects high-value moments (milestones, idle states, errors) and
 * generates proactive hint messages from the Sous Chef.
 */

import { useState, useCallback, useRef, useEffect } from 'react'

// Milestone types and their configurations
const MILESTONES = {
  first_dish: {
    trigger: (prev, current) => prev.dishCount === 0 && current.dishCount === 1,
    message: "Great job creating your first dish! 🎉 Want help creating a meal to package it for customers?",
    priority: 'high',
    action: { type: 'create', target: 'meal', label: 'Create a Meal' }
  },
  first_meal: {
    trigger: (prev, current) => prev.mealCount === 0 && current.mealCount === 1,
    message: "Your first meal is ready! 🍽️ Schedule an event to start taking orders.",
    priority: 'high',
    action: { type: 'create', target: 'event', label: 'Schedule Event' }
  },
  first_event: {
    trigger: (prev, current) => prev.eventCount === 0 && current.eventCount === 1,
    message: "Your event is live! 📅 Share the link with your customers or promote it on social media.",
    priority: 'medium',
    action: null
  },
  first_service: {
    trigger: (prev, current) => prev.serviceCount === 0 && current.serviceCount === 1,
    message: "Your service is set up! 💼 Add pricing tiers to accept bookings at different household sizes.",
    priority: 'medium',
    action: { type: 'navigate', target: 'services', label: 'Add Pricing' }
  },
  profile_complete: {
    trigger: (prev, current) => prev.profileCompletion < 80 && current.profileCompletion >= 80,
    message: "Your profile is looking great! 🌟 A complete profile helps customers trust you.",
    priority: 'low',
    action: null
  }
}

// Idle thresholds (in milliseconds)
const IDLE_FORM_THRESHOLD = 45 * 1000  // 45 seconds idle on a form before "need help?" prompt
const IDLE_CHECK_INTERVAL = 10 * 1000  // Check every 10 seconds

/**
 * useProactiveHints - Generates proactive hints based on chef activity
 * 
 * @param {Object} context - Chef context from useChefContext
 * @param {Object} stats - Chef stats (dishCount, mealCount, etc.)
 * @param {boolean} enabled - Whether proactive hints are enabled
 * @returns {Object} Hint state and actions
 */
export function useProactiveHints({ context, stats = {}, enabled = true }) {
  const [activeHint, setActiveHint] = useState(null)
  const [hintHistory, setHintHistory] = useState([])
  const [dismissed, setDismissed] = useState(new Set())
  
  // Track previous stats for milestone detection
  const prevStatsRef = useRef(stats)
  const idleCheckRef = useRef(null)
  const hintQueueRef = useRef([])
  
  /**
   * Check if a hint should be shown (not dismissed, not recently shown)
   */
  const shouldShowHint = useCallback((hintId) => {
    if (dismissed.has(hintId)) return false
    
    // Check if hint was shown in the last 5 minutes
    const recentlySeen = hintHistory.some(
      h => h.id === hintId && Date.now() - h.timestamp < 5 * 60 * 1000
    )
    
    return !recentlySeen
  }, [dismissed, hintHistory])
  
  /**
   * Show a proactive hint
   */
  const showHint = useCallback((hint) => {
    if (!enabled || !shouldShowHint(hint.id)) return false
    
    setActiveHint(hint)
    setHintHistory(prev => [
      { id: hint.id, timestamp: Date.now() },
      ...prev.slice(0, 9)  // Keep last 10
    ])
    
    return true
  }, [enabled, shouldShowHint])
  
  /**
   * Dismiss the current hint
   */
  const dismissHint = useCallback((permanent = false) => {
    if (activeHint && permanent) {
      setDismissed(prev => new Set([...prev, activeHint.id]))
    }
    setActiveHint(null)
  }, [activeHint])
  
  /**
   * Accept a hint action
   */
  const acceptHint = useCallback(() => {
    const hint = activeHint
    setActiveHint(null)
    return hint?.action || null
  }, [activeHint])
  
  /**
   * Queue a hint (for delayed showing)
   */
  const queueHint = useCallback((hint, delay = 500) => {
    hintQueueRef.current.push(hint)
    
    setTimeout(() => {
      const queued = hintQueueRef.current.shift()
      if (queued && !activeHint) {
        showHint(queued)
      }
    }, delay)
  }, [activeHint, showHint])
  
  /**
   * Check for milestone triggers
   */
  useEffect(() => {
    if (!enabled) return
    
    const prevStats = prevStatsRef.current
    
    // Check each milestone
    for (const [id, config] of Object.entries(MILESTONES)) {
      if (config.trigger(prevStats, stats)) {
        queueHint({
          id,
          type: 'milestone',
          message: config.message,
          priority: config.priority,
          action: config.action
        })
        break  // Only show one milestone at a time
      }
    }
    
    // Update previous stats
    prevStatsRef.current = { ...stats }
  }, [stats, enabled, queueHint])
  
  /**
   * Check for idle state on forms
   */
  useEffect(() => {
    if (!enabled || !context) return
    
    const checkIdle = () => {
      const { openForms, lastActivity, isIdle } = context
      
      if (!isIdle || openForms.length === 0) return
      
      // Find a form that's been open long enough
      const idleForm = openForms.find(form => {
        const formTime = Date.now() - (form.openedAt || 0)
        return formTime > IDLE_FORM_THRESHOLD && form.completion > 0.1 && form.completion < 0.9
      })
      
      if (idleForm && shouldShowHint(`idle_${idleForm.type}`)) {
        const formLabel = idleForm.type.replace('_', ' ')
        showHint({
          id: `idle_${idleForm.type}`,
          type: 'idle',
          message: `Need help finishing your ${formLabel}? I can suggest values based on your style.`,
          priority: 'medium',
          action: { type: 'suggest', target: idleForm.type, label: 'Get Suggestions' },
          formType: idleForm.type
        })
      }
    }
    
    // Check periodically
    idleCheckRef.current = setInterval(checkIdle, IDLE_CHECK_INTERVAL)
    
    return () => {
      if (idleCheckRef.current) {
        clearInterval(idleCheckRef.current)
      }
    }
  }, [context, enabled, shouldShowHint, showHint])
  
  /**
   * Generate a hint for validation errors
   */
  const generateErrorHint = useCallback((errors) => {
    if (!enabled || !errors || errors.length === 0) return
    
    const error = errors[0]  // Focus on first error
    const fieldLabel = (error.field || 'field').replace('_', ' ')
    
    showHint({
      id: `error_${error.type}_${error.field}`,
      type: 'error',
      message: `I noticed an issue with the ${fieldLabel}. ${error.message || 'Would you like help fixing it?'}`,
      priority: 'high',
      action: null,
      formType: error.formType
    })
  }, [enabled, showHint])
  
  /**
   * Clear dismissed hints (for settings reset)
   */
  const clearDismissed = useCallback(() => {
    setDismissed(new Set())
  }, [])
  
  return {
    // State
    activeHint,
    hasHint: !!activeHint,
    hintPriority: activeHint?.priority || 'low',
    
    // Actions
    dismissHint,
    acceptHint,
    generateErrorHint,
    clearDismissed,
    
    // For manual hint triggering
    showHint,
    queueHint
  }
}

export default useProactiveHints
