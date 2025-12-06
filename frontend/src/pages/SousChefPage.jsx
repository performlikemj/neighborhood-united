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
      {/* Compact Header Bar */}
      <header className="page-header">
        <div className="header-content">
          <div className="header-left">
            <button 
              className="emoji-btn"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              title="Customize icon"
            >
              {currentEmoji}
            </button>
            <div className="header-title">
              <h1>Sous Chef</h1>
              {selectedFamily.familyName && (
                <span className="current-family">with {selectedFamily.familyName}</span>
              )}
            </div>
          </div>
          
          <div className="header-right">
            {/* Family selector in header when family is selected */}
            {selectedFamily.familyId && (
              <div className="header-family-selector">
                <FamilySelector
                  selectedFamilyId={selectedFamily.familyId}
                  selectedFamilyType={selectedFamily.familyType}
                  onFamilySelect={handleFamilySelect}
                  compact
                />
              </div>
            )}
            <button 
              className="minimize-btn"
              onClick={handleMinimize}
              title="Return to dashboard"
            >
              <span className="minimize-icon">↙</span>
              <span className="minimize-label">Minimize</span>
            </button>
          </div>
        </div>
      </header>

      {/* Emoji Picker Popover */}
      {showEmojiPicker && (
        <div className="emoji-overlay" onClick={() => setShowEmojiPicker(false)}>
          <div className="emoji-picker" onClick={(e) => e.stopPropagation()}>
            <div className="picker-title">Choose your Sous Chef</div>
            <div className="emoji-grid">
              {CHEF_EMOJIS.map((emoji, idx) => (
                <button
                  key={idx}
                  className={`emoji-item ${emoji === currentEmoji ? 'selected' : ''}`}
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

      {/* Main Content Area */}
      <main className="page-main">
        {selectedFamily.familyId ? (
          <div className="chat-container">
            <SousChefChat
              familyId={selectedFamily.familyId}
              familyType={selectedFamily.familyType}
              familyName={selectedFamily.familyName}
              initialInput={draftInput}
            />
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-card">
              <div className="empty-icon">{currentEmoji}</div>
              <h2>Welcome to Sous Chef</h2>
              <p>Select a client to get started. I'll have full context about their dietary needs, allergies, and history.</p>
              <div className="empty-selector">
                <FamilySelector
                  selectedFamilyId={selectedFamily.familyId}
                  selectedFamilyType={selectedFamily.familyType}
                  onFamilySelect={handleFamilySelect}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      <style>{`
        .sous-chef-page {
          min-height: calc(100vh - 60px);
          display: flex;
          flex-direction: column;
          background: var(--surface-2, var(--bg-page, #f5f5f5));
          color: var(--text, #1a1a1a);
          animation: pageEnter 0.3s ease-out;
          
          /* Ensure CSS variables cascade properly */
          --bg-card: var(--surface, #fff);
          --border-color: var(--border, #e0e0e0);
          --text-muted: var(--muted, #666);
          --accent-color: var(--primary, #5cb85c);
          --accent-color-alpha: rgba(92, 184, 92, 0.12);
        }

        @keyframes pageEnter {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .sous-chef-page.minimizing {
          animation: pageExit 0.25s ease-in forwards;
          pointer-events: none;
        }

        @keyframes pageExit {
          to {
            opacity: 0;
            transform: scale(0.98) translateY(12px);
          }
        }

        /* ============================================
           HEADER
           ============================================ */
        .page-header {
          background: linear-gradient(135deg, var(--primary, #5cb85c) 0%, var(--primary-700, #449d44) 100%);
          padding: 0.75rem 1rem;
          position: sticky;
          top: 0;
          z-index: 100;
          box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        }

        .header-content {
          max-width: 1400px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .emoji-btn {
          width: 42px;
          height: 42px;
          border: none;
          border-radius: 10px;
          background: rgba(255,255,255,0.2);
          font-size: 1.5rem;
          cursor: pointer;
          transition: all 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .emoji-btn:hover {
          background: rgba(255,255,255,0.3);
          transform: scale(1.05);
        }

        .header-title {
          color: white;
        }

        .header-title h1 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          line-height: 1.2;
        }

        .current-family {
          font-size: 0.75rem;
          opacity: 0.85;
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .header-family-selector {
          max-width: 220px;
        }

        .header-family-selector .family-selector-trigger {
          background: rgba(255,255,255,0.15);
          border-color: rgba(255,255,255,0.2);
          color: white;
          padding: 0.4rem 0.75rem;
          font-size: 0.8rem;
        }

        .header-family-selector .family-selector-trigger:hover {
          background: rgba(255,255,255,0.25);
        }

        .minimize-btn {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.5rem 0.875rem;
          background: rgba(255,255,255,0.15);
          border: 1px solid rgba(255,255,255,0.25);
          border-radius: 8px;
          color: white;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s;
        }

        .minimize-btn:hover {
          background: rgba(255,255,255,0.25);
        }

        .minimize-icon {
          font-size: 1rem;
        }

        /* ============================================
           EMOJI PICKER
           ============================================ */
        .emoji-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0,0,0,0.4);
          display: flex;
          align-items: flex-start;
          justify-content: flex-start;
          padding: 4.5rem 1rem 1rem 1rem;
          z-index: 1000;
          animation: fadeIn 0.15s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .emoji-picker {
          background: var(--surface, #fff);
          border-radius: 12px;
          padding: 1rem;
          box-shadow: 0 8px 32px rgba(0,0,0,0.25);
          border: 1px solid var(--border, #e0e0e0);
          animation: slideDown 0.2s ease;
        }

        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .picker-title {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--muted, #666);
          text-align: center;
          margin-bottom: 0.75rem;
        }

        .emoji-grid {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 4px;
        }

        .emoji-item {
          width: 40px;
          height: 40px;
          border: 2px solid transparent;
          border-radius: 8px;
          background: var(--surface-2, #f5f5f5);
          font-size: 1.25rem;
          cursor: pointer;
          transition: all 0.15s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .emoji-item:hover {
          background: var(--surface-3, #eee);
          transform: scale(1.1);
        }

        .emoji-item.selected {
          border-color: var(--primary, #5cb85c);
          background: rgba(92,184,92,0.15);
        }

        .emoji-item:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* ============================================
           MAIN CONTENT
           ============================================ */
        .page-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          padding: 1rem;
          min-height: 0;
        }

        .chat-container {
          flex: 1;
          display: flex;
          flex-direction: column;
          background: var(--surface, #fff);
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0,0,0,0.08);
          max-width: 1200px;
          width: 100%;
          margin: 0 auto;
        }

        .chat-container .sous-chef-chat {
          flex: 1;
          height: 100%;
        }

        /* ============================================
           EMPTY STATE (No family selected)
           ============================================ */
        .empty-state {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 2rem;
        }

        .empty-card {
          background: var(--surface, #fff);
          border-radius: 16px;
          padding: 2rem 2.5rem;
          text-align: center;
          max-width: 420px;
          width: 100%;
          box-shadow: 0 4px 24px rgba(0,0,0,0.12);
          border: 1px solid var(--border, #e5e5e5);
        }

        .empty-icon {
          font-size: 3.5rem;
          margin-bottom: 1rem;
        }

        .empty-card h2 {
          margin: 0 0 0.5rem 0;
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text, #1a1a1a);
        }

        .empty-card p {
          margin: 0 0 1.5rem 0;
          color: var(--muted, #666);
          font-size: 0.9rem;
          line-height: 1.5;
        }

        .empty-selector {
          text-align: left;
        }

        /* ============================================
           CHAT OVERRIDES FOR FULL PAGE
           ============================================ */
        .chat-container .context-panel {
          display: block;
        }

        .chat-container .chat-header {
          display: flex;
          padding: 1rem 1.25rem;
        }

        .chat-container .messages-container {
          padding: 1.25rem;
        }

        .chat-container .bubble {
          max-width: 80%;
        }

        .chat-container .bubble.assistant {
          max-width: 90%;
        }

        .chat-container .composer {
          padding: 1rem 1.25rem;
        }

        /* ============================================
           FAMILY SELECTOR DARK MODE FIXES
           ============================================ */
        .sous-chef-page .family-selector-trigger {
          background: var(--surface, #fff);
          border-color: var(--border, #e0e0e0);
          color: var(--text, #1a1a1a);
        }

        .sous-chef-page .family-selector-trigger:hover {
          border-color: var(--primary, #5cb85c);
        }

        .sous-chef-page .family-selector-trigger.open {
          border-color: var(--primary, #5cb85c);
          box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.15);
        }

        .sous-chef-page .family-selector-dropdown {
          background: var(--surface, #fff);
          border-color: var(--border, #e0e0e0);
          box-shadow: 0 12px 40px rgba(0,0,0,0.35);
        }

        .sous-chef-page .search-wrapper {
          background: var(--surface, #fff);
          border-bottom-color: var(--border, #e0e0e0);
        }

        .sous-chef-page .search-input {
          background: var(--surface-2, #f5f5f5);
          border-color: var(--border, #e0e0e0);
          color: var(--text, #1a1a1a);
        }

        .sous-chef-page .search-input::placeholder {
          color: var(--muted, #888);
        }

        .sous-chef-page .search-input:focus {
          border-color: var(--primary, #5cb85c);
          box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.15);
        }

        .sous-chef-page .group-header {
          background: var(--surface-2, #f5f5f5);
          color: var(--muted, #888);
          border-bottom-color: var(--border, #e0e0e0);
        }

        .sous-chef-page .family-option {
          border-bottom-color: var(--border, #e0e0e0);
          color: var(--text, #1a1a1a);
        }

        .sous-chef-page .family-option:hover {
          background: var(--surface-2, #f5f5f5);
        }

        .sous-chef-page .family-option.selected {
          background: rgba(92, 184, 92, 0.1);
        }

        .sous-chef-page .type-badge {
          font-size: 0.6rem;
          padding: 0.1rem 0.35rem;
          border-radius: 3px;
          font-weight: 600;
        }

        /* Badge colors - enhanced for visibility */
        .sous-chef-page .type-badge.badge-platform {
          background: rgba(16, 185, 129, 0.18);
          color: #059669;
        }

        .sous-chef-page .type-badge.badge-manual {
          background: rgba(139, 92, 246, 0.18);
          color: #7c3aed;
        }

        .sous-chef-page .family-meta,
        .sous-chef-page .family-dietary,
        .sous-chef-page .family-stats {
          color: var(--muted, #888);
        }

        .sous-chef-page .no-results {
          color: var(--muted, #888);
        }

        /* Header family selector special styling */
        .header-family-selector .family-selector-trigger {
          background: rgba(255,255,255,0.12) !important;
          border-color: rgba(255,255,255,0.2) !important;
          color: white !important;
          padding: 0.4rem 0.7rem;
          min-width: 180px;
        }

        .header-family-selector .family-selector-trigger:hover {
          background: rgba(255,255,255,0.2) !important;
        }

        .header-family-selector .family-selector-trigger .chevron {
          color: rgba(255,255,255,0.7);
        }

        .header-family-selector .family-selector-trigger .family-name {
          font-size: 0.85rem;
        }

        .header-family-selector .family-selector-trigger .family-meta {
          font-size: 0.7rem;
          color: rgba(255,255,255,0.75);
        }

        .header-family-selector .family-selector-trigger .family-avatar {
          width: 28px;
          height: 28px;
          font-size: 0.9rem;
        }

        .header-family-selector .type-badge {
          display: none;
        }

        /* ============================================
           RESPONSIVE
           ============================================ */
        @media (max-width: 768px) {
          .page-header {
            padding: 0.625rem 0.75rem;
          }

          .header-content {
            flex-wrap: wrap;
          }

          .header-family-selector {
            display: none;
          }

          .minimize-label {
            display: none;
          }

          .minimize-btn {
            padding: 0.5rem 0.625rem;
          }

          .emoji-btn {
            width: 38px;
            height: 38px;
            font-size: 1.25rem;
          }

          .header-title h1 {
            font-size: 1rem;
          }

          .page-main {
            padding: 0.75rem;
          }

          .empty-card {
            padding: 1.5rem;
          }

          .empty-icon {
            font-size: 2.5rem;
          }

          .empty-card h2 {
            font-size: 1.1rem;
          }
        }

        @media (max-width: 480px) {
          .page-main {
            padding: 0.5rem;
          }

          .chat-container {
            border-radius: 8px;
          }

          .empty-card {
            padding: 1.25rem;
            border-radius: 12px;
          }
        }
      `}</style>
    </div>
  )
}
