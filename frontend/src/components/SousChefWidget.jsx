/**
 * SousChefWidget Component
 * 
 * Floating chatbot-style widget for the Sous Chef AI assistant.
 * Lives in the bottom-right corner of the chef dashboard.
 * Expands to show family selector and chat interface.
 * Shows notifications when background tasks complete.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { CHEF_EMOJIS } from '../utils/emojis.js'
import FamilySelector from './FamilySelector.jsx'
import SousChefChat from './SousChefChat.jsx'
import { api } from '../api.js'
import { useSousChefNotifications } from '../contexts/SousChefNotificationContext.jsx'

export default function SousChefWidget({ 
  sousChefEmoji = '🧑‍🍳',
  onEmojiChange
}) {
  // Notification context
  let notifications = null
  try {
    notifications = useSousChefNotifications()
  } catch (e) {
    // Context not available
  }
  
  const [isOpen, setIsOpen] = useState(false)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [selectedFamily, setSelectedFamily] = useState({ 
    familyId: null, 
    familyType: 'customer', 
    familyName: null 
  })
  const [currentEmoji, setCurrentEmoji] = useState(sousChefEmoji)
  const [savingEmoji, setSavingEmoji] = useState(false)
  const [showToast, setShowToast] = useState(false)
  const [toastNotification, setToastNotification] = useState(null)
  const [pendingContext, setPendingContext] = useState(null)
  
  const widgetRef = useRef(null)
  const emojiPickerRef = useRef(null)
  const prevUnreadCount = useRef(0)

  // Sync emoji from props
  useEffect(() => {
    setCurrentEmoji(sousChefEmoji)
  }, [sousChefEmoji])

  // Close emoji picker when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (emojiPickerRef.current && !emojiPickerRef.current.contains(event.target)) {
        setShowEmojiPicker(false)
      }
    }
    
    if (showEmojiPicker) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showEmojiPicker])

  // Watch for new notifications and show toast
  useEffect(() => {
    if (!notifications) return
    
    const currentCount = notifications.unreadCount
    const latestUnread = notifications.getLatestUnread()
    
    // New notification arrived
    if (currentCount > prevUnreadCount.current && latestUnread) {
      setToastNotification(latestUnread)
      setShowToast(true)
      
      // Auto-hide toast after 8 seconds
      const timer = setTimeout(() => {
        setShowToast(false)
      }, 8000)
      
      return () => clearTimeout(timer)
    }
    
    prevUnreadCount.current = currentCount
  }, [notifications?.unreadCount])

  // Handle clicking on toast notification
  const handleToastClick = useCallback(() => {
    if (!toastNotification || !notifications) return
    
    // Store context for Sous Chef
    if (toastNotification.context) {
      setPendingContext(toastNotification.context)
    }
    
    // Mark as read
    notifications.markAsRead(toastNotification.id)
    
    // Open widget
    setIsOpen(true)
    setShowToast(false)
  }, [toastNotification, notifications])

  // Handle dismissing toast
  const handleDismissToast = useCallback((e) => {
    e.stopPropagation()
    setShowToast(false)
    if (toastNotification && notifications) {
      notifications.markAsRead(toastNotification.id)
    }
  }, [toastNotification, notifications])

  const handleEmojiSelect = useCallback(async (emoji) => {
    setCurrentEmoji(emoji)
    setShowEmojiPicker(false)
    setSavingEmoji(true)
    
    try {
      await api.patch('/chefs/api/me/chef/profile/update/', {
        sous_chef_emoji: emoji
      })
      if (onEmojiChange) {
        onEmojiChange(emoji)
      }
    } catch (err) {
      console.error('Failed to save sous chef emoji:', err)
      // Revert on error
      setCurrentEmoji(sousChefEmoji)
    } finally {
      setSavingEmoji(false)
    }
  }, [sousChefEmoji, onEmojiChange])

  const handleFamilySelect = useCallback((family) => {
    setSelectedFamily(family)
  }, [])

  const toggleWidget = useCallback(() => {
    setIsOpen(prev => {
      // When opening the widget, mark all notifications as read
      if (!prev && notifications?.markAllAsRead) {
        notifications.markAllAsRead()
      }
      return !prev
    })
    setShowEmojiPicker(false)
  }, [notifications])

  const unreadCount = notifications?.unreadCount || 0

  return (
    <div className="sous-chef-widget-container" ref={widgetRef}>
      {/* Toast Notification */}
      {showToast && toastNotification && (
        <div className="sous-chef-toast" onClick={handleToastClick}>
          <div className="toast-icon">{toastNotification.title?.substring(0, 2) || '✨'}</div>
          <div className="toast-content">
            <div className="toast-title">{toastNotification.title}</div>
            <div className="toast-message">{toastNotification.message}</div>
          </div>
          <button 
            className="toast-dismiss" 
            onClick={handleDismissToast}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {/* Expanded Chat Panel */}
      {isOpen && (
        <div className="sous-chef-panel">
          {/* Panel Header */}
          <div className="panel-header">
            <div className="header-left">
              <div 
                className="emoji-trigger"
                onClick={(e) => {
                  e.stopPropagation()
                  setShowEmojiPicker(!showEmojiPicker)
                }}
                title="Click to customize your Sous Chef icon"
              >
                <span className="emoji">{currentEmoji}</span>
                <span className="edit-hint">✎</span>
              </div>
              <div className="header-text">
                <h3>Sous Chef</h3>
                <span className="subtitle">Your AI kitchen assistant</span>
              </div>
            </div>
            <div className="header-actions">
              {notifications?.notifications?.length > 0 && (
                <button 
                  className="clear-notifs-btn"
                  onClick={() => notifications.clearAll()}
                  title="Clear all notifications"
                >
                  🗑️
                </button>
              )}
              <button 
                className="close-btn" 
                onClick={toggleWidget}
                aria-label="Close Sous Chef"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Emoji Picker Popover */}
          {showEmojiPicker && (
            <div className="emoji-picker" ref={emojiPickerRef}>
              <div className="picker-header">Choose your Sous Chef</div>
              <div className="emoji-grid">
                {CHEF_EMOJIS.map((emoji, idx) => (
                  <button
                    key={idx}
                    className={`emoji-option ${emoji === currentEmoji ? 'selected' : ''}`}
                    onClick={() => handleEmojiSelect(emoji)}
                    disabled={savingEmoji}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Family Selector */}
          <div className="family-selector-area">
            {/* Show hint when there's pending context */}
            {pendingContext && !selectedFamily.familyId && (
              <div className="pending-context-hint">
                💡 Select <strong>{pendingContext.clientName || 'the client'}</strong> to see the AI suggestion context
              </div>
            )}
            <FamilySelector
              selectedFamilyId={selectedFamily.familyId}
              selectedFamilyType={selectedFamily.familyType}
              onFamilySelect={handleFamilySelect}
              className="widget-family-selector"
            />
          </div>

          {/* Chat Area */}
          <div className="chat-area">
            <SousChefChat
              familyId={selectedFamily.familyId}
              familyType={selectedFamily.familyType}
              familyName={selectedFamily.familyName}
              initialContext={pendingContext}
              onContextHandled={() => setPendingContext(null)}
            />
          </div>
        </div>
      )}

      {/* Floating Action Button */}
      <button
        className={`sous-chef-fab ${isOpen ? 'open' : ''}`}
        onClick={toggleWidget}
        aria-label={isOpen ? 'Close Sous Chef' : 'Open Sous Chef'}
        title="Sous Chef Assistant"
      >
        {isOpen ? (
          <span className="fab-icon">✕</span>
        ) : (
          <>
            <span className="fab-icon emoji">{currentEmoji}</span>
            {unreadCount > 0 && (
              <span className="fab-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
            )}
          </>
        )}
      </button>

      <style>{`
        .sous-chef-widget-container {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 1000;
          font-family: inherit;
        }

        /* Floating Action Button */
        .sous-chef-fab {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          border: none;
          background: linear-gradient(135deg, var(--primary, #5cb85c) 0%, var(--primary-700, #3E8F3E) 100%);
          color: white;
          cursor: pointer;
          box-shadow: 0 4px 16px rgba(92, 184, 92, 0.35);
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .sous-chef-fab:hover {
          transform: scale(1.05);
          box-shadow: 0 6px 24px rgba(92, 184, 92, 0.45);
        }

        .sous-chef-fab.open {
          background: var(--bg-card, var(--surface, #fff));
          color: var(--text-muted, var(--muted, #666));
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .fab-icon {
          font-size: 1.5rem;
          line-height: 1;
        }

        .fab-icon.emoji {
          font-size: 1.75rem;
        }

        /* Notification Badge */
        .fab-badge {
          position: absolute;
          top: -4px;
          right: -4px;
          min-width: 20px;
          height: 20px;
          background: #ef4444;
          color: white;
          font-size: 0.7rem;
          font-weight: 600;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 0 5px;
          animation: badgePop 0.3s ease;
        }

        @keyframes badgePop {
          0% { transform: scale(0); }
          50% { transform: scale(1.2); }
          100% { transform: scale(1); }
        }

        /* Toast Notification */
        .sous-chef-toast {
          position: absolute;
          bottom: 70px;
          right: 0;
          width: 320px;
          background: var(--surface);
          border-radius: 12px;
          box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
          display: flex;
          align-items: flex-start;
          padding: 12px;
          gap: 12px;
          cursor: pointer;
          animation: toastSlideIn 0.3s ease;
          border-left: 4px solid var(--primary);
          color: var(--text);
        }

        @keyframes toastSlideIn {
          from {
            opacity: 0;
            transform: translateX(20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .sous-chef-toast:hover {
          box-shadow: 0 6px 28px rgba(0, 0, 0, 0.3);
        }

        .toast-icon {
          width: 40px;
          height: 40px;
          background: linear-gradient(135deg, var(--primary), var(--primary-700));
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.25rem;
          flex-shrink: 0;
        }

        .toast-content {
          flex: 1;
          min-width: 0;
        }

        .toast-title {
          font-weight: 600;
          font-size: 0.9rem;
          color: var(--text);
          margin-bottom: 2px;
        }

        .toast-message {
          font-size: 0.8rem;
          color: var(--muted);
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .toast-dismiss {
          background: none;
          border: none;
          color: var(--muted);
          cursor: pointer;
          padding: 4px;
          font-size: 0.9rem;
          line-height: 1;
          opacity: 0.6;
          transition: opacity 0.15s;
        }

        .toast-dismiss:hover {
          opacity: 1;
        }

        /* Expanded Panel */
        .sous-chef-panel {
          position: absolute;
          bottom: 70px;
          right: 0;
          width: 380px;
          height: 520px;
          background: var(--surface);
          border-radius: 16px;
          box-shadow: 0 8px 40px rgba(0, 0, 0, 0.25);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideUp 0.2s ease;
          color: var(--text);
          /* Theme tokens for nested family selector */
          --bg-card: var(--surface, #fff);
          --bg-page: var(--surface-2, #f3f4f6);
          --border-color: var(--border, #e5e7eb);
          --text-muted: var(--muted, #666);
          --accent-color: var(--primary, #5cb85c);
          --accent-color-alpha: rgba(92, 184, 92, 0.14);
          --accent-gradient: linear-gradient(135deg, var(--primary, #5cb85c), var(--primary-700, #3E8F3E));
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        /* Panel Header */
        .panel-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          background: linear-gradient(135deg, var(--primary, #5cb85c) 0%, var(--primary-700, #3E8F3E) 100%);
          color: white;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .emoji-trigger {
          position: relative;
          width: 44px;
          height: 44px;
          background: rgba(255, 255, 255, 0.2);
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: background 0.15s;
        }

        .emoji-trigger:hover {
          background: rgba(255, 255, 255, 0.3);
        }

        .emoji-trigger .emoji {
          font-size: 1.5rem;
        }

        .emoji-trigger .edit-hint {
          position: absolute;
          bottom: -2px;
          right: -2px;
          width: 18px;
          height: 18px;
          background: white;
          color: var(--primary, #5cb85c);
          border-radius: 50%;
          font-size: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          opacity: 0;
          transition: opacity 0.15s;
        }

        .emoji-trigger:hover .edit-hint {
          opacity: 1;
        }

        .header-text h3 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
        }

        .header-text .subtitle {
          font-size: 0.75rem;
          opacity: 0.85;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .clear-notifs-btn {
          background: rgba(255, 255, 255, 0.2);
          border: none;
          color: white;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 0.85rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
          opacity: 0.8;
        }

        .clear-notifs-btn:hover {
          background: rgba(255, 255, 255, 0.3);
          opacity: 1;
        }

        .close-btn {
          background: rgba(255, 255, 255, 0.2);
          border: none;
          color: white;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
        }

        .close-btn:hover {
          background: rgba(255, 255, 255, 0.3);
        }

        /* Emoji Picker */
        .emoji-picker {
          position: absolute;
          top: 60px;
          left: 16px;
          background: var(--surface);
          border-radius: 12px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
          padding: 12px;
          z-index: 10;
          animation: fadeIn 0.15s ease;
          border: 1px solid var(--border);
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .picker-header {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--muted);
          margin-bottom: 10px;
          text-align: center;
        }

        .emoji-grid {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 4px;
        }

        .emoji-option {
          width: 40px;
          height: 40px;
          border: 2px solid transparent;
          border-radius: 8px;
          background: var(--surface-2);
          cursor: pointer;
          font-size: 1.25rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }

        .emoji-option:hover {
          background: var(--bg2);
          transform: scale(1.1);
        }

        .emoji-option.selected {
          border-color: var(--primary);
          background: rgba(92, 184, 92, 0.15);
        }

        .emoji-option:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Family Selector Area */
        .family-selector-area {
          padding: 12px;
          border-bottom: 1px solid var(--border);
          background: var(--surface);
        }

        .pending-context-hint {
          background: linear-gradient(135deg, rgba(92, 184, 92, 0.15), rgba(92, 184, 92, 0.05));
          border: 1px solid rgba(92, 184, 92, 0.3);
          color: var(--text);
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 0.8rem;
          margin-bottom: 8px;
          text-align: center;
        }

        .pending-context-hint strong {
          color: var(--primary, #5cb85c);
        }

        .family-selector-area .family-selector-trigger {
          padding: 0.5rem 0.75rem;
        }

        .family-selector-area .family-avatar {
          width: 32px;
          height: 32px;
          font-size: 1rem;
        }

        .family-selector-area .family-name {
          font-size: 0.875rem;
        }

        .family-selector-area .family-meta {
          font-size: 0.75rem;
        }

        /* Chat Area */
        .chat-area {
          flex: 1;
          min-height: 0;
          display: flex;
          flex-direction: column;
        }

        .chat-area .sous-chef-chat {
          height: 100%;
          border-radius: 0;
        }

        .chat-area .sous-chef-chat.empty-state {
          padding: 1.5rem;
        }

        .chat-area .empty-content {
          padding: 1.5rem;
        }

        .chat-area .empty-icon {
          font-size: 2.5rem;
        }

        .chat-area .empty-content h3 {
          font-size: 1rem;
        }

        .chat-area .empty-content p {
          font-size: 0.85rem;
        }

        .chat-area .chat-header {
          padding: 0.75rem;
          display: none;
        }

        .chat-area .context-panel {
          display: none;
        }

        .chat-area .messages-container {
          padding: 0.75rem;
        }

        .chat-area .welcome-content {
          padding: 1rem;
        }

        .chat-area .welcome-icon {
          font-size: 2rem;
        }

        .chat-area .welcome-content h3 {
          font-size: 0.95rem;
        }

        .chat-area .welcome-content p {
          font-size: 0.8rem;
        }

        .chat-area .quick-actions {
          margin-top: 1rem;
        }

        .chat-area .quick-action-btn {
          padding: 0.4rem 0.75rem;
          font-size: 0.8rem;
        }

        .chat-area .bubble {
          padding: 0.6rem 0.85rem;
          max-width: 85%;
          font-size: 0.875rem;
        }

        .chat-area .composer {
          padding: 0.75rem;
          gap: 0.5rem;
        }

        .chat-area .composer-input {
          padding: 0.6rem 0.85rem;
          font-size: 0.875rem;
        }

        /* Responsive */
        @media (max-width: 480px) {
          .sous-chef-widget-container {
            bottom: 16px;
            right: 16px;
          }

          .sous-chef-panel {
            width: calc(100vw - 32px);
            height: calc(100vh - 100px);
            max-height: 600px;
            right: -8px;
          }

          .sous-chef-fab {
            width: 52px;
            height: 52px;
          }
        }
      `}</style>
    </div>
  )
}
