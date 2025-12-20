/**
 * useSuggestions Hook
 * 
 * Fetches and manages contextual suggestions from the Sous Chef assistant.
 * Integrates with the ChefContext to provide intelligent form suggestions.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { api } from '../api.js'

// Debounce delay for suggestion fetches
const FETCH_DEBOUNCE_MS = 500

// Cache duration for suggestions
const CACHE_DURATION_MS = 30000

/**
 * useSuggestions Hook
 * 
 * @param {Object} options
 * @param {string} options.formType - The type of form to get suggestions for (optional)
 * @param {boolean} options.enabled - Whether suggestions are enabled
 * @returns {Object} Suggestion state and actions
 */
export function useSuggestions({ formType = null, enabled = true } = {}) {
  const [suggestions, setSuggestions] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [priority, setPriority] = useState('low')
  
  // Cache and debounce refs
  const cacheRef = useRef({})
  const debounceRef = useRef(null)
  const lastFetchRef = useRef(0)
  
  /**
   * Fetch suggestions from the API
   */
  const fetchSuggestions = useCallback(async (context) => {
    if (!enabled) {
      console.log('[SousChef] Suggestions disabled')
      return
    }
    
    console.log('[SousChef] Fetching suggestions for context:', context)
    
    // Clear existing debounce
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    
    // Check cache
    const cacheKey = JSON.stringify(context)
    const cached = cacheRef.current[cacheKey]
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION_MS) {
      console.log('[SousChef] Using cached suggestions:', cached.suggestions)
      setSuggestions(cached.suggestions)
      setPriority(cached.priority)
      return
    }
    
    // Debounce the fetch
    debounceRef.current = setTimeout(async () => {
      try {
        setIsLoading(true)
        setError(null)
        
        console.log('[SousChef] Making API call...')
        const response = await api.post('/chefs/api/me/sous-chef/suggest/', {
          context
        })
        
        console.log('[SousChef] API response:', response.data)
        
        if (response.data.status === 'success') {
          const newSuggestions = response.data.suggestions || []
          const newPriority = response.data.priority || 'low'
          
          // Filter by form type if specified
          const filteredSuggestions = formType
            ? newSuggestions.filter(s => !s.formType || s.formType === formType)
            : newSuggestions
          
          console.log('[SousChef] Filtered suggestions:', filteredSuggestions)
          
          setSuggestions(filteredSuggestions)
          setPriority(newPriority)
          
          // Update cache
          cacheRef.current[cacheKey] = {
            suggestions: filteredSuggestions,
            priority: newPriority,
            timestamp: Date.now()
          }
        }
        
        lastFetchRef.current = Date.now()
      } catch (err) {
        console.error('[SousChef] Failed to fetch suggestions:', err)
        setError(err.message)
      } finally {
        setIsLoading(false)
      }
    }, FETCH_DEBOUNCE_MS)
  }, [enabled, formType])
  
  /**
   * Get suggestion for a specific field
   */
  const getSuggestionForField = useCallback((targetFormType, field) => {
    return suggestions.find(
      s => s.type === 'field' && 
           s.formType === targetFormType && 
           s.field === field
    )
  }, [suggestions])
  
  /**
   * Get action suggestions
   */
  const getActionSuggestions = useCallback(() => {
    return suggestions.filter(s => s.type === 'action' || s.type === 'tip')
  }, [suggestions])
  
  /**
   * Accept a suggestion
   */
  const acceptSuggestion = useCallback((suggestionId) => {
    setSuggestions(prev => prev.filter(s => s.id !== suggestionId))
    // Could also track acceptance analytics here
  }, [])
  
  /**
   * Dismiss a suggestion
   */
  const dismissSuggestion = useCallback((suggestionId) => {
    setSuggestions(prev => prev.filter(s => s.id !== suggestionId))
    // Could also track dismissal analytics here
  }, [])
  
  /**
   * Clear all suggestions
   */
  const clearSuggestions = useCallback(() => {
    setSuggestions([])
    setPriority('low')
  }, [])
  
  /**
   * Clear the cache
   */
  const clearCache = useCallback(() => {
    cacheRef.current = {}
  }, [])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [])
  
  return {
    // State
    suggestions,
    isLoading,
    error,
    priority,
    
    // Suggestion count
    count: suggestions.length,
    hasHighPriority: priority === 'high',
    hasSuggestions: suggestions.length > 0,
    
    // Actions
    fetchSuggestions,
    getSuggestionForField,
    getActionSuggestions,
    acceptSuggestion,
    dismissSuggestion,
    clearSuggestions,
    clearCache
  }
}

export default useSuggestions
