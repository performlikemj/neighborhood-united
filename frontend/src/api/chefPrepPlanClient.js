/**
 * Chef Prep Plan API Client
 * 
 * Provides functions for chef resource planning including:
 * - Prep plan CRUD operations
 * - Shopping list management
 * - Batch cooking suggestions
 * - Shelf life lookups
 */

import { api } from '../api'

const PREP_BASE = '/chefs/api/me'

// =============================================================================
// Prep Plan CRUD
// =============================================================================

/**
 * Get list of prep plans.
 * @param {Object} params - Query parameters
 * @param {string} params.status - Filter by status (draft, generated, in_progress, completed)
 */
export async function getPrepPlans({ status } = {}) {
  const params = {}
  if (status) params.status = status
  
  const response = await api.get(`${PREP_BASE}/prep-plans/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get details of a specific prep plan.
 * @param {number} planId - The prep plan ID
 */
export async function getPrepPlanDetail(planId) {
  const response = await api.get(`${PREP_BASE}/prep-plans/${planId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Create a new prep plan.
 * @param {Object} params - Plan parameters
 * @param {string} params.start_date - Start date (YYYY-MM-DD)
 * @param {string} params.end_date - End date (YYYY-MM-DD)
 * @param {string} params.notes - Optional notes
 */
export async function createPrepPlan({ start_date, end_date, notes = '' }) {
  const response = await api.post(`${PREP_BASE}/prep-plans/`, {
    start_date,
    end_date,
    notes
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update a prep plan (notes, status).
 * @param {number} planId - The prep plan ID
 * @param {Object} updates - Fields to update
 * @param {string} updates.notes - New notes
 * @param {string} updates.status - New status
 */
export async function updatePrepPlan(planId, updates) {
  const response = await api.patch(`${PREP_BASE}/prep-plans/${planId}/`, updates, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Delete a prep plan.
 * @param {number} planId - The prep plan ID
 */
export async function deletePrepPlan(planId) {
  await api.delete(`${PREP_BASE}/prep-plans/${planId}/`, {
    skipUserId: true,
    withCredentials: true
  })
}

/**
 * Regenerate a prep plan with fresh data.
 * @param {number} planId - The prep plan ID
 */
export async function regeneratePrepPlan(planId) {
  const response = await api.post(`${PREP_BASE}/prep-plans/${planId}/regenerate/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Quick generate a prep plan for the next N days.
 * @param {Object} params - Generation parameters
 * @param {number} params.days - Number of days to plan (1-30, default 7)
 * @param {string} params.notes - Optional notes
 */
export async function quickGeneratePrepPlan({ days = 7, notes = '' } = {}) {
  const response = await api.post(`${PREP_BASE}/prep-plans/quick-generate/`, {
    days,
    notes
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Shopping List
// =============================================================================

/**
 * Get shopping list for a prep plan.
 * @param {number} planId - The prep plan ID
 * @param {string} groupBy - How to group items: 'date' or 'category'
 */
export async function getShoppingList(planId, groupBy = 'date') {
  const response = await api.get(`${PREP_BASE}/prep-plans/${planId}/shopping-list/`, {
    params: { group_by: groupBy },
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark shopping list items as purchased.
 * @param {number} planId - The prep plan ID
 * @param {number[]} itemIds - Array of item IDs to mark
 * @param {string} purchasedDate - Optional purchase date (YYYY-MM-DD)
 */
export async function markItemsPurchased(planId, itemIds, purchasedDate = null) {
  const payload = { item_ids: itemIds }
  if (purchasedDate) payload.purchased_date = purchasedDate
  
  const response = await api.post(`${PREP_BASE}/prep-plans/${planId}/mark-purchased/`, payload, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Unmark shopping list items as purchased.
 * @param {number} planId - The prep plan ID
 * @param {number[]} itemIds - Array of item IDs to unmark
 */
export async function unmarkItemsPurchased(planId, itemIds) {
  const response = await api.post(`${PREP_BASE}/prep-plans/${planId}/unmark-purchased/`, {
    item_ids: itemIds
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Batch Suggestions
// =============================================================================

/**
 * Get batch cooking suggestions for a prep plan.
 * @param {number} planId - The prep plan ID
 */
export async function getBatchSuggestions(planId) {
  const response = await api.get(`${PREP_BASE}/prep-plans/${planId}/batch-suggestions/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Summary & Utilities
// =============================================================================

/**
 * Get prep planning summary for the chef.
 * Returns active plans count, items needing purchase today, etc.
 */
export async function getPrepPlanSummary() {
  const response = await api.get(`${PREP_BASE}/prep-plans/summary/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Look up shelf life for ingredients.
 * @param {string[]} ingredients - Array of ingredient names
 * @param {string} storagePreference - Optional storage preference hint
 */
export async function lookupShelfLife(ingredients, storagePreference = null) {
  const payload = { ingredients }
  if (storagePreference) payload.storage_preference = storagePreference
  
  const response = await api.post(`${PREP_BASE}/ingredients/shelf-life/`, payload, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}






