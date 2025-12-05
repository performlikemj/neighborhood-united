import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const customerDashboardPath = resolve('src/pages/CustomerOrders.jsx')

function loadCustomerDashboard(){
  return readFileSync(customerDashboardPath, 'utf8')
}

test('Customer dashboard imports and uses useConnections', () => {
  const source = loadCustomerDashboard()
  assert.match(
    source,
    /from\s+'..\/hooks\/useConnections\.js'/,
    'Customer dashboard should import the shared useConnections hook.'
  )
  assert.match(
    source,
    /connections/,
    'Customer dashboard should reference connection data.'
  )
})

test('Customer dashboard allows ending an active service connection', () => {
  const source = loadCustomerDashboard()
  assert.match(
    source,
    /End Service/,
    'Customer dashboard should offer an End Service button.'
  )
  assert.match(
    source,
    /respondToConnection/,
    'End Service action should call respondToConnection.'
  )
})
