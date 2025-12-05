import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const clientPath = resolve('src/api/servicesClient.js')

function loadSource(){
  assert.ok(
    existsSync(clientPath),
    'Expected src/api/servicesClient.js to be created with the new services helpers.'
  )
  return readFileSync(clientPath, 'utf8')
}

test('services client exposes connection helper signatures', () => {
  const source = loadSource()
  assert.match(
    source,
    /export\s+async\s+function\s+listConnections\s*\(\s*\{\s*status/,
    'listConnections(status) helper should be exported.'
  )
  assert.match(
    source,
    /export\s+async\s+function\s+requestConnection\s*\(/,
    'requestConnection helper should be exported.'
  )
  assert.match(
    source,
    /export\s+async\s+function\s+respondConnection\s*\(\s*\{\s*connectionId/,
    'respondConnection({ connectionId, action }) helper should be exported.'
  )
  assert.match(
    source,
    /export\s+async\s+function\s+createOffering\s*\(\s*\{/,
    'createOffering helper should be exported.'
  )
  assert.match(
    source,
    /export\s+async\s+function\s+listOfferings\s*\(\s*\{/,
    'listOfferings helper should be exported.'
  )
})

test('services client targets the connections endpoints with credentials', () => {
  const source = loadSource()
  assert.match(
    source,
    /const\s+params\s*=\s*\{\s*\}/,
    'listConnections should start with an empty params object.'
  )
  assert.match(
    source,
    /if\s*\(\s*status\s*!=\s*null[^)]*\)\s*params\.status\s*=\s*status/,
    'listConnections should guard status and only send it when defined.'
  )
  assert.match(
    source,
    /throw\s+new\s+Error\(['"]requestConnection requires a chefId \(customer flow\) or customerId \(chef flow\)['"]\)/,
    'requestConnection should throw if neither chefId nor customerId are provided.'
  )
  assert.match(
    source,
    /const\s+resolvedChefId\s*=\s*chefId\s*\?\?\s*chefIdSnake\s*\?\?\s*null/,
    'requestConnection should resolve chefId from both camel and snake case inputs.'
  )
  assert.match(
    source,
    /const\s+resolvedCustomerId\s*=\s*customerId\s*\?\?\s*customerIdSnake\s*\?\?\s*customerUserId\s*\?\?\s*customerUserIdSnake\s*\?\?\s*chefUser\s*\?\?\s*chefUserSnake\s*\?\?\s*chefUserId\s*\?\?\s*chefUserIdSnake\s*\?\?\s*null/,
    'requestConnection should resolve customerId from multiple possible keys.'
  )
  assert.match(
    source,
    /const\s+hasChefId\s*=\s*resolvedChefId\s*!=\s*null\s*&&\s*resolvedChefId\s*!==\s*''/,
    'requestConnection should compute whether chefId is present.'
  )
  assert.match(
    source,
    /if\s*\(\s*hasChefId\)\s*payload\.chef_id\s*=\s*resolvedChefId/,
    'requestConnection should only include chef_id when present.'
  )
  assert.match(
    source,
    /api\.patch\(\s*`\/services\/connections\/\$\{connectionId\}\/`\s*,\s*\{\s*action/,
    'respondConnection should patch /services/connections/{id}/ with an action payload.'
  )
  assert.match(
    source,
    /withCredentials:\s*true/,
    'Service helpers should opt into sending credentials/cookies.'
  )
})

test('services client forwards target_customer_ids for offerings', () => {
  const source = loadSource()
  assert.match(
    source,
    /api\.post\(\s*['"]\/services\/offerings\/['"]\s*,\s*\{\s*[^}]*target_customer_ids/,
    'createOffering should post target_customer_ids alongside the offering payload.'
  )
  assert.match(
    source,
    /const\s+params\s*=\s*\{\s*\}/,
    'listOfferings should start with an empty params object.'
  )
  assert.match(
    source,
    /if\s*\(\s*chefId\s*!=\s*null[^)]*\)\s*params\.chef_id\s*=\s*chefId/,
    'listOfferings should guard optional chef_id filter.'
  )
  assert.match(
    source,
    /serviceType/,
    'listOfferings helper should accept a serviceType filter.'
  )
})
