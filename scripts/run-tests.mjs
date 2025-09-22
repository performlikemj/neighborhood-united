#!/usr/bin/env node
import { spawn } from 'node:child_process'

const passthroughArgs = process.argv.slice(2).filter(arg => arg !== '--' && arg !== '--runInBand')

const child = spawn(process.execPath, ['--test', ...passthroughArgs], { stdio: 'inherit' })

child.on('exit', code => {
  if (code === null) {
    process.exit(1)
    return
  }
  process.exit(code)
})

child.on('error', err => {
  console.error(err)
  process.exit(1)
})
