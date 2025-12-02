import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const galleryPath = resolve('src/pages/ChefGallery.jsx')

function loadGallery(){
  return readFileSync(galleryPath, 'utf8')
}

test('ChefGallery preselects photo based on query parameter', () => {
  const source = loadGallery()
  assert.match(
    source,
    /useLocation\(/,
    'Expected ChefGallery to access the current location for query params.'
  )
  assert.match(
    source,
    /new URLSearchParams\(location\.search\)/,
    'Expected ChefGallery to parse the photo query parameter.'
  )
  assert.match(
    source,
    /photoParam\s*=\s*params\.get\('photo'\)/,
    'Expected ChefGallery to read the `photo` query value.'
  )
  assert.match(
    source,
    /let\s+nextIndex\s*=\s*photos\.findIndex/,
    'Expected ChefGallery to derive a candidate index from the query parameter.'
  )
  assert.match(
    source,
    /if \(nextIndex !== lightboxIndex\)\s*{\s*setLightboxIndex\(nextIndex\)/,
    'Expected ChefGallery to update the lightbox index when the derived index changes.'
  )
})
