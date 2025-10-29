import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appPath = resolve('src/App.jsx')

test('App no longer exposes the Family Poll route', () => {
  const source = readFileSync(appPath, 'utf8')
  assert.doesNotMatch(
    source,
    /Route\s+path=["']\/family-poll["']/,
    'Expected App to remove the /family-poll route.'
  )
  assert.doesNotMatch(
    source,
    /FamilyPoll from '\.\/pages\/FamilyPoll\.jsx'/,
    'Expected App to stop importing the FamilyPoll page.'
  )
})
