import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const mapPanelPath = resolve('src/components/MapPanel.jsx')
const packageJsonPath = resolve('package.json')

function loadMapPanel(){
  return readFileSync(mapPanelPath, 'utf8')
}

test('MapPanel Overpass query requests JSON and trims whitespace', () => {
  const source = loadMapPanel()
  assert.match(
    source,
    /\[out:json\]\[timeout:\d+]/,
    'Expected the Overpass query to explicitly request JSON output.'
  )
  assert.match(
    source,
    /body:\s*q\.trim\(\)/,
    'Expected the Overpass request body to trim whitespace so the query begins with [out:json].'
  )
})

test('package.json pins vulnerable Overpass transitive dependencies', () => {
  const pkg = JSON.parse(readFileSync(packageJsonPath, 'utf8'))
  assert.ok(pkg.overrides, 'Expected package.json to define overrides for vulnerable transitives.')
  const requiredPins = [
    '@xmldom/xmldom',
    'xmldom',
    'geojson-rewind',
    '@mapbox/geojson-rewind',
    'minimist'
  ]
  for (const key of requiredPins){
    assert.ok(Object.prototype.hasOwnProperty.call(pkg.overrides, key), `Expected override for ${key} to mitigate the audit warning.`)
  }
})
