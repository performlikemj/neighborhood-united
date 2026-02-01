/**
 * SousChefNotificationPanel
 * 
 * Slide-out panel showing all notifications from Sous Chef.
 * Opens from the widget, shows proactive notifications with actions.
 */

import React, { useCallback } from 'react'
import { useSousChefNotifications } from '../contexts/SousChefNotificationContext.jsx'

// Format relative time
function formatRelativeTime(dateString) {
  if (!dateString) return ''
  
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  
  return date.toLocaleDateString()
}

// Notification type icons
const TYPE_ICONS = {
  birthday: '🎂',
  anniversary: '💍',
  followup: '👋',
  todo: '📝',
  seasonal: '🌱',
  milestone: '🎉',
  tip: '💡',
  welcome: '🍳',
  meal_generation: '✨',
  error: '❌',
  info: '💬',
}

export default function SousChefNotificationPanel({ 
  isOpen, 
  onClose, 
  onNotificationClick,
  onClearAll 
}) {
  const { 
    notifications, 
    unreadCount, 
    markAsRead, 
    markAllAsRead, 
    clearNotification,
    clearAll 
  } = useSousChefNotifications() || {}

  const handleNotificationClick = useCallback((notification) => {
    if (markAsRead) {
      markAsRead(notification.id)
    }
    onNotificationClick?.(notification)
  }, [markAsRead, onNotificationClick])

  const handleDismiss = useCallback((e, notificationId) => {
    e.stopPropagation()
    if (clearNotification) {
      clearNotification(notificationId)
    }
  }, [clearNotification])

  const handleClearAll = useCallback(() => {
    if (clearAll) {
      clearAll()
    }
    onClearAll?.()
  }, [clearAll, onClearAll])

  const handleMarkAllRead = useCallback(() => {
    if (markAllAsRead) {
      markAllAsRead()
    }
  }, [markAllAsRead])

  if (!isOpen) return null

  const sortedNotifications = [...(notifications || [])].sort((a, b) => {
    // Unread first, then by timestamp
    if (a.read !== b.read) return a.read ? 1 : -1
    const aTime = new Date(a.timestamp || a.createdAt || 0)
    const bTime = new Date(b.timestamp || b.createdAt || 0)
    return bTime - aTime
  })

  return (
    <div className="sc-notif-panel">
      {/* Header */}
      <div className="sc-notif-header">
        <div className="sc-notif-header-left">
          <h3>Notifications</h3>
          {unreadCount > 0 && (
            <span className="sc-notif-badge">{unreadCount}</span>
          )}
        </div>
        <div className="sc-notif-header-actions">
          {unreadCount > 0 && (
            <button 
              className="sc-notif-action-btn"
              onClick={handleMarkAllRead}
              title="Mark all as read"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </button>
          )}
          {notifications?.length > 0 && (
            <button 
              className="sc-notif-action-btn"
              onClick={handleClearAll}
              title="Clear all"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          )}
          <button 
            className="sc-notif-close-btn"
            onClick={onClose}
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Notification List */}
      <div className="sc-notif-list">
        {sortedNotifications.length === 0 ? (
          <div className="sc-notif-empty">
            <div className="sc-notif-empty-icon">🔔</div>
            <p>No notifications yet</p>
            <span>When Sous Chef has something to tell you, it'll appear here</span>
          </div>
        ) : (
          sortedNotifications.map((notif) => {
            const icon = TYPE_ICONS[notif.type] || '🔔'
            const isUnread = !notif.read
            
            return (
              <div
                key={notif.id}
                className={`sc-notif-item ${isUnread ? 'sc-notif-item--unread' : ''}`}
                onClick={() => handleNotificationClick(notif)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && handleNotificationClick(notif)}
              >
                <div className="sc-notif-icon">{icon}</div>
                <div className="sc-notif-content">
                  <div className="sc-notif-title">{notif.title}</div>
                  <div className="sc-notif-message">{notif.message}</div>
                  <div className="sc-notif-meta">
                    <span className="sc-notif-time">
                      {formatRelativeTime(notif.timestamp || notif.createdAt)}
                    </span>
                    {notif.context?.clientName && (
                      <span className="sc-notif-client">
                        • {notif.context.clientName}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  className="sc-notif-dismiss"
                  onClick={(e) => handleDismiss(e, notif.id)}
                  aria-label="Dismiss"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                  </svg>
                </button>
                {isUnread && <div className="sc-notif-unread-dot" />}
              </div>
            )
          })
        )}
      </div>

      <style>{`
        .sc-notif-panel {
          position: absolute;
          bottom: 64px;
          right: 0;
          width: 360px;
          max-height: 480px;
          background: var(--surface, #fff);
          border-radius: 16px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
          border: 1px solid var(--border, #e5e7eb);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: sc-panel-open 0.2s ease-out;
          color: var(--text);
          z-index: 1001;
        }

        @keyframes sc-panel-open {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(8px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }

        .sc-notif-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 16px;
          border-bottom: 1px solid var(--border, #e5e7eb);
          background: var(--surface, #fff);
        }

        .sc-notif-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .sc-notif-header h3 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
        }

        .sc-notif-badge {
          background: var(--primary, #5cb85c);
          color: white;
          font-size: 0.7rem;
          font-weight: 600;
          padding: 2px 6px;
          border-radius: 10px;
          min-width: 18px;
          text-align: center;
        }

        .sc-notif-header-actions {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .sc-notif-action-btn,
        .sc-notif-close-btn {
          background: none;
          border: none;
          cursor: pointer;
          padding: 6px;
          border-radius: 6px;
          color: var(--muted);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }

        .sc-notif-action-btn:hover,
        .sc-notif-close-btn:hover {
          background: var(--surface-2, #f3f4f6);
          color: var(--text);
        }

        .sc-notif-list {
          flex: 1;
          overflow-y: auto;
          padding: 8px;
        }

        .sc-notif-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 40px 20px;
          text-align: center;
        }

        .sc-notif-empty-icon {
          font-size: 2.5rem;
          margin-bottom: 12px;
          opacity: 0.5;
        }

        .sc-notif-empty p {
          margin: 0 0 4px 0;
          font-weight: 500;
          color: var(--text);
        }

        .sc-notif-empty span {
          font-size: 0.85rem;
          color: var(--muted);
        }

        .sc-notif-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 12px;
          border-radius: 10px;
          cursor: pointer;
          transition: background 0.15s;
          position: relative;
        }

        .sc-notif-item:hover {
          background: var(--surface-2, #f9fafb);
        }

        .sc-notif-item--unread {
          background: rgba(92, 184, 92, 0.08);
        }

        .sc-notif-item--unread:hover {
          background: rgba(92, 184, 92, 0.12);
        }

        .sc-notif-icon {
          font-size: 1.5rem;
          flex-shrink: 0;
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--surface-2, #f3f4f6);
          border-radius: 8px;
        }

        .sc-notif-content {
          flex: 1;
          min-width: 0;
        }

        .sc-notif-title {
          font-weight: 600;
          font-size: 0.9rem;
          margin-bottom: 2px;
          color: var(--text);
        }

        .sc-notif-message {
          font-size: 0.85rem;
          color: var(--muted);
          line-height: 1.4;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .sc-notif-meta {
          display: flex;
          align-items: center;
          gap: 4px;
          margin-top: 6px;
          font-size: 0.75rem;
          color: var(--muted);
        }

        .sc-notif-dismiss {
          position: absolute;
          top: 8px;
          right: 8px;
          background: none;
          border: none;
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          color: var(--muted);
          opacity: 0;
          transition: all 0.15s;
        }

        .sc-notif-item:hover .sc-notif-dismiss {
          opacity: 0.6;
        }

        .sc-notif-dismiss:hover {
          opacity: 1 !important;
          background: var(--surface-2, #f3f4f6);
        }

        .sc-notif-unread-dot {
          position: absolute;
          top: 12px;
          right: 32px;
          width: 8px;
          height: 8px;
          background: var(--primary, #5cb85c);
          border-radius: 50%;
        }

        /* Dark mode */
        [data-theme="dark"] .sc-notif-panel {
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }

        [data-theme="dark"] .sc-notif-item--unread {
          background: rgba(92, 184, 92, 0.15);
        }

        /* Mobile */
        @media (max-width: 480px) {
          .sc-notif-panel {
            position: fixed;
            bottom: 0;
            right: 0;
            left: 0;
            width: 100%;
            max-height: 70vh;
            border-radius: 20px 20px 0 0;
          }
        }
      `}</style>
    </div>
  )
}
