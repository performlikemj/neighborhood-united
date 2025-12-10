import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chefDashboardPath = resolve('src/pages/ChefDashboard.jsx')
const stylesPath = resolve('src/styles.css')

function loadFile(path){
  return readFileSync(path, 'utf8')
}

test('Chef Dashboard uses sidebar navigation', () => {
  const source = loadFile(chefDashboardPath)
  // ChefDashboard uses a sidebar navigation pattern with chef-nav class
  const pattern = /className="chef-nav"/
  assert.match(
    source,
    pattern,
    'Expected ChefDashboard to use chef-nav sidebar navigation.'
  )
})

test('Chef Dashboard sidebar has proper accessibility attributes', () => {
  const source = loadFile(chefDashboardPath)
  // Should have role="navigation" and aria-label for accessibility
  assert.match(source, /role="navigation"/, 'Sidebar nav should have role="navigation"')
  assert.match(source, /aria-label=/, 'Sidebar nav should have aria-label for accessibility')
})
