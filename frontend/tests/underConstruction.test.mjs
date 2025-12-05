import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const underConstructionPath = resolve('src/pages/UnderConstruction.jsx')
const appPath = resolve('src/App.jsx')

function load(filePath){
  return readFileSync(filePath, 'utf8')
}

test('UnderConstruction page surfaces the temporary downtime message', () => {
  const source = load(underConstructionPath)
  assert.match(
    source,
    /under construction; we're cooking up something good/i,
    'Expected UnderConstruction to include the promised under-construction message.'
  )
})

test('App routes root to Home and wildcard to NotFound (app is live)', () => {
  const source = load(appPath)
  assert.match(
    source,
    /<Route[^>]+path=["']\/["'][^>]*element=\{<Home/,
    'Expected App to route "/" to Home now that the app is live.'
  )
  assert.match(
    source,
    /<Route[^>]+path=["']\*["'][^>]*element=\{<NotFound/,
    'Expected App to route unknown paths to NotFound.'
  )
})
