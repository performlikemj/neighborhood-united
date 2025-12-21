import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve('src/pages/ChefDashboard.jsx')
const clientsPath = resolve('src/components/ChefAllClients.jsx')

function loadDashboard(){
  return readFileSync(dashboardPath, 'utf8')
}

function loadClients(){
  return readFileSync(clientsPath, 'utf8')
}

test('ChefDashboard imports and uses the useConnections hook', () => {
  const source = loadDashboard()
  assert.match(
    source,
    /from\s+'..\/hooks\/useConnections\.js'/,
    'ChefDashboard should import the shared useConnections hook.'
  )
  assert.match(
    source,
    /const\s+\{\s*connections/,
    'ChefDashboard should pull connection data from the hook.'
  )
})

test('ChefAllClients manages connections with accept/decline/end actions', () => {
  const source = loadClients()
  // Connection management is now in ChefAllClients (Clients tab)
  assert.match(
    source,
    /useConnections/,
    'ChefAllClients should import useConnections hook.'
  )
  assert.match(
    source,
    /handleConnectionAction/,
    'ChefAllClients should have a connection action handler.'
  )
  // Check for accept/decline/end actions
  assert.match(
    source,
    /action.*accept/i,
    'ChefAllClients should support accepting connections.'
  )
  assert.match(
    source,
    /action.*decline/i,
    'ChefAllClients should support declining connections.'
  )
  assert.match(
    source,
    /action.*end/i,
    'ChefAllClients should support ending connections.'
  )
})

test('Offering form allows targeting accepted customers', () => {
  const source = loadDashboard()
  assert.match(
    source,
    /target_customer_ids/,
    'Offering form submission should include target_customer_ids.'
  )
  assert.match(
    source,
    /acceptedConnections/,
    'Offering form should rely on acceptedConnections from the hook.'
  )
  assert.match(
    source,
    /multiselect/i,
    'UI should mention a multiselect for picking accepted customers.'
  )
})
