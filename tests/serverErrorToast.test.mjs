import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const apiPath = resolve('src/api.js')

function loadSource(){
  return readFileSync(apiPath, 'utf8')
}

test('API client surfaces a friendly toast for backend 500 errors', () => {
  const source = loadSource()
  assert.match(
    source,
    /status[\s\S]*>=\s*500[\s\S]*"We're having trouble processing your request\. Please try again soon\."/,
    'Expected a dedicated error toast for 500-level responses.'
  )
  assert.match(
    source,
    /export function buildErrorMessage[\s\S]*if \(typeof status === 'number' && status >= 500\)[\s\S]*return "We're having trouble processing your request\. Please try again soon\."/,
    'buildErrorMessage should normalize 500 responses to the friendly message.'
  )
})
