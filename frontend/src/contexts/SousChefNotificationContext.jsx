/**
 * SousChefNotificationContext
 * 
 * Provides a way for any component to send notifications to the Sous Chef widget.
 * Also handles global job tracking for AI meal generation so jobs continue
 * even when components unmount (like closing the meal plan modal).
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react'
import { getGenerationJobStatus } from '../api/chefMealPlanClient.js'

const SousChefNotificationContext = createContext(null)

export function SousChefNotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  
  // Global job tracking - persists even when components unmount
  const [activeJobs, setActiveJobs] = useState([])
  const pollingIntervalsRef = useRef({})
  
  /**
   * Add a notification to show in Sous Chef
   * @param {Object} notification
   * @param {string} notification.type - 'meal_generation' | 'plan_update' | 'suggestion' | 'info'
   * @param {string} notification.title - Short title for the notification
   * @param {string} notification.message - Detailed message
   * @param {Object} notification.context - Context data for Sous Chef conversation
   * @param {string} notification.actionLabel - Optional button label
   * @param {function} notification.onAction - Optional callback when action clicked
   */
  const addNotification = useCallback((notification) => {
    const id = Date.now()
    const newNotification = {
      id,
      timestamp: new Date(),
      read: false,
      ...notification
    }
    
    setNotifications(prev => [newNotification, ...prev])
    setUnreadCount(prev => prev + 1)
    
    return id
  }, [])
  
  /**
   * Mark a notification as read
   */
  const markAsRead = useCallback((notificationId) => {
    setNotifications(prev => 
      prev.map(n => 
        n.id === notificationId ? { ...n, read: true } : n
      )
    )
    setUnreadCount(prev => Math.max(0, prev - 1))
  }, [])
  
  /**
   * Mark all notifications as read
   */
  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
    setUnreadCount(0)
  }, [])
  
  /**
   * Clear a specific notification
   */
  const clearNotification = useCallback((notificationId) => {
    setNotifications(prev => {
      const notification = prev.find(n => n.id === notificationId)
      if (notification && !notification.read) {
        setUnreadCount(c => Math.max(0, c - 1))
      }
      return prev.filter(n => n.id !== notificationId)
    })
  }, [])
  
  /**
   * Clear all notifications
   */
  const clearAll = useCallback(() => {
    setNotifications([])
    setUnreadCount(0)
  }, [])
  
  /**
   * Get the most recent unread notification
   */
  const getLatestUnread = useCallback(() => {
    return notifications.find(n => !n.read)
  }, [notifications])
  
  /**
   * Track a generation job globally.
   * This allows the job to continue polling even if the originating component unmounts.
   * 
   * @param {Object} jobInfo
   * @param {number} jobInfo.jobId - The generation job ID
   * @param {number} jobInfo.planId - The meal plan ID
   * @param {string} jobInfo.planTitle - Plan title for display
   * @param {string} jobInfo.clientName - Client name for display
   * @param {string} jobInfo.mode - 'full_week' | 'fill_empty' | 'single_slot'
   * @param {Object} jobInfo.slot - For single_slot mode: { day, meal_type }
   * @param {function} jobInfo.onComplete - Optional callback when job completes
   */
  const trackJob = useCallback((jobInfo) => {
    const { jobId, planId, planTitle, clientName, mode, slot, onComplete } = jobInfo
    
    // Add to active jobs
    setActiveJobs(prev => [...prev, {
      jobId,
      planId,
      planTitle,
      clientName,
      mode,
      slot,
      status: 'pending',
      startedAt: new Date()
    }])
    
    // Start polling
    const pollInterval = setInterval(async () => {
      try {
        const data = await getGenerationJobStatus(jobId)
        
        // Update job status
        setActiveJobs(prev => prev.map(j => 
          j.jobId === jobId 
            ? { ...j, status: data.status, slotsGenerated: data.slots_generated, slotsRequested: data.slots_requested }
            : j
        ))
        
        if (data.status === 'completed') {
          // Stop polling
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[jobId]
          
          // Remove from active jobs
          setActiveJobs(prev => prev.filter(j => j.jobId !== jobId))
          
          // Create rich notification
          const suggestionsCount = data.suggestions?.length || 0
          const notification = createMealGenerationNotification({
            planTitle: planTitle || 'Meal Plan',
            clientName: clientName || 'Client',
            suggestionsCount,
            planId,
            mode,
            slot,
            suggestions: data.suggestions || []
          })
          
          addNotification(notification)
          
          // Call completion callback if provided
          if (onComplete) {
            onComplete(data)
          }
        } else if (data.status === 'failed') {
          // Stop polling
          clearInterval(pollInterval)
          delete pollingIntervalsRef.current[jobId]
          
          // Remove from active jobs
          setActiveJobs(prev => prev.filter(j => j.jobId !== jobId))
          
          // Notify of failure
          addNotification({
            type: 'error',
            title: '❌ Generation Failed',
            message: data.error_message || 'Meal generation failed. Please try again.',
            context: {
              topic: 'meal_generation_error',
              planId,
              error: data.error_message
            }
          })
        }
      } catch (err) {
        console.error('Error polling job status:', err)
        // Don't stop polling on transient errors, but after many failures give up
      }
    }, 2500) // Poll every 2.5 seconds
    
    pollingIntervalsRef.current[jobId] = pollInterval
    
    return jobId
  }, [addNotification])
  
  /**
   * Check if a job is currently being tracked
   */
  const isJobActive = useCallback((jobId) => {
    return activeJobs.some(j => j.jobId === jobId)
  }, [activeJobs])
  
  /**
   * Get status of an active job
   */
  const getJobStatus = useCallback((jobId) => {
    return activeJobs.find(j => j.jobId === jobId)
  }, [activeJobs])
  
  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      Object.values(pollingIntervalsRef.current).forEach(clearInterval)
    }
  }, [])
  
  const value = {
    notifications,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    clearNotification,
    clearAll,
    getLatestUnread,
    // Job tracking
    activeJobs,
    trackJob,
    isJobActive,
    getJobStatus
  }
  
  return (
    <SousChefNotificationContext.Provider value={value}>
      {children}
    </SousChefNotificationContext.Provider>
  )
}

