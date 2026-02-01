/**
 * React hooks for Sous Chef Notifications.
 *
 * Uses @tanstack/react-query for caching and state management.
 * Provides hooks for listing, reading, and dismissing notifications.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getNotifications,
  getUnreadCount,
  markAsRead,
  dismissNotification,
  deleteNotification,
  markAllAsRead,
  dismissAll,
} from '../api/notificationsClient'

// Query key factory
const notificationKeys = {
  all: ['chef-notifications'],
  lists: () => [...notificationKeys.all, 'list'],
  list: (filters) => [...notificationKeys.lists(), filters],
  unreadCount: () => [...notificationKeys.all, 'unread-count'],
  detail: (id) => [...notificationKeys.all, 'detail', id],
}

/**
 * Hook to fetch notifications.
 *
 * @param {Object} options
 * @param {string} [options.status] - Filter by status
 * @param {string} [options.type] - Filter by notification type
 * @param {number} [options.limit] - Max results
 * @param {number} [options.offset] - Pagination offset
 * @param {boolean} [options.unreadOnly] - Only unread notifications
 * @param {boolean} [options.enabled] - Enable/disable query
 * @returns Query result with notifications list
 */
export function useNotifications({
  status,
  type,
  limit = 50,
  offset = 0,
  unreadOnly = false,
  enabled = true
} = {}) {
  const filters = { status, type, limit, offset, unreadOnly }

  return useQuery({
    queryKey: notificationKeys.list(filters),
    queryFn: () => getNotifications(filters),
    enabled,
    staleTime: 30 * 1000, // 30 seconds - notifications change frequently
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch only unread notifications.
 */
export function useUnreadNotifications({ limit = 50, enabled = true } = {}) {
  return useNotifications({ unreadOnly: true, limit, enabled })
}

/**
 * Hook to fetch the unread notification count.
 * Useful for badge display.
 */
export function useUnreadCount({ enabled = true } = {}) {
  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: async () => {
      const result = await getUnreadCount()
      return result?.unread_count || 0
    },
    enabled,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 30 * 1000, // Poll every 30 seconds
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to mark a notification as read.
 */
export function useMarkAsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationId) => markAsRead(notificationId),
    onMutate: async (notificationId) => {
      // Optimistically update any notification lists
      await queryClient.cancelQueries({ queryKey: notificationKeys.lists() })

      // Update unread count optimistically
      const previousCount = queryClient.getQueryData(notificationKeys.unreadCount())
      if (typeof previousCount === 'number' && previousCount > 0) {
        queryClient.setQueryData(notificationKeys.unreadCount(), previousCount - 1)
      }

      return { previousCount }
    },
    onError: (err, variables, context) => {
      if (context?.previousCount !== undefined) {
        queryClient.setQueryData(notificationKeys.unreadCount(), context.previousCount)
      }
    },
    onSettled: () => {
      // Refetch notification lists to ensure consistency
      queryClient.invalidateQueries({ queryKey: notificationKeys.lists() })
    },
  })
}

/**
 * Hook to dismiss a notification.
 */
export function useDismissNotification() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationId) => dismissNotification(notificationId),
    onMutate: async (notificationId) => {
      await queryClient.cancelQueries({ queryKey: notificationKeys.lists() })

      // Update unread count optimistically
      const previousCount = queryClient.getQueryData(notificationKeys.unreadCount())
      if (typeof previousCount === 'number' && previousCount > 0) {
        queryClient.setQueryData(notificationKeys.unreadCount(), previousCount - 1)
      }

      return { previousCount }
    },
    onError: (err, variables, context) => {
      if (context?.previousCount !== undefined) {
        queryClient.setQueryData(notificationKeys.unreadCount(), context.previousCount)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.lists() })
    },
  })
}

/**
 * Hook to delete a notification.
 */
export function useDeleteNotification() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationId) => deleteNotification(notificationId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

/**
 * Hook to mark all notifications as read.
 */
export function useMarkAllAsRead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: markAllAsRead,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: notificationKeys.all })

      // Reset unread count optimistically
      queryClient.setQueryData(notificationKeys.unreadCount(), 0)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

/**
 * Hook to dismiss all notifications.
 */
export function useDismissAll() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: dismissAll,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: notificationKeys.all })
      queryClient.setQueryData(notificationKeys.unreadCount(), 0)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

/**
 * Hook that returns a function to invalidate notification cache.
 */
export function useInvalidateNotifications() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: notificationKeys.all })
  }
}

/**
 * Convenience hook that combines notifications with common actions.
 */
export function useNotificationManager({ limit = 50, enabled = true } = {}) {
  const notificationsQuery = useNotifications({ unreadOnly: true, limit, enabled })
  const countQuery = useUnreadCount({ enabled })
  const markReadMutation = useMarkAsRead()
  const dismissMutation = useDismissNotification()
  const markAllReadMutation = useMarkAllAsRead()

  return {
    // Queries
    notifications: notificationsQuery.data?.notifications || [],
    total: notificationsQuery.data?.total || 0,
    unreadCount: countQuery.data || 0,
    isLoading: notificationsQuery.isLoading || countQuery.isLoading,
    error: notificationsQuery.error || countQuery.error,

    // Actions
    markAsRead: markReadMutation.mutate,
    dismiss: dismissMutation.mutate,
    markAllAsRead: markAllReadMutation.mutate,

    // Action states
    isMarkingRead: markReadMutation.isPending,
    isDismissing: dismissMutation.isPending,
    isMarkingAllRead: markAllReadMutation.isPending,

    // Refetch
    refetch: () => {
      notificationsQuery.refetch()
      countQuery.refetch()
    },
  }
}

export default {
  useNotifications,
  useUnreadNotifications,
  useUnreadCount,
  useMarkAsRead,
  useDismissNotification,
  useDeleteNotification,
  useMarkAllAsRead,
  useDismissAll,
  useInvalidateNotifications,
  useNotificationManager,
}
