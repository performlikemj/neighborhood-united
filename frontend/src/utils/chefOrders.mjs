const STATUS_BUCKETS = {
  active: new Set(['confirmed', 'active', 'paid', 'in_progress']),
  pending: new Set(['awaiting_payment', 'pending', 'draft', 'open']),
  completed: new Set(['completed', 'fulfilled', 'delivered']),
  cancelled: new Set(['cancelled', 'canceled', 'refund_pending', 'failed'])
}

export function bucketOrderStatus(status){
  const normalized = String(status || '').toLowerCase().trim()
  if (!normalized) return 'unknown'
  if (STATUS_BUCKETS.active.has(normalized)) return 'active'
  if (STATUS_BUCKETS.pending.has(normalized)) return 'pending'
  if (STATUS_BUCKETS.completed.has(normalized)) return 'completed'
  if (STATUS_BUCKETS.cancelled.has(normalized)) return 'cancelled'
  return 'other'
}

export function buildOrderSearchText({
  customerName,
  contact,
  title,
  status,
  type,
  notes,
  schedule,
  priceLabel
} = {}){
  return [
    customerName,
    contact,
    title,
    status,
    type,
    notes,
    schedule,
    priceLabel
  ]
    .filter(Boolean)
    .map(value => String(value))
    .join(' ')
    .trim()
}

function normalizeQuery(value){
  return String(value || '').trim().toLowerCase()
}

function orderSearchText(order){
  if (!order) return ''
  if (order.searchText) return String(order.searchText)
  return buildOrderSearchText({
    customerName: order.customerName,
    contact: order.contactLine || order.contact,
    title: order.title,
    status: order.status,
    type: order.type,
    notes: order.notes,
    schedule: order.scheduleLabel || order.schedule,
    priceLabel: order.priceLabel
  })
}

export function filterOrders(orders = [], { query = '', type = 'all', statusBucket = 'all' } = {}){
  const normalizedQuery = normalizeQuery(query)
  return (orders || []).filter(order => {
    if (type && type !== 'all' && order.type !== type) return false
    if (statusBucket && statusBucket !== 'all') {
      const bucket = order.statusBucket || bucketOrderStatus(order.status)
      if (bucket !== statusBucket) return false
    }
    if (!normalizedQuery) return true
    const haystack = normalizeQuery(orderSearchText(order))
    return haystack.includes(normalizedQuery)
  })
}

export function paginateOrders(items = [], { page = 1, pageSize = 10 } = {}){
  const safePageSize = Math.max(1, Number(pageSize) || 1)
  const totalPages = Math.max(1, Math.ceil((items || []).length / safePageSize))
  const safePage = Math.min(Math.max(1, Number(page) || 1), totalPages)
  const start = (safePage - 1) * safePageSize
  const slice = (items || []).slice(start, start + safePageSize)
  return {
    page: safePage,
    pageSize: safePageSize,
    totalPages,
    items: slice
  }
}
