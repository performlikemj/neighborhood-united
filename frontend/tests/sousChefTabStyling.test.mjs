import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dashboardPath = resolve('src/pages/ChefDashboard.jsx')
const stylesPath = resolve('src/styles.css')

function load(path) {
  return readFileSync(path, 'utf8')
}

test('Sous Chef tab uses structured classes instead of inline layout', () => {
  const src = load(dashboardPath)
  assert.match(src, /className=\"sous-chef-tab\"/, 'Sous Chef tab should be wrapped in sous-chef-tab class.')
  assert.match(src, /className=\"sous-chef-grid\"/, 'Sous Chef layout should use sous-chef-grid for spacing.')
  assert.match(src, /className=\"sous-chef-chat-shell\"/, 'Chat wrapper should use dedicated shell class.')
})

test('Sous Chef tab has dark-friendly card styling tokens', () => {
  const css = load(stylesPath)
  const block = css.match(/\.sous-chef-tab\s*\{[^}]+\}/)?.[0] || ''
  assert.ok(block, 'Expected .sous-chef-tab styles block in styles.css.')
  assert.match(block, /--bg-card:\s*var\(--surface/, 'Sous Chef tab should seed --bg-card token to themed surface.')
  assert.match(block, /--border-color:\s*var\(--border/, 'Sous Chef tab should seed --border-color token.')
})

test('Sous Chef chat shell enforces min-height and border', () => {
  const css = load(stylesPath)
  const block = css.match(/\.sous-chef-chat-shell\s*\{[^}]+\}/)?.[0] || ''
  assert.ok(block, 'Expected .sous-chef-chat-shell styles.')
  assert.match(block, /min-height:\s*520px/, 'Chat shell should reserve vertical space.')
  assert.match(block, /border:\s*1px solid var\(--border/, 'Chat shell should use themed border.')
})
