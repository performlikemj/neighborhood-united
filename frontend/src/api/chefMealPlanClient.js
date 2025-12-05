/**
 * Chef Meal Plan API Client
 * 
 * Functions for managing chef-created meal plans for clients,
 * including AI-assisted meal generation.
 */

import { api } from '../api.js'

const BASE = '/chefs/api/me'

// ============================================================================
// Plan CRUD
// ============================================================================

/**
 * Get all meal plans for a client
 */
export async function getClientPlans(clientId, { status } = {}) {
  const params = {}
  if (status) params.status = status
  
  const response = await api.get(`${BASE}/clients/${clientId}/plans/`, {
    params,
    skipUserId: true
  })
  return response?.data
}

/**
 * Create a new meal plan for a client
 */
export async function createPlan(clientId, { title, start_date, end_date, notes }) {
  const response = await api.post(`${BASE}/clients/${clientId}/plans/`, {
    title,
    start_date,
    end_date,
    notes
  }, { skipUserId: true })
  return response?.data
}

/**
 * Get plan details with all days and items
 */
export async function getPlanDetail(planId) {
  const response = await api.get(`${BASE}/plans/${planId}/`, { skipUserId: true })
  return response?.data
}

/**
 * Update plan metadata
 */
export async function updatePlan(planId, updates) {
  const response = await api.put(`${BASE}/plans/${planId}/`, updates, { skipUserId: true })
  return response?.data
}

/**
 * Delete a draft plan
 */
export async function deletePlan(planId) {
  const response = await api.delete(`${BASE}/plans/${planId}/`, { skipUserId: true })
  return response?.data
}

/**
 * Publish a plan to make it visible to the customer
 */
export async function publishPlan(planId) {
  const response = await api.post(`${BASE}/plans/${planId}/publish/`, {}, { skipUserId: true })
  return response?.data
}

/**
 * Archive a plan
 */
export async function archivePlan(planId) {
  const response = await api.post(`${BASE}/plans/${planId}/archive/`, {}, { skipUserId: true })
  return response?.data
}

// ============================================================================
// Days Management
// ============================================================================

/**
 * Add a day to a plan
 */
export async function addPlanDay(planId, { date, is_skipped, skip_reason, notes }) {
  const response = await api.post(`${BASE}/plans/${planId}/days/`, {
    date,
    is_skipped,
    skip_reason,
    notes
  }, { skipUserId: true })
  return response?.data
}

/**
 * Update a day
 */
export async function updatePlanDay(planId, dayId, updates) {
  const response = await api.put(`${BASE}/plans/${planId}/days/${dayId}/`, updates, { skipUserId: true })
  return response?.data
}

/**
 * Delete a day
 */
export async function deletePlanDay(planId, dayId) {
  const response = await api.delete(`${BASE}/plans/${planId}/days/${dayId}/`, { skipUserId: true })
  return response?.data
}

// ============================================================================
// Items (Meals) Management
// ============================================================================

/**
 * Add a meal item to a day
 */
export async function addPlanItem(planId, dayId, { meal_type, meal_id, custom_name, custom_description, servings, notes }) {
  const response = await api.post(`${BASE}/plans/${planId}/days/${dayId}/items/`, {
    meal_type,
    meal_id,
    custom_name,
    custom_description,
    servings,
    notes
  }, { skipUserId: true })
  return response?.data
}

/**
 * Update a meal item
 */
export async function updatePlanItem(planId, dayId, itemId, updates) {
  const response = await api.put(`${BASE}/plans/${planId}/days/${dayId}/items/${itemId}/`, updates, { skipUserId: true })
  return response?.data
}

/**
 * Delete a meal item
 */
export async function deletePlanItem(planId, dayId, itemId) {
  const response = await api.delete(`${BASE}/plans/${planId}/days/${dayId}/items/${itemId}/`, { skipUserId: true })
  return response?.data
}

// ============================================================================
// AI Generation (Async)
// ============================================================================

/**
 * Start async AI meal generation for a plan
 * Returns a job_id to poll for results
 * @param {number} planId - The plan ID
 * @param {Object} options
 * @param {string} options.mode - 'full_week' | 'fill_empty' | 'single_slot'
 * @param {string} options.day - Day name for single slot (e.g., 'Monday')
 * @param {string} options.meal_type - Meal type for single slot (e.g., 'Dinner')
 * @param {string} options.prompt - Optional custom prompt/preferences
 */
