/**
 * WorkspaceSettings Component
 *
 * Modal component for editing Sous Chef workspace settings.
 * Provides tabs for Personality (soul_prompt) and Business Rules.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { useWorkspace, useUpdateWorkspace, useResetWorkspace } from '../hooks/useWorkspace'

const MAX_SOUL_PROMPT_LENGTH = 2000
const MAX_BUSINESS_RULES_LENGTH = 2000

/**
 * WorkspaceSettings - Modal for Sous Chef customization
 *
 * @param {boolean} isOpen - Whether the modal is open
 * @param {function} onClose - Callback to close the modal
 */
export default function WorkspaceSettings({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('personality')
  const [soulPrompt, setSoulPrompt] = useState('')
  const [businessRules, setBusinessRules] = useState('')
  const [isDirty, setIsDirty] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Fetch workspace data
  const { data: workspace, isLoading, error: fetchError } = useWorkspace({ enabled: isOpen })

  // Mutations
  const updateMutation = useUpdateWorkspace()
  const resetMutation = useResetWorkspace()

  // Sync form state with fetched data
  useEffect(() => {
    if (workspace) {
      setSoulPrompt(workspace.soul_prompt || '')
      setBusinessRules(workspace.business_rules || '')
      setIsDirty(false)
    }
  }, [workspace])

  // Track dirty state
  useEffect(() => {
    if (workspace) {
      const hasChanges =
        soulPrompt !== (workspace.soul_prompt || '') ||
        businessRules !== (workspace.business_rules || '')
      setIsDirty(hasChanges)
    }
  }, [soulPrompt, businessRules, workspace])

  // Clear success message after delay
  useEffect(() => {
    if (saveSuccess) {
      const timer = setTimeout(() => setSaveSuccess(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [saveSuccess])

  const handleSave = useCallback(async () => {
    const updates = {}

    if (soulPrompt !== (workspace?.soul_prompt || '')) {
      updates.soul_prompt = soulPrompt
    }
    if (businessRules !== (workspace?.business_rules || '')) {
      updates.business_rules = businessRules
    }

    if (Object.keys(updates).length === 0) {
      return
    }

    try {
      await updateMutation.mutateAsync(updates)
      setIsDirty(false)
      setSaveSuccess(true)
    } catch (err) {
      // Error handled by mutation
    }
  }, [soulPrompt, businessRules, workspace, updateMutation])

  const handleReset = useCallback(async (field) => {
    try {
      await resetMutation.mutateAsync([field])
      setSaveSuccess(true)
    } catch (err) {
      // Error handled by mutation
    }
  }, [resetMutation])

  const handleClose = useCallback(() => {
    if (isDirty) {
      if (window.confirm('You have unsaved changes. Discard them?')) {
        onClose?.()
      }
    } else {
      onClose?.()
    }
  }, [isDirty, onClose])

  if (!isOpen) return null

  const isSaving = updateMutation.isPending || resetMutation.isPending

  return (
    <div className="ws-modal-overlay" onClick={handleClose}>
      <div className="ws-modal" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <header className="ws-header">
          <h2 className="ws-title">Workspace Settings</h2>
          <button className="ws-close-btn" onClick={handleClose} aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </header>

        {/* Tabs */}
        <nav className="ws-tabs">
          <button
            className={`ws-tab ${activeTab === 'personality' ? 'active' : ''}`}
            onClick={() => setActiveTab('personality')}
          >
            Personality
          </button>
          <button
            className={`ws-tab ${activeTab === 'rules' ? 'active' : ''}`}
            onClick={() => setActiveTab('rules')}
          >
            Business Rules
          </button>
        </nav>

        {/* Content */}
        <div className="ws-content">
          {isLoading && (
            <div className="ws-loading">Loading settings...</div>
          )}

          {fetchError && (
            <div className="ws-error">
              Failed to load settings. Please try again.
            </div>
          )}

          {!isLoading && !fetchError && (
            <>
              {/* Personality Tab */}
              {activeTab === 'personality' && (
                <div className="ws-field-group">
                  <div className="ws-field-header">
                    <label className="ws-label" htmlFor="soul-prompt">
                      Sous Chef Personality
                    </label>
                    <button
                      className="ws-reset-btn"
                      onClick={() => handleReset('soul_prompt')}
                      disabled={isSaving}
                      title="Reset to default"
                    >
                      Reset
                    </button>
                  </div>
                  <p className="ws-description">
                    Define how your Sous Chef communicates. This shapes the tone, style, and approach in all conversations.
                  </p>
                  <textarea
                    id="soul-prompt"
                    className="ws-textarea"
                    value={soulPrompt}
                    onChange={(e) => setSoulPrompt(e.target.value)}
                    placeholder="You are Sous Chef, a knowledgeable culinary assistant..."
                    maxLength={MAX_SOUL_PROMPT_LENGTH}
                    rows={10}
                  />
                  <div className="ws-char-count">
                    {soulPrompt.length} / {MAX_SOUL_PROMPT_LENGTH}
                  </div>
                </div>
              )}

              {/* Business Rules Tab */}
              {activeTab === 'rules' && (
                <div className="ws-field-group">
                  <div className="ws-field-header">
                    <label className="ws-label" htmlFor="business-rules">
                      Business Rules
                    </label>
                    <button
                      className="ws-reset-btn"
                      onClick={() => handleReset('business_rules')}
                      disabled={isSaving}
                      title="Clear rules"
                    >
                      Clear
                    </button>
                  </div>
                  <p className="ws-description">
                    Set operating constraints like hours, pricing policies, service boundaries, and other rules your Sous Chef should follow.
                  </p>
                  <textarea
                    id="business-rules"
                    className="ws-textarea"
                    value={businessRules}
                    onChange={(e) => setBusinessRules(e.target.value)}
                    placeholder="Example:&#10;- Operating hours: 9am-6pm, Monday-Saturday&#10;- No rush orders under 48 hours notice&#10;- Minimum order: $150&#10;- No seafood delivery on Mondays"
                    maxLength={MAX_BUSINESS_RULES_LENGTH}
                    rows={10}
                  />
                  <div className="ws-char-count">
                    {businessRules.length} / {MAX_BUSINESS_RULES_LENGTH}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Status Messages */}
          {updateMutation.isError && (
            <div className="ws-error">
              Failed to save changes. Please try again.
            </div>
          )}

          {resetMutation.isError && (
            <div className="ws-error">
              Failed to reset. Please try again.
            </div>
          )}

          {saveSuccess && (
            <div className="ws-success">
              Settings saved successfully!
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="ws-footer">
          <button className="ws-btn ws-btn-outline" onClick={handleClose}>
            Cancel
          </button>
          <button
            className="ws-btn ws-btn-primary"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </footer>

        <style>{`
          .ws-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1100;
            animation: wsFadeIn 0.2s ease;
          }

          @keyframes wsFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }

          .ws-modal {
            background: var(--surface, #fff);
            border-radius: 16px;
            width: 90%;
            max-width: 560px;
            max-height: 85vh;
            max-height: 85dvh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: wsSlideUp 0.25s ease;
          }

          @keyframes wsSlideUp {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }

          /* Header */
          .ws-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border, #e5e5e5);
            flex-shrink: 0;
          }

          .ws-title {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--text, #333);
          }

          .ws-close-btn {
            background: none;
            border: none;
            color: var(--muted, #888);
            cursor: pointer;
            padding: 0.25rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            transition: all 0.15s;
          }

          .ws-close-btn:hover {
            background: var(--surface-2, #f5f5f5);
            color: var(--text, #333);
          }

          /* Tabs */
          .ws-tabs {
            display: flex;
            border-bottom: 1px solid var(--border, #e5e5e5);
            padding: 0 1.25rem;
            flex-shrink: 0;
          }

          .ws-tab {
            padding: 0.875rem 1.25rem;
            background: none;
            border: none;
            border-bottom: 2px solid transparent;
            color: var(--muted, #888);
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            margin-bottom: -1px;
          }

          .ws-tab:hover {
            color: var(--text, #333);
          }

          .ws-tab.active {
            color: var(--primary, #5cb85c);
            border-bottom-color: var(--primary, #5cb85c);
          }

          /* Content */
          .ws-content {
            flex: 1;
            overflow-y: auto;
            padding: 1.25rem;
            -webkit-overflow-scrolling: touch;
          }

          .ws-loading {
            text-align: center;
            padding: 2rem;
            color: var(--muted, #888);
          }

          .ws-field-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
          }

          .ws-field-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
          }

          .ws-label {
            font-weight: 600;
            font-size: 1rem;
            color: var(--text, #333);
          }

          .ws-reset-btn {
            background: none;
            border: none;
            color: var(--primary, #5cb85c);
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            transition: all 0.15s;
          }

          .ws-reset-btn:hover:not(:disabled) {
            background: rgba(92, 184, 92, 0.1);
          }

          .ws-reset-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .ws-description {
            font-size: 0.875rem;
            color: var(--muted, #888);
            margin: 0;
            line-height: 1.5;
          }

          .ws-textarea {
            width: 100%;
            padding: 0.875rem;
            border: 1px solid var(--border, #ddd);
            border-radius: 10px;
            font-size: 0.9rem;
            font-family: inherit;
            line-height: 1.5;
            resize: vertical;
            background: var(--surface, #fff);
            color: var(--text, #333);
            transition: border-color 0.15s;
          }

          .ws-textarea:focus {
            outline: none;
            border-color: var(--primary, #5cb85c);
            box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.1);
          }

          .ws-textarea::placeholder {
            color: var(--muted, #aaa);
          }

          .ws-char-count {
            text-align: right;
            font-size: 0.8rem;
            color: var(--muted, #888);
          }

          /* Messages */
          .ws-error {
            padding: 0.75rem;
            background: rgba(220, 53, 69, 0.1);
            border: 1px solid rgba(220, 53, 69, 0.3);
            border-radius: 8px;
            color: #dc3545;
            font-size: 0.9rem;
            margin-top: 1rem;
          }

          .ws-success {
            padding: 0.75rem;
            background: rgba(92, 184, 92, 0.1);
            border: 1px solid rgba(92, 184, 92, 0.3);
            border-radius: 8px;
            color: var(--primary, #5cb85c);
            font-size: 0.9rem;
            margin-top: 1rem;
          }

          /* Footer */
          .ws-footer {
            display: flex;
            justify-content: flex-end;
            gap: 0.75rem;
            padding: 1rem 1.25rem;
            padding-bottom: max(1rem, env(safe-area-inset-bottom));
            border-top: 1px solid var(--border, #e5e5e5);
            flex-shrink: 0;
          }

          .ws-btn {
            padding: 0.625rem 1.25rem;
            border-radius: 8px;
            font-weight: 500;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.15s;
          }

          .ws-btn-outline {
            background: transparent;
            border: 1px solid var(--border, #ddd);
            color: var(--text, #333);
          }

          .ws-btn-outline:hover {
            border-color: var(--text, #333);
          }

          .ws-btn-primary {
            background: var(--primary, #5cb85c);
            border: none;
            color: white;
          }

          .ws-btn-primary:hover:not(:disabled) {
            background: var(--primary-700, #449d44);
          }

          .ws-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          /* Responsive */
          @media (max-width: 600px) {
            .ws-modal {
              width: 95%;
              max-height: 90vh;
              max-height: 90dvh;
              border-radius: 12px;
            }

            .ws-tabs {
              padding: 0 1rem;
            }

            .ws-tab {
              padding: 0.75rem 1rem;
              font-size: 0.85rem;
            }

            .ws-content {
              padding: 1rem;
            }

            .ws-footer {
              padding: 0.875rem 1rem;
            }
          }
        `}</style>
      </div>
    </div>
  )
}
