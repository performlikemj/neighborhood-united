import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const hookPath = resolve('src/hooks/useWebSocket.js')

function loadSource(){
  return readFileSync(hookPath, 'utf8')
}

test('useWebSocket omits expired JWT tokens from the WS URL', () => {
  const source = loadSource()
  assert.match(
    source,
    /function\s+isJwtExpired\(|const\s+isJwtExpired\s*=\s*\(/,
    'Expected an isJwtExpired helper for JWT expiry detection.'
  )
  assert.match(
    source,
    /exp\s*\)?\s*<=\s*nowSec|nowSec\s*>=\s*exp/,
    'Expected expiry comparison against exp claim.'
  )
  assert.match(
    source,
    /tokenParam\s*=\s*token\s*&&\s*!isJwtExpired\(token\)\s*\?/, 
    'Expected WS URL to skip token when it is expired.'
  )
})
