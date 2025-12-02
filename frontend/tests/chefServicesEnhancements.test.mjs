import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chefDashboardPath = resolve('src/pages/ChefDashboard.jsx')

function loadSource(){
  return readFileSync(chefDashboardPath, 'utf8')
}

test('ChefDashboard derives tier summary examples for the guidance panel', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+tierSummaryExamples\s*=\s*useMemo\(/,
    'Expected a tierSummaryExamples useMemo to collect example summaries.'
  )
  assert.match(
    source,
    /tierSummaryExamples[\s\S]*tier_summary/,
    'tierSummaryExamples should pull from offering.tier_summary arrays.'
  )
  assert.match(
    source,
    /(summaries\.length\s*<\s*4|\.slice\(\s*0\s*,\s*4\s*\))/,
    'Tier summary examples list should be capped at roughly four items.'
  )
})

test('Services tab renders a guidance panel with tier summary examples', () => {
  const source = loadSource()
  assert.match(
    source,
    /Service tier basics/,
    'Guidance panel headline should introduce service tier basics.'
  )
  assert.match(
    source,
    /tierSummaryExamples\s*\.map\(\s*\(summary/,
    'Guidance panel should iterate over tier summary examples.'
  )
  assert.match(
    source,
    /Stripe sync runs automatically/,
    'Guidance panel should remind chefs that Stripe sync runs automatically.'
  )
})

test('Service cards use the backend-provided service_type_label when available', () => {
  const source = loadSource()
  assert.match(
    source,
    /offering\.service_type_label/,
    'Offering cards should prefer offering.service_type_label over local lookup helpers.'
  )
})

test('ChefDashboard targets the services API namespace for offerings and tiers', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+SERVICES_ROOT\s*=\s*['"]\/services['"]/,
    'Expected SERVICES_ROOT to point at the /services namespace.'
  )
  assert.match(
    source,
    /\$\{SERVICES_ROOT\}\/my\/offerings\//,
    'Expected ChefDashboard to load offerings from /services/my/offerings/.'
  )
  assert.match(
    source,
    /\$\{SERVICES_ROOT\}\/offerings\//,
    'Expected ChefDashboard to reference /services/offerings/.'
  )
  assert.match(
    source,
    /\$\{SERVICES_ROOT\}\/tiers\//,
    'Expected ChefDashboard to reference /services/tiers/.'
  )
})

test('Offering cards surface tier summaries ahead of detailed tier cards', () => {
  const source = loadSource()
  assert.match(
    source,
    /Tier overview/,
    'Offering card should label the tier summary list as a Tier overview section.'
  )
  assert.match(
    source,
    /offering\.tier_summary/,
    'Tier overview list should be backed by offering.tier_summary data.'
  )
})

test('Tier cards translate Stripe sync metadata into friendly status messages', () => {
  const source = loadSource()
  ;['Stripe sync successful', 'Stripe sync failed', 'Stripe sync pending'].forEach(label => {
    assert.match(
      source,
      new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
      `Expected tier cards to include the friendly status label: ${label}.`
    )
  })
  assert.match(
    source,
    /tier\.last_price_sync_error/,
    'Tier sync error copy should reference last_price_sync_error when present.'
  )
})

test('ChefDashboard no longer renders the service order tester card', () => {
  const source = loadSource()
  assert.doesNotMatch(
    source,
    /Service order tester/,
    'Service order tester card should be removed from the dashboard.'
  )
})

test('Tier form includes inline helper copy about household ranges, billing, and Stripe linkage', () => {
  const source = loadSource()
  assert.match(
    source,
    /Household range defines how many people each tier covers\./,
    'Tier form should explain how household ranges work.'
  )
  assert.match(
    source,
    /Recurring tiers automatically handle future invoices\./,
    'Tier form should explain recurring billing expectations.'
  )
  assert.match(
    source,
    /Stripe creates or updates prices after you save a tier\./,
    'Tier form should clarify how Stripe linkage works.'
  )
})

test('ChefDashboard loads service orders via the services API', () => {
  const source = loadSource()
  assert.match(
    source,
    /\$\{SERVICES_ROOT\}\/my\/orders\//,
    'Expected ChefDashboard to fetch service orders from /services/my/orders/.'
  )
})

test('ChefDashboard surfaces a dedicated service orders list', () => {
  const source = loadSource()
  assert.match(
    source,
    /Service orders/,
    'Service orders section heading should be visible.'
  )
  assert.match(
    source,
    /serviceOrders\.length/,
    'Service orders list should be backed by serviceOrders state.'
  )
})
