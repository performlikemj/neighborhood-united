/**
 * Proactive Settings API Client
 *
 * Provides functions for managing chef notification preferences
 * for the proactive engine (birthdays, follow-ups, etc).
 */

import { api } from '../api'

const PROACTIVE_BASE = '/chefs/api/me/proactive'

/**
 * Get the chef's proactive notification settings.
 *
 * @returns {Promise<Object>} Proactive settings
 */
export async function getProactiveSettings() {
  const response = await api.get(`${PROACTIVE_BASE}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update proactive notification settings.
 *
 * @param {Object} updates - Settings to update
 * @param {boolean} [updates.enabled] - Master switch
 * @param {boolean} [updates.notify_birthdays] - Notify about birthdays
 * @param {boolean} [updates.notify_anniversaries] - Notify about anniversaries
 * @param {boolean} [updates.notify_followups] - Notify about inactive clients
 * @param {boolean} [updates.notify_todos] - Notify about to-do items
 * @param {boolean} [updates.notify_seasonal] - Notify about seasonal ingredients
 * @param {boolean} [updates.notify_milestones] - Notify about client milestones
 * @param {number} [updates.birthday_lead_days] - Days before birthday to notify
 * @param {number} [updates.anniversary_lead_days] - Days before anniversary to notify
 * @param {number} [updates.followup_threshold_days] - Days of inactivity for follow-up
 * @param {string} [updates.notification_frequency] - realtime, daily, or weekly
 * @param {boolean} [updates.channel_in_app] - Show in-app notifications
 * @param {boolean} [updates.channel_email] - Send email notifications
 * @param {boolean} [updates.channel_push] - Send push notifications
 * @param {boolean} [updates.quiet_hours_enabled] - Enable quiet hours
 * @param {string} [updates.quiet_hours_start] - Quiet hours start (HH:MM)
 * @param {string} [updates.quiet_hours_end] - Quiet hours end (HH:MM)
 * @param {string} [updates.quiet_hours_timezone] - Timezone for quiet hours
 * @returns {Promise<Object>} Updated settings
 */
export async function updateProactiveSettings(updates) {
  const response = await api.patch(`${PROACTIVE_BASE}/update/`, updates, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Quick disable - turn off the master switch.
 *
 * @returns {Promise<Object>} Updated settings
 */
export async function disableProactive() {
  const response = await api.post(`${PROACTIVE_BASE}/disable/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Quick enable - turn on the master switch.
 *
 * @returns {Promise<Object>} Updated settings
 */
export async function enableProactive() {
  const response = await api.post(`${PROACTIVE_BASE}/enable/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export default {
  getProactiveSettings,
  updateProactiveSettings,
  disableProactive,
  enableProactive,
}
