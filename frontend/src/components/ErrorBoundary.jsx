import React from 'react'

// Only show error details in development, never in production
const isDev = import.meta.env.DEV

export default class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null, errorInfo: null }
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  
  componentDidCatch(error, errorInfo) {
    // Only log to console in development
    if (isDev) {
      console.error('ErrorBoundary caught:', error, errorInfo)
    }
    this.setState({ errorInfo })
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', maxWidth: '600px', margin: '2rem auto' }}>
          <h2 style={{ marginBottom: '1rem' }}>Something went wrong</h2>
          <p style={{ marginBottom: '1rem', color: '#666' }}>
            An unexpected error occurred. Please try refreshing the page.
          </p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              padding: '0.75rem 1.5rem',
              fontSize: '1rem',
              cursor: 'pointer',
              background: '#2f3e46',
              color: 'white',
              border: 'none',
              borderRadius: '6px'
            }}
          >
            Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
