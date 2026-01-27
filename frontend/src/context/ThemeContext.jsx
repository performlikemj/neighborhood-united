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

// Update SVG favicon based on theme (for browsers that support SVG favicons)
function updateFavicon(isDark){
  try{
    const svgPath = isDark ? '/sautai_logo_new_dark.svg' : '/sautai_logo_new.svg'
    // Update SVG favicons only - PNG fallback stays constant for Safari
    document.querySelectorAll('link[rel="icon"][type="image/svg+xml"]').forEach(link => {
      link.href = svgPath
    })
  }catch(e){
    console.warn('Failed to update favicon:', e)
  }
}

export function ThemeProvider({ children }){
  const [theme, setThemeState] = useState(getInitialTheme)

  useEffect(()=>{
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    root.style.colorScheme = theme
    try{ localStorage.setItem('theme', theme) }catch{}
    // Update favicon based on theme
    updateFavicon(theme === 'dark')
    // Update theme-color meta for browser chrome
    try{
      const metaThemeColor = document.querySelector('meta[name="theme-color"]')
      if (metaThemeColor) {
        metaThemeColor.setAttribute('content', theme === 'dark' ? '#0d1410' : '#FFFFFF')
      }
    }catch{}
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


