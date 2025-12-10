import { useCallback, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listConnections, requestConnection, respondConnection } from '../api/servicesClient.js'
import { useAuth } from '../context/AuthContext.jsx'

const CONNECTION_QUERY_KEY = role => ['services', 'connections', role || 'any']

function toArray(payload){
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.data?.results)) return payload.data.results
  if (Array.isArray(payload?.details?.results)) return payload.details.results
  if (Array.isArray(payload?.details)) return payload.details
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

function coerceId(value){
  if (value == null) return null
  const numeric = Number(value)
  if (!Number.isNaN(numeric)) return numeric
  if (typeof value === 'string'){
    const trimmed = value.trim()
    if (!trimmed) return null
    const asNumber = Number(trimmed)
    return Number.isNaN(asNumber) ? trimmed : asNumber
  }
  return value
}

function mapRole(value){
  const normalized = String(value || '').toLowerCase()
  if (normalized.includes('chef')) return 'chef'
  if (normalized.includes('customer')) return 'customer'
  return normalized || null
}

function deriveConnection(connection = {}, viewerRole, viewerId){
  const status = String(connection?.status || '').toLowerCase()
  const normalizedViewerRole = mapRole(viewerRole) || 'customer'
  const initiatedByRole = mapRole(connection?.initiated_by)
  const initiatorId = coerceId(
    connection?.initiated_by_id
    ?? connection?.initiated_by_user_id
    ?? connection?.initiator_id
    ?? connection?.initiator?.id
  )
  const viewerNumericId = coerceId(viewerId)
  // Determine if viewer initiated: prefer ID comparison if both IDs are available,
  // otherwise fall back to role-based comparison
  const viewerInitiated = (initiatorId != null && viewerNumericId != null)
    ? viewerNumericId === initiatorId
    : (initiatedByRole ? initiatedByRole === normalizedViewerRole : false)

  const isPending = status === 'pending'
  const isAccepted = status === 'accepted'
  const isDeclined = status === 'declined'
  const isEnded = status === 'ended'
  const isActive = isAccepted

  const chefId = coerceId(
    connection?.chef_id
    ?? connection?.chef_user_id
    ?? connection?.chef?.id
    ?? connection?.chef?.user_id
    ?? connection?.chef?.user?.id
  )
  const customerId = coerceId(
    connection?.customer_id
    ?? connection?.customer_user_id
    ?? connection?.customer?.id
    ?? connection?.customer?.user_id
    ?? connection?.customer?.user?.id
  )

  const canAccept = isPending && !viewerInitiated
  const canDecline = isPending && !viewerInitiated
  const canEnd = isAccepted

  return {
    ...connection,
    status,
    chefId,
    customerId,
    viewerInitiated,
    isPending,
    isAccepted,
    isDeclined,
    isEnded,
    isActive,
    canAccept,
    canDecline,
    canEnd
  }
}

function mergeConnection(list, incoming, viewerRole, viewerId){
  if (!incoming) return list
  const derivedIncoming = deriveConnection(incoming, viewerRole, viewerId)
  if (!derivedIncoming?.id){
    return [...list, derivedIncoming]
  }
  const idx = list.findIndex(item => item?.id === derivedIncoming.id)
  if (idx === -1) return [...list, derivedIncoming]
  const clone = list.slice()
  clone[idx] = { ...list[idx], ...derivedIncoming }
  return clone
}

function mapById(connections, selector){
  const map = new Map()
  connections.forEach(connection => {
    const key = selector(connection)
    if (key == null) return
    map.set(String(key), connection)
  })
  return map
}

