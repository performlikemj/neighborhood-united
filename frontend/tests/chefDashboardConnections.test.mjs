import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve('src/pages/ChefDashboard.jsx')

function loadDashboard(){
  return readFileSync(dashboardPath, 'utf8')
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

test('ChefDashboard surfaces a Client Connections tab with actions', () => {
  const source = loadDashboard()
  assert.match(
    source,
    /Client Connections/,
    'Expected a Client Connections tab label.'
  )
  ;['Accept', 'Decline', 'End'].forEach(action => {
    assert.match(
      source,
      new RegExp(`>${action}<`),
      `Client Connections tab should expose a ${action} button.`
    )
  })
  assert.match(
    source,
    /respondToConnection/,
    'Connection actions should be wired through respondToConnection.'
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
