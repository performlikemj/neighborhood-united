/**
 * Onboarding API Client
 *
 * Provides functions for managing chef onboarding state
 * including welcome flow, setup wizard, and milestone tracking.
 */

import { api } from '../api'

const ONBOARDING_BASE = '/chefs/api/me/onboarding'

/**
 * Get the chef's onboarding state.
 * Auto-creates if it doesn't exist.
 *
 * @returns {Promise<Object>} Onboarding state
 */
export async function getOnboardingState() {
  const response = await api.get(`${ONBOARDING_BASE}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark that the chef has seen the welcome modal.
 *
 * @returns {Promise<Object>} Updated onboarding state
 */
export async function markWelcomed() {
  const response = await api.post(`${ONBOARDING_BASE}/welcomed/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark that the chef has started the setup wizard.
 *
 * @returns {Promise<Object>} Updated onboarding state
 */
export async function startSetup() {
  const response = await api.post(`${ONBOARDING_BASE}/start/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark that the chef has completed the setup wizard.
 *
 * @param {string} [personalityChoice] - Optional final personality selection
 * @returns {Promise<Object>} Updated onboarding state
 */
export async function completeSetup(personalityChoice = null) {
  const body = personalityChoice ? { personality_choice: personalityChoice } : {}
  const response = await api.post(`${ONBOARDING_BASE}/complete/`, body, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark that the chef has skipped the setup wizard.
 *
 * @returns {Promise<Object>} Updated onboarding state
 */
export async function skipSetup() {
  const response = await api.post(`${ONBOARDING_BASE}/skip/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Record a milestone achievement.
 *
 * @param {string} milestone - Milestone name:
 *   first_dish, first_client, first_conversation,
 *   first_memory, first_order, proactive_enabled
 * @returns {Promise<Object>} Result with newly_recorded flag
 */
export async function recordMilestone(milestone) {
  const response = await api.post(`${ONBOARDING_BASE}/milestone/`, { milestone }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Record that a tip was shown.
 *
 * @param {string} tipId - The tip ID
 * @returns {Promise<Object>} Updated tips_shown list
 */
export async function showTip(tipId) {
  const response = await api.post(`${ONBOARDING_BASE}/tip/show/`, { tip_id: tipId }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Permanently dismiss a tip.
 *
 * @param {string} tipId - The tip ID
 * @returns {Promise<Object>} Updated tips_dismissed list
 */
export async function dismissTip(tipId) {
  const response = await api.post(`${ONBOARDING_BASE}/tip/dismiss/`, { tip_id: tipId }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Set the chef's communication style preference.
 * Updates both onboarding state and workspace soul_prompt.
 *
 * @param {string} personality - Personality choice: professional, friendly, or efficient
 * @returns {Promise<Object>} Updated onboarding state
 */
export async function setPersonality(personality) {
  const response = await api.post(`${ONBOARDING_BASE}/personality/`, { personality }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export default {
  getOnboardingState,
  markWelcomed,
  startSetup,
  completeSetup,
  skipSetup,
  recordMilestone,
  showTip,
  dismissTip,
  setPersonality,
}
