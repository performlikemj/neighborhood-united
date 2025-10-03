import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const publicChefPath = resolve('src/pages/PublicChef.jsx')

function loadSource(){
  return readFileSync(publicChefPath, 'utf8')
}

test('PublicChef calls services endpoint with viewer postal code when available', () => {
  const source = loadSource()
  assert.match(
    source,
    /api\.get\('\/services\/offerings\/'[\s\S]*postal_code/,
    'Expected PublicChef to request /services/offerings/ with a postal_code parameter.'
  )
})

test('PublicChef surfaces out-of-area messaging for services', () => {
  const source = loadSource()
  assert.match(
    source,
    /services aren't available in your area yet\./,
    'Expected a customer-facing message when services are outside the viewer\'s area.'
  )
})

test('PublicChef exposes a CTA so guests can book a chef service tier', () => {
  const source = loadSource()
  assert.match(
    source,
    /Book this service tier/,
    'Expected a visible button that invites the guest to book a service tier.'
  )
})

test('PublicChef creates chef service orders before starting checkout', () => {
  const source = loadSource()
  assert.match(
    source,
    /api\.post\(`\/services\/orders\//,
    'Expected PublicChef to create chef service orders via POST /services/orders/.'
  )
  assert.match(
    source,
    /\/services\/orders\/\$\{[^}]+\}\/checkout/,
    'Expected PublicChef to request a checkout session for the created order.'
  )
})

test('PublicChef labels whether a service tier is recurring', () => {
  const source = loadSource()
  assert.match(
    source,
    /tier-recurring-chip|tier-once-chip/,
    'Expected a prominent visual badge indicating recurring vs. one-time tier.'
  )
})
