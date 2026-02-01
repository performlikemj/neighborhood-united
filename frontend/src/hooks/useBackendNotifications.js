/**
 * useBackendNotifications
 * 
 * Polls the backend for proactive notifications (birthdays, followups, etc.)
 * and merges them into the SousChefNotificationContext.
 */

import { useEffect, useRef, useCallback } from 'react'
import { useSousChefNotifications } from '../contexts/SousChefNotificationContext.jsx'

const POLL_INTERVAL_MS = 30000 // 30 seconds
const API_BASE = '/chefs/api/me/notifications/'

// Map backend notification types to frontend display
const NOTIFICATION_ICONS = {
  birthday: '🎂',
  anniversary: '💍',
  followup: '👋',
  todo: '📝',
  seasonal: '🌱',
  milestone: '🎉',
  tip: '💡',
  welcome: '🍳',
  system: '🔔',
}

export function useBackendNotifications({ enabled = true } = {}) {
  const notifications = useSousChefNotifications()
  const seenIdsRef = useRef(new Set())
  const pollIntervalRef = useRef(null)

  const fetchNotifications = useCallback(async () => {
    if (!notifications) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await fetch(`${API_BASE}?unread_only=true&limit=20`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) return

      const data = await response.json()
      
      if (data.status !== 'success' || !data.notifications) return

      // Process each notification we haven't seen
      for (const notif of data.notifications) {
        const backendId = `backend-${notif.id}`
        
        if (seenIdsRef.current.has(backendId)) continue
        seenIdsRef.current.add(backendId)

        // Transform backend notification to frontend format
        const icon = NOTIFICATION_ICONS[notif.type] || '🔔'
        
        notifications.addNotification({
          id: backendId,
          backendId: notif.id, // Keep reference for marking read
          source: 'backend',
          type: notif.type,
          title: `${icon} ${notif.title}`,
          message: notif.message,
          context: {
            topic: `proactive_${notif.type}`,
            clientName: notif.client_name,
            clientId: notif.client_id,
            clientType: notif.client_type,
            actionContext: notif.action_context,
          },
          actionLabel: notif.client_id ? 'View Client' : null,
          createdAt: notif.created_at,
        })
      }
    } catch (err) {
      console.error('Error fetching backend notifications:', err)
    }
  }, [notifications])

  // Mark notification as read on backend
  const markReadOnBackend = useCallback(async (backendId) => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      await fetch(`${API_BASE}${backendId}/read/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
    } catch (err) {
      console.error('Error marking notification read:', err)
    }
  }, [])

  // Start/stop polling based on enabled state
  useEffect(() => {
    if (!enabled) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
      return
    }

    // Initial fetch
    fetchNotifications()

    // Set up polling
    pollIntervalRef.current = setInterval(fetchNotifications, POLL_INTERVAL_MS)

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [enabled, fetchNotifications])

  return {
    fetchNotifications,
    markReadOnBackend,
  }
}

export default useBackendNotifications
