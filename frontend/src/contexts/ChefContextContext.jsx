/**
 * ChefContextContext
 * 
 * React context provider that shares chef activity state across the dashboard.
 * Used for contextual AI suggestions from the Sous Chef assistant.
 */

import React, { createContext, useContext, useMemo, useCallback, useRef, useEffect } from 'react'
import { useChefContext } from '../hooks/useChefContext'

// Create the context
const ChefContextContext = createContext(null)

// Suggestion fetch debounce (don't spam the API)
const SUGGESTION_DEBOUNCE_MS = 800

/**
 * ChefContextProvider
 * 
 * Wraps the chef dashboard and provides context tracking to all children.
 * 
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 * @param {Function} props.onSuggestionRequest - Callback when suggestions should be fetched
 */
export function ChefContextProvider({ children, onSuggestionRequest }) {
  const chefContext = useChefContext()
  const suggestionDebounceRef = useRef(null)
  const lastSuggestionContextRef = useRef(null)
  
  const {
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
  } = chefContext
  
  /**
   * Check if context has changed meaningfully since last suggestion request
   */
  const hasContextChanged = useCallback((newContext) => {
    const last = lastSuggestionContextRef.current
    if (!last) return true
    
    // Check if tab changed
    if (last.currentTab !== newContext.currentTab) return true
    
    // Check if open forms changed
    if (last.openForms.length !== newContext.openForms.length) return true
    
    // Check if any form's completion changed significantly
    for (const form of newContext.openForms) {
      const lastForm = last.openForms.find(f => f.type === form.type)
      if (!lastForm) return true
      if (Math.abs(form.completion - lastForm.completion) > 0.2) return true
    }
    
    return false
  }, [])
  
  /**
   * Request suggestions based on current context
   * Debounced to avoid excessive API calls
   */
  const requestSuggestions = useCallback(() => {
    if (!onSuggestionRequest) return
    if (!hasContextChanged(context)) return
    
    if (suggestionDebounceRef.current) {
      clearTimeout(suggestionDebounceRef.current)
    }
    
    suggestionDebounceRef.current = setTimeout(() => {
      lastSuggestionContextRef.current = { ...context }
      onSuggestionRequest(context)
    }, SUGGESTION_DEBOUNCE_MS)
  }, [context, onSuggestionRequest, hasContextChanged])
  
  /**
   * Enhanced setTab that also triggers suggestion check
   */
  const setTabWithSuggestions = useCallback((tab) => {
    setTab(tab)
    // Delay suggestion request to let context update
    setTimeout(requestSuggestions, 100)
  }, [setTab, requestSuggestions])
  
  /**
   * Enhanced openForm that also triggers suggestion check
   */
  const openFormWithSuggestions = useCallback((formType, initialFields = {}) => {
    openForm(formType, initialFields)
    setTimeout(requestSuggestions, 100)
  }, [openForm, requestSuggestions])
  
  /**
   * Enhanced updateFormFields that triggers suggestions on significant changes
   */
  const updateFormFieldsWithSuggestions = useCallback((formType, fields) => {
    updateFormFields(formType, fields)
    // Only request suggestions if a meaningful amount of data is present
    const form = context.openForms.find(f => f.type === formType)
    if (form && form.completion > 0.3) {
      setTimeout(requestSuggestions, 500)
    }
  }, [updateFormFields, context.openForms, requestSuggestions])
  
  /**
   * Enhanced reportAction that may trigger milestone suggestions
   */
  const reportActionWithSuggestions = useCallback((actionType, metadata = {}) => {
    reportAction(actionType, metadata)
    
    // Milestone actions that should trigger suggestions
    const milestoneActions = [
      'created_dish',
      'created_meal',
      'created_event',
      'created_service',
      'first_dish',
      'first_meal',
      'first_event',
      'profile_updated'
    ]
    
    if (milestoneActions.includes(actionType)) {
      setTimeout(requestSuggestions, 200)
    }
  }, [reportAction, requestSuggestions])
  
  // Request suggestions when idle state changes
  useEffect(() => {
    if (isIdle && context.openForms.length > 0) {
      requestSuggestions()
    }
  }, [isIdle, context.openForms.length, requestSuggestions])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (suggestionDebounceRef.current) {
        clearTimeout(suggestionDebounceRef.current)
      }
    }
  }, [])
  
  // Memoize context value to prevent unnecessary re-renders
  const value = useMemo(() => ({
    // State
    context,
    isIdle,
    
    // Actions (enhanced with suggestion triggers)
    setTab: setTabWithSuggestions,
    openForm: openFormWithSuggestions,
    closeForm,
    updateFormFields: updateFormFieldsWithSuggestions,
    reportAction: reportActionWithSuggestions,
    reportError,
    clearErrors,
    
    // Utilities
    getFormTime,
    isFormIdle,
    requestSuggestions
  }), [
    context,
    isIdle,
    setTabWithSuggestions,
    openFormWithSuggestions,
    closeForm,
    updateFormFieldsWithSuggestions,
    reportActionWithSuggestions,
    reportError,
    clearErrors,
    getFormTime,
    isFormIdle,
    requestSuggestions
  ])
  
  return (
    <ChefContextContext.Provider value={value}>
      {children}
    </ChefContextContext.Provider>
  )
}

/**
 * Hook to access the chef context
 * @returns {Object} Chef context value
 * @throws {Error} If used outside of ChefContextProvider
 */
export function useChefContextValue() {
  const value = useContext(ChefContextContext)
  
  if (!value) {
    throw new Error('useChefContextValue must be used within a ChefContextProvider')
  }
  
  return value
}

/**
 * Hook to safely access chef context (returns null if not in provider)
 * Use this in components that may or may not be wrapped in the provider
 */
export function useChefContextSafe() {
  return useContext(ChefContextContext)
}

export default ChefContextContext
