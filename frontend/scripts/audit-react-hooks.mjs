#!/usr/bin/env node
/**
 * React Hooks Audit Script
 * 
 * Detects common anti-patterns in useCallback/useEffect that cause infinite loops:
 * 
 * 1. useCallback that sets state X and has X in its dependency array
 * 2. "hasFetched" refs that are only set on success, not on error
 * 3. useEffect with callbacks in deps that could be recreated frequently
 * 
 * Usage: node scripts/audit-react-hooks.mjs
 * 
 * SECURITY: This script runs locally/CI only and does not expose any code externally.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const ROOT = resolve(import.meta.dirname, '..')
const SRC_DIR = join(ROOT, 'src')

// Recursively get all JS/JSX files
function getAllSourceFiles(dir, files = []) {
  const entries = readdirSync(dir)
  
  for (const entry of entries) {
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    
    if (stat.isDirectory()) {
      getAllSourceFiles(fullPath, files)
    } else if (/\.(js|jsx)$/.test(entry)) {
      files.push(fullPath)
    }
  }
  
  return files
}

// Analyze a file for hook anti-patterns
function analyzeFile(filePath) {
  const content = readFileSync(filePath, 'utf8')
  const relativePath = filePath.replace(ROOT, '')
  const issues = []
  
  // Pattern 1: useCallback that sets state AND reads it (not via functional update)
  // This is specifically looking for the dangerous pattern where:
  // - State is in deps
  // - State is read (not just set)
  // - Setter doesn't use functional update form
  const useCallbackPattern = /useCallback\s*\(\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([\s\S]*?)\},\s*\[([^\]]*)\]\s*\)/g
  
  let match
  while ((match = useCallbackPattern.exec(content)) !== null) {
    const callbackBody = match[1]
    const depsArray = match[2]
    const lineNumber = content.substring(0, match.index).split('\n').length
    
    // Pattern 2: Check for refs only set in try block, not finally
    // This is the CRITICAL pattern that causes infinite retry loops
    if (callbackBody.includes('.current = true')) {
      const hasTryBlock = callbackBody.includes('try')
      const hasFinally = callbackBody.includes('finally')
      
      if (hasTryBlock) {
        // Check if ref assignment is inside try but not in finally
        const tryBlockMatch = callbackBody.match(/try\s*\{([\s\S]*?)\}\s*catch/)
        const finallyBlockMatch = callbackBody.match(/finally\s*\{([\s\S]*?)\}/)
        
        if (tryBlockMatch && tryBlockMatch[1].includes('.current = true')) {
          if (!finallyBlockMatch || !finallyBlockMatch[1].includes('.current = true')) {
            issues.push({
              type: 'REF_NOT_SET_ON_ERROR',
              severity: 'error',
              file: relativePath,
              line: lineNumber,
              message: `Ref is set to true only in try block - if API fails, retries may loop infinitely`,
              suggestion: `Move '.current = true' to the finally block so it runs regardless of success/failure`
            })
          }
        }
      }
    }
  }
  
  // Pattern 3: Look for state variables in useCallback deps that the callback also modifies
  // Focus on the exact pattern that caused our bug: array/object state in deps
  // that changes on every setState, causing callback recreation
  const dangerousStatePattern = /useCallback\s*\(\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{[\s\S]*?set(\w+)\s*\([^)]*\)[\s\S]*?\},\s*\[([^\]]*)\1[^\]]*\]\s*\)/gi
  
  while ((match = dangerousStatePattern.exec(content)) !== null) {
    const stateName = match[1]
    const lineNumber = content.substring(0, match.index).split('\n').length
    
    // Only flag if it looks like an array or object state (plural names, etc.)
    const looksLikeCollection = /s$|list|array|items|data|chefs|orders|addresses/i.test(stateName)
    
    if (looksLikeCollection) {
      issues.push({
        type: 'COLLECTION_STATE_IN_DEPS',
        severity: 'warning',
        file: relativePath,
        line: lineNumber,
        message: `useCallback modifies '${stateName}' state (likely array/object) and has it in deps`,
        suggestion: `Consider removing '${stateName}' from deps or use a ref to track if already fetched`
      })
    }
  }
  
  // Pattern 4: useEffect with fetch functions in deps
  const useEffectPattern = /useEffect\s*\(\s*\(\)\s*=>\s*\{[\s\S]*?(fetch\w+|load\w+)\s*\([\s\S]*?\},\s*\[([^\]]*)\]\s*\)/g
  
  while ((match = useEffectPattern.exec(content)) !== null) {
    const funcName = match[1]
    const depsArray = match[2]
    const lineNumber = content.substring(0, match.index).split('\n').length
    
    // Check if the function being called is also in deps
    if (depsArray.includes(funcName)) {
      issues.push({
        type: 'CALLBACK_IN_EFFECT_DEPS',
        severity: 'info',
        file: relativePath,
        line: lineNumber,
        message: `useEffect calls '${funcName}' and has it in deps - ensure the callback has stable identity`,
        suggestion: `Verify '${funcName}' useCallback deps don't cause unnecessary recreations`
      })
    }
  }
  
  return issues
}

// Main execution
function main() {
  console.log('🔍 React Hooks Audit\n')
  console.log('Checking for common hook anti-patterns that cause infinite loops...\n')
  
  // Get all source files
  const sourceFiles = getAllSourceFiles(SRC_DIR)
  console.log(`📁 Scanning ${sourceFiles.length} source files...\n`)
  
  // Analyze each file
  const allIssues = []
  for (const file of sourceFiles) {
    const issues = analyzeFile(file)
    allIssues.push(...issues)
  }
  
  // Group by severity
  const errors = allIssues.filter(i => i.severity === 'error')
  const warnings = allIssues.filter(i => i.severity === 'warning')
  const infos = allIssues.filter(i => i.severity === 'info')
  
  // Report results
  if (errors.length === 0 && warnings.length === 0) {
    console.log('✅ No critical hook anti-patterns detected!\n')
  }
  
  if (errors.length > 0) {
    console.log(`❌ ${errors.length} error(s) - likely infinite loops:\n`)
    for (const error of errors) {
      console.log(`  ${error.type}`)
      console.log(`    File: ${error.file}:${error.line}`)
      console.log(`    Issue: ${error.message}`)
      console.log(`    Fix: ${error.suggestion}`)
      console.log()
    }
  }
  
  if (warnings.length > 0) {
    console.log(`⚠️  ${warnings.length} warning(s) - potential issues:\n`)
    for (const warning of warnings) {
      console.log(`  ${warning.type}`)
      console.log(`    File: ${warning.file}:${warning.line}`)
      console.log(`    Issue: ${warning.message}`)
      console.log(`    Fix: ${warning.suggestion}`)
      console.log()
    }
  }
  
  if (infos.length > 0) {
    console.log(`ℹ️  ${infos.length} info item(s) - review recommended:\n`)
    for (const info of infos) {
      console.log(`  ${info.file}:${info.line} - ${info.message}`)
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
