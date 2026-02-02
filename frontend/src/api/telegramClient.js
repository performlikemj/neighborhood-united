/**
 * Telegram Integration API Client
 *
 * Provides functions for managing Telegram account linking
 * and notification settings for chefs.
 */

import { api } from '../api'

const TELEGRAM_BASE = '/chefs/api/telegram'

/**
 * Get the chef's Telegram link status and settings.
 *
 * @returns {Promise<Object>} Status object with linked state and settings
 * 
 * Response when linked:
 * {
 *   linked: true,
 *   telegram_username: "username",
 *   telegram_first_name: "Name",
 *   linked_at: "2024-01-01T12:00:00Z",
 *   settings: {
 *     notify_new_orders: true,
 *     notify_order_updates: true,
 *     notify_schedule_reminders: true,
 *     notify_customer_messages: false,
 *     quiet_hours_start: "22:00",
 *     quiet_hours_end: "08:00",
 *     quiet_hours_enabled: true
 *   }
 * }
 * 
 * Response when not linked:
 * { linked: false }
 */
export async function getTelegramStatus() {
  const response = await api.get(`${TELEGRAM_BASE}/status/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Generate a one-time link token for connecting Telegram.
 *
 * @returns {Promise<Object>} Link data with QR code and deep link
 * {
 *   deep_link: "https://t.me/SautaiChefBot?start=TOKEN",
 *   qr_code: "data:image/png;base64,...",
 *   expires_at: "2024-01-01T12:00:00Z"
 * }
 */
export async function generateTelegramLink() {
  const response = await api.post(`${TELEGRAM_BASE}/generate-link/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Unlink the chef's Telegram account.
 *
 * @returns {Promise<Object>} { success: true }
 */
export async function unlinkTelegram() {
  const response = await api.post(`${TELEGRAM_BASE}/unlink/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update Telegram notification settings.
 *
 * @param {Object} settings - Settings to update (all optional)
 * @param {boolean} [settings.notify_new_orders] - Notify on new orders
 * @param {boolean} [settings.notify_order_updates] - Notify on order updates
 * @param {boolean} [settings.notify_schedule_reminders] - Notify on schedule reminders
 * @param {boolean} [settings.notify_customer_messages] - Notify on customer messages
 * @param {string} [settings.quiet_hours_start] - Quiet hours start time (HH:MM)
 * @param {string} [settings.quiet_hours_end] - Quiet hours end time (HH:MM)
 * @param {boolean} [settings.quiet_hours_enabled] - Enable quiet hours
 * @returns {Promise<Object>} { settings: {...} }
 */
export async function updateTelegramSettings(settings) {
  const response = await api.patch(`${TELEGRAM_BASE}/settings/`, settings, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export default {
  getTelegramStatus,
  generateTelegramLink,
  unlinkTelegram,
  updateTelegramSettings,
}
