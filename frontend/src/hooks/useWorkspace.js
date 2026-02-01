/**
 * React hooks for Sous Chef Workspace settings.
 *
 * Uses @tanstack/react-query for caching and state management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getWorkspace,
  updateWorkspace,
  resetWorkspace,
} from '../api/workspaceClient'

// Query key factory
const workspaceKeys = {
  all: ['chef-workspace'],
  detail: () => [...workspaceKeys.all, 'detail'],
}

/**
 * Hook to fetch the chef's workspace settings.
 *
 * @param {{ enabled?: boolean }} options
 * @returns Query result with workspace data
 */
export function useWorkspace({ enabled = true } = {}) {
  return useQuery({
    queryKey: workspaceKeys.detail(),
    queryFn: getWorkspace,
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes - workspace doesn't change often
    refetchOnWindowFocus: false,
  })
}

/**
 * Hook to update workspace settings.
 *
 * @returns Mutation with mutate(updates) function
 */
export function useUpdateWorkspace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: updateWorkspace,
    onSuccess: (data) => {
      // Update cache with new data
      queryClient.setQueryData(workspaceKeys.detail(), data)
    },
    onError: (error) => {
      console.error('Failed to update workspace:', error)
    },
  })
}

/**
 * Hook to reset workspace fields to defaults.
 *
 * @returns Mutation with mutate(fields) function
 */
export function useResetWorkspace() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: resetWorkspace,
    onSuccess: (data) => {
      // Update cache with reset data
      queryClient.setQueryData(workspaceKeys.detail(), data)
    },
    onError: (error) => {
      console.error('Failed to reset workspace:', error)
    },
  })
}

/**
 * Hook that returns a function to invalidate workspace cache.
 */
export function useInvalidateWorkspace() {
  const queryClient = useQueryClient()

  return () => {
    queryClient.invalidateQueries({ queryKey: workspaceKeys.all })
  }
}

export default {
  useWorkspace,
  useUpdateWorkspace,
  useResetWorkspace,
  useInvalidateWorkspace,
}
