import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chefDashboardPath = resolve('src/pages/ChefDashboard.jsx')

function loadFile(path){
  return readFileSync(path, 'utf8')
}

test('ChefDashboard public preview uses service area summary + modal', () => {
  const source = loadFile(chefDashboardPath)
  assert.match(
    source,
    /ServiceAreasModal/,
    'Expected ChefDashboard to import and render ServiceAreasModal for the public preview.'
  )
  assert.match(
    source,
    /getAreaSummary/,
    'Expected ChefDashboard to use getAreaSummary for preview service areas.'
  )
  assert.match(
    source,
    /Check Availability/,
    'Expected ChefDashboard preview to use a Check Availability button instead of listing all areas.'
  )
})
