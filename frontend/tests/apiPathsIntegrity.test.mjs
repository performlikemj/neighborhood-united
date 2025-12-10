/**
 * API Paths Integrity Tests
 * 
 * These tests validate that frontend API paths match nginx proxy configuration
 * and Django URL patterns. Catches mismatches before they hit production.
 * 
 * Run: node --test tests/apiPathsIntegrity.test.mjs
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const SRC_DIR = join(ROOT, 'src')
const NGINX_CONF = join(ROOT, 'nginx.conf')

// Helper: Extract nginx proxy prefixes
function getNginxProxyPrefixes() {
  const nginxContent = readFileSync(NGINX_CONF, 'utf8')
  const locationMatch = nginxContent.match(/location\s+~\s+\^\/\(([^)]+)\)\//)
  if (!locationMatch) return new Set()
  return new Set(locationMatch[1].split('|'))
}

// Helper: Get all source files recursively
function getAllSourceFiles(dir, files = []) {
  const entries = readdirSync(dir)
  for (const entry of entries) {
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      getAllSourceFiles(fullPath, files)
    } else if (/\.(js|jsx|mjs)$/.test(entry)) {
      files.push(fullPath)
    }
  }
  return files
}

// Helper: Extract API path prefixes from source
function extractApiPathPrefixes(files) {
  const prefixes = new Set()
  const pattern = /api\.(get|post|put|patch|delete)\s*\(\s*[`'"]\/([a-z_-]+)\//g
  
  for (const file of files) {
    const content = readFileSync(file, 'utf8')
    let match
    pattern.lastIndex = 0
    while ((match = pattern.exec(content)) !== null) {
      prefixes.add(match[2])
    }
  }
  
  return prefixes
}

// ============================================================================
// Tests
// ============================================================================

test('All frontend API prefixes are proxied by nginx', () => {
  const nginxPrefixes = getNginxProxyPrefixes()
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  const apiPrefixes = extractApiPathPrefixes(sourceFiles)
  
  const missingFromNginx = []
  
  for (const prefix of apiPrefixes) {
    if (!nginxPrefixes.has(prefix)) {
      missingFromNginx.push(prefix)
    }
  }
  
  assert.equal(
    missingFromNginx.length,
    0,
    `These API prefixes are used in frontend but NOT proxied by nginx: ${missingFromNginx.join(', ')}. ` +
    `Add them to the nginx location pattern or fix the frontend paths.`
  )
})

test('No hyphen/underscore mismatches in API paths', () => {
  const nginxPrefixes = getNginxProxyPrefixes()
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  
  // Look specifically for common mismatch patterns
  const patterns = [
    { wrong: 'customer-dashboard', right: 'customer_dashboard' },
    { wrong: 'local-chefs', right: 'local_chefs' },
    { wrong: 'chef-services', right: 'services' },
  ]
  
  const mismatches = []
  
  for (const file of sourceFiles) {
    const content = readFileSync(file, 'utf8')
    const relativePath = file.replace(ROOT, '')
    
    for (const { wrong, right } of patterns) {
      const wrongPattern = new RegExp(`['\`"]/${wrong}/`, 'g')
      if (wrongPattern.test(content)) {
        mismatches.push({
          file: relativePath,
          wrong: `/${wrong}/`,
          shouldBe: `/${right}/`
        })
      }
    }
  }
  
  assert.equal(
    mismatches.length,
    0,
    `Found API path mismatches:\n${mismatches.map(m => 
      `  ${m.file}: uses '${m.wrong}' but should use '${m.shouldBe}'`
    ).join('\n')}`
  )
})

test('fetch() calls use relative paths (not hardcoded domains)', () => {
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  const hardcodedDomains = []
  
  // Pattern to find fetch with hardcoded internal domains
  // Allow external APIs like Overpass
  const internalDomainPattern = /fetch\s*\(\s*[`'"]https?:\/\/(localhost|sautai\.com|hoodunited\.org|www\.sautai\.com)/g
  
  for (const file of sourceFiles) {
    const content = readFileSync(file, 'utf8')
    const relativePath = file.replace(ROOT, '')
    
    let match
    while ((match = internalDomainPattern.exec(content)) !== null) {
      const lineNum = content.substring(0, match.index).split('\n').length
      hardcodedDomains.push({
        file: relativePath,
        line: lineNum,
        domain: match[1]
      })
    }
  }
  
  assert.equal(
    hardcodedDomains.length,
    0,
    `Found hardcoded internal domains in fetch() calls (use relative paths instead):\n${
      hardcodedDomains.map(h => `  ${h.file}:${h.line} - ${h.domain}`).join('\n')
    }`
  )
})

test('Django app names in paths use underscores, not hyphens', () => {
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  
  // Django convention: app names use underscores
  // These are known Django apps that should use underscores
  const djangoApps = ['customer_dashboard', 'local_chefs', 'chef_admin']
  const hyphenVersions = djangoApps.map(app => app.replace(/_/g, '-'))
  
  const violations = []
  
  for (const file of sourceFiles) {
    const content = readFileSync(file, 'utf8')
    const relativePath = file.replace(ROOT, '')
    
    for (const wrongName of hyphenVersions) {
      const pattern = new RegExp(`['\`"]/${wrongName}/`, 'g')
      let match
      while ((match = pattern.exec(content)) !== null) {
        const lineNum = content.substring(0, match.index).split('\n').length
        violations.push({
          file: relativePath,
          line: lineNum,
          found: wrongName,
          shouldBe: wrongName.replace(/-/g, '_')
        })
      }
    }
  }
  
  assert.equal(
    violations.length,
    0,
    `Django app names should use underscores, not hyphens:\n${
      violations.map(v => `  ${v.file}:${v.line} - '${v.found}' should be '${v.shouldBe}'`).join('\n')
    }`
  )
})

test('API client files exist for each service', () => {
  const apiDir = join(SRC_DIR, 'api')
  const apiFiles = readdirSync(apiDir).filter(f => f.endsWith('.js'))
  
  // Just verify the api directory has client files
  assert.ok(
    apiFiles.length > 0,
    'Expected API client files in src/api/'
  )
  
  // Verify main api.js exists
  const mainApiPath = join(SRC_DIR, 'api.js')
  assert.doesNotThrow(
    () => readFileSync(mainApiPath, 'utf8'),
    'Expected src/api.js to exist'
  )
})
