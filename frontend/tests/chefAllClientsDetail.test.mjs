import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const clientsPath = resolve('src/components/ChefAllClients.jsx')

function loadClients(){
  return readFileSync(clientsPath, 'utf8')
}

test('Client detail panel avoids nested scroll and uses more vertical space', () => {
  const source = loadClients()
  assert.match(
    source,
    /detailContent:\s*\{[^}]*minHeight:/s,
    'Detail panel should reserve more vertical space with a minHeight.'
  )
  assert.doesNotMatch(
    source,
    /detailContent:[\s\S]*maxHeight:\s*'60vh'/,
    'Detail panel should not clamp content to 60vh.'
  )
  assert.doesNotMatch(
    source,
    /detailContent:[\s\S]*overflowY:\s*'auto'/,
    'Detail panel should avoid nested scroll containers.'
  )
})
