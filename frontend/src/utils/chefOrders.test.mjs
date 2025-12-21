import test from 'node:test'
import assert from 'node:assert/strict'

import {
  bucketOrderStatus,
  buildOrderSearchText,
  filterOrders,
  paginateOrders,
} from './chefOrders.mjs'

test('bucketOrderStatus groups common statuses', () => {
  assert.equal(bucketOrderStatus('confirmed'), 'active')
  assert.equal(bucketOrderStatus('paid'), 'active')
  assert.equal(bucketOrderStatus('awaiting_payment'), 'pending')
  assert.equal(bucketOrderStatus('completed'), 'completed')
  assert.equal(bucketOrderStatus('canceled'), 'cancelled')
  assert.equal(bucketOrderStatus('cancelled'), 'cancelled')
  assert.equal(bucketOrderStatus('mystery'), 'other')
})

test('filterOrders matches by type, status bucket, and query text', () => {
  const orders = [
    {
      id: 'service-1',
      type: 'service',
      status: 'confirmed',
      customerName: 'Kiho',
      title: 'Jamaican Food',
      searchText: buildOrderSearchText({
        customerName: 'Kiho',
        title: 'Jamaican Food',
        status: 'confirmed',
        type: 'service',
        contact: 'kiho@example.com',
      }),
    },
    {
      id: 'meal-2',
      type: 'meal',
      status: 'completed',
      customerName: 'Tari',
      title: 'Lunch Prep',
      searchText: buildOrderSearchText({
        customerName: 'Tari',
        title: 'Lunch Prep',
        status: 'completed',
        type: 'meal',
        contact: 'tari@example.com',
      }),
    },
  ]

  const byType = filterOrders(orders, { type: 'meal', statusBucket: 'all', query: '' })
  assert.equal(byType.length, 1)
  assert.equal(byType[0].id, 'meal-2')

  const byStatus = filterOrders(orders, { type: 'all', statusBucket: 'active', query: '' })
  assert.equal(byStatus.length, 1)
  assert.equal(byStatus[0].id, 'service-1')

  const byQuery = filterOrders(orders, { type: 'all', statusBucket: 'all', query: 'jamaican' })
  assert.equal(byQuery.length, 1)
  assert.equal(byQuery[0].id, 'service-1')
})

test('paginateOrders clamps pages and slices correctly', () => {
  const items = Array.from({ length: 9 }, (_, idx) => ({ id: idx + 1 }))
  const page1 = paginateOrders(items, { page: 1, pageSize: 4 })
  assert.equal(page1.totalPages, 3)
  assert.deepEqual(page1.items.map(i => i.id), [1, 2, 3, 4])

  const page2 = paginateOrders(items, { page: 2, pageSize: 4 })
  assert.deepEqual(page2.items.map(i => i.id), [5, 6, 7, 8])

  const page3 = paginateOrders(items, { page: 4, pageSize: 4 })
  assert.equal(page3.page, 3)
  assert.deepEqual(page3.items.map(i => i.id), [9])
})
