#!/usr/bin/env node
/**
 * API Path Audit Script
 * 
 * Validates that all frontend API paths are properly proxied by nginx.
 * Run this in CI to catch path mismatches before they hit production.
 * 
 * Usage: node scripts/audit-api-paths.mjs
 * 
 * SECURITY: This script runs locally/CI only. It does NOT expose paths externally
 * and should never be bundled into production builds.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const SRC_DIR = join(ROOT, 'src')
const NGINX_CONF = join(ROOT, 'nginx.conf')

// Extract proxy prefixes from nginx.conf
function extractNginxProxyPrefixes() {
  const nginxContent = readFileSync(NGINX_CONF, 'utf8')
  
  // Match: location ~ ^/(auth|meals|chefs|...)/ {
  // The pattern inside parens can contain letters, underscores, and pipe separators
  const locationMatch = nginxContent.match(/location\s+~\s+\^\/\(([^)]+)\)\//)
  if (!locationMatch) {
    console.error('❌ Could not find proxy location pattern in nginx.conf')
    console.error('   Expected format: location ~ ^/(prefix1|prefix2|...)/ {')
    process.exit(1)
  }
  
  const prefixes = locationMatch[1].split('|')
  return new Set(prefixes)
}

// Recursively get all JS/JSX files
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

// Extract API paths from source files
function extractApiPaths(files) {
  const paths = []
  
  // Patterns to match API calls
  const patterns = [
    // api.get('/path/'), api.post('/path/'), etc.
    /api\.(get|post|put|patch|delete)\s*\(\s*[`'"]([^`'"]+)[`'"]/g,
    // fetch('/path/')
    /fetch\s*\(\s*[`'"]([^`'"]+)[`'"]/g,
  ]
  
  for (const file of files) {
    const content = readFileSync(file, 'utf8')
    const relativePath = file.replace(ROOT, '')
    
    for (const pattern of patterns) {
      let match
      // Reset lastIndex for global regex
      pattern.lastIndex = 0
      
      while ((match = pattern.exec(content)) !== null) {
        // Get the path (last capture group)
        const apiPath = match[match.length - 1]
        
        // Skip external URLs
        if (apiPath.startsWith('http://') || apiPath.startsWith('https://')) {
          continue
        }
        
        // Skip template literals that are clearly dynamic
        if (apiPath.includes('${') && !apiPath.startsWith('/')) {
          continue
        }
        
        // Extract the prefix (first path segment after leading /)
        const pathMatch = apiPath.match(/^\/([a-z_-]+)\//)
        if (pathMatch) {
          paths.push({
            prefix: pathMatch[1],
            fullPath: apiPath,
            file: relativePath,
            line: content.substring(0, match.index).split('\n').length
          })
        }
      }
    }
  }
  
  return paths
}

// Validate paths against nginx prefixes
function validatePaths(apiPaths, nginxPrefixes) {
  const errors = []
  const warnings = []
  const checkedPrefixes = new Set()
  
  for (const { prefix, fullPath, file, line } of apiPaths) {
    checkedPrefixes.add(prefix)
    
    // Check if prefix is in nginx proxy rules
    if (!nginxPrefixes.has(prefix)) {
      // Check for common mistakes
      const underscoreVersion = prefix.replace(/-/g, '_')
      const hyphenVersion = prefix.replace(/_/g, '-')
      
      if (nginxPrefixes.has(underscoreVersion)) {
        errors.push({
          type: 'HYPHEN_UNDERSCORE_MISMATCH',
          message: `Path uses hyphen but nginx expects underscore`,
          path: fullPath,
          file,
          line,
          fix: `Change '${prefix}' to '${underscoreVersion}'`
        })
      } else if (nginxPrefixes.has(hyphenVersion)) {
        errors.push({
          type: 'UNDERSCORE_HYPHEN_MISMATCH', 
          message: `Path uses underscore but nginx expects hyphen`,
          path: fullPath,
          file,
          line,
          fix: `Change '${prefix}' to '${hyphenVersion}'`
        })
      } else {
        errors.push({
          type: 'MISSING_PROXY',
          message: `Path prefix '${prefix}' is not proxied by nginx`,
          path: fullPath,
          file,
          line,
          fix: `Add '${prefix}' to nginx proxy location pattern`
        })
      }
    }
  }
  
  // Check for unused nginx prefixes (informational)
  for (const prefix of nginxPrefixes) {
    if (!checkedPrefixes.has(prefix)) {
      warnings.push({
        type: 'UNUSED_PREFIX',
        message: `Nginx prefix '${prefix}' is not used by any frontend API call`
      })
    }
  }
  
  return { errors, warnings }
}

// Main execution
function main() {
  console.log('🔍 API Path Audit\n')
  console.log('Checking frontend API paths against nginx proxy configuration...\n')
  
  // Extract nginx prefixes
  const nginxPrefixes = extractNginxProxyPrefixes()
  console.log(`📋 Nginx proxy prefixes: ${[...nginxPrefixes].join(', ')}\n`)
  
  // Get all source files
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  console.log(`📁 Scanning ${sourceFiles.length} source files...\n`)
  
  // Extract API paths
  const apiPaths = extractApiPaths(sourceFiles)
  
  // Get unique prefixes found
  const uniquePrefixes = [...new Set(apiPaths.map(p => p.prefix))]
  console.log(`🔗 Found ${apiPaths.length} API calls with ${uniquePrefixes.length} unique prefixes\n`)
  
  // Validate
  const { errors, warnings } = validatePaths(apiPaths, nginxPrefixes)
  
  // Report results
  if (errors.length === 0) {
    console.log('✅ All API paths are properly proxied!\n')
  } else {
    console.log(`❌ Found ${errors.length} error(s):\n`)
    
    for (const error of errors) {
      console.log(`  ${error.type}`)
      console.log(`    Path: ${error.path}`)
      console.log(`    File: ${error.file}:${error.line}`)
      console.log(`    Fix:  ${error.fix}`)
      console.log()
    }
  }
  
  if (warnings.length > 0) {
    console.log(`⚠️  ${warnings.length} warning(s):\n`)
    for (const warning of warnings) {
      console.log(`  ${warning.type}: ${warning.message}`)
    }
    console.log()
  }
  
  // Exit with error code if there are errors
  if (errors.length > 0) {
    process.exit(1)
  }
  
  console.log('✨ Audit complete!')
}

main()
