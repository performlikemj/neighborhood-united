/**
 * Workspace API Client
 *
 * Provides functions for managing Sous Chef workspace settings
 * including personality (soul_prompt) and business rules.
 */

import { api } from '../api'

const WORKSPACE_BASE = '/chefs/api/me/workspace'

/**
 * Get the chef's workspace settings.
 * Auto-creates with defaults if workspace doesn't exist.
 *
 * @returns {Promise<Object>} Workspace settings
 */
export async function getWorkspace() {
  const response = await api.get(`${WORKSPACE_BASE}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update workspace settings.
 * Only provided fields are updated.
 *
 * @param {Object} updates - Fields to update
 * @param {string} [updates.soul_prompt] - Personality/tone prompt
 * @param {string} [updates.business_rules] - Business constraints
 * @param {string[]} [updates.enabled_tools] - List of enabled tool names
 * @param {boolean} [updates.include_analytics] - Include analytics in context
 * @param {boolean} [updates.include_seasonal] - Include seasonal suggestions
 * @param {boolean} [updates.auto_memory_save] - Auto-save important insights
 * @returns {Promise<Object>} Updated workspace with updated_fields list
 */
export async function updateWorkspace(updates) {
  const response = await api.patch(`${WORKSPACE_BASE}/update/`, updates, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Reset workspace fields to their defaults.
 *
 * @param {string[]} [fields] - Specific fields to reset.
 *   If not provided, resets soul_prompt and business_rules only.
 * @returns {Promise<Object>} Reset workspace with reset_fields list
 */
export async function resetWorkspace(fields = null) {
  const body = fields ? { fields } : {}
  const response = await api.post(`${WORKSPACE_BASE}/reset/`, body, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export default {
  getWorkspace,
  updateWorkspace,
  resetWorkspace,
}
