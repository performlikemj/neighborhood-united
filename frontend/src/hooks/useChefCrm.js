/**
 * React hooks for Chef CRM Dashboard data management.
 * 
 * Uses @tanstack/react-query for caching and state management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getDashboardSummary,
  getClients,
  getClientDetail,
  getClientNotes,
  addClientNote,
  getRevenueBreakdown,
  getUpcomingOrders,
  getLeads,
  createLead,
  getLeadDetail,
  updateLead,
  deleteLead,
  addLeadInteraction,
} from '../api/chefCrmClient'

// Query key factory
const crmKeys = {
  all: ['chef-crm'],
  dashboard: () => [...crmKeys.all, 'dashboard'],
  clients: (filters) => [...crmKeys.all, 'clients', filters],
  clientDetail: (id) => [...crmKeys.all, 'client', id],
  clientNotes: (id) => [...crmKeys.all, 'client', id, 'notes'],
  revenue: (params) => [...crmKeys.all, 'revenue', params],
  upcomingOrders: (params) => [...crmKeys.all, 'upcoming-orders', params],
  leads: (filters) => [...crmKeys.all, 'leads', filters],
  leadDetail: (id) => [...crmKeys.all, 'lead', id],
  leadInteractions: (id) => [...crmKeys.all, 'lead', id, 'interactions'],
}

// =============================================================================
// Dashboard Summary Hook
// =============================================================================

/**
 * Hook to fetch dashboard summary stats.
 * @param {{ enabled?: boolean }} options
 */
export function useDashboardSummary({ enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.dashboard(),
    queryFn: getDashboardSummary,
    enabled,
    staleTime: 30 * 1000, // 30 seconds
    refetchOnWindowFocus: true,
  })
}

// =============================================================================
// Client Management Hooks
// =============================================================================

/**
 * Hook to fetch paginated client list.
 * @param {{ search?: string, status?: string, ordering?: string, page?: number, page_size?: number }} filters
 * @param {{ enabled?: boolean }} options
 */
export function useClients(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.clients(filters),
    queryFn: () => getClients(filters),
    enabled,
    staleTime: 60 * 1000, // 1 minute
  })
}

/**
 * Hook to fetch a single client's details.
 * @param {number|string} customerId
 * @param {{ enabled?: boolean }} options
 */
export function useClientDetail(customerId, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.clientDetail(customerId),
    queryFn: () => getClientDetail(customerId),
    enabled: enabled && !!customerId,
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to fetch client interaction notes.
 * @param {number|string} customerId
 * @param {{ enabled?: boolean }} options
 */
export function useClientNotes(customerId, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.clientNotes(customerId),
    queryFn: () => getClientNotes(customerId),
    enabled: enabled && !!customerId,
    staleTime: 30 * 1000,
  })
}

/**
 * Hook to add a client note.
 */
export function useAddClientNote() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ customerId, note }) => addClientNote(customerId, note),
    onSuccess: (_, { customerId }) => {
      // Invalidate notes for this client
      queryClient.invalidateQueries({ queryKey: crmKeys.clientNotes(customerId) })
    },
  })
}

// =============================================================================
// Revenue & Analytics Hooks
// =============================================================================

/**
 * Hook to fetch revenue breakdown.
 * @param {{ period?: string, start_date?: string, end_date?: string }} params
 * @param {{ enabled?: boolean }} options
 */
export function useRevenueBreakdown(params = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.revenue(params),
    queryFn: () => getRevenueBreakdown(params),
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch upcoming orders.
 * @param {{ page?: number, page_size?: number, limit?: number }} params
 * @param {{ enabled?: boolean }} options
 */
export function useUpcomingOrders(params = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.upcomingOrders(params),
    queryFn: () => getUpcomingOrders(params),
    enabled,
    staleTime: 30 * 1000, // 30 seconds - orders change frequently
    refetchOnWindowFocus: true,
  })
}

// =============================================================================
// Lead Pipeline Hooks
// =============================================================================

/**
 * Hook to fetch leads.
 * @param {{ status?: string, source?: string, is_priority?: boolean, search?: string, ordering?: string, page?: number, page_size?: number }} filters
 * @param {{ enabled?: boolean }} options
 */
export function useLeads(filters = {}, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.leads(filters),
    queryFn: () => getLeads(filters),
    enabled,
    staleTime: 60 * 1000,
  })
}

/**
 * Hook to fetch a single lead's details.
 * @param {number|string} leadId
 * @param {{ enabled?: boolean }} options
 */
export function useLeadDetail(leadId, { enabled = true } = {}) {
  return useQuery({
    queryKey: crmKeys.leadDetail(leadId),
    queryFn: () => getLeadDetail(leadId),
    enabled: enabled && !!leadId,
    staleTime: 30 * 1000,
  })
}

/**
 * Hook to create a new lead.
 */
export function useCreateLead() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: createLead,
    onSuccess: () => {
      // Invalidate all lead queries
      queryClient.invalidateQueries({ queryKey: [...crmKeys.all, 'leads'] })
      queryClient.invalidateQueries({ queryKey: crmKeys.dashboard() })
    },
  })
}

/**
 * Hook to update a lead.
 */
export function useUpdateLead() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ leadId, updates }) => updateLead(leadId, updates),
    onSuccess: (_, { leadId }) => {
      queryClient.invalidateQueries({ queryKey: crmKeys.leadDetail(leadId) })
      queryClient.invalidateQueries({ queryKey: [...crmKeys.all, 'leads'] })
    },
  })
}

/**
 * Hook to delete a lead.
 */
export function useDeleteLead() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: deleteLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...crmKeys.all, 'leads'] })
      queryClient.invalidateQueries({ queryKey: crmKeys.dashboard() })
    },
  })
}

/**
 * Hook to add a lead interaction.
 */
export function useAddLeadInteraction() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ leadId, interaction }) => addLeadInteraction(leadId, interaction),
    onSuccess: (_, { leadId }) => {
      queryClient.invalidateQueries({ queryKey: crmKeys.leadDetail(leadId) })
      queryClient.invalidateQueries({ queryKey: crmKeys.leadInteractions(leadId) })
      queryClient.invalidateQueries({ queryKey: [...crmKeys.all, 'leads'] })
    },
  })
}

// =============================================================================
// Utility: Invalidate all CRM data
// =============================================================================

/**
 * Hook that returns a function to invalidate all CRM queries.
 * Useful after major changes or role switches.
 */
export function useInvalidateCrmQueries() {
  const queryClient = useQueryClient()
  
  return () => {
    queryClient.invalidateQueries({ queryKey: crmKeys.all })
  }
}

export default {
  // Dashboard
  useDashboardSummary,
  
  // Clients
  useClients,
  useClientDetail,
  useClientNotes,
  useAddClientNote,
  
  // Revenue
  useRevenueBreakdown,
  useUpcomingOrders,
  
  // Leads
  useLeads,
  useLeadDetail,
  useCreateLead,
  useUpdateLead,
  useDeleteLead,
  useAddLeadInteraction,
  
  // Utilities
  useInvalidateCrmQueries,
}
