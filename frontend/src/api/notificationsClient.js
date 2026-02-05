/**
 * Notifications API Client
 *
 * Provides functions for managing chef notifications
 * from the Sous Chef proactive engine.
 */

import { api } from '../api'

const NOTIFICATIONS_BASE = '/chefs/api/me/notifications'

/**
 * List notifications for the chef.
 *
 * @param {Object} [options] - Query options
 * @param {string} [options.status] - Filter by status: pending, sent, read, dismissed
 * @param {string} [options.type] - Filter by notification type
 * @param {number} [options.limit] - Max results (default 50, max 100)
 * @param {number} [options.offset] - Pagination offset
 * @param {boolean} [options.unreadOnly] - Only show unread notifications
 * @returns {Promise<Object>} List of notifications with total count
 */
export async function getNotifications({
  status,
  type,
  limit,
  offset,
  unreadOnly
} = {}) {
  const params = {}
  if (status) params.status = status
  if (type) params.type = type
  if (limit) params.limit = limit
  if (offset) params.offset = offset
  if (unreadOnly) params.unread_only = 'true'

  const response = await api.get(`${NOTIFICATIONS_BASE}/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get count of unread notifications.
 * Useful for badge display.
 *
 * @returns {Promise<Object>} Unread count
 */
export async function getUnreadCount() {
  const response = await api.get(`${NOTIFICATIONS_BASE}/unread-count/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get details of a specific notification.
 *
 * @param {number} notificationId - The notification ID
 * @returns {Promise<Object>} Notification details
 */
export async function getNotification(notificationId) {
  const response = await api.get(`${NOTIFICATIONS_BASE}/${notificationId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark a notification as read.
 *
 * @param {number} notificationId - The notification ID
 * @returns {Promise<Object>} Updated notification
 */
export async function markAsRead(notificationId) {
  const response = await api.post(`${NOTIFICATIONS_BASE}/${notificationId}/read/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Dismiss a notification.
 *
 * @param {number} notificationId - The notification ID
 * @returns {Promise<Object>} Updated notification
 */
export async function dismissNotification(notificationId) {
  const response = await api.post(`${NOTIFICATIONS_BASE}/${notificationId}/dismiss/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Delete a notification permanently.
 *
 * @param {number} notificationId - The notification ID
 * @returns {Promise<Object>} Deleted notification ID
 */
export async function deleteNotification(notificationId) {
  const response = await api.delete(`${NOTIFICATIONS_BASE}/${notificationId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Mark all unread notifications as read.
 *
 * @returns {Promise<Object>} Count of marked notifications
 */
export async function markAllAsRead() {
  const response = await api.post(`${NOTIFICATIONS_BASE}/mark-all-read/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Dismiss all notifications.
 *
 * @returns {Promise<Object>} Count of dismissed notifications
 */
export async function dismissAll() {
  const response = await api.post(`${NOTIFICATIONS_BASE}/dismiss-all/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export default {
  getNotifications,
  getUnreadCount,
  getNotification,
  markAsRead,
  dismissNotification,
  deleteNotification,
  markAllAsRead,
  dismissAll,
}
