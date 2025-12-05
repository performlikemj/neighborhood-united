import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const hookPath = resolve('src/hooks/useConnections.js')

function loadHook(){
  assert.ok(
    existsSync(hookPath),
    'Expected src/hooks/useConnections.js to be implemented for shared connection state.'
  )
  return readFileSync(hookPath, 'utf8')
}

test('useConnections hook wires up TanStack Query helpers', () => {
  const source = loadHook()
  assert.match(
    source,
    /from\s+'@tanstack\/react-query'/,
    'Hook should import helpers from @tanstack/react-query.'
  )
  assert.match(
    source,
    /export\s+function\s+useConnections\s*\(/,
    'useConnections should be exported.'
  )
  assert.match(
    source,
    /useQuery\(/,
    'Hook should rely on useQuery to load connections.'
  )
  assert.match(
    source,
    /useMutation\(/,
    'Hook should expose mutations via useMutation.'
  )
  assert.match(
    source,
    /queryClient\.setQueryData/,
    'Hook should optimistically update cached data.'
  )
})

test('useConnections derives helpful status flags and helpers', () => {
  const source = loadHook()
  ;['isPending', 'isAccepted', 'canAccept', 'canDecline', 'canEnd'].forEach(flag => {
    assert.match(
      source,
      new RegExp(flag),
      `Hook should expose the ${flag} derived property.`
    )
  })
  assert.match(
    source,
    /requestConnection:\s*requestMutation\.mutateAsync/,
    'Hook should surface a requestConnection mutation helper.'
  )
  assert.match(
    source,
    /respondToConnection:\s*respondMutation\.mutateAsync/,
    'Hook should surface a respondToConnection mutation helper.'
  )
})
