import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const publicChefPath = resolve('src/pages/PublicChef.jsx')

function loadPublicChef(){
  return readFileSync(publicChefPath, 'utf8')
}

test('PublicChef wires up request invitation CTA', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /from\s+'..\/hooks\/useConnections\.js'/,
    'PublicChef should import the shared useConnections hook.'
  )
  assert.match(
    source,
    /Request Invitation/,
    'Public chef profile should expose a Request Invitation call-to-action.'
  )
  assert.match(
    source,
    /requestConnection\(\s*\{\s*chefId:[^}]*customerId:/,
    'CTA should call requestConnection with both chefId and customerId.'
  )
})

test('PublicChef surfaces connection status feedback to customers', () => {
  const source = loadPublicChef()
  assert.match(
    source,
    /connectionStatus/,
    'Component should derive connectionStatus state for feedback.'
  )
  assert.match(
    source,
    /Pending invitation|Pending request/,
    'UI should describe the pending invitation state.'
  )
})
