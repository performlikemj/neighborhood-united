const STORAGE_KEY = 'serviceOrderIds'

function normalize(id){
  if (id == null) return null
  const str = String(id).trim()
  return str ? str : null
}

export function getStoredServiceOrderIds(){
  try{
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(normalize).filter(Boolean)
  }catch{}
  return []
}

export function rememberServiceOrderId(id){
  try{
    const normalized = normalize(id)
    if (!normalized) return
    const existing = getStoredServiceOrderIds()
    if (!existing.includes(normalized)){
      existing.push(normalized)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(existing))
    }
  }catch{}
}

export function removeServiceOrderId(id){
  try{
    const normalized = normalize(id)
    if (!normalized) return
    const filtered = getStoredServiceOrderIds().filter(entry => entry !== normalized)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
  }catch{}
}

export function replaceServiceOrderIds(ids){
  try{
    const normalized = Array.isArray(ids) ? ids.map(normalize).filter(Boolean) : []
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized))
  }catch{}
}

export const SERVICE_ORDER_STORAGE_KEY = STORAGE_KEY
