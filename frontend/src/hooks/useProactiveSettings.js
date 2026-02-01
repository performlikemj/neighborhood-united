/**
 * React hooks for Sous Chef Proactive Settings.
 *
 * Uses @tanstack/react-query for caching and state management.
 * Provides hooks for managing notification preferences.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getProactiveSettings,
  updateProactiveSettings,
  disableProactive,
  enableProactive,
} from '../api/proactiveClient'

// Query key factory
const proactiveKeys = {
  all: ['chef-proactive'],
  detail: () => [...proactiveKeys.all, 'detail'],
}

/**
 * Hook to fetch the chef's proactive notification settings.
 *
 * @param {{ enabled?: boolean }} options
 * @returns Query result with proactive settings
 */
export function useProactiveSettings({ enabled = true } = {}) {
  return useQuery({
    queryKey: proactiveKeys.detail(),
    queryFn: async () => {
      const result = await getProactiveSettings()
      return result?.settings || result
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  })
}

/**
 * Hook to update proactive notification settings.
 *
 * @returns Mutation with mutate(updates) function
 */
export function useUpdateProactiveSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateProactiveSettings,
    onMutate: async (updates) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: proactiveKeys.detail() })

      // Snapshot previous value
      const previous = queryClient.getQueryData(proactiveKeys.detail())

      // Optimistically update
      queryClient.setQueryData(proactiveKeys.detail(), (old) => {
        if (!old) return old
        return { ...old, ...updates }
      })

      return { previous }
    },
    onError: (err, updates, context) => {
      // Roll back on error
      if (context?.previous) {
        queryClient.setQueryData(proactiveKeys.detail(), context.previous)
      }
    },
    onSuccess: (data) => {
      // Ensure we have the server's response
      queryClient.setQueryData(proactiveKeys.detail(), data?.settings)
    },
  })
}

/**
 * Hook to quickly disable proactive notifications.
 */
export function useDisableProactive() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: disableProactive,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: proactiveKeys.detail() })
      const previous = queryClient.getQueryData(proactiveKeys.detail())

      queryClient.setQueryData(proactiveKeys.detail(), (old) => {
        if (!old) return old
        return { ...old, enabled: false }
      })

      return { previous }
    },
    onError: (err, variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(proactiveKeys.detail(), context.previous)
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(proactiveKeys.detail(), data?.settings)
    },
  })
}

/**
 * Hook to quickly enable proactive notifications.
 */
export function useEnableProactive() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: enableProactive,
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: proactiveKeys.detail() })
      const previous = queryClient.getQueryData(proactiveKeys.detail())

      queryClient.setQueryData(proactiveKeys.detail(), (old) => {
        if (!old) return old
        return { ...old, enabled: true }
      })

      return { previous }
    },
    onError: (err, variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(proactiveKeys.detail(), context.previous)
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(proactiveKeys.detail(), data?.settings)
      // Also invalidate onboarding to update proactive_enabled milestone
      queryClient.invalidateQueries({ queryKey: ['chef-onboarding'] })
    },
  })
}

/**
 * Hook that returns a function to invalidate proactive settings cache.
 */
export function useInvalidateProactiveSettings() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: proactiveKeys.all })
  }
}

/**
 * Helper hook that provides computed properties for proactive settings.
 */
export function useProactiveStatus({ enabled = true } = {}) {
  const query = useProactiveSettings({ enabled })

  const settings = query.data || {}

  return {
    ...query,
    // Computed helpers
    isEnabled: settings.enabled || false,
    hasAnyNotificationEnabled: Boolean(
      settings.notify_birthdays ||
      settings.notify_anniversaries ||
      settings.notify_followups ||
      settings.notify_todos ||
      settings.notify_seasonal ||
      settings.notify_milestones
    ),
    hasAnyChannelEnabled: Boolean(
      settings.channel_in_app ||
      settings.channel_email ||
      settings.channel_push
    ),
    isInQuietHours: false, // Would need real-time check
    frequency: settings.notification_frequency || 'daily',
  }
}

export default {
  useProactiveSettings,
  useProactiveStatus,
  useUpdateProactiveSettings,
  useDisableProactive,
  useEnableProactive,
  useInvalidateProactiveSettings,
}
