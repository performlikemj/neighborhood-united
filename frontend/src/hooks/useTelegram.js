/**
 * React hooks for Telegram integration.
 *
 * Uses @tanstack/react-query for caching and state management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getTelegramStatus,
  generateTelegramLink,
  unlinkTelegram,
  updateTelegramSettings,
} from '../api/telegramClient'

// Query key factory
const telegramKeys = {
  all: ['telegram'],
  status: () => [...telegramKeys.all, 'status'],
}

/**
 * Hook to fetch the chef's Telegram link status and settings.
 *
 * @param {{ enabled?: boolean }} options
 * @returns Query result with status data
 */
export function useTelegramStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: telegramKeys.status(),
    queryFn: getTelegramStatus,
    enabled,
    staleTime: 30 * 1000, // 30 seconds - check for link status changes
    refetchOnWindowFocus: true, // Re-check when user returns to tab (might have linked via phone)
  })
}

/**
 * Hook to generate a Telegram link token.
 *
 * @returns Mutation with mutate() function
 */
export function useGenerateTelegramLink() {
  return useMutation({
    mutationFn: generateTelegramLink,
    onError: (error) => {
      console.error('Failed to generate Telegram link:', error)
    },
  })
}

/**
 * Hook to unlink Telegram account.
 *
 * @returns Mutation with mutate() function
 */
export function useUnlinkTelegram() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: unlinkTelegram,
    onSuccess: () => {
      // Update cache to show unlinked state
      queryClient.setQueryData(telegramKeys.status(), { linked: false })
    },
    onError: (error) => {
      console.error('Failed to unlink Telegram:', error)
    },
  })
}

/**
 * Hook to update Telegram notification settings.
 *
 * @returns Mutation with mutate(settings) function
 */
export function useUpdateTelegramSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateTelegramSettings,
    onSuccess: (data) => {
      // Update cached status with new settings
      queryClient.setQueryData(telegramKeys.status(), (oldData) => {
        if (!oldData?.linked) return oldData
        return {
          ...oldData,
          settings: data.settings,
        }
      })
    },
    onError: (error) => {
      console.error('Failed to update Telegram settings:', error)
    },
  })
}

/**
 * Hook that returns a function to invalidate Telegram status cache.
 */
export function useInvalidateTelegramStatus() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: telegramKeys.all })
  }
}

export default {
  useTelegramStatus,
  useGenerateTelegramLink,
  useUnlinkTelegram,
  useUpdateTelegramSettings,
  useInvalidateTelegramStatus,
}
