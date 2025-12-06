/**
 * Chef CRM Dashboard API Client
 * 
 * Provides functions for the chef CRM dashboard including:
 * - Dashboard summary stats
 * - Client management (platform users)
 * - Contacts management (off-platform clients with households)
 * - Revenue analytics
 * - Lead pipeline
 */

import { api } from '../api'

const CRM_BASE = '/chefs/api/me'

// =============================================================================
// Dashboard Summary
// =============================================================================

export async function getDashboardSummary() {
  const response = await api.get(`${CRM_BASE}/dashboard/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Client Management (Platform Users)
// =============================================================================

export async function getClients({ search, status, ordering, page, page_size } = {}) {
  const params = {}
  if (search) params.search = search
  if (status) params.status = status
  if (ordering) params.ordering = ordering
  if (page) params.page = page
  if (page_size) params.page_size = page_size
  
  const response = await api.get(`${CRM_BASE}/clients/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export async function getClientDetail(customerId) {
  const response = await api.get(`${CRM_BASE}/clients/${customerId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export async function addClientNote(customerId, note) {
  const response = await api.post(`${CRM_BASE}/clients/${customerId}/notes/`, note, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Contacts (Off-Platform Clients / Leads)
// =============================================================================

/**
 * Get all contacts (leads) for the chef.
 */
export async function getLeads({ status, source, is_priority, search, ordering, page, page_size } = {}) {
  const params = {}
  if (status) params.status = status
  if (source) params.source = source
  if (is_priority !== undefined) params.is_priority = is_priority
  if (search) params.search = search
  if (ordering) params.ordering = ordering
  if (page) params.page = page
  if (page_size) params.page_size = page_size
  
  const response = await api.get(`${CRM_BASE}/leads/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Create a new contact with optional household members.
 */
export async function createLead(contact) {
  const response = await api.post(`${CRM_BASE}/leads/`, contact, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get full contact details including household members.
 */
export async function getLeadDetail(leadId) {
  const response = await api.get(`${CRM_BASE}/leads/${leadId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update a contact's info.
 */
export async function updateLead(leadId, updates) {
  const response = await api.patch(`${CRM_BASE}/leads/${leadId}/`, updates, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Delete a contact.
 */
export async function deleteLead(leadId) {
  await api.delete(`${CRM_BASE}/leads/${leadId}/`, {
    skipUserId: true,
    withCredentials: true
  })
}

// =============================================================================
// Contact Interactions (Notes)
// =============================================================================

export async function addLeadInteraction(leadId, interaction) {
  const response = await api.post(`${CRM_BASE}/leads/${leadId}/interactions/`, interaction, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export async function getLeadInteractions(leadId) {
  const response = await api.get(`${CRM_BASE}/leads/${leadId}/interactions/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Household Members (for Contacts)
// =============================================================================

/**
 * Get household members for a contact.
 */
export async function getHouseholdMembers(leadId) {
  const response = await api.get(`${CRM_BASE}/leads/${leadId}/household/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Add a household member to a contact.
 */
export async function addHouseholdMember(leadId, member) {
  const response = await api.post(`${CRM_BASE}/leads/${leadId}/household/`, member, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Update a household member.
 */
export async function updateHouseholdMember(leadId, memberId, updates) {
  const response = await api.patch(`${CRM_BASE}/leads/${leadId}/household/${memberId}/`, updates, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Delete a household member.
 */
export async function deleteHouseholdMember(leadId, memberId) {
  await api.delete(`${CRM_BASE}/leads/${leadId}/household/${memberId}/`, {
    skipUserId: true,
    withCredentials: true
  })
}

// =============================================================================
// Email Verification
// =============================================================================

/**
 * Send email verification to a contact.
 */
export async function sendEmailVerification(leadId) {
  const response = await api.post(`${CRM_BASE}/leads/${leadId}/send-verification/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Check email verification status for a contact.
 */
export async function getEmailVerificationStatus(leadId) {
  const response = await api.get(`${CRM_BASE}/leads/${leadId}/verification-status/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Revenue & Analytics
// =============================================================================

export async function getRevenueBreakdown({ period, start_date, end_date } = {}) {
  const params = {}
  if (period) params.period = period
  if (start_date) params.start_date = start_date
  if (end_date) params.end_date = end_date
  
  const response = await api.get(`${CRM_BASE}/revenue/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

export async function getUpcomingOrders({ page, page_size, limit } = {}) {
  const params = {}
  if (page) params.page = page
  if (page_size) params.page_size = page_size
  if (limit) params.limit = limit
  
  const response = await api.get(`${CRM_BASE}/orders/upcoming/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Constants
// =============================================================================

export const DIETARY_OPTIONS = [
  'Vegan', 'Vegetarian', 'Pescatarian', 'Gluten-Free', 'Keto',
  'Paleo', 'Halal', 'Kosher', 'Low-Calorie', 'Low-Sodium',
  'High-Protein', 'Dairy-Free', 'Nut-Free', 'Diabetic-Friendly', 'Everything'
]

export const ALLERGY_OPTIONS = [
  'Peanuts', 'Tree nuts', 'Milk', 'Egg', 'Wheat', 'Soy',
  'Fish', 'Shellfish', 'Sesame', 'Gluten', 'None'
]

export default {
  getDashboardSummary,
  getClients,
  getClientDetail,
  addClientNote,
  getLeads,
  createLead,
  getLeadDetail,
  updateLead,
  deleteLead,
  addLeadInteraction,
  getLeadInteractions,
  getHouseholdMembers,
  addHouseholdMember,
  updateHouseholdMember,
  deleteHouseholdMember,
  sendEmailVerification,
  getEmailVerificationStatus,
  getRevenueBreakdown,
  getUpcomingOrders,
  DIETARY_OPTIONS,
  ALLERGY_OPTIONS,
}
