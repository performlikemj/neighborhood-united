/**
 * React hooks for Sous Chef Onboarding.
 *
 * Uses @tanstack/react-query for caching and state management.
 * Provides hooks for tracking onboarding state, milestones, and tips.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getOnboardingState,
  markWelcomed,
  startSetup,
  completeSetup,
  skipSetup,
  recordMilestone,
  showTip,
  dismissTip,
  setPersonality,
} from '../api/onboardingClient'

// Query key factory
const onboardingKeys = {
  all: ['chef-onboarding'],
  detail: () => [...onboardingKeys.all, 'detail'],
}

/**
 * Hook to fetch the chef's onboarding state.
 *
 * @param {{ enabled?: boolean }} options
 * @returns Query result with onboarding data
 */
export function useOnboarding({ enabled = true } = {}) {
  return useQuery({
    queryKey: onboardingKeys.detail(),
    queryFn: async () => {
      const result = await getOnboardingState()
      return result?.onboarding || result
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  })
}

/**
 * Hook to mark the chef as welcomed (seen welcome modal).
 */
export function useMarkWelcomed() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: markWelcomed,
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
    },
  })
}

/**
 * Hook to start the setup wizard.
 */
export function useStartSetup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: startSetup,
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
    },
  })
}

/**
 * Hook to complete the setup wizard.
 */
export function useCompleteSetup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (personalityChoice) => completeSetup(personalityChoice),
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
    },
  })
}

/**
 * Hook to skip the setup wizard.
 */
export function useSkipSetup() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: skipSetup,
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
    },
  })
}

/**
 * Hook to record a milestone achievement.
 */
export function useRecordMilestone() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (milestone) => recordMilestone(milestone),
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
    },
  })
}

/**
 * Hook to show a tip (record that it was shown).
 */
export function useShowTip() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (tipId) => showTip(tipId),
    onSuccess: (data, tipId) => {
      // Update just the tips_shown array
      queryClient.setQueryData(onboardingKeys.detail(), (old) => {
        if (!old) return old
        return {
          ...old,
          tips_shown: data?.tips_shown || [...(old.tips_shown || []), tipId],
        }
      })
    },
  })
}

/**
 * Hook to dismiss a tip permanently.
 */
export function useDismissTip() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (tipId) => dismissTip(tipId),
    onSuccess: (data, tipId) => {
      // Update just the tips_dismissed array
      queryClient.setQueryData(onboardingKeys.detail(), (old) => {
        if (!old) return old
        return {
          ...old,
          tips_dismissed: data?.tips_dismissed || [...(old.tips_dismissed || []), tipId],
        }
      })
    },
  })
}

/**
 * Hook to set personality choice.
 * Updates both onboarding state and workspace soul_prompt.
 */
export function useSetPersonality() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (personality) => setPersonality(personality),
    onSuccess: (data) => {
      queryClient.setQueryData(onboardingKeys.detail(), data?.onboarding)
      // Also invalidate workspace since soul_prompt was updated
      queryClient.invalidateQueries({ queryKey: ['chef-workspace'] })
    },
  })
}

/**
 * Hook that returns a function to invalidate onboarding cache.
 */
export function useInvalidateOnboarding() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: onboardingKeys.all })
  }
}

/**
 * Helper hook that combines onboarding state with computed properties
 * useful for determining what to show in the UI.
 */
export function useOnboardingStatus({ enabled = true } = {}) {
  const query = useOnboarding({ enabled })

  const data = query.data || {}

  return {
    ...query,
    // Computed helpers
    shouldShowWelcome: !data.welcomed && !query.isLoading,
    shouldShowSetup: data.welcomed && !data.setup_completed && !data.setup_skipped && !query.isLoading,
    isSetupComplete: data.setup_completed || data.setup_skipped,
    hasPersonality: data.personality_set,
    // Milestone helpers
    milestones: {
      firstDish: data.first_dish_added,
      firstClient: data.first_client_added,
      firstConversation: data.first_conversation,
      firstMemory: data.first_memory_saved,
      firstOrder: data.first_order_completed,
      proactiveEnabled: data.proactive_enabled,
    },
    // Tips helpers
    shownTips: new Set(data.tips_shown || []),
    dismissedTips: new Set(data.tips_dismissed || []),
    shouldShowTip: (tipId) => {
      const dismissed = new Set(data.tips_dismissed || [])
      return !dismissed.has(tipId)
    },
  }
}

export default {
  useOnboarding,
  useOnboardingStatus,
  useMarkWelcomed,
  useStartSetup,
  useCompleteSetup,
  useSkipSetup,
  useRecordMilestone,
  useShowTip,
  useDismissTip,
  useSetPersonality,
  useInvalidateOnboarding,
}
