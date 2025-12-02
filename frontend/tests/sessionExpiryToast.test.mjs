import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const apiPath = resolve('src/api.js')

function loadSource(){
  return readFileSync(apiPath, 'utf8')
}

test('API client surfaces a toast before forcing re-authentication', () => {
  const source = loadSource()
  assert.match(
    source,
    /window\.dispatchEvent\(\s*new\s+CustomEvent\('global-toast',[\s\S]*?tone:\s*'error'[\s\S]*?'Session expired\. Please log in again\.'/,
    'Expected the API client to dispatch an error toast instructing the user to log in again before redirecting.'
  )
  assert.match(
    source,
    /window\.dispatchEvent[\s\S]*window\.location\.href\s*=\s*['"]\/login['"]/,
    'The toast should be emitted prior to redirecting users back to the login page.'
  )
})