export function useConnections(role){
  const { user } = useAuth() || {}
  const viewerRole = role || user?.current_role || (user?.is_chef ? 'chef' : 'customer')
  const viewerId = user?.id
  const queryClient = useQueryClient()
  const queryKey = CONNECTION_QUERY_KEY(viewerRole)

  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const payload = await listConnections({})
      return toArray(payload)
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    // Only fetch connections if user is authenticated
    enabled: Boolean(user?.id)
  })

  const connections = useMemo(() => {
    return toArray(query.data).map(item => deriveConnection(item, viewerRole, viewerId))
  }, [query.data, viewerRole, viewerId])

  const pendingConnections = useMemo(() => connections.filter(c => c.isPending), [connections])
  const acceptedConnections = useMemo(() => connections.filter(c => c.isAccepted), [connections])
  const declinedConnections = useMemo(() => connections.filter(c => c.isDeclined), [connections])
  const endedConnections = useMemo(() => connections.filter(c => c.isEnded), [connections])
  const connectionsByChefId = useMemo(() => mapById(connections, c => c.chefId), [connections])
  const connectionsByCustomerId = useMemo(() => mapById(connections, c => c.customerId), [connections])

  const requestMutation = useMutation({
    mutationFn: async (variables) => {
      const payload = variables || {}
      if (viewerRole === 'chef'){
        const id = payload.customerId
        if (id == null || id === ''){
          if (import.meta?.env?.DEV){
            console.warn('[useConnections] Missing customerId for chef requestConnection', payload)
          }
          throw new Error('customerId is required when chefs request connections')
        }
      } else {
        const id = payload.chefId
        if (id == null || id === ''){
          if (import.meta?.env?.DEV){
            console.warn('[useConnections] Missing chefId for customer requestConnection', payload)
          }
          throw new Error('chefId is required when customers request connections')
        }
      }
      if (import.meta?.env?.DEV){
        console.debug('[useConnections] requestConnection payload about to send', payload)
      }
      return requestConnection(payload)
    },
    onMutate: async variables => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData(queryKey)
      queryClient.setQueryData(queryKey, old => {
        const list = toArray(old)
        const targetChefId = variables?.chefId ?? null
        const targetCustomerId = viewerRole === 'chef'
          ? variables?.customerId ?? null
          : viewerId
        const optimistic = deriveConnection({
          id: `tmp-${Date.now()}`,
          status: 'pending',
          initiated_by: viewerRole,
          initiated_by_id: viewerId,
          chef_id: targetChefId,
          customer_id: targetCustomerId,
          note: variables?.note ?? ''
        }, viewerRole, viewerId)
        return [...list, optimistic]
      })
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (import.meta?.env?.DEV){
        console.error('[useConnections] requestConnection failed', _error)
      }
      if (context?.previous !== undefined){
        queryClient.setQueryData(queryKey, context.previous)
      }
    },
    onSuccess: data => {
      queryClient.setQueryData(queryKey, old => {
        const list = toArray(old)
        return mergeConnection(list, data, viewerRole, viewerId)
      })
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    }
  })

  const respondMutation = useMutation({
    mutationFn: respondConnection,
    onMutate: async ({ connectionId, action }) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData(queryKey)
      queryClient.setQueryData(queryKey, old => {
        const list = toArray(old).map(item => {
          if (!item) return item
          if (String(item.id) !== String(connectionId)) return item
          const nextStatus = action === 'accept'
            ? 'accepted'
            : action === 'decline'
              ? 'declined'
              : action === 'end'
                ? 'ended'
                : item.status
          return deriveConnection({ ...item, status: nextStatus }, viewerRole, viewerId)
        })
        return list
      })
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous !== undefined){
        queryClient.setQueryData(queryKey, context.previous)
      }
    },
    onSuccess: data => {
      queryClient.setQueryData(queryKey, old => {
        const list = toArray(old)
        return mergeConnection(list, data, viewerRole, viewerId)
      })
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey })
    }
  })

  const hasActiveConnectionForChef = useCallback(
    chefId => {
      if (chefId == null) return false
      const match = connectionsByChefId.get(String(chefId))
      return Boolean(match?.isAccepted)
    },
    [connectionsByChefId]
  )

  const getConnectionForChef = useCallback(
    chefId => {
      if (chefId == null) return null
      return connectionsByChefId.get(String(chefId)) || null
    },
    [connectionsByChefId]
  )

  const hasActiveConnectionForCustomer = useCallback(
    customerId => {
      if (customerId == null) return false
      const match = connectionsByCustomerId.get(String(customerId))
      return Boolean(match?.isAccepted)
    },
    [connectionsByCustomerId]
  )

  const getConnectionForCustomer = useCallback(
    customerId => {
      if (customerId == null) return null
      return connectionsByCustomerId.get(String(customerId)) || null
    },
    [connectionsByCustomerId]
  )

  return {
    viewerRole,
    viewerId,
    connections,
    pendingConnections,
    acceptedConnections,
    declinedConnections,
    endedConnections,
    requestConnection: requestMutation.mutateAsync,
    respondToConnection: respondMutation.mutateAsync,
    refetchConnections: query.refetch,
    hasActiveConnectionForChef,
    getConnectionForChef,
    hasActiveConnectionForCustomer,
    getConnectionForCustomer,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    requestStatus: requestMutation.status,
    respondStatus: respondMutation.status,
    requestError: requestMutation.error,
    respondError: respondMutation.error
  }
}
