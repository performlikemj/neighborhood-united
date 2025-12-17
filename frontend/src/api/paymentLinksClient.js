/**
 * Chef Payment Links API Client
 * 
 * Provides functions for managing payment links:
 * - List, create, send, and cancel payment links
 * - Email verification for manual contacts
 * - Payment link statistics
 */

import { api } from '../api'

const BASE_URL = '/chefs/api/me'

// =============================================================================
// Payment Links CRUD
// =============================================================================

/**
 * Get all payment links for the chef.
 * @param {Object} options - Filter options
 * @param {string} options.status - Filter by status (draft, pending, paid, expired, cancelled)
 * @param {string} options.client_type - Filter by client type (lead, customer)
 * @param {string} options.search - Search by recipient name or description
 * @param {string} options.ordering - Sort order (created_at, -created_at, expires_at, amount_cents)
 * @param {number} options.page - Page number
 * @param {number} options.page_size - Items per page
 */
export async function getPaymentLinks({ status, client_type, search, ordering, page, page_size } = {}) {
  const params = {}
  if (status) params.status = status
  if (client_type) params.client_type = client_type
  if (search) params.search = search
  if (ordering) params.ordering = ordering
  if (page) params.page = page
  if (page_size) params.page_size = page_size
  
  const response = await api.get(`${BASE_URL}/payment-links/`, {
    params,
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get payment link statistics.
 */
export async function getPaymentLinkStats() {
  const response = await api.get(`${BASE_URL}/payment-links/stats/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get a single payment link by ID.
 * @param {number} linkId - Payment link ID
 */
export async function getPaymentLink(linkId) {
  const response = await api.get(`${BASE_URL}/payment-links/${linkId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Create a new payment link.
 * @param {Object} data - Payment link data
 * @param {number} data.amount_cents - Amount in cents (minimum 50)
 * @param {string} data.description - Description of the payment
 * @param {number} [data.lead_id] - ID of the manual contact (lead)
 * @param {number} [data.customer_id] - ID of the platform customer
 * @param {number} [data.expires_days] - Days until expiration (default 30)
 * @param {string} [data.internal_notes] - Internal notes for the chef
 */
export async function createPaymentLink(data) {
  const response = await api.post(`${BASE_URL}/payment-links/`, data, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Send (or resend) a payment link via email.
 * @param {number} linkId - Payment link ID
 * @param {string} [email] - Override recipient email (optional)
 */
export async function sendPaymentLink(linkId, email = null) {
  const data = email ? { email } : {}
  const response = await api.post(`${BASE_URL}/payment-links/${linkId}/send/`, data, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Cancel a payment link.
 * @param {number} linkId - Payment link ID
 */
export async function cancelPaymentLink(linkId) {
  const response = await api.delete(`${BASE_URL}/payment-links/${linkId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Email Verification
// =============================================================================

/**
 * Send email verification to a contact.
 * @param {number} leadId - Lead/contact ID
 */
export async function sendEmailVerification(leadId) {
  const response = await api.post(`${BASE_URL}/leads/${leadId}/send-verification/`, {}, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Check email verification status for a contact.
 * @param {number} leadId - Lead/contact ID
 */
export async function getEmailVerificationStatus(leadId) {
  const response = await api.get(`${BASE_URL}/leads/${leadId}/verification-status/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format cents to dollars for display.
 * @param {number} cents - Amount in cents
 * @returns {string} Formatted amount (e.g., "$50.00")
 */
export function formatAmount(cents) {
  return `$${(cents / 100).toFixed(2)}`
}

/**
 * Get status badge color for a payment link status.
 * @param {string} status - Payment link status
 * @returns {string} CSS color class or hex color
 */
export function getStatusColor(status) {
  const colors = {
    draft: '#6c757d',      // gray
    pending: '#ffc107',    // yellow
    paid: '#28a745',       // green
    expired: '#dc3545',    // red
    cancelled: '#6c757d',  // gray
  }
  return colors[status] || '#6c757d'
}

/**
 * Get human-readable status label.
 * @param {string} status - Payment link status
 * @returns {string} Human-readable label
 */
export function getStatusLabel(status) {
  const labels = {
    draft: 'Draft',
    pending: 'Pending Payment',
    paid: 'Paid',
    expired: 'Expired',
    cancelled: 'Cancelled',
  }
  return labels[status] || status
}

// =============================================================================
// Constants
// =============================================================================

export const PAYMENT_LINK_STATUSES = [
  { value: '', label: 'All Statuses' },
  { value: 'pending', label: 'Pending Payment' },
  { value: 'paid', label: 'Paid' },
  { value: 'draft', label: 'Draft' },
  { value: 'expired', label: 'Expired' },
  { value: 'cancelled', label: 'Cancelled' },
]

export const CLIENT_TYPES = [
  { value: '', label: 'All Clients' },
  { value: 'lead', label: 'Manual Contacts' },
  { value: 'customer', label: 'Platform Users' },
]

export default {
  getPaymentLinks,
  getPaymentLinkStats,
  getPaymentLink,
  createPaymentLink,
  sendPaymentLink,
  cancelPaymentLink,
  sendEmailVerification,
  getEmailVerificationStatus,
  formatAmount,
  getStatusColor,
  getStatusLabel,
  PAYMENT_LINK_STATUSES,
  CLIENT_TYPES,
}



