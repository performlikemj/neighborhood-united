const BLOCK_PATTERN = /Batch\s+(?:user\s+)?prompt:[\s\S]*?(?:Request\s+id:[^\n]*\n?)/gi

const LINE_PATTERNS = [
  /Return\s+JSON[\s\S]*?(?:\n|$)/gi,
  /PromptMealMap[\s\S]*?(?:\n|$)/gi,
  /Schema\s+(?:instructions|definition|guidelines):[\s\S]*?(?:\n|$)/gi,
  /(?:System|Developer)\s+prompt:[\s\S]*?(?:\n|$)/gi,
  /(?:User|Household|Family)\s+context:[\s\S]*?(?:\n|$)/gi,
  /Prompt\s+metadata:[\s\S]*?(?:\n|$)/gi,
  /Request\s+id:[^\n]*(?:\n|$)/gi
]

const LINE_FILTERS = [
  /batch\s+(?:ai\s+)?user\s+prompt/i,
  /return\s+json/i,
  /promptmealmap/i,
  /schema/i,
  /request\s+id/i,
  /system\s+prompt/i,
  /developer\s+prompt/i,
  /household\s+context/i,
  /user\s+context/i,
  /family\s+context/i,
  /prompt\s+metadata/i,
  /raw\s+ai\s+payload/i
]

function normalizeInput(value){
  if (value == null) return ''
  if (typeof value === 'string') return value
  try{ return String(value) }catch{ return '' }
}

export function stripPromptLeak(value){
  let text = normalizeInput(value)
  if (!text) return ''

  if (/Request\s+id:/i.test(text)){
    text = text.replace(BLOCK_PATTERN, '')
  } else {
    text = text.replace(/Batch\s+(?:user\s+)?prompt:[^\n]*(?:\n|$)/gi, '')
  }

  for (const pattern of LINE_PATTERNS){
    text = text.replace(pattern, '')
  }

  let lines = text.split(/\r?\n/)
  lines = lines.filter(line => {
    const trimmed = line.trim()
    if (!trimmed) return false
    return !LINE_FILTERS.some(re => re.test(trimmed))
  })
  if (!lines.length) return ''

  const joined = lines.join(' ').replace(/\s{2,}/g, ' ').trim()
  return joined
}

export function scrubPromptLeaks(value, seen = new WeakSet()){
  if (value == null) return value
  if (typeof value === 'string') return stripPromptLeak(value)
  if (typeof value !== 'object') return value

  if (value instanceof Date || value instanceof RegExp || value instanceof Set || value instanceof Map){
    return value
  }
  if (seen.has(value)) return value
  seen.add(value)

  if (Array.isArray(value)){
    for (let i = 0; i < value.length; i += 1){
      value[i] = scrubPromptLeaks(value[i], seen)
    }
    return value
  }

  for (const key of Object.keys(value)){
    value[key] = scrubPromptLeaks(value[key], seen)
  }
  return value
}

export function hasPromptLeak(value){
  const text = normalizeInput(value)
  if (!text) return false
  return LINE_FILTERS.some(re => re.test(text))
}