export async function startMealGeneration(planId, { mode = 'full_week', day, meal_type, prompt } = {}) {
  const response = await api.post(`${BASE}/plans/${planId}/generate/`, {
    mode,
    day,
    meal_type,
    prompt
  }, { skipUserId: true })
  return response?.data
}

/**
 * Check the status of an AI generation job
 * @param {number} jobId - The generation job ID
 */
export async function getGenerationJobStatus(jobId) {
  const response = await api.get(`${BASE}/generation-jobs/${jobId}/`, { skipUserId: true })
  return response?.data
}

/**
 * List all generation jobs for a plan
 * @param {number} planId - The plan ID
 */
export async function listGenerationJobs(planId) {
  const response = await api.get(`${BASE}/plans/${planId}/generation-jobs/`, { skipUserId: true })
  return response?.data
}

/**
 * Poll for generation job completion
 * @param {number} jobId - The job ID to poll
 * @param {Object} options
 * @param {number} options.interval - Polling interval in ms (default 2000)
 * @param {number} options.maxAttempts - Max poll attempts (default 30)
 * @param {function} options.onProgress - Callback for status updates
 * @returns {Promise} - Resolves with job data when complete, rejects on failure/timeout
 */
export async function pollGenerationJob(jobId, { interval = 2000, maxAttempts = 30, onProgress } = {}) {
  let attempts = 0
  
  return new Promise((resolve, reject) => {
    const poll = async () => {
      attempts++
      
      try {
        const data = await getGenerationJobStatus(jobId)
        
        if (onProgress) {
          onProgress(data)
        }
        
        if (data.status === 'completed') {
          resolve(data)
        } else if (data.status === 'failed') {
          reject(new Error(data.error_message || 'Generation failed'))
        } else if (attempts >= maxAttempts) {
          reject(new Error('Generation timed out. Please check back later.'))
        } else {
          // Still pending/processing, poll again
          setTimeout(poll, interval)
        }
      } catch (err) {
        reject(err)
      }
    }
    
    poll()
  })
}

// Legacy alias for backwards compatibility
export async function generateMealSuggestions(planId, options = {}) {
  return startMealGeneration(planId, options)
}

/**
 * Accept an AI-generated suggestion
 */
export async function acceptSuggestion(planId, suggestionId) {
  const response = await api.post(`${BASE}/plans/${planId}/suggestions/${suggestionId}/accept/`, {}, { skipUserId: true })
  return response?.data
}

/**
 * Reject an AI-generated suggestion
 */
export async function rejectSuggestion(planId, suggestionId) {
  const response = await api.post(`${BASE}/plans/${planId}/suggestions/${suggestionId}/reject/`, {}, { skipUserId: true })
  return response?.data
}

// ============================================================================
// Chef's Dishes & Meals (for quick add)
// ============================================================================

/**
 * Get chef's saved meals
 * @param {Object} options
 * @param {string} options.meal_type - Filter by meal type
 * @param {string} options.search - Search by name
 * @param {number} options.limit - Max results
 * @param {boolean} options.composed_only - Only return composed meals (2+ dishes)
 * @param {boolean} options.include_dishes - Include dish breakdown in response
 */
export async function getChefDishes({ meal_type, search, limit = 50, composed_only = false, include_dishes = false } = {}) {
  const params = { limit }
  if (meal_type) params.meal_type = meal_type
  if (search) params.search = search
  if (composed_only) params.composed_only = 'true'
  if (include_dishes) params.include_dishes = 'true'
  
  const response = await api.get(`${BASE}/dishes/`, { params, skipUserId: true })
  return response?.data
}

/**
 * Get chef's composed meals (meals with multiple dishes)
 * Convenience wrapper for getChefDishes with composed_only=true
 */
export async function getChefComposedMeals({ meal_type, search, limit = 50 } = {}) {
  return getChefDishes({ meal_type, search, limit, composed_only: true, include_dishes: true })
}

// ============================================================================
// Customer Suggestions
// ============================================================================

/**
 * Get customer suggestions for a plan
 */
export async function getPlanSuggestions(planId, { status } = {}) {
  const params = {}
  if (status) params.status = status
  
  const response = await api.get(`${BASE}/plans/${planId}/suggestions/`, { params, skipUserId: true })
  return response?.data
}

/**
 * Respond to a customer suggestion
 */
export async function respondToSuggestion(suggestionId, { action, response }) {
  const resp = await api.post(`${BASE}/suggestions/${suggestionId}/respond/`, {
    action,
    response
  }, { skipUserId: true })
  return resp?.data
}