export function useSousChefNotifications() {
  const context = useContext(SousChefNotificationContext)
  if (!context) {
    throw new Error('useSousChefNotifications must be used within SousChefNotificationProvider')
  }
  return context
}

/**
 * Helper to create a meal generation completion notification with rich context
 */
export function createMealGenerationNotification({ 
  planTitle, 
  clientName, 
  suggestionsCount, 
  planId,
  mode = 'full_week',
  slot = null,
  suggestions = []
}) {
  // Build a summary of what was generated
  let modeDescription = ''
  let suggestionSummary = ''
  
  if (mode === 'single_slot' && slot) {
    modeDescription = `for ${slot.day} ${slot.meal_type}`
    const suggestion = suggestions[0]
    if (suggestion) {
      suggestionSummary = `I suggested "${suggestion.name}"${suggestion.dietary_tags?.length ? ` (${suggestion.dietary_tags.join(', ')})` : ''}.`
    }
  } else if (mode === 'fill_empty') {
    modeDescription = 'for empty slots'
    // Group by day for summary
    const dayGroups = suggestions.reduce((acc, s) => {
      acc[s.day] = acc[s.day] || []
      acc[s.day].push(s.meal_type)
      return acc
    }, {})
    const days = Object.keys(dayGroups).length
    suggestionSummary = `Filled ${suggestionsCount} empty slots across ${days} day${days > 1 ? 's' : ''}.`
  } else {
    modeDescription = 'for the full week'
    // Get unique meal names for variety summary
    const uniqueMeals = [...new Set(suggestions.map(s => s.name))].slice(0, 5)
    suggestionSummary = `Included meals like: ${uniqueMeals.join(', ')}${uniqueMeals.length < suggestions.length ? '...' : ''}`
  }
  
  // Build rich pre-prompt with full context
  const prePrompt = mode === 'single_slot' && slot
    ? `I just generated an AI meal suggestion for ${clientName}'s ${slot.meal_type} on ${slot.day} in their meal plan "${planTitle}". ${suggestionSummary} Can you tell me more about this meal and whether it's a good fit for their dietary needs?`
    : `I just generated ${suggestionsCount} AI meal suggestions ${modeDescription} for ${clientName}'s meal plan "${planTitle}". ${suggestionSummary} Can you help me review them and make sure they're appropriate for the family's dietary needs?`
  
  return {
    type: 'meal_generation',
    title: '✨ AI Meals Ready!',
    message: mode === 'single_slot' && slot
      ? `Generated ${slot.day} ${slot.meal_type} for ${clientName}`
      : `Generated ${suggestionsCount} meal suggestions for ${clientName}`,
    context: {
      topic: 'meal_plan_suggestions',
      planId,
      planTitle,
      clientName,
      suggestionsCount,
      mode,
      slot,
      // Include actual suggestions so Sous Chef can discuss them
      suggestions: suggestions.slice(0, 10), // Limit to avoid huge context
      // Pre-built prompt for Sous Chef to start the conversation
      prePrompt
    },
    actionLabel: mode === 'single_slot' ? 'View Suggestion' : 'Review Suggestions'
  }
}

export default SousChefNotificationContext

