/**
 * Sous Chef API Client
 * 
 * Client functions for interacting with the Sous Chef AI assistant API.
 */

import { api, refreshAccessToken } from '../api'

const SOUS_CHEF_BASE = '/chefs/api/me/sous-chef'

/**
 * Stream a message to the Sous Chef assistant.
 * 
 * @param {Object} params
 * @param {number} params.familyId - The family ID (customer or lead)
 * @param {string} params.familyType - 'customer' or 'lead'
 * @param {string} params.message - The message to send
 * @param {function} params.onText - Callback for text chunks
 * @param {function} params.onToolCall - Callback for tool call events
 * @param {function} params.onComplete - Callback when streaming completes
 * @param {function} params.onError - Callback for errors
 * @param {AbortSignal} params.signal - Optional abort signal
 * @returns {Promise<void>}
 */
export async function streamSousChefMessage({
  familyId,
  familyType,
  message,
  onText,
  onToolCall,
  onToolResult,
  onComplete,
  onError,
  signal
}) {
  try {
    // Refresh token before streaming
    try {
      await refreshAccessToken()
    } catch {
      // Ignore refresh errors
    }
    
    const token = localStorage.getItem('accessToken') || ''
    
    const response = await fetch(`${SOUS_CHEF_BASE}/stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        family_id: familyId,
        family_type: familyType,
        message
      }),
      credentials: 'include',
      signal
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || `Request failed: ${response.status}`)
    }
    
    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      
      // Parse SSE events
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const chunk = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        
        const lines = chunk.split('\n')
        for (const line of lines) {
          const trimmed = line.trim()
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6)
            try {
              const event = JSON.parse(data)
              processEvent(event, { onText, onToolCall, onToolResult, onComplete, onError })
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    }
    
    // Ensure completion callback is called
    if (onComplete) onComplete()
    
  } catch (error) {
    if (error.name !== 'AbortError') {
      if (onError) onError(error)
    }
  }
}

/**
 * Process a streaming event.
 */
function processEvent(event, callbacks) {
  const { onText, onToolCall, onToolResult, onComplete, onError } = callbacks
  const type = event?.type
  
  switch (type) {
    case 'text':
      if (onText && event.content) {
        onText(event.content)
      }
      break
      
    case 'response.function_call':
      if (onToolCall) {
        onToolCall({
          name: event.name,
          arguments: event.arguments,
          callId: event.call_id
        })
      }
      break
      
    case 'tool_result':
      if (onToolResult && event.name !== 'response.render') {
        onToolResult({
          name: event.name,
          output: event.output,
          callId: event.tool_call_id
        })
      }
      break
      
    case 'response.completed':
      if (onComplete) onComplete()
      break
      
    case 'error':
      if (onError) onError(new Error(event.message || 'Unknown error'))
      break
  }
}

/**
 * Send a message and get a complete response (non-streaming).
 * 
 * @param {Object} params
 * @param {number} params.familyId - The family ID
 * @param {string} params.familyType - 'customer' or 'lead'
 * @param {string} params.message - The message to send
 * @returns {Promise<Object>} The response object
 */
export async function sendSousChefMessage({ familyId, familyType, message }) {
  const response = await api.post(`${SOUS_CHEF_BASE}/message/`, {
    family_id: familyId,
    family_type: familyType,
    message
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Send a message and get a structured JSON response.
 * Uses OpenAI's structured output for consistent formatting.
 * 
 * @param {Object} params
 * @param {number} params.familyId - The family ID
 * @param {string} params.familyType - 'customer' or 'lead'
 * @param {string} params.message - The message to send
 * @returns {Promise<Object>} Response with content.blocks array
 */
export async function sendStructuredMessage({ familyId, familyType, message }) {
  const response = await api.post(`${SOUS_CHEF_BASE}/structured/`, {
    family_id: familyId,
    family_type: familyType,
    message
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Start a new conversation for a family.
 * 
 * @param {number} familyId - The family ID
 * @param {string} familyType - 'customer' or 'lead'
 * @returns {Promise<Object>}
 */
export async function newSousChefConversation(familyId, familyType) {
  const response = await api.post(`${SOUS_CHEF_BASE}/new-conversation/`, {
    family_id: familyId,
    family_type: familyType
  }, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get conversation history for a family.
 * 
 * @param {number} familyId - The family ID
 * @param {string} familyType - 'customer' or 'lead'
 * @returns {Promise<Object>}
 */
export async function getSousChefHistory(familyId, familyType) {
  const response = await api.get(`${SOUS_CHEF_BASE}/history/${familyType}/${familyId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

/**
 * Get family context summary.
 * 
 * @param {number} familyId - The family ID
 * @param {string} familyType - 'customer' or 'lead'
 * @returns {Promise<Object>}
 */
export async function getFamilyContext(familyId, familyType) {
  const response = await api.get(`${SOUS_CHEF_BASE}/context/${familyType}/${familyId}/`, {
    skipUserId: true,
    withCredentials: true
  })
  return response?.data
}

