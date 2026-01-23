import { api } from '../api'

/**
 * @typedef {'pending'|'accepted'|'declined'|'ended'} ConnectionStatus
 */

/**
 * Fetch the authenticated user's connections.
 * @param {{ status?: ConnectionStatus }=} options
 * @returns {Promise<any>}
 */
export async function listConnections({ status } = {}){
  const params = {}
  if (status != null && status !== '') params.status = status
  const response = await api.get('/services/connections/', {
    params,
    withCredentials: true
  })
  return response?.data
}

/**
 * Initiate a new connection. Customers pass chefId; chefs may provide customerId.
 * @param {{ chefId?: number|string, customerId?: number|string, note?: string }=} payload
 * @returns {Promise<any>}
 */
export async function requestConnection(params = {}){
  const {
    chefId,
    chef_id: chefIdSnake,
    customerId,
    customer_id: customerIdSnake,
    customerUserId,
    customer_user_id: customerUserIdSnake,
    chefUser,
    chef_user: chefUserSnake,
    chefUserId,
    chef_user_id: chefUserIdSnake,
    note,
    ...rest
  } = params
  const resolvedChefId = chefId ?? chefIdSnake ?? null
  const resolvedCustomerId = customerId
    ?? customerIdSnake
    ?? customerUserId
    ?? customerUserIdSnake
    ?? chefUser
    ?? chefUserSnake
    ?? chefUserId
    ?? chefUserIdSnake
    ?? null
  const hasChefId = resolvedChefId != null && resolvedChefId !== ''
  const hasCustomerId = resolvedCustomerId != null && resolvedCustomerId !== ''
  if (import.meta?.env?.DEV){
    console.debug('[servicesClient] requestConnection params:', params)
    console.debug('[servicesClient] resolved connection ids:', { resolvedChefId, resolvedCustomerId, hasChefId, hasCustomerId })
  }
  if (!hasChefId && !hasCustomerId){
    throw new Error('requestConnection requires a chefId (customer flow) or customerId (chef flow)')
  }
  const payload = { ...rest }
  if (hasChefId) payload.chef_id = resolvedChefId
  if (hasCustomerId) payload.customer_id = resolvedCustomerId
  if (note != null) payload.note = note
  console.log('payload', payload)
  const response = await api.post('/services/connections/', payload, {
    withCredentials: true
  })
  return response?.data
}

/**
 * Respond to an existing connection request.
 * @param {{ connectionId: number|string, action: 'accept'|'decline'|'end' }} payload
 * @returns {Promise<any>}
 */
export async function respondConnection({ connectionId, action }){
  if (connectionId == null) throw new Error('connectionId is required')
  const response = await api.patch(`/services/connections/${connectionId}/`, { action }, {
    withCredentials: true
  })
  return response?.data
}

/**
 * Create a new offering.
 * @param {{ targetCustomerIds?: Array<number|string> } & Record<string, any>} payload
 * @returns {Promise<any>}
 */
export async function createOffering({ targetCustomerIds = [], ...fields }){
  const response = await api.post('/services/offerings/', {
    ...fields,
    target_customer_ids: Array.isArray(targetCustomerIds) ? targetCustomerIds : []
  }, {
    withCredentials: true
  })
  return response?.data
}

/**
 * List offerings visible to the current viewer.
 * @param {{ chefId?: number|string, serviceType?: string }=} params
 * @returns {Promise<any>}
 */
export async function listOfferings({ chefId, serviceType } = {}){
  const params = {}
  if (chefId != null && chefId !== '') params.chef_id = chefId
  if (serviceType) params.service_type = serviceType
  const response = await api.get('/services/offerings/', {
    params,
    withCredentials: true
  })
  return response?.data
}

/**
 * Delete a service offering.
 * @param {number|string} offeringId - The ID of the offering to delete
 * @returns {Promise<void>}
 * @throws {Error} If the offering has orders or user is not authorized
 */
export async function deleteOffering(offeringId){
  await api.delete(`/services/offerings/${offeringId}/delete/`, {
    withCredentials: true
  })
}
