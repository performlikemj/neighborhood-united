/**
 * SousChefPage Component
 * 
 * Full-page view for the Sous Chef AI assistant.
 * Provides more space for viewing tables, meal plans, and detailed content.
 * Accessed by expanding the widget or navigating directly.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { CHEF_EMOJIS } from '../utils/emojis.js'
import FamilySelector from '../components/FamilySelector.jsx'
import SousChefChat from '../components/SousChefChat.jsx'
import { api } from '../api.js'

export default function SousChefPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  
  // Read initial family from URL params
  const initialFamilyId = searchParams.get('familyId')
  const initialFamilyType = searchParams.get('familyType') || 'customer'
  const initialFamilyName = searchParams.get('familyName')
  
  // Read draft input from router state (passed from widget expansion)
  const draftInput = location.state?.draftInput || ''
  
  const [selectedFamily, setSelectedFamily] = useState({
    familyId: initialFamilyId ? parseInt(initialFamilyId, 10) : null,
    familyType: initialFamilyType,
    familyName: initialFamilyName
  })
  
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [currentEmoji, setCurrentEmoji] = useState('🧑‍🍳')
  const [savingEmoji, setSavingEmoji] = useState(false)
  const [isMinimizing, setIsMinimizing] = useState(false)

  // Load chef's sous chef emoji on mount
  useEffect(() => {
    api.get('/chefs/api/me/chef/').then(res => {
      if (res.data?.sous_chef_emoji) {
        setCurrentEmoji(res.data.sous_chef_emoji)
      }
    }).catch(() => {})
  }, [])

  const handleFamilySelect = useCallback((family) => {
    setSelectedFamily(family)
    // Update URL params to preserve state on refresh
    const params = new URLSearchParams()
    if (family.familyId) {
      params.set('familyId', family.familyId)
      params.set('familyType', family.familyType)
      if (family.familyName) {
        params.set('familyName', family.familyName)
      }
    }
    navigate(`/chefs/dashboard/sous-chef?${params.toString()}`, { replace: true })
  }, [navigate])

  const handleEmojiSelect = useCallback(async (emoji) => {
    setCurrentEmoji(emoji)
    setShowEmojiPicker(false)
    setSavingEmoji(true)
    
    try {
      await api.patch('/chefs/api/me/chef/profile/update/', {
        sous_chef_emoji: emoji
      })
    } catch (err) {
      console.error('Failed to save sous chef emoji:', err)
    } finally {
      setSavingEmoji(false)
    }
  }, [])

  const handleMinimize = useCallback(() => {
    setIsMinimizing(true)
    setTimeout(() => {
      navigate('/chefs/dashboard')
    }, 250)
  }, [navigate])

  return (
    <div className={`sous-chef-page ${isMinimizing ? 'minimizing' : ''}`}>
      {/* Page Header */}
      <header className="page-header">
        <div className="header-inner">
          <div className="header-left">
            <div 
              className="emoji-trigger"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              title="Click to customize your Sous Chef icon"
            >
              <span className="emoji">{currentEmoji}</span>
              <span className="edit-hint">✎</span>
            </div>
            <div className="header-text">
              <h1>Sous Chef</h1>
              <span className="subtitle">Your AI kitchen assistant</span>
            </div>
          </div>
          <div className="header-actions">
            <button 
              className="btn btn-outline minimize-btn"
              onClick={handleMinimize}
              title="Return to dashboard"
            >
              <span className="minimize-icon">↙</span>
              <span className="minimize-text">Minimize</span>
            </button>
          </div>
        </div>
      </header>

      {/* Emoji Picker Popover */}
      {showEmojiPicker && (
        <div className="emoji-picker-overlay" onClick={() => setShowEmojiPicker(false)}>
          <div className="emoji-picker" onClick={(e) => e.stopPropagation()}>
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
        </div>
      )}

      {/* Main Content */}
      <div className="page-content">
        {/* Sidebar - Family Selector & Context */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <h3 className="sidebar-title">Select Client</h3>
            <FamilySelector
              selectedFamilyId={selectedFamily.familyId}
              selectedFamilyType={selectedFamily.familyType}
              onFamilySelect={handleFamilySelect}
            />
          </div>
        </aside>

        {/* Chat Area - Full Width */}
        <main className="chat-main">
          <SousChefChat
            familyId={selectedFamily.familyId}
            familyType={selectedFamily.familyType}
            familyName={selectedFamily.familyName}
            initialInput={draftInput}
          />
        </main>
      </div>

      <style>{`
        .sous-chef-page {
          min-height: calc(100vh - 60px);
          display: flex;
          flex-direction: column;
          background: var(--bg-page, var(--surface-2, #f3f4f6));
          color: var(--text, #1f2937);
          animation: pageSlideIn 0.35s ease-out;
          /* Dark mode CSS variable overrides */
          --bg-card: var(--surface, #fff);
          --border-color: var(--border, #e5e7eb);
          --text-muted: var(--muted, #6b7280);
        }

        @keyframes pageSlideIn {
          0% {
            opacity: 0;
            transform: scale(0.98) translateY(10px);
          }
          100% {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }

        .sous-chef-page.minimizing {
          animation: pageSlideOut 0.25s ease-in forwards;
          pointer-events: none;
        }

        @keyframes pageSlideOut {
          0% {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
          100% {
            opacity: 0;
            transform: scale(0.96) translateY(20px);
          }
        }

        /* Page Header */
        .page-header {
          position: relative;
          padding: 0.85rem 1rem;
          background: linear-gradient(135deg,
            color-mix(in oklab, var(--primary, #5cb85c) 72%, var(--surface, #0f1511) 28%),
            color-mix(in oklab, var(--primary-700, #3E8F3E) 70%, var(--surface, #0f1511) 20%)
          );
          color: white;
          box-shadow: 0 8px 28px rgba(0, 0, 0, 0.25);
        }

        .header-inner {
          max-width: 1240px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 1rem;
        }

        .emoji-trigger {
          position: relative;
          width: 56px;
          height: 56px;
          background: rgba(255, 255, 255, 0.2);
          border-radius: 14px;
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
          font-size: 2rem;
        }

        .emoji-trigger .edit-hint {
          position: absolute;
          bottom: -2px;
          right: -2px;
          width: 22px;
          height: 22px;
          background: white;
          color: var(--primary, #5cb85c);
          border-radius: 50%;
          font-size: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          opacity: 0;
          transition: opacity 0.15s;
        }

        .emoji-trigger:hover .edit-hint {
          opacity: 1;
        }

        .header-text h1 {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 700;
        }

        .header-text .subtitle {
          font-size: 0.8rem;
          opacity: 0.92;
        }

        .header-actions {
          display: flex;
          gap: 0.75rem;
        }

        .minimize-btn {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          background: rgba(255, 255, 255, 0.2);
          border-color: rgba(255, 255, 255, 0.3);
          color: white;
        }

        .minimize-btn:hover {
          background: rgba(255, 255, 255, 0.3);
          border-color: rgba(255, 255, 255, 0.4);
        }

        .minimize-icon {
          font-size: 1.1rem;
        }

        /* Emoji Picker */
        .emoji-picker-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.3);
          display: flex;
          align-items: flex-start;
          justify-content: flex-start;
          padding: 5rem 0 0 6rem;
          z-index: 1000;
        }

        .emoji-picker {
          background: var(--surface, #fff);
          border-radius: 12px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
          padding: 1rem;
          animation: fadeIn 0.15s ease;
          border: 1px solid var(--border, #e5e7eb);
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .picker-header {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--muted);
          margin-bottom: 0.75rem;
          text-align: center;
        }

        .emoji-grid {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 6px;
        }

        .emoji-option {
          width: 44px;
          height: 44px;
          border: 2px solid transparent;
          border-radius: 10px;
          background: var(--surface-2, var(--bg-page, #f3f4f6));
          cursor: pointer;
          font-size: 1.5rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }

        .emoji-option:hover {
          background: var(--surface-3, var(--border, #e5e7eb));
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

        /* Main Content Layout */
        .page-content {
          flex: 1;
          display: flex;
          gap: 1.5rem;
          padding: 1.5rem;
          min-height: 0;
          max-width: 1600px;
          margin: 0 auto;
          width: 100%;
        }

        /* Sidebar */
        .sidebar {
          width: 320px;
          flex-shrink: 0;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .sidebar-section {
          background: var(--surface, #fff);
          border-radius: 12px;
          padding: 1rem;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
          border: 1px solid var(--border, transparent);
        }

        .sidebar-title {
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--muted, #6b7280);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin: 0 0 0.75rem 0;
        }

        /* Chat Main Area */
        .chat-main {
          flex: 1;
          min-width: 0;
          display: flex;
          flex-direction: column;
          background: var(--surface, #fff);
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
          overflow: hidden;
          border: 1px solid var(--border, transparent);
          /* Pass theme tokens to child components */
          --bg-card: var(--surface, #fff);
          --bg-page: var(--surface-2, #f3f4f6);
          --text-muted: var(--muted, #6b7280);
          --accent-color: var(--primary, #5cb85c);
        }

        .chat-main .sous-chef-chat {
          height: 100%;
          border-radius: 0;
        }

        /* Override SousChefChat styles for full-page view */
        .chat-main .context-panel {
          display: block;
        }

        .chat-main .chat-header {
          display: flex;
          padding: 1rem;
        }

        .chat-main .messages-container {
          padding: 1.5rem;
        }

        .chat-main .bubble {
          max-width: 75%;
          font-size: 0.95rem;
        }

        .chat-main .bubble.assistant {
          max-width: 85%;
        }

        /* Better table visibility in full page */
        .chat-main .bubble.assistant table {
          font-size: 0.9rem;
        }

        .chat-main .welcome-content {
          max-width: 500px;
        }

        .chat-main .quick-actions {
          gap: 0.75rem;
        }

        .chat-main .quick-action-btn {
          padding: 0.6rem 1.25rem;
          font-size: 0.9rem;
        }

        .chat-main .composer {
          padding: 1rem 1.5rem;
        }

        .chat-main .composer-input {
          padding: 0.875rem 1rem;
          font-size: 0.95rem;
        }

        /* Responsive */
        @media (max-width: 1024px) {
          .page-content {
            flex-direction: column;
            padding: 1rem;
          }

          .sidebar {
            width: 100%;
          }

          .chat-main {
            min-height: 500px;
          }
        }

        @media (max-width: 640px) {
          .page-header {
            padding: 0.75rem 1rem;
          }

          .header-inner {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.5rem;
          }

          .header-text h1 {
            font-size: 1.25rem;
          }

          .emoji-trigger {
            width: 48px;
            height: 48px;
          }

          .emoji-trigger .emoji {
            font-size: 1.5rem;
          }

          .minimize-text {
            display: none;
          }

          .page-content {
            padding: 0.75rem;
            gap: 0.75rem;
          }
        }
      `}</style>
    </div>
  )
}
