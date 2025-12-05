import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const mainPath = resolve('src/main.jsx')

function loadMain(){
  return readFileSync(mainPath, 'utf8')
}

test('main.jsx wraps the app with a QueryClientProvider', () => {
  const source = loadMain()
  assert.match(
    source,
    /import\s+\{\s*QueryClient,\s*QueryClientProvider\s*\}\s+from\s+'@tanstack\/react-query'/,
    'main.jsx should import QueryClient and QueryClientProvider.'
  )
  assert.match(
    source,
    /const\s+queryClient\s*=\s*new\s+QueryClient\(/,
    'main.jsx should instantiate a QueryClient.'
  )
  assert.match(
    source,
    /<QueryClientProvider\s+client=\{queryClient\}>/,
    'Application tree should be wrapped in a QueryClientProvider.'
  )
})
