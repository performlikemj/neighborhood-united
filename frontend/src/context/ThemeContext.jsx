import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'

const ThemeContext = createContext({ theme: 'light', setTheme: () => {}, toggleTheme: () => {} })

function getSystemTheme(){
  try{
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }catch{
    return 'light'
  }
}

function getInitialTheme(){
  try{
    const stored = localStorage.getItem('theme')
    if (stored === 'light' || stored === 'dark') return stored
  }catch{}
  return getSystemTheme()
}

// Update favicon based on theme
function updateFavicon(isDark){
  try{
    const faviconPath = isDark ? '/sautai_logo_new_dark.svg' : '/sautai_logo_new.svg'
    // Update all favicon link elements
    const linkElements = document.querySelectorAll('link[rel*="icon"]')
    linkElements.forEach(link => {
      // Only update SVG/PNG favicon links, not apple-touch-icon
      if (link.getAttribute('rel') === 'icon' || link.getAttribute('rel') === 'shortcut icon'){
        link.href = faviconPath
      }
    })
    // Also update or create a primary favicon link if none exists
    let primaryFavicon = document.querySelector('link[rel="icon"][type="image/svg+xml"]')
    if (!primaryFavicon){
      primaryFavicon = document.createElement('link')
      primaryFavicon.rel = 'icon'
      primaryFavicon.type = 'image/svg+xml'
      document.head.appendChild(primaryFavicon)
    }
    primaryFavicon.href = faviconPath
  }catch(e){
    console.warn('Failed to update favicon:', e)
  }
}

export function ThemeProvider({ children }){
  const [theme, setThemeState] = useState(getInitialTheme)

  useEffect(()=>{
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    try{ localStorage.setItem('theme', theme) }catch{}
    // Update favicon based on theme
    updateFavicon(theme === 'dark')
  }, [theme])

  useEffect(()=>{
    // React to system preference changes only if user hasn't explicitly chosen
    let stored
    try{ stored = localStorage.getItem('theme') }catch{}
    if (stored === 'light' || stored === 'dark') return
    const mql = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null
    const onChange = () => setThemeState(getSystemTheme())
    try{ mql && mql.addEventListener('change', onChange) }catch{ try{ mql && mql.addListener(onChange) }catch{} }
    return () => { try{ mql && mql.removeEventListener('change', onChange) }catch{ try{ mql && mql.removeListener(onChange) }catch{} } }
  }, [])

  const api = useMemo(()=>({
    theme,
    setTheme: (t) => setThemeState(t === 'dark' ? 'dark' : 'light'),
    toggleTheme: () => setThemeState(prev => prev === 'dark' ? 'light' : 'dark')
  }), [theme])

  return (
    <ThemeContext.Provider value={api}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(){
  return useContext(ThemeContext)
}


