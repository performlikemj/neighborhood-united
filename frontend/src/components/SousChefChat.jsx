/**
 * SousChefChat Component
 * 
 * AI chat interface for chefs to interact with the Sous Chef assistant
 * about a specific family. Includes streaming responses, tool call
 * visualization, and family context panel.
 */

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { getRandomChefEmoji } from '../utils/emojis.js'
import StructuredContent from './StructuredContent'
import {
  sendStructuredMessage,
  getSousChefHistory,
  newSousChefConversation,
  getFamilyContext
} from '../api/sousChefClient'

// Tool name display mapping
const TOOL_NAME_MAP = {
  get_family_dietary_summary: 'Checking dietary requirements',
  check_recipe_compliance: 'Checking recipe safety',
  suggest_family_menu: 'Generating menu suggestions',
  scale_recipe_for_household: 'Scaling recipe',
  get_family_order_history: 'Looking up order history',
  add_family_note: 'Adding note to CRM',
  get_upcoming_family_orders: 'Checking upcoming orders',
  estimate_prep_time: 'Estimating prep time',
  get_household_members: 'Getting household details'
}

export default function SousChefChat({
  familyId,
  familyType,
  familyName,
  chefEmoji: chefEmojiProp,
  initialContext,  // Pre-populated context from notifications
  onContextHandled, // Callback when context has been used
  initialInput,     // Pre-populated input text (from widget expansion)
  externalInputRef, // External ref to access the input element
  onAction          // Callback for action blocks (navigation/prefill)
}) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState(initialInput || '')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeTools, setActiveTools] = useState([])
  const [error, setError] = useState(null)
  const [familyContext, setFamilyContext] = useState(null)
  const [showContext, setShowContext] = useState(true)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [pendingPrompt, setPendingPrompt] = useState(null)
  
  // Use provided emoji or fallback to random for inclusive representation
  const chefEmoji = useMemo(() => chefEmojiProp || getRandomChefEmoji(), [chefEmojiProp])
  
  const endRef = useRef(null)
  const abortRef = useRef(null)
  const inputRef = useRef(null)
  const isInitialLoadRef = useRef(true)

  // Track the initial context prePrompt to detect new contexts
  const initialPrePromptRef = useRef(null)
  
  // Handle initial context from notifications
  // Store the context but don't clear it until it's actually used
  useEffect(() => {
    const prePrompt = initialContext?.prePrompt
    if (prePrompt && prePrompt !== initialPrePromptRef.current) {
      console.log('[SousChefChat] Received NEW context with prePrompt:', prePrompt.substring(0, 50) + '...')
      initialPrePromptRef.current = prePrompt
      setPendingPrompt(prePrompt)
      // DON'T call onContextHandled yet - wait until we actually use the prompt
    }
  }, [initialContext?.prePrompt])

  // Auto-fill pending prompt when a family is selected and history is loaded
  useEffect(() => {
    if (pendingPrompt && familyId && !historyLoading && !isStreaming) {
      console.log('[SousChefChat] Applying pending prompt for family:', familyId)
      // Small delay to ensure UI is ready
      const timer = setTimeout(() => {
        setInput(pendingPrompt)
        setPendingPrompt(null)
        initialPrePromptRef.current = null // Reset so we can receive new contexts
        // NOW we can mark context as handled
        if (onContextHandled) {
          onContextHandled()
        }
        // Focus the input so user can see and optionally edit before sending
        if (inputRef.current) {
          inputRef.current.focus()
        }
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [pendingPrompt, familyId, historyLoading, isStreaming, onContextHandled])

  // Determine if we're in general mode (no family selected)
  const isGeneralMode = !familyId

  // Load history and context when family changes (or general mode)
  useEffect(() => {
    let mounted = true
    
    async function loadData() {
      isInitialLoadRef.current = true  // Reset for new family/mode
      setHistoryLoading(true)
      setMessages([])
      setFamilyContext(null)
      setError(null)
      
      try {
        // Load history and context in parallel
        // For general mode, pass null values - API client handles this
        const [historyData, contextData] = await Promise.all([
          getSousChefHistory(familyId || null, familyType || null).catch(() => null),
          getFamilyContext(familyId || null, familyType || null).catch(() => null)
        ])
        
        if (!mounted) return
        
        if (historyData?.messages) {
          const formattedMessages = historyData.messages.map((msg, idx) => ({
            id: `hist-${idx}`,
            role: msg.role,
            content: msg.content,
            finalized: true
          }))
          setMessages(formattedMessages)
        }
        
        if (contextData) {
          setFamilyContext(contextData)
        }
      } catch (err) {
        if (mounted) {
          setError(err.message || 'Failed to load conversation')
        }
      } finally {
        if (mounted) {
          setHistoryLoading(false)
        }
      }
    }
    
    loadData()
    return () => { mounted = false }
  }, [familyId, familyType])

  // Auto-scroll - use instant on initial load, smooth for new messages
  useEffect(() => {
    if (isInitialLoadRef.current) {
      // Use instant scroll for initial load to avoid "spazzing" effect
      endRef.current?.scrollIntoView({ behavior: 'instant', block: 'end' })
      // Mark initial load as complete after a short delay
      const timer = setTimeout(() => {
        isInitialLoadRef.current = false
      }, 500)
      return () => clearTimeout(timer)
    } else {
      // Use smooth scroll for new messages
      endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [messages, activeTools])

  // Focus input when not streaming
  useEffect(() => {
    if (!isStreaming && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isStreaming, familyId])

  const handleNewChat = async () => {
    // Works in both family mode and general mode
    
    // Abort any in-progress stream
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    
    try {
      await newSousChefConversation(familyId, familyType)
      setMessages([])
      setActiveTools([])
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to start new conversation')
    }
  }

  const handleSend = useCallback(async () => {
    const text = input.trim()
    // Allow sending in both family mode and general mode
    if (!text || isStreaming) return
    
    setError(null)
    setInput('')
    
    // Add user message
    const userMsgId = `user-${Date.now()}`
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'chef',
      content: text,
      finalized: true
    }])
    
    // Add thinking indicator (placeholder assistant message)
    const assistantId = `assistant-${Date.now()}`
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      finalized: false,
      isThinking: true
    }])
    
    setIsStreaming(true)
    setActiveTools([])
    
    try {
      // Use structured output endpoint (non-streaming)
      // Pass null for family params in general mode
      const result = await sendStructuredMessage({
        familyId: familyId || null,
        familyType: familyType || null,
        message: text
      })
      
      if (result.status === 'success' && result.content) {
        // Convert structured content to JSON string for storage/display
        const contentJson = JSON.stringify(result.content)
        setMessages(prev => prev.map(m => 
          m.id === assistantId 
            ? { ...m, content: contentJson, finalized: true, isThinking: false }
            : m
        ))
      } else {
        // Handle error response
        const errorMsg = result.message || 'Something went wrong'
        setError(errorMsg)
        setMessages(prev => prev.map(m => 
          m.id === assistantId 
            ? { ...m, content: JSON.stringify({ blocks: [{ type: 'text', content: errorMsg }] }), finalized: true, isThinking: false }
            : m
        ))
      }
    } catch (err) {
      const errorMsg = err.message || 'An error occurred'
      setError(errorMsg)
      setMessages(prev => prev.map(m => 
        m.id === assistantId 
          ? { ...m, content: JSON.stringify({ blocks: [{ type: 'text', content: 'Sorry, something went wrong. Please try again.' }] }), finalized: true, isThinking: false }
          : m
      ))
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, familyId, familyType])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
      setIsStreaming(false)
    }
  }

  // Quick action buttons - different for general mode vs family mode
  const quickActions = isGeneralMode ? [
    { label: '📚 Platform help', prompt: 'How do I use Chef Hub?' },
    { label: '💳 Payment links', prompt: 'How do I send a payment link to a client?' },
    { label: '🍳 Kitchen setup', prompt: 'How do I set up my kitchen with ingredients and dishes?' },
    { label: '📅 Meal Shares', prompt: 'How do I create meal shares for multiple customers?' }
  ] : [
    { label: '🍽️ Menu suggestions', prompt: 'What should I make for this family this week?' },
    { label: '⚠️ Check allergies', prompt: 'What are the critical allergies I need to watch out for?' },
    { label: '📊 Order history', prompt: "Show me what I've made for them before." },
    { label: '👨‍👩‍👧 Family details', prompt: 'Tell me about each household member and their dietary needs.' }
  ]

  const handleQuickAction = (prompt) => {
    if (isStreaming) return
    setInput(prompt)
    // Auto-send after a brief delay for UX
    setTimeout(() => {
      const sendBtn = document.querySelector('.sous-chef-send-btn')
      if (sendBtn) sendBtn.click()
    }, 100)
  }

  return (
    <div className="sous-chef-chat">
      {/* Family Context Panel - only show in family mode */}
      {familyContext && !isGeneralMode && (
        <div className={`context-panel ${showContext ? 'expanded' : 'collapsed'}`}>
          <div className="context-header" onClick={() => setShowContext(!showContext)}>
            <span className="context-title">
              <span className="icon">👨‍👩‍👧‍👦</span>
              {familyContext.family_name}
            </span>
            <span className="toggle">{showContext ? '▼' : '▶'}</span>
          </div>
          
          {showContext && (
            <div className="context-body">
              <div className="context-row">
                <span className="label">Household:</span>
                <span className="value">{familyContext.household_size} members</span>
              </div>
              
              {familyContext.dietary_restrictions?.length > 0 && (
                <div className="context-row">
                  <span className="label">Dietary:</span>
                  <span className="value tags">
                    {familyContext.dietary_restrictions.map((d, i) => (
                      <span key={i} className="tag diet">{d}</span>
                    ))}
                  </span>
                </div>
              )}
              
              {familyContext.allergies?.length > 0 && (
                <div className="context-row">
                  <span className="label">Allergies:</span>
                  <span className="value tags">
                    {familyContext.allergies.map((a, i) => (
                      <span key={i} className="tag allergy">⚠️ {a}</span>
                    ))}
                  </span>
                </div>
              )}
              
              {familyContext.stats?.total_orders > 0 && (
                <div className="context-row">
                  <span className="label">History:</span>
                  <span className="value">
                    {familyContext.stats.total_orders} orders • ${familyContext.stats.total_spent?.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Chat Header */}
      <div className="chat-header">
        <div className="header-left">
          <span className="chef-icon">{chefEmoji}</span>
          <div>
            <h3>Sous Chef</h3>
            <span className="subtitle muted">
              {isGeneralMode 
                ? 'General Assistant — ask me anything about Chef Hub'
                : `Helping you serve ${familyName || 'this family'}`
              }
            </span>
          </div>
        </div>
        <button className="btn btn-outline btn-sm" onClick={handleNewChat} disabled={isStreaming}>
          New Chat
        </button>
      </div>

      {/* Messages */}
      <div className="messages-container">
        {historyLoading ? (
          <div className="loading-state">
            <span className="spinner" /> Loading conversation...
          </div>
        ) : messages.length === 0 ? (
          <div className="welcome-state">
            <div className="welcome-content">
              <span className="welcome-icon">{isGeneralMode ? '💡' : '🍳'}</span>
              <h3>How can I help you today?</h3>
              <p>
                {isGeneralMode 
                  ? "I can help with platform questions, SOPs, prep planning, and more. Select a client for personalized meal planning."
                  : "I have full context about this family's dietary needs, allergies, and your history with them."
                }
              </p>
              
              <div className="quick-actions">
                {quickActions.map((action, idx) => (
                  <button
                    key={idx}
                    className="quick-action-btn"
                    onClick={() => handleQuickAction(action.prompt)}
                    disabled={isStreaming}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                onAction={onAction}
                finalized={msg.finalized}
                isThinking={msg.isThinking}
              />
            ))}
            
            {/* Tool calls indicator */}
            {isStreaming && activeTools.length > 0 && (
              <div className="tools-row">
                {activeTools.map(tool => (
                  <span key={tool.id} className={`tool-chip ${tool.status}`}>
                    <span className="dot" />
                    {tool.name}
                  </span>
                ))}
              </div>
            )}
            
          </>
        )}
        
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}
        
        <div ref={endRef} />
      </div>

      {/* Input Area */}
      <div className="composer">
        <textarea
          ref={(el) => {
            inputRef.current = el
            if (externalInputRef) externalInputRef.current = el
          }}
          className="composer-input"
          rows={1}
          placeholder={`Ask about ${familyName || 'this family'}...`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming || historyLoading}
        />
        <div className="composer-actions">
          {isStreaming ? (
            <button className="btn btn-outline" onClick={handleStop}>
              Stop
            </button>
          ) : (
            <button 
              className="btn btn-primary sous-chef-send-btn" 
              onClick={handleSend}
              disabled={!input.trim() || historyLoading}
            >
              Send
            </button>
          )}
        </div>
      </div>

      <style>{`
        .sous-chef-chat {
          display: flex;
          flex-direction: column;
          height: 100%;
          background: var(--surface-2, #f9fafb);
          border-radius: 12px;
          overflow: hidden;
          color: var(--text);
        }
        
        .sous-chef-chat.empty-state {
          align-items: center;
          justify-content: center;
        }
        
        .empty-content {
          text-align: center;
          padding: 3rem;
          color: var(--muted);
        }
        
        .empty-icon {
          font-size: 4rem;
          display: block;
          margin-bottom: 1rem;
        }
        
        .empty-content h3 {
          margin: 0 0 0.5rem 0;
          color: var(--text);
        }
        
        /* Context Panel */
        .context-panel {
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          color: var(--text);
        }
        
        .context-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.75rem 1rem;
          cursor: pointer;
          user-select: none;
        }
        
        .context-header:hover {
          background: var(--surface-2);
        }
        
        .context-title {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-weight: 600;
          color: var(--text);
        }
        
        .context-title .icon {
          font-size: 1.25rem;
        }
        
        .toggle {
          color: var(--muted);
          font-size: 0.75rem;
        }
        
        .context-body {
          padding: 0 1rem 1rem 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        
        .context-row {
          display: flex;
          gap: 0.5rem;
          font-size: 0.875rem;
          color: var(--text);
        }
        
        .context-row .label {
          color: var(--muted);
          min-width: 70px;
        }
        
        .context-row .value.tags {
          display: flex;
          flex-wrap: wrap;
          gap: 0.25rem;
        }
        
        .tag {
          padding: 0.125rem 0.5rem;
          border-radius: 12px;
          font-size: 0.75rem;
        }
        
        .tag.diet {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
        }
        
        .tag.allergy {
          background: rgba(220, 38, 38, 0.15);
          color: #ef4444;
        }
        
        /* Chat Header */
        .chat-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem;
          background: var(--surface);
          border-bottom: 1px solid var(--border);
        }
        
        .header-left {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        
        .chef-icon {
          font-size: 2rem;
        }
        
        .chat-header h3 {
          margin: 0;
          font-size: 1.125rem;
          color: var(--text);
        }
        
        .subtitle {
          font-size: 0.8rem;
          color: var(--muted);
        }
        
        /* Messages */
        .messages-container {
          flex: 1;
          overflow-y: auto;
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .loading-state,
        .welcome-state {
          display: flex;
          align-items: center;
          justify-content: center;
          flex: 1;
          color: var(--muted);
        }
        
        .welcome-content {
          text-align: center;
          max-width: 400px;
        }
        
        .welcome-icon {
          font-size: 3rem;
          display: block;
          margin-bottom: 1rem;
        }
        
        .welcome-content h3 {
          margin: 0 0 0.5rem 0;
          color: var(--text);
        }
        
        .welcome-content p {
          color: var(--muted);
        }
        
        .quick-actions {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          justify-content: center;
          margin-top: 1.5rem;
        }
        
        .quick-action-btn {
          padding: 0.5rem 1rem;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 20px;
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
          color: var(--text);
        }
        
        .quick-action-btn:hover:not(:disabled) {
          background: var(--primary);
          color: white;
          border-color: var(--primary);
        }
        
        .quick-action-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        /* Message Bubbles */
        .msg-row {
          display: flex;
        }
        
        .msg-row.chef {
          justify-content: flex-end;
        }
        
        .msg-row.assistant {
          justify-content: flex-start;
        }
        
        .bubble {
          max-width: 80%;
          padding: 0.75rem 1rem;
          border-radius: 12px;
          word-wrap: break-word;
        }
        
        .bubble.chef {
          background: var(--primary);
          color: white;
          border-bottom-right-radius: 4px;
        }
        
        .bubble.assistant {
          background: var(--surface);
          border: 1px solid var(--border);
          border-bottom-left-radius: 4px;
          color: var(--text);
        }
        
        /* Thinking indicator - animated dots */
        .thinking-indicator {
          display: flex;
          gap: 4px;
          padding: 4px 0;
        }
        
        .thinking-dot {
          width: 8px;
          height: 8px;
          background: var(--primary);
          border-radius: 50%;
          animation: thinking-bounce 1.4s infinite ease-in-out both;
        }
        
        .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
        .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
        .thinking-dot:nth-child(3) { animation-delay: 0s; }
        
        @keyframes thinking-bounce {
          0%, 80%, 100% {
            transform: scale(0.6);
            opacity: 0.5;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
        
        /* ═══════════════════════════════════════════════════════════════════ */
        /* STRUCTURED CONTENT STYLING                                          */
        /* ═══════════════════════════════════════════════════════════════════ */
        
        .bubble.assistant .markdown-content {
          line-height: 1.6;
          color: var(--text);
          font-size: 0.9rem;
          word-break: break-word;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Paragraphs                                                          */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content p {
          color: var(--text);
          margin: 0.75em 0;
        }
        
        .bubble.assistant .markdown-content p:first-child {
          margin-top: 0;
        }
        
        .bubble.assistant .markdown-content p:last-child {
          margin-bottom: 0;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Headings                                                            */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content h1,
        .bubble.assistant .markdown-content h2,
        .bubble.assistant .markdown-content h3,
        .bubble.assistant .markdown-content h4,
        .bubble.assistant .markdown-content h5,
        .bubble.assistant .markdown-content h6 {
          color: var(--text);
          font-weight: 600;
          line-height: 1.3;
          margin-top: 1.25em;
          margin-bottom: 0.5em;
        }
        
        .bubble.assistant .markdown-content h1 {
          font-size: 1.3em;
          border-bottom: 1px solid var(--border);
          padding-bottom: 0.3em;
        }
        
        .bubble.assistant .markdown-content h2 {
          font-size: 1.15em;
          border-bottom: 1px solid var(--border);
          padding-bottom: 0.25em;
        }
        
        .bubble.assistant .markdown-content h3 {
          font-size: 1.05em;
        }
        
        .bubble.assistant .markdown-content h4,
        .bubble.assistant .markdown-content h5,
        .bubble.assistant .markdown-content h6 {
          font-size: 1em;
        }
        
        .bubble.assistant .markdown-content h1:first-child,
        .bubble.assistant .markdown-content h2:first-child,
        .bubble.assistant .markdown-content h3:first-child,
        .bubble.assistant .markdown-content h4:first-child {
          margin-top: 0;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Lists                                                               */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content ul,
        .bubble.assistant .markdown-content ol {
          margin: 0.75em 0;
          padding-left: 1.5em;
          color: var(--text);
        }
        
        .bubble.assistant .markdown-content li {
          color: var(--text);
          margin: 0.35em 0;
          line-height: 1.5;
        }
        
        .bubble.assistant .markdown-content li > p {
          margin: 0.25em 0;
        }
        
        /* Nested lists */
        .bubble.assistant .markdown-content ul ul,
        .bubble.assistant .markdown-content ul ol,
        .bubble.assistant .markdown-content ol ul,
        .bubble.assistant .markdown-content ol ol {
          margin: 0.25em 0;
        }
        
        /* Unordered list markers */
        .bubble.assistant .markdown-content ul {
          list-style-type: disc;
        }
        
        .bubble.assistant .markdown-content ul ul {
          list-style-type: circle;
        }
        
        .bubble.assistant .markdown-content ul ul ul {
          list-style-type: square;
        }
        
        /* Ordered list markers */
        .bubble.assistant .markdown-content ol {
          list-style-type: decimal;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Inline text styles                                                  */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content strong {
          color: var(--text);
          font-weight: 700;
        }
        
        .bubble.assistant .markdown-content em {
          color: var(--text);
          font-style: italic;
        }
        
        .bubble.assistant .markdown-content a {
          color: var(--link, var(--primary));
          text-decoration: underline;
        }
        
        .bubble.assistant .markdown-content a:hover {
          opacity: 0.8;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Inline code                                                         */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content code {
          background: var(--surface-2);
          border: 1px solid var(--border);
          padding: 0.15em 0.4em;
          border-radius: 4px;
          font-size: 0.85em;
          font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, monospace;
          color: var(--text);
          white-space: nowrap;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Code blocks (pre > code)                                            */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content pre {
          background: var(--surface-2);
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 0.75em 1em;
          margin: 0.75em 0;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }
        
        .bubble.assistant .markdown-content pre code {
          background: transparent;
          border: none;
          padding: 0;
          font-size: 0.85em;
          white-space: pre;
          word-break: normal;
          overflow-wrap: normal;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Blockquotes                                                         */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content blockquote {
          margin: 0.75em 0;
          padding: 0.5em 0 0.5em 1em;
          border-left: 4px solid var(--primary);
          background: rgba(92, 184, 92, 0.08);
          border-radius: 0 6px 6px 0;
          color: var(--muted);
          font-style: italic;
        }
        
        .bubble.assistant .markdown-content blockquote p {
          margin: 0.25em 0;
          color: inherit;
        }
        
        .bubble.assistant .markdown-content blockquote p:first-child {
          margin-top: 0;
        }
        
        .bubble.assistant .markdown-content blockquote p:last-child {
          margin-bottom: 0;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Tables                                                              */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content table {
          border-collapse: collapse;
          margin: 0.75em 0;
          font-size: 0.85em;
          width: 100%;
          display: block;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }
        
        .bubble.assistant .markdown-content thead {
          background: var(--surface-2);
        }
        
        .bubble.assistant .markdown-content th {
          background: var(--surface-2);
          border: 1px solid var(--border);
          padding: 0.5em 0.75em;
          color: var(--text);
          font-weight: 600;
          text-align: left;
          white-space: nowrap;
        }
        
        .bubble.assistant .markdown-content td {
          border: 1px solid var(--border);
          padding: 0.5em 0.75em;
          color: var(--text);
          vertical-align: top;
        }
        
        /* Alternating row colors */
        .bubble.assistant .markdown-content tbody tr:nth-child(even) {
          background: rgba(128, 128, 128, 0.05);
        }
        
        .bubble.assistant .markdown-content tbody tr:hover {
          background: rgba(92, 184, 92, 0.08);
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Horizontal rules                                                    */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content hr {
          border: none;
          border-top: 1px solid var(--border);
          margin: 1.25em 0;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Images                                                              */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content img {
          max-width: 100%;
          height: auto;
          border-radius: 6px;
          margin: 0.5em 0;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Task lists (GFM)                                                    */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content input[type="checkbox"] {
          margin-right: 0.5em;
          vertical-align: middle;
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Definition lists (if supported)                                     */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content dl {
          margin: 0.75em 0;
        }
        
        .bubble.assistant .markdown-content dt {
          font-weight: 600;
          color: var(--text);
          margin-top: 0.5em;
        }
        
        .bubble.assistant .markdown-content dd {
          margin-left: 1.5em;
          color: var(--muted);
        }
        
        /* ─────────────────────────────────────────────────────────────────── */
        /* Spacing between block elements                                      */
        /* ─────────────────────────────────────────────────────────────────── */
        .bubble.assistant .markdown-content > *:first-child {
          margin-top: 0 !important;
        }
        
        .bubble.assistant .markdown-content > *:last-child {
          margin-bottom: 0 !important;
        }
        
        /* Tools Row */
        .tools-row {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          padding: 0.5rem 0;
        }
        
        .tool-chip {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.25rem 0.75rem;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 16px;
          font-size: 0.8rem;
          color: var(--text);
        }
        
        .tool-chip .dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--primary);
        }
        
        .tool-chip.running .dot {
          animation: pulse 1s infinite;
        }
        
        .tool-chip.done .dot {
          background: #10b981;
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        
        /* Typing Indicator */
        .typing-indicator {
          display: flex;
          gap: 4px;
          padding: 0.75rem 1rem;
          background: var(--surface);
          border-radius: 12px;
          width: fit-content;
        }
        
        .typing-indicator .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--muted);
          animation: bounce 1.4s infinite;
        }
        
        .typing-indicator .dot:nth-child(2) {
          animation-delay: 0.2s;
        }
        
        .typing-indicator .dot:nth-child(3) {
          animation-delay: 0.4s;
        }
        
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-4px); }
        }
        
        /* Error */
        .error-message {
          padding: 0.75rem 1rem;
          background: rgba(220, 38, 38, 0.15);
          color: #ef4444;
          border-radius: 8px;
          font-size: 0.875rem;
        }
        
        /* Composer */
        .composer {
          display: flex;
          gap: 0.75rem;
          padding: 1rem;
          background: var(--surface);
          border-top: 1px solid var(--border);
        }
        
        .composer-input {
          flex: 1;
          padding: 0.75rem 1rem;
          border: 1px solid var(--border);
          border-radius: 8px;
          resize: none;
          font-family: inherit;
          font-size: 0.9rem;
          background: var(--surface, #fff);
          color: var(--text);
        }
        
        .composer-input::placeholder {
          color: var(--muted);
        }
        
        .composer-input:focus {
          outline: none;
          border-color: var(--primary);
        }
        
        .composer-input:disabled {
          background: var(--surface-2);
          color: var(--muted);
        }
        
        .spinner {
          display: inline-block;
          width: 18px;
          height: 18px;
          border: 2px solid var(--border);
          border-top-color: var(--primary);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-right: 0.5rem;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

/**
 * Message bubble component with structured content rendering.
 * Uses StructuredContent for assistant messages to render JSON blocks.
 */
function MessageBubble({ role, content, finalized, isThinking, onAction }) {
  const isChef = role === 'chef'
  
  return (
    <div className={`msg-row ${isChef ? 'chef' : 'assistant'}`}>
      <div className={`bubble ${isChef ? 'chef' : 'assistant'} ${!finalized ? 'streaming' : ''}`}>
        {isChef ? (
          <div>{content}</div>
        ) : isThinking ? (
          <div className="thinking-indicator">
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
            <span className="thinking-dot"></span>
          </div>
        ) : (
          <StructuredContent content={content} onAction={onAction} />
        )}
      </div>
    </div>
  )
}
