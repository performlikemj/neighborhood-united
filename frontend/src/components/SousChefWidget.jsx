/**
 * SousChefWidget Component
 * 
 * Floating chatbot-style widget for the Sous Chef AI assistant.
 * Lives in the bottom-right corner of the chef dashboard.
 * Expands to show family selector and chat interface.
 * Shows notifications when background tasks complete.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { CHEF_EMOJIS } from '../utils/emojis.js'
import FamilySelector from './FamilySelector.jsx'
import SousChefChat from './SousChefChat.jsx'
import { api } from '../api.js'
import { useSousChefNotifications } from '../contexts/SousChefNotificationContext.jsx'

// Resize configuration
const MIN_WIDTH = 320
const MIN_HEIGHT = 400
const DEFAULT_WIDTH = 380
const DEFAULT_HEIGHT = 520

// Dynamic threshold calculation based on screen size
function getExpandThresholds() {
  const screenWidth = window.innerWidth
  const screenHeight = window.innerHeight
  
  // Phone (< 640px): expand at 90% of screen
  if (screenWidth < 640) {
    return {
      width: Math.floor(screenWidth * 0.9),
      height: Math.floor(screenHeight * 0.7)
    }
  }
  
  // Tablet (640px - 1024px): expand at 70% of screen
  if (screenWidth < 1024) {
    return {
      width: Math.floor(screenWidth * 0.7),
      height: Math.floor(screenHeight * 0.65)
    }
  }
  
  // Small desktop (1024px - 1440px): expand at 50% of screen
  if (screenWidth < 1440) {
    return {
      width: Math.floor(screenWidth * 0.5),
      height: Math.floor(screenHeight * 0.6)
    }
  }
  
  // Large desktop (>= 1440px): fixed thresholds
  return {
    width: 700,
    height: 750
  }
}

export default function SousChefWidget({ 
  sousChefEmoji = '🧑‍🍳',
  onEmojiChange
}) {
  const navigate = useNavigate()
  const location = useLocation()
  
  // Hide widget when on the full-page Sous Chef view
  const isOnSousChefPage = location.pathname === '/chefs/dashboard/sous-chef'
  
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
  
  // Resize state
  const [panelWidth, setPanelWidth] = useState(DEFAULT_WIDTH)
  const [panelHeight, setPanelHeight] = useState(DEFAULT_HEIGHT)
  const [isResizing, setIsResizing] = useState(false)
  const [resizeDirection, setResizeDirection] = useState(null)
  const [expandThresholds, setExpandThresholds] = useState(getExpandThresholds)
  const [isExpanding, setIsExpanding] = useState(false)
  
  // Update thresholds on window resize
  useEffect(() => {
    const handleWindowResize = () => {
      setExpandThresholds(getExpandThresholds())
    }
    
    window.addEventListener('resize', handleWindowResize)
    return () => window.removeEventListener('resize', handleWindowResize)
  }, [])
  
  // Calculate how close we are to threshold (for visual feedback)
  const widthProgress = Math.min((panelWidth - MIN_WIDTH) / (expandThresholds.width - MIN_WIDTH), 1)
  const heightProgress = Math.min((panelHeight - MIN_HEIGHT) / (expandThresholds.height - MIN_HEIGHT), 1)
  const expandProgress = Math.max(widthProgress, heightProgress)
  const isNearThreshold = expandProgress > 0.7
  
  const widgetRef = useRef(null)
  const emojiPickerRef = useRef(null)
  const prevUnreadCount = useRef(0)
  const resizeStartRef = useRef({ x: 0, y: 0, width: 0, height: 0 })

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

  // Get the current draft input from the SousChefChat component
  const chatInputRef = useRef(null)
  
  // Navigate to full page when threshold is exceeded (with smooth transition)
  const navigateToFullPage = useCallback(() => {
    // Start expansion animation
    setIsExpanding(true)
    
    // Capture the current draft input before navigating
    const draftInput = chatInputRef.current?.value || ''
    
    // Wait for animation to complete before navigating
    setTimeout(() => {
      const params = new URLSearchParams()
      if (selectedFamily.familyId) {
        params.set('familyId', selectedFamily.familyId)
        params.set('familyType', selectedFamily.familyType)
        if (selectedFamily.familyName) {
          params.set('familyName', selectedFamily.familyName)
        }
      }
      const queryString = params.toString()
      // Pass draft input via router state
      navigate(`/chefs/dashboard/sous-chef${queryString ? `?${queryString}` : ''}`, {
        state: { draftInput }
      })
    }, 300) // Match animation duration
  }, [navigate, selectedFamily])

  // Resize handlers
  const handleResizeStart = useCallback((e, direction) => {
    e.preventDefault()
    e.stopPropagation()
    setIsResizing(true)
    setResizeDirection(direction)
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: panelWidth,
      height: panelHeight
    }
  }, [panelWidth, panelHeight])

  const handleResizeMove = useCallback((e) => {
    if (!isResizing) return
    
    const { x: startX, y: startY, width: startWidth, height: startHeight } = resizeStartRef.current
    const deltaX = startX - e.clientX  // Inverted because panel grows to left/top
    const deltaY = startY - e.clientY
    
    let newWidth = startWidth
    let newHeight = startHeight
    
    // Calculate new dimensions based on resize direction
    if (resizeDirection.includes('w')) {
      newWidth = Math.max(MIN_WIDTH, startWidth + deltaX)
    }
    if (resizeDirection.includes('n')) {
      newHeight = Math.max(MIN_HEIGHT, startHeight + deltaY)
    }
    if (resizeDirection.includes('e')) {
      newWidth = Math.max(MIN_WIDTH, startWidth - deltaX)
    }
    if (resizeDirection.includes('s')) {
      newHeight = Math.max(MIN_HEIGHT, startHeight - deltaY)
    }
    
    // Check if we've exceeded the threshold to expand to full page (using dynamic thresholds)
    if (newWidth >= expandThresholds.width || newHeight >= expandThresholds.height) {
      setIsResizing(false)
      setResizeDirection(null)
      navigateToFullPage()
      return
    }
    
    setPanelWidth(newWidth)
    setPanelHeight(newHeight)
  }, [isResizing, resizeDirection, navigateToFullPage, expandThresholds])

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false)
    setResizeDirection(null)
  }, [])

  // Attach global mouse events for resize
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleResizeMove)
      document.addEventListener('mouseup', handleResizeEnd)
      // Prevent text selection while resizing
      document.body.style.userSelect = 'none'
      document.body.style.cursor = resizeDirection === 'nw' ? 'nwse-resize' : 
                                   resizeDirection === 'ne' ? 'nesw-resize' :
                                   resizeDirection === 'n' ? 'ns-resize' :
                                   resizeDirection === 'w' ? 'ew-resize' : 'default'
      return () => {
        document.removeEventListener('mousemove', handleResizeMove)
        document.removeEventListener('mouseup', handleResizeEnd)
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
      }
    }
  }, [isResizing, resizeDirection, handleResizeMove, handleResizeEnd])

  const unreadCount = notifications?.unreadCount || 0

  // Don't render if on the full-page Sous Chef view
  if (isOnSousChefPage) {
    return null
  }

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
        <div 
          className={`sous-chef-panel ${isResizing ? 'resizing' : ''} ${isResizing && isNearThreshold ? 'near-threshold' : ''} ${isExpanding ? 'expanding' : ''}`}
          style={{ width: panelWidth, height: panelHeight }}
        >
          {/* Resize Handles */}
          <div 
            className="resize-handle resize-n" 
            onMouseDown={(e) => handleResizeStart(e, 'n')}
          />
          <div 
            className="resize-handle resize-w" 
            onMouseDown={(e) => handleResizeStart(e, 'w')}
          />
          <div 
            className="resize-handle resize-nw" 
            onMouseDown={(e) => handleResizeStart(e, 'nw')}
          />
          
          {/* Resize hint indicator */}
          {!isResizing && (
            <div className="resize-hint" title="Drag to resize, expand for full view">
              <span className="resize-hint-icon">⤡</span>
            </div>
          )}
          
          {/* Expand threshold indicator */}
          {isResizing && isNearThreshold && (
            <div className="expand-indicator">
              <span className="expand-text">Release to expand</span>
            </div>
          )}

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
                className="expand-btn" 
                onClick={navigateToFullPage}
                aria-label="Expand to full page"
                title="Open full view"
              >
                ⛶
              </button>
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
              externalInputRef={chatInputRef}
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

        .sous-chef-panel.resizing {
          transition: none;
          user-select: none;
        }

        .sous-chef-panel.near-threshold {
          box-shadow: 0 8px 40px rgba(0, 0, 0, 0.25), 
                      0 0 0 2px var(--primary, #5cb85c),
                      0 0 20px rgba(92, 184, 92, 0.3);
        }

        /* Expanding to full page animation */
        .sous-chef-panel.expanding {
          animation: expandToFullPage 0.3s ease-out forwards;
          pointer-events: none;
        }

        @keyframes expandToFullPage {
          0% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 1;
            transform: scale(1.02);
            box-shadow: 0 12px 60px rgba(0, 0, 0, 0.3),
                        0 0 0 3px var(--primary, #5cb85c),
                        0 0 40px rgba(92, 184, 92, 0.4);
          }
          100% {
            opacity: 0;
            transform: scale(1.05) translateY(-10px);
            box-shadow: 0 20px 80px rgba(0, 0, 0, 0.2),
                        0 0 60px rgba(92, 184, 92, 0.5);
          }
        }

        /* Also fade out the FAB button during expansion */
        .sous-chef-widget-container:has(.expanding) .sous-chef-fab {
          animation: fadeOutFab 0.3s ease-out forwards;
        }

        @keyframes fadeOutFab {
          0% { opacity: 1; transform: scale(1); }
          100% { opacity: 0; transform: scale(0.8); }
        }

        /* Resize Handles */
        .resize-handle {
          position: absolute;
          z-index: 20;
        }

        .resize-handle.resize-n {
          top: 0;
          left: 16px;
          right: 16px;
          height: 8px;
          cursor: ns-resize;
        }

        .resize-handle.resize-w {
          top: 16px;
          left: 0;
          bottom: 16px;
          width: 8px;
          cursor: ew-resize;
        }

        .resize-handle.resize-nw {
          top: 0;
          left: 0;
          width: 16px;
          height: 16px;
          cursor: nwse-resize;
        }

        .resize-handle:hover {
          background: rgba(92, 184, 92, 0.15);
        }

        /* Resize Hint */
        .resize-hint {
          position: absolute;
          top: 4px;
          left: 4px;
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, 0.1);
          border-radius: 4px;
          opacity: 0;
          transition: opacity 0.2s;
          z-index: 15;
          pointer-events: none;
        }

        .sous-chef-panel:hover .resize-hint {
          opacity: 0.6;
        }

        .resize-hint-icon {
          font-size: 12px;
          color: var(--muted);
          transform: rotate(45deg);
        }

        /* Expand Threshold Indicator */
        .expand-indicator {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background: linear-gradient(135deg, var(--primary, #5cb85c), var(--primary-700, #3E8F3E));
          color: white;
          padding: 12px 24px;
          border-radius: 24px;
          font-size: 0.9rem;
          font-weight: 600;
          z-index: 30;
          box-shadow: 0 4px 20px rgba(92, 184, 92, 0.4);
          animation: pulseGlow 1s ease-in-out infinite;
          pointer-events: none;
        }

        @keyframes pulseGlow {
          0%, 100% {
            box-shadow: 0 4px 20px rgba(92, 184, 92, 0.4);
            transform: translate(-50%, -50%) scale(1);
          }
          50% {
            box-shadow: 0 6px 30px rgba(92, 184, 92, 0.6);
            transform: translate(-50%, -50%) scale(1.02);
          }
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

        .expand-btn {
          background: rgba(255, 255, 255, 0.2);
          border: none;
          color: white;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 0.9rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
          opacity: 0.8;
        }

        .expand-btn:hover {
          background: rgba(255, 255, 255, 0.3);
          opacity: 1;
          transform: scale(1.1);
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
            width: calc(100vw - 32px) !important;
            height: calc(100vh - 100px) !important;
            max-height: 600px;
            right: -8px;
          }

          .sous-chef-fab {
            width: 52px;
            height: 52px;
          }

          /* Hide resize handles on mobile */
          .resize-handle,
          .resize-hint {
            display: none;
          }
        }
      `}</style>
    </div>
  )
}
