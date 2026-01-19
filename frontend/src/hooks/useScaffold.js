/**
 * useScaffold Hook
 * 
 * Manages scaffold state and operations for meal creation.
 * Provides methods to generate, update, and execute scaffolds.
 */

import { useState, useCallback } from 'react'
import { api } from '../api.js'

/**
 * useScaffold - Hook for scaffold operations
 * 
 * @returns {Object} Scaffold state and actions
 */
export function useScaffold() {
  const [scaffold, setScaffold] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)
  const [isFetchingIngredients, setIsFetchingIngredients] = useState(false)
  const [includeIngredients, setIncludeIngredients] = useState(false)
  const [error, setError] = useState(null)
  const [lastResult, setLastResult] = useState(null)
  const [lastHint, setLastHint] = useState('')
  const [lastMealType, setLastMealType] = useState('Dinner')
  
  /**
   * Generate a new scaffold from a hint
   */
  const generateScaffold = useCallback(async (hint, options = {}) => {
    const {
      includeDishes = true,
      includeIngredients: includeIngs = false,
      mealType = 'Dinner'
    } = options
    
    setIsGenerating(true)
    setError(null)
    setLastHint(hint)
    setLastMealType(mealType)
    setIncludeIngredients(includeIngs)
    
    try {
      console.log('[Scaffold] Generating scaffold for:', hint, { includeIngredients: includeIngs })
      
      const response = await api.post('/chefs/api/me/sous-chef/scaffold/generate/', {
        hint,
        include_dishes: includeDishes,
        include_ingredients: includeIngs,
        meal_type: mealType
      })
      
      console.log('[Scaffold] Generated:', response.data)
      
      if (response.data.status === 'success') {
        setScaffold(response.data.scaffold)
        return response.data.scaffold
      } else {
        throw new Error(response.data.message || 'Failed to generate scaffold')
      }
    } catch (err) {
      console.error('[Scaffold] Generation failed:', err)
      setError(err.message || 'Failed to generate scaffold')
      return null
    } finally {
      setIsGenerating(false)
    }
  }, [])
  
  /**
   * Toggle ingredient inclusion and re-fetch if needed
   */
  const toggleIngredients = useCallback(async (enabled) => {
    setIncludeIngredients(enabled)
    
    if (enabled && scaffold && lastHint) {
      // Re-fetch with ingredients
      setIsFetchingIngredients(true)
      try {
        console.log('[Scaffold] Re-fetching with ingredients')
        
        const response = await api.post('/chefs/api/me/sous-chef/scaffold/generate/', {
          hint: lastHint,
          include_dishes: true,
          include_ingredients: true,
          meal_type: lastMealType
        })
        
        if (response.data.status === 'success') {
          setScaffold(response.data.scaffold)
        }
      } catch (err) {
        console.error('[Scaffold] Ingredient fetch failed:', err)
        setError('Failed to load ingredient suggestions')
      } finally {
        setIsFetchingIngredients(false)
      }
    } else if (!enabled && scaffold) {
      // Remove ingredients from existing scaffold (keep dishes)
      const removeIngredients = (item) => {
        if (item.type === 'dish') {
          return { ...item, children: [] }
        }
        return {
          ...item,
          children: (item.children || []).map(removeIngredients)
        }
      }
      setScaffold(removeIngredients(scaffold))
    }
  }, [scaffold, lastHint, lastMealType])
  
  /**
   * Update the scaffold (for editing)
   */
  const updateScaffold = useCallback((newScaffold) => {
    setScaffold(newScaffold)
  }, [])
  
  /**
   * Update a specific item in the scaffold by path
   */
  const updateScaffoldItem = useCallback((itemId, updates) => {
    const updateRecursive = (item) => {
      if (item.id === itemId) {
        return {
          ...item,
          data: { ...item.data, ...updates },
          status: item.status === 'suggested' ? 'edited' : item.status
        }
      }
      return {
        ...item,
        children: (item.children || []).map(updateRecursive)
      }
    }
    
    setScaffold(prev => prev ? updateRecursive(prev) : null)
  }, [])
  
  /**
   * Remove an item from the scaffold
   */
  const removeScaffoldItem = useCallback((itemId) => {
    const removeRecursive = (item) => {
      if (item.id === itemId) {
        return { ...item, status: 'removed' }
      }
      return {
        ...item,
        children: (item.children || []).map(removeRecursive)
      }
    }
    
    setScaffold(prev => prev ? removeRecursive(prev) : null)
  }, [])
  
  /**
   * Restore a removed item
   */
  const restoreScaffoldItem = useCallback((itemId) => {
    const restoreRecursive = (item) => {
      if (item.id === itemId) {
        return { ...item, status: 'suggested' }
      }
      return {
        ...item,
        children: (item.children || []).map(restoreRecursive)
      }
    }
    
    setScaffold(prev => prev ? restoreRecursive(prev) : null)
  }, [])
  
  /**
   * Execute the scaffold (create all items)
   */
  const executeScaffold = useCallback(async () => {
    if (!scaffold) {
      setError('No scaffold to execute')
      return null
    }
    
    setIsExecuting(true)
    setError(null)
    
    try {
      console.log('[Scaffold] Executing scaffold:', scaffold)
      
      const response = await api.post('/chefs/api/me/sous-chef/scaffold/execute/', {
        scaffold
      })
      
      console.log('[Scaffold] Execution result:', response.data)
      
      if (response.data.status === 'success') {
        setLastResult(response.data)
        setScaffold(null) // Clear scaffold after successful execution
        return response.data
      } else {
        throw new Error(response.data.message || 'Failed to execute scaffold')
      }
    } catch (err) {
      console.error('[Scaffold] Execution failed:', err)
      setError(err.message || 'Failed to execute scaffold')
      return null
    } finally {
      setIsExecuting(false)
    }
  }, [scaffold])
  
  /**
   * Clear the scaffold
   */
  const clearScaffold = useCallback(() => {
    setScaffold(null)
    setError(null)
    setLastResult(null)
    setIncludeIngredients(false)
    setLastHint('')
  }, [])
  
  /**
   * Get count of items to be created
   */
  const getItemCounts = useCallback(() => {
    const countRecursive = (item) => {
      if (!item || item.status === 'removed') {
        return { meals: 0, dishes: 0, ingredients: 0 }
      }
      
      let counts = { meals: 0, dishes: 0, ingredients: 0 }
      
      if (item.type === 'meal' && item.status !== 'exists') counts.meals = 1
      if (item.type === 'dish' && item.status !== 'exists') counts.dishes = 1
      if (item.type === 'ingredient' && item.status !== 'exists') counts.ingredients = 1
      
      for (const child of (item.children || [])) {
        const childCounts = countRecursive(child)
        counts.meals += childCounts.meals
        counts.dishes += childCounts.dishes
        counts.ingredients += childCounts.ingredients
      }
      
      return counts
    }
    
    return scaffold ? countRecursive(scaffold) : { meals: 0, dishes: 0, ingredients: 0 }
  }, [scaffold])
  
  return {
    // State
    scaffold,
    isGenerating,
    isExecuting,
    isFetchingIngredients,
    includeIngredients,
    error,
    lastResult,
    
    // Computed
    hasScaffold: !!scaffold,
    itemCounts: getItemCounts(),
    
    // Actions
    generateScaffold,
    toggleIngredients,
    updateScaffold,
    updateScaffoldItem,
    removeScaffoldItem,
    restoreScaffoldItem,
    executeScaffold,
    clearScaffold
  }
}

export default useScaffold



