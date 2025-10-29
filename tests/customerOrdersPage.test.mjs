import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const customerOrdersPath = resolve('src/pages/CustomerOrders.jsx')
const appPath = resolve('src/App.jsx')
const navPath = resolve('src/components/NavBar.jsx')

function load(path){
  return readFileSync(path, 'utf8')
}

test('CustomerOrders fetches service orders and reuses meal order tab', () => {
  const source = load(customerOrdersPath)
  assert.match(
    source,
    /api\.get\('\/services\/my\/customer-orders\/'/,
    'Expected CustomerOrders to load service orders from /services/my/customer-orders/.'
  )
  assert.match(source, /OrdersTab/, 'Expected CustomerOrders to reuse the OrdersTab component for meal orders.')
})

test('CustomerOrders renders service and meal sections', () => {
  const source = load(customerOrdersPath)
  assert.match(source, /Service orders/, 'Expected a Service orders section heading.')
  assert.match(source, /Meal orders/, 'Expected a Meal orders section heading.')
})

test('App routes include the customer orders page', () => {
  const source = load(appPath)
  assert.match(source, /path="\/orders"/, 'Expected App routes to expose /orders.')
})

test('NavBar offers a link to the orders page for authenticated users', () => {
  const source = load(navPath)
  assert.match(source, /\{ to:\'\/orders\'/, 'Expected NavBar more-menu items to include /orders link.')
})

test('CustomerOrders renders the chef name as a link to their public profile', () => {
  const source = load(customerOrdersPath)
  assert.match(source, /getChefProfilePath/, 'Expected a helper that derives the chef profile path from an order.')
  assert.match(source, /<Link[^>]+to=\{chefProfilePath\}/, 'Expected the chef name to render inside a Link to the chef profile.')
})

test('CustomerOrders hydrates chef details when only chef IDs are returned', () => {
  const source = load(customerOrdersPath)
  assert.match(source, /const \[chefDetails, setChefDetails\] = useState\(\{\}\)/, 'Expected state to track fetched chef details.')
  assert.match(source, /function getChefId\(/, 'Expected a helper that extracts chef IDs from service orders.')
  assert.match(source, /api.get\(`\/chefs\/api\/public\/\$\{encodeURIComponent\(id\)\}\//, 'Expected CustomerOrders to fetch chef profiles by id from the public chefs API.')
  assert.match(source, /function appendChefIdParam\(/, 'Expected a helper that appends chef_id query parameters to profile links.')
})
