import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chefDashboardPath = resolve('src/pages/ChefDashboard.jsx')
const stylesPath = resolve('src/styles.css')

function loadFile(path){
  return readFileSync(path, 'utf8')
}

test('Chef Dashboard tablist uses scrollable segment control', () => {
  const source = loadFile(chefDashboardPath)
  const pattern = /className="seg-control[^"]*seg-scroll/
  assert.match(
    source,
    pattern,
    'Expected ChefDashboard tablist to include the seg-scroll class so it can scroll horizontally.'
  )
})

test('Scrollable segment control styles enable horizontal overflow', () => {
  const styles = loadFile(stylesPath)
  const blockMatch = styles.match(/\.seg-control\.seg-scroll\s*\{[^}]+\}/)
  assert.ok(blockMatch, 'Expected styles.css to define .seg-control.seg-scroll rules.')

  const rules = blockMatch[0]
  assert.match(rules, /overflow-x:\s*auto/, 'seg-scroll should allow horizontal scrolling via overflow-x: auto;')
  assert.match(rules, /flex-wrap:\s*nowrap/, 'seg-scroll should prevent wrapping so tabs scroll instead of stacking.')
})
