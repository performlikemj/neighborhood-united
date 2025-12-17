import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useAuth } from './AuthContext.jsx'

const MessagingContext = createContext()

export function useMessaging() {
  const context = useContext(MessagingContext)
  if (!context) {
    throw new Error('useMessaging must be used within MessagingProvider')
  }
  return context
}

/**
 * MessagingProvider - Global messaging state management
 * 
 * Provides:
 * - Unread message counts
 * - Conversation list
 * - Polling for unread counts
 */
export function MessagingProvider({ children }) {
  const { user } = useAuth()
  const [unreadCounts, setUnreadCounts] = useState({
    total: 0,
    customer: 0,
    chef: 0,
  })
  const [conversations, setConversations] = useState([])
  const [conversationsLoading, setConversationsLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch unread counts
  const fetchUnreadCounts = useCallback(async () => {
    if (!user) return
    
    try {
      const resp = await api.get('/messaging/api/unread-counts/')
      setUnreadCounts({
        total: resp.data.total_unread || 0,
        customer: resp.data.customer_conversations_unread || 0,
        chef: resp.data.chef_conversations_unread || 0,
      })
    } catch (err) {
      console.error('Failed to fetch unread counts:', err)
    }
  }, [user])

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    if (!user) return
    
    setConversationsLoading(true)
    setError(null)
    
    try {
      const resp = await api.get('/messaging/api/conversations/')
      setConversations(resp.data.conversations || [])
    } catch (err) {
      console.error('Failed to fetch conversations:', err)
      setError('Unable to load conversations')
    } finally {
      setConversationsLoading(false)
    }
  }, [user])

  // Get or create conversation with a chef
  const getOrCreateConversation = useCallback(async (chefId) => {
    try {
      const resp = await api.post(`/messaging/api/conversations/with-chef/${chefId}/`)
      const conversation = resp.data.conversation
      
      // Update local conversations list
      setConversations(prev => {
        const exists = prev.find(c => c.id === conversation.id)
        if (exists) {
          return prev.map(c => c.id === conversation.id ? conversation : c)
        }
        return [conversation, ...prev]
      })
      
      return conversation
    } catch (err) {
      console.error('Failed to get/create conversation:', err)
      throw err
    }
  }, [])

  // Mark conversation as read
  const markConversationRead = useCallback(async (conversationId) => {
    try {
      await api.post(`/messaging/api/conversations/${conversationId}/read/`)
      
      // Update local state
      setConversations(prev => prev.map(c => {
        if (c.id === conversationId) {
          return { ...c, unread_count: 0 }
        }
        return c
      }))
      
      // Refresh unread counts
      fetchUnreadCounts()
    } catch (err) {
      console.error('Failed to mark conversation as read:', err)
    }
  }, [fetchUnreadCounts])

  // Send message (REST fallback)
  const sendMessage = useCallback(async (conversationId, content) => {
    try {
      const resp = await api.post(`/messaging/api/conversations/${conversationId}/send/`, {
        content
      })
      return resp.data
    } catch (err) {
      console.error('Failed to send message:', err)
      throw err
    }
  }, [])

  // Update conversation when new message received (called from ChatPanel)
  const updateConversationWithMessage = useCallback((conversationId, message) => {
    setConversations(prev => {
      return prev.map(c => {
        if (c.id === conversationId) {
          return {
            ...c,
            last_message_at: message.sent_at,
            last_message_preview: message.content.substring(0, 255),
          }
        }
        return c
      }).sort((a, b) => {
        const dateA = a.last_message_at ? new Date(a.last_message_at) : new Date(0)
        const dateB = b.last_message_at ? new Date(b.last_message_at) : new Date(0)
        return dateB - dateA
      })
    })
  }, [])

  // Poll for unread counts every 30 seconds when user is logged in
  useEffect(() => {
    if (!user) {
      setUnreadCounts({ total: 0, customer: 0, chef: 0 })
      setConversations([])
      return
    }

    // Initial fetch
    fetchUnreadCounts()

    // Set up polling
    const interval = setInterval(fetchUnreadCounts, 30000)

    return () => clearInterval(interval)
  }, [user, fetchUnreadCounts])

  const value = {
    unreadCounts,
    totalUnread: unreadCounts.total,
    conversations,
    conversationsLoading,
    error,
    fetchConversations,
    fetchUnreadCounts,
    getOrCreateConversation,
    markConversationRead,
    sendMessage,
    updateConversationWithMessage,
  }

  return (
    <MessagingContext.Provider value={value}>
      {children}
    </MessagingContext.Provider>
  )
}

