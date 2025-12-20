/**
 * GhostTextarea Component
 * 
 * Textarea with Copilot-style ghost text suggestions.
 * Shows suggested value in lighter text after the current value.
 * Press Tab to accept, Escape to dismiss, or keep typing to overwrite.
 */

import React, { useState, useRef, useEffect, useCallback, forwardRef } from 'react'

/**
 * GhostTextarea - Textarea with inline ghost text suggestions
 * 
 * @param {string} value - Current textarea value
 * @param {function} onChange - Callback when value changes
 * @param {string} ghostValue - Suggested value to show as ghost text
 * @param {function} onAccept - Callback when suggestion is accepted (Tab)
 * @param {function} onDismiss - Callback when suggestion is dismissed (Escape)
 * @param {string} placeholder - Textarea placeholder text
 * @param {string} className - Additional CSS classes
 * @param {boolean} disabled - Whether textarea is disabled
 * @param {number} rows - Number of visible rows
 * @param {number} minRows - Minimum rows for auto-resize
 * @param {number} maxRows - Maximum rows for auto-resize
 * @param {boolean} autoResize - Whether to auto-resize based on content
 * @param {object} rest - Other textarea props
 */
const GhostTextarea = forwardRef(function GhostTextarea({
  value = '',
  onChange,
  ghostValue = '',
  onAccept,
  onDismiss,
  placeholder = '',
  className = '',
  disabled = false,
  rows = 3,
  minRows = 2,
  maxRows = 10,
  autoResize = true,
  showHint = true,
  ...rest
}, ref) {
  const [isFocused, setIsFocused] = useState(false)
  const [localValue, setLocalValue] = useState(value)
  const textareaRef = useRef(null)
  const ghostRef = useRef(null)
  const containerRef = useRef(null)
  
  // Sync local value with prop
  useEffect(() => {
    setLocalValue(value)
  }, [value])
  
  // Combine refs
  useEffect(() => {
    if (ref) {
      if (typeof ref === 'function') {
        ref(textareaRef.current)
      } else {
        ref.current = textareaRef.current
      }
    }
  }, [ref])
  
  /**
   * Auto-resize textarea based on content
   */
  useEffect(() => {
    if (!autoResize || !textareaRef.current) return
    
    const textarea = textareaRef.current
    const lineHeight = parseInt(getComputedStyle(textarea).lineHeight) || 24
    const paddingTop = parseInt(getComputedStyle(textarea).paddingTop) || 10
    const paddingBottom = parseInt(getComputedStyle(textarea).paddingBottom) || 10
    
    // Reset height to calculate scroll height
    textarea.style.height = 'auto'
    
    const minHeight = lineHeight * minRows + paddingTop + paddingBottom
    const maxHeight = lineHeight * maxRows + paddingTop + paddingBottom
    const scrollHeight = textarea.scrollHeight
    
    const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight)
    textarea.style.height = `${newHeight}px`
    
    // Also resize ghost layer to match
    if (ghostRef.current) {
      ghostRef.current.style.height = `${newHeight}px`
    }
  }, [localValue, autoResize, minRows, maxRows])
  
  /**
   * Calculate what ghost text to show
   * Only show ghost text that extends beyond current value
   */
  const getDisplayGhostText = useCallback(() => {
    if (!ghostValue || disabled) return ''
    
    const currentVal = String(localValue || '')
    const ghostVal = String(ghostValue)
    
    // If ghost value starts with current value, show the rest
    if (ghostVal.toLowerCase().startsWith(currentVal.toLowerCase()) && ghostVal !== currentVal) {
      return ghostVal.slice(currentVal.length)
    }
    
    // If current value is empty and we have a ghost, show full ghost
    if (!currentVal && ghostVal) {
      return ghostVal
    }
    
    return ''
  }, [localValue, ghostValue, disabled])
  
  const displayGhostText = getDisplayGhostText()
  const hasGhost = !!displayGhostText && isFocused
  
  /**
   * Handle textarea change
   */
  const handleChange = useCallback((e) => {
    const newValue = e.target.value
    setLocalValue(newValue)
    
    if (onChange) {
      onChange(newValue)
    }
  }, [onChange])
  
  /**
   * Handle key down events
   */
  const handleKeyDown = useCallback((e) => {
    // Tab to accept suggestion (only if at end of content and no selection)
    if (e.key === 'Tab' && hasGhost && ghostValue) {
      const textarea = textareaRef.current
      const atEnd = textarea.selectionStart === localValue.length && 
                    textarea.selectionEnd === localValue.length
      
      if (atEnd) {
        e.preventDefault()
        setLocalValue(ghostValue)
        
        if (onChange) {
          onChange(ghostValue)
        }
        
        if (onAccept) {
          onAccept(ghostValue)
        }
        
        // Move cursor to end
        setTimeout(() => {
          textarea.selectionStart = textarea.selectionEnd = ghostValue.length
        }, 0)
        return
      }
    }
    
    // Escape to dismiss suggestion
    if (e.key === 'Escape' && hasGhost) {
      e.preventDefault()
      if (onDismiss) {
        onDismiss()
      }
      return
    }
    
    // Pass through other key events
    if (rest.onKeyDown) {
      rest.onKeyDown(e)
    }
  }, [hasGhost, ghostValue, localValue, onChange, onAccept, onDismiss, rest])
  
  /**
   * Handle focus events
   */
  const handleFocus = useCallback((e) => {
    setIsFocused(true)
    if (rest.onFocus) {
      rest.onFocus(e)
    }
  }, [rest])
  
  const handleBlur = useCallback((e) => {
    setIsFocused(false)
    if (rest.onBlur) {
      rest.onBlur(e)
    }
  }, [rest])
  
  return (
    <div className={`ghost-textarea-container ${className}`} ref={containerRef}>
      <div className="ghost-textarea-wrapper">
        {/* Ghost text layer (behind textarea) */}
        {hasGhost && (
          <div className="ghost-text-layer" ref={ghostRef} aria-hidden="true">
            <span className="ghost-current">{localValue}</span>
            <span className="ghost-suggestion">{displayGhostText}</span>
          </div>
        )}
        
        {/* Actual textarea */}
        <textarea
          ref={textareaRef}
          value={localValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder={!hasGhost ? placeholder : ''}
          disabled={disabled}
          rows={rows}
          className={`ghost-textarea ${hasGhost ? 'has-ghost' : ''}`}
          autoComplete="off"
          {...rest}
        />
      </div>
      
      {/* Hint text */}
      {hasGhost && showHint && (
        <div className="ghost-hint">
          <kbd>Tab</kbd> to accept
        </div>
      )}
      
      <style>{`
        .ghost-textarea-container {
          position: relative;
          width: 100%;
        }
        
        .ghost-textarea-wrapper {
          position: relative;
          width: 100%;
        }
        
        /* Ghost text layer */
        .ghost-text-layer {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          pointer-events: none;
          white-space: pre-wrap;
          word-wrap: break-word;
          overflow: hidden;
          font: inherit;
        }
        
        /* Match textarea padding */
        .ghost-text-layer {
          padding: 0.625rem 0.875rem;
          line-height: 1.5;
        }
        
        .ghost-current {
          color: transparent;
        }
        
        .ghost-suggestion {
          color: var(--muted, #888);
          opacity: 0.6;
        }
        
        /* Textarea styles */
        .ghost-textarea {
          width: 100%;
          padding: 0.625rem 0.875rem;
          border: 1px solid var(--border, #ddd);
          border-radius: 8px;
          font-size: 0.95rem;
          font-family: inherit;
          line-height: 1.5;
          background: var(--surface, #fff);
          color: var(--text, #333);
          resize: vertical;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        
        .ghost-textarea:focus {
          outline: none;
          border-color: var(--primary, #5cb85c);
          box-shadow: 0 0 0 3px var(--primary-alpha, rgba(92, 184, 92, 0.15));
        }
        
        .ghost-textarea.has-ghost {
          background: transparent;
        }
        
        .ghost-textarea:disabled {
          opacity: 0.6;
          cursor: not-allowed;
          background: var(--surface-2, #f5f5f5);
          resize: none;
        }
        
        .ghost-textarea::placeholder {
          color: var(--muted, #888);
          opacity: 0.6;
        }
        
        /* Hint */
        .ghost-hint {
          position: absolute;
          bottom: -1.5rem;
          right: 0;
          font-size: 0.7rem;
          color: var(--muted, #888);
          display: flex;
          align-items: center;
          gap: 0.25rem;
          opacity: 0.8;
        }
        
        .ghost-hint kbd {
          background: var(--surface-2, #f0f0f0);
          border: 1px solid var(--border, #ddd);
          border-radius: 3px;
          padding: 0.1rem 0.35rem;
          font-size: 0.65rem;
          font-family: inherit;
        }
        
        /* Animation for ghost appearance */
        @keyframes ghostFadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 0.6;
          }
        }
        
        .ghost-suggestion {
          animation: ghostFadeIn 0.2s ease;
        }
      `}</style>
    </div>
  )
})

export default GhostTextarea
