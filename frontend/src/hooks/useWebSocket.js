import { useEffect, useRef, useState, useCallback } from 'react'

function decodeJwtPayload(token) {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(normalized.length + (4 - (normalized.length % 4 || 4)), '=')
    const json = atob(padded)
    return JSON.parse(json)
  } catch {
    return null
  }
}

function isJwtExpired(token, nowSec = Math.floor(Date.now() / 1000)) {
  if (!token) return false
  const payload = decodeJwtPayload(token)
  const exp = payload?.exp
  if (typeof exp !== 'number') return false
  return exp <= nowSec
}

/**
 * WebSocket hook for real-time chat connections.
 * 
 * Handles:
 * - Connection lifecycle (connect, disconnect, reconnect)
 * - Automatic reconnection with exponential backoff
 * - Message sending and receiving
 * - Connection state management
 * 
 * @param {string} conversationId - The ID of the conversation to connect to
 * @param {object} options - Configuration options
 * @param {function} options.onMessage - Callback for incoming messages
 * @param {function} options.onTyping - Callback for typing indicators
 * @param {function} options.onRead - Callback for read receipts
 * @param {function} options.onConnect - Callback when connected
 * @param {function} options.onDisconnect - Callback when disconnected
 * @returns {object} - WebSocket controls and state
 */
export default function useWebSocket(conversationId, options = {}) {
  const {
    onMessage,
    onTyping,
    onRead,
    onConnect,
    onDisconnect,
    autoConnect = true,
    maxRetries = 5,
  } = options

  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const retryCountRef = useRef(0)
  
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState(null)

  // Build WebSocket URL - connect to backend directly (not through SWA)
  const getWebSocketUrl = useCallback(() => {
    // Use VITE_API_BASE to get backend host, or fall back to same origin for dev
    const apiBase = import.meta.env.VITE_API_BASE || ''
    
    // Get JWT token for authentication
    const token = localStorage.getItem('accessToken')
    const tokenParam = token && !isJwtExpired(token) ? `?token=${encodeURIComponent(token)}` : ''
    
    if (apiBase) {
      // Convert http(s):// to ws(s)://
      const wsBase = apiBase.replace(/^http/, 'ws')
      return `${wsBase}/ws/chat/${conversationId}/${tokenParam}`
    }
    
    // Fallback for local dev (same origin)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws/chat/${conversationId}/${tokenParam}`
  }, [conversationId])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!conversationId || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setIsConnecting(true)
    setError(null)

    try {
      const url = getWebSocketUrl()
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('[WebSocket] Connected to', conversationId)
        setIsConnected(true)
        setIsConnecting(false)
        retryCountRef.current = 0
        onConnect?.()
      }

      wsRef.current.onclose = (event) => {
        console.log('[WebSocket] Disconnected', event.code, event.reason)
        setIsConnected(false)
        setIsConnecting(false)
        onDisconnect?.()

        // Attempt reconnection for abnormal closures
        if (event.code !== 1000 && event.code !== 4001 && event.code !== 4003) {
          attemptReconnect()
        }
      }

      wsRef.current.onerror = (event) => {
        console.error('[WebSocket] Error', event)
        setError('Connection error')
      }

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleMessage(data)
        } catch (err) {
          console.error('[WebSocket] Failed to parse message', err)
        }
      }
    } catch (err) {
      console.error('[WebSocket] Failed to connect', err)
      setError('Failed to connect')
      setIsConnecting(false)
      attemptReconnect()
    }
  }, [conversationId, getWebSocketUrl, onConnect, onDisconnect])

  // Handle incoming messages
  const handleMessage = useCallback((data) => {
    switch (data.type) {
      case 'message':
        onMessage?.(data.message)
        break
      case 'typing':
        onTyping?.(data.user_id, data.is_typing)
        break
      case 'read':
        onRead?.(data.reader_id)
        break
      case 'error':
        console.error('[WebSocket] Server error:', data.message)
        setError(data.message)
        break
      default:
        console.log('[WebSocket] Unknown message type:', data.type)
    }
  }, [onMessage, onTyping, onRead])

  // Attempt reconnection with exponential backoff
  const attemptReconnect = useCallback(() => {
    if (retryCountRef.current >= maxRetries) {
      console.log('[WebSocket] Max retries reached')
      setError('Unable to connect. Please refresh the page.')
      return
    }

    const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000)
    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${retryCountRef.current + 1})`)

    reconnectTimeoutRef.current = setTimeout(() => {
      retryCountRef.current++
      connect()
    }, delay)
  }, [connect, maxRetries])

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected')
      wsRef.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
  }, [])

  // Send a message
  const sendMessage = useCallback((content) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WebSocket] Cannot send message - not connected')
      return false
    }

    wsRef.current.send(JSON.stringify({
      type: 'message',
      content
    }))
    return true
  }, [])

  // Send typing indicator
  const sendTyping = useCallback((isTyping) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return
    }

    wsRef.current.send(JSON.stringify({
      type: 'typing',
      is_typing: isTyping
    }))
  }, [])

  // Send read receipt
  const sendRead = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return
    }

    wsRef.current.send(JSON.stringify({
      type: 'read'
    }))
  }, [])

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && conversationId) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [autoConnect, conversationId, connect, disconnect])

  return {
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    sendMessage,
    sendTyping,
    sendRead,
  }
}
