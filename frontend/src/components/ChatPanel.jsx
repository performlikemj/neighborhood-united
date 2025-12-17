import React, { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import { useMessaging } from '../context/MessagingContext.jsx'
import useWebSocket from '../hooks/useWebSocket.js'

/** Photo with fallback placeholder - reusable for different sizes */
function PhotoWithFallback({ src, alt, className, placeholderClass }) {
  const [failed, setFailed] = useState(false)
  
  if (!src || failed) {
    return (
      <div className={placeholderClass}>
        <i className="fa-solid fa-user"></i>
      </div>
    )
  }
  
  return (
    <img 
      src={src} 
      alt={alt} 
      className={className}
      onError={() => setFailed(true)}
    />
  )
}

/**
 * ChatPanel - Slide-out chat panel for messaging
 * 
 * Supports real-time messaging via WebSocket with REST fallback.
 * Includes conversation switcher for easy navigation between chats.
 */
export default function ChatPanel({ isOpen, onClose, conversationId, recipientName, recipientPhoto, onSwitchConversation }) {
  const { user } = useAuth()
  const { markConversationRead, updateConversationWithMessage, sendMessage: sendMessageRest, conversations, fetchConversations } = useMessaging()
  
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const [typingUsers, setTypingUsers] = useState(new Set())
  const [showConversationList, setShowConversationList] = useState(false)
  
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const typingTimeoutRef = useRef(null)
  const conversationListRef = useRef(null)

  // Scroll to bottom of messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Handle new message from WebSocket
  const handleNewMessage = useCallback((message) => {
    setMessages(prev => {
      // Avoid duplicates
      if (prev.find(m => m.id === message.id)) {
        return prev
      }
      return [...prev, message]
    })
    scrollToBottom()
    updateConversationWithMessage(conversationId, message)
    
    // Mark as read if panel is open
    if (isOpen) {
      markConversationRead(conversationId)
    }
  }, [conversationId, isOpen, markConversationRead, scrollToBottom, updateConversationWithMessage])

  // Handle typing indicator
  const handleTyping = useCallback((userId, isTyping) => {
    setTypingUsers(prev => {
      const next = new Set(prev)
      if (isTyping) {
        next.add(userId)
      } else {
        next.delete(userId)
      }
      return next
    })
  }, [])

  // Handle read receipt
  const handleRead = useCallback((readerId) => {
    // Update messages to show as read
    if (readerId !== user?.id) {
      setMessages(prev => prev.map(m => ({
        ...m,
        is_read: true
      })))
    }
  }, [user])

  // WebSocket connection
  const {
    isConnected,
    isConnecting,
    error: wsError,
    sendMessage: wsSendMessage,
    sendTyping,
    sendRead,
  } = useWebSocket(isOpen ? conversationId : null, {
    onMessage: handleNewMessage,
    onTyping: handleTyping,
    onRead: handleRead,
    autoConnect: isOpen && !!conversationId,
  })

  // Fetch initial messages
  const fetchMessages = useCallback(async () => {
    if (!conversationId) return
    
    setLoading(true)
    setError(null)
    
    try {
      const resp = await api.get(`/messaging/api/conversations/${conversationId}/`)
      setMessages(resp.data.messages || [])
      scrollToBottom()
    } catch (err) {
      console.error('Failed to fetch messages:', err)
      setError('Unable to load messages')
    } finally {
      setLoading(false)
    }
  }, [conversationId, scrollToBottom])

  // Load messages when panel opens
  useEffect(() => {
    if (isOpen && conversationId) {
      fetchMessages()
      markConversationRead(conversationId)
    }
  }, [isOpen, conversationId, fetchMessages, markConversationRead])

  // Scroll to bottom when messages change
  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom()
    }
  }, [messages, scrollToBottom])

  // Focus input when panel opens and fetch conversations
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
      // Fetch conversations for the switcher
      fetchConversations()
    } else {
      setShowConversationList(false)
    }
  }, [isOpen, fetchConversations])

  // Close conversation list when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (conversationListRef.current && !conversationListRef.current.contains(e.target)) {
        setShowConversationList(false)
      }
    }
    if (showConversationList) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showConversationList])

  // Handle input change with typing indicator
  const handleInputChange = (e) => {
    setInputValue(e.target.value)
    
    // Send typing indicator
    if (isConnected) {
      sendTyping(true)
      
      // Clear previous timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
      }
      
      // Stop typing after 2 seconds of inactivity
      typingTimeoutRef.current = setTimeout(() => {
        sendTyping(false)
      }, 2000)
    }
  }

  // Send message
  const handleSend = async () => {
    const content = inputValue.trim()
    if (!content || sending) return
    
    setSending(true)
    setInputValue('')
    
    // Stop typing indicator
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current)
    }
    sendTyping(false)
    
    // Optimistic update
    const tempMessage = {
      id: `temp-${Date.now()}`,
      sender_id: user?.id,
      sender_type: user?.is_chef ? 'chef' : 'customer',
      content,
      sent_at: new Date().toISOString(),
      is_read: false,
      pending: true,
    }
    setMessages(prev => [...prev, tempMessage])
    scrollToBottom()
    
    try {
      // Try WebSocket first, fall back to REST
      if (isConnected && wsSendMessage(content)) {
        // Message sent via WebSocket - server will broadcast back
        // Remove temp message when real one arrives (handled in handleNewMessage)
      } else {
        // REST fallback
        const message = await sendMessageRest(conversationId, content)
        setMessages(prev => prev.filter(m => m.id !== tempMessage.id).concat(message))
      }
    } catch (err) {
      console.error('Failed to send message:', err)
      // Remove temp message and show error
      setMessages(prev => prev.filter(m => m.id !== tempMessage.id))
      showToast('Failed to send message', 'error')
    } finally {
      setSending(false)
    }
  }

  // Handle Enter key
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const showToast = (text, tone) => {
    try {
      window.dispatchEvent(new CustomEvent('global-toast', { detail: { text, tone } }))
    } catch {}
  }

  const formatTime = (dateStr) => {
    const date = new Date(dateStr)
    const now = new Date()
    const isToday = date.toDateString() === now.toDateString()
    
    if (isToday) {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    }
    
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    })
  }

  if (!isOpen) return null

  return (
    <>
      <div className="chat-panel-overlay" onClick={onClose} />
      <aside className="chat-panel" role="dialog" aria-label="Chat">
        {/* Header */}
        <div className="chat-panel-header">
          <div className="chat-recipient-wrapper" ref={conversationListRef}>
            <button 
              className="chat-recipient" 
              onClick={() => onSwitchConversation && setShowConversationList(v => !v)}
              title={onSwitchConversation ? "Switch conversation" : undefined}
              style={{ cursor: onSwitchConversation ? 'pointer' : 'default' }}
            >
              <PhotoWithFallback 
                src={recipientPhoto} 
                alt={recipientName} 
                className="chat-recipient-photo"
                placeholderClass="chat-recipient-placeholder"
              />
              <div className="chat-recipient-info">
                <div className="chat-recipient-name">
                  {recipientName}
                  {onSwitchConversation && conversations.length > 1 && (
                    <i className={`fa-solid fa-chevron-down chat-switch-icon ${showConversationList ? 'open' : ''}`}></i>
                  )}
                </div>
                {/* Only show status when connected (real-time) */}
                {isConnected && (
                  <div className="chat-status online">
                    <i className="fa-solid fa-circle" style={{fontSize: '6px', marginRight: '4px'}}></i>
                    Real-time
                  </div>
                )}
              </div>
            </button>

            {/* Conversation switcher dropdown */}
            {showConversationList && onSwitchConversation && (
              <div className="chat-conversation-list">
                <div className="chat-conversation-list-header">Recent Chats</div>
                {conversations.length === 0 ? (
                  <div className="chat-conversation-empty">No conversations yet</div>
                ) : (
                  conversations.map(conv => {
                    // Determine the other party's info based on current user role
                    const isCustomer = conv.customer === user?.id
                    const otherName = isCustomer ? conv.chef_name : conv.customer_name
                    const otherPhoto = isCustomer ? conv.chef_photo : conv.customer_photo
                    const isActive = conv.id === conversationId
                    
                    return (
                      <button
                        key={conv.id}
                        className={`chat-conversation-item ${isActive ? 'active' : ''}`}
                        onClick={() => {
                          if (!isActive) {
                            onSwitchConversation(conv.id, otherName, otherPhoto)
                          }
                          setShowConversationList(false)
                        }}
                      >
                        <PhotoWithFallback 
                          src={otherPhoto} 
                          alt={otherName}
                          className="chat-conv-photo"
                          placeholderClass="chat-conv-photo-placeholder"
                        />
                        <div className="chat-conv-info">
                          <div className="chat-conv-name">{otherName}</div>
                          {conv.last_message_preview && (
                            <div className="chat-conv-preview">{conv.last_message_preview}</div>
                          )}
                        </div>
                        {conv.unread_count > 0 && (
                          <span className="chat-conv-unread">{conv.unread_count}</span>
                        )}
                      </button>
                    )
                  })
                )}
              </div>
            )}
          </div>
          <button className="chat-panel-close" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-times"></i>
          </button>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {loading && (
            <div className="chat-loading">
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <p>Loading messages...</p>
            </div>
          )}

          {error && (
            <div className="chat-error">
              <p>{error}</p>
              <button className="btn btn-outline btn-sm" onClick={fetchMessages}>
                Try Again
              </button>
            </div>
          )}

          {!loading && !error && messages.length === 0 && (
            <div className="chat-empty">
              <i className="fa-regular fa-comment-dots"></i>
              <p>No messages yet</p>
              <p className="muted">Start the conversation!</p>
            </div>
          )}

          {!loading && !error && messages.length > 0 && (
            <div className="messages-list">
              {messages.map((message, index) => {
                // Check both sender and sender_id for compatibility
                const senderId = message.sender_id ?? message.sender
                const isOwn = senderId === user?.id
                const showDate = index === 0 || 
                  new Date(message.sent_at).toDateString() !== 
                  new Date(messages[index - 1].sent_at).toDateString()
                
                // Show sender name for "other" messages
                const prevMessage = messages[index - 1]
                const prevSenderId = prevMessage?.sender_id ?? prevMessage?.sender
                const showSenderName = !isOwn && (index === 0 || prevSenderId !== senderId || showDate)
                
                return (
                  <React.Fragment key={message.id}>
                    {showDate && (
                      <div className="message-date-divider">
                        {new Date(message.sent_at).toLocaleDateString('en-US', {
                          weekday: 'long',
                          month: 'short',
                          day: 'numeric'
                        })}
                      </div>
                    )}
                    <div className={`message-bubble ${isOwn ? 'own' : 'other'} ${message.pending ? 'pending' : ''}`}>
                      {showSenderName && message.sender_name && (
                        <div className="message-sender-name">{message.sender_name}</div>
                      )}
                      <div className="message-content">{message.content}</div>
                      <div className="message-meta">
                        <span className="message-time">{formatTime(message.sent_at)}</span>
                        {isOwn && (
                          <span className="message-status">
                            {message.pending ? (
                              <i className="fa-solid fa-clock"></i>
                            ) : message.is_read ? (
                              <i className="fa-solid fa-check-double"></i>
                            ) : (
                              <i className="fa-solid fa-check"></i>
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  </React.Fragment>
                )
              })}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Typing indicator */}
          {typingUsers.size > 0 && (
            <div className="typing-indicator">
              <span className="typing-dots">
                <span></span><span></span><span></span>
              </span>
              {recipientName} is typing...
            </div>
          )}
        </div>

        {/* Input */}
        <div className="chat-input-container">
          {wsError && !isConnected && (
            <div className="chat-ws-error">
              <i className="fa-solid fa-exclamation-triangle"></i>
              {wsError}
            </div>
          )}
          <div className="chat-input-wrapper">
            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Type a message..."
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={sending}
            />
            <button
              className="chat-send-btn"
              onClick={handleSend}
              disabled={!inputValue.trim() || sending}
            >
              {sending ? (
                <span className="spinner-sm"></span>
              ) : (
                <i className="fa-solid fa-paper-plane"></i>
              )}
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}


