import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const sidebarPath = resolve('src/components/CartSidebar.jsx')

function loadSidebar(){
  return readFileSync(sidebarPath, 'utf8')
}

test('CartSidebar updates draft chef service orders before checkout', () => {
  const source = loadSidebar()
  assert.match(
    source,
    /api\.patch\(`\/services\/orders\/\$\{[^}]+\}\/update\//,
    'Expected CartSidebar to patch chef service orders using the /services draft update endpoint.'
  )
  assert.match(
    source,
    /api\.post\(`\/services\/orders\/\$\{[^}]+\}\/checkout/,
    'Expected CartSidebar to call /services/orders/{id}/checkout after updating the draft.'
  )
})

test('CartSidebar surfaces checkout validation errors to the customer', () => {
  const source = loadSidebar()
  assert.match(
    source,
    /validation_errors/,
    'Expected CartSidebar to reference validation_errors returned from the checkout endpoint.'
  )
})

test('CartSidebar loads customer addresses and offers an add-new address form', () => {
  const source = loadSidebar()
  assert.match(
    source,
    /authUser\?\.address|userAddress/,
    'Expected CartSidebar to use the user address from auth context.'
  )
  assert.match(
    source,
    /Add new address|Add address/i,
    'CartSidebar should present a CTA so customers can add a new service address from the cart.'
  )
})
