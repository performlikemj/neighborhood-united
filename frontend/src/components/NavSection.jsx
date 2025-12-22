/**
 * NavSection Component
 * 
 * Collapsible navigation section wrapper for grouped navigation items.
 * Styles are in styles.css under .nav-section* classes.
 */

import React, { useState, useRef, useEffect } from 'react'

const STORAGE_PREFIX = 'chef_nav_section_'

export default function NavSection({
  id,
  title,
  children,
  defaultCollapsed = false,
  collapsible = true,
  sidebarCollapsed = false,
  className = ''
}) {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    if (!collapsible) return false
    try {
      const stored = localStorage.getItem(`${STORAGE_PREFIX}${id}`)
      return stored !== null ? stored === 'true' : defaultCollapsed
    } catch {
      return defaultCollapsed
    }
  })
  
  const contentRef = useRef(null)
  const [contentHeight, setContentHeight] = useState('auto')

  // Measure content height for animation
  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(isCollapsed ? 0 : contentRef.current.scrollHeight)
    }
  }, [isCollapsed, children])

  // Persist collapsed state
  const toggleCollapsed = () => {
    const newState = !isCollapsed
    setIsCollapsed(newState)
    try {
      localStorage.setItem(`${STORAGE_PREFIX}${id}`, String(newState))
    } catch {}
  }

  // When sidebar is collapsed, show minimal version (no headers, just items with divider)
  if (sidebarCollapsed) {
    return (
      <div className={`nav-section nav-section-collapsed-sidebar ${className}`}>
        <div className="nav-section-items">
          {children}
        </div>
      </div>
    )
  }

  return (
    <div className={`nav-section ${isCollapsed ? 'collapsed' : ''} ${className}`}>
      {title && (
        <button
          className="nav-section-header"
          onClick={collapsible ? toggleCollapsed : undefined}
          aria-expanded={!isCollapsed}
          aria-controls={`nav-section-${id}`}
          type="button"
        >
          <span className="nav-section-title">{title}</span>
          {collapsible && (
            <span className="nav-section-chevron">
              <svg 
                width="10" 
                height="10" 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor" 
                strokeWidth="2.5"
              >
                <path d="M6 9l6 6 6-6"/>
              </svg>
            </span>
          )}
        </button>
      )}
      <div 
        id={`nav-section-${id}`}
        className="nav-section-content"
        style={{ 
          height: title ? (isCollapsed ? 0 : contentHeight) : 'auto',
          overflow: title ? 'hidden' : 'visible'
        }}
      >
        <div ref={contentRef} className="nav-section-items">
          {children}
        </div>
      </div>
    </div>
  )
}
