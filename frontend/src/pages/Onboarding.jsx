import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, refreshAccessToken, setTokens, buildErrorMessage } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import ResponseView from '../components/ResponseView.jsx'

export default function Onboarding(){
  const nav = useNavigate()
  const { refreshUser } = useAuth()
  const [guestId, setGuestId] = useState(() => localStorage.getItem('onboarding_guest_id') || '')
  const [responseId, setResponseId] = useState(null)
  const [messages, setMessages] = useState([]) // {id, role, content}
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState(null)
  const [aborter, setAborter] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [pwSubmitting, setPwSubmitting] = useState(false)

  const endRef = useRef(null)
  const debug = React.useMemo(()=>{ try{ return localStorage.getItem('chatDebug') === '1' || (import.meta?.env?.VITE_CHAT_DEBUG === 'true') }catch{ return false } }, [])

  // Using centralized ResponseView renderer; easy swap to v0 later

  useEffect(()=>{ endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, isStreaming])

  // Start or resume onboarding conversation
  useEffect(()=>{
    let mounted = true
    async function boot(){
    try{
      const payload = guestId ? { guest_id: guestId } : {}
      const resp = await api.post('/customer_dashboard/api/assistant/onboarding/new-conversation/', payload, { skipUserId: true })
        const gid = resp?.data?.guest_id || guestId
        if (!gid) throw new Error('No guest id returned')
        if (!guestId){ localStorage.setItem('onboarding_guest_id', gid) }
        if (mounted){ setGuestId(gid) }
      }catch(e){
        const msg = buildErrorMessage(e?.response?.data, 'Unable to start onboarding', e?.response?.status)
        setError(new Error(msg))
      }
    }
    boot()
    return ()=>{ mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Seed a friendly assistant greeting on first show (frontend-only)
  useEffect(()=>{
    if (!guestId) return
    try{
      const greeted = localStorage.getItem('onboarding_greeted')
      if (!greeted && messages.length === 0){
        setMessages([{ id: 'greet', role: 'assistant', content: 'Welcome to sautai! What username would you like me to call you?' }])
        localStorage.setItem('onboarding_greeted', '1')
      }
    }catch{}
  }, [guestId])

  function resetConversation(){
    aborter?.abort()
    setAborter(null)
    setMessages([])
    setResponseId(null)
    setInput('')
    setError(null)
    try{ localStorage.removeItem('onboarding_greeted') }catch{}
  }

  async function send(){
    const text = input.trim()
    if (!text || !guestId || isStreaming) return
    setInput('')
    setError(null)

    // Push user bubble
    setMessages(prev => [...prev, { id: `u-${Date.now()}`, role: 'user', content: text, finalized: true }])
    // Placeholder assistant bubble
    const aid = `a-${Date.now()}`
    setMessages(prev => [...prev, { id: aid, role: 'assistant', content: '', finalized: false }])

    const controller = new AbortController()
    setAborter(controller)
    setIsStreaming(true)

    try{
      const url = `/customer_dashboard/api/assistant/onboarding/stream-message/`
      const body = { message: text, guest_id: guestId }
      if (responseId) body.response_id = responseId

      // We use fetch for SSE; include cookies for guest sticky session
      let resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify(body),
        signal: controller.signal,
        credentials: 'include'
      })
      if (!resp.ok) throw new Error(`Request failed ${resp.status}`)

      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let passwordRequested = false

      const commitAppend = (delta)=>{
        if (!delta) return
        
        setMessages(prev => prev.map(m => {
          if (m.id !== aid) return m
          const curr = m.content || ''
          const d = String(delta)
          if (d.startsWith(curr)) return { ...m, content: d }
          if (curr && (curr.endsWith(d) || curr.includes(d))) return m
          return { ...m, content: curr + d }
        }))
      }

      const normalizeMarkdownOnFinalize = (text)=>{
        try{
          const src = String(text||'')
          const lines = src.split('\n')
          const out = []
          let inTable = false
          for (let i=0; i<lines.length; i++){
            const line = lines[i]
            const isTableRow = /^\s*\|.*\|\s*$/.test(line)
            if (isTableRow){
              if (!inTable){
                inTable = true
                if (out.length && out[out.length-1].trim() !== '') out.push('')
                out.push(line)
                const next = lines[i+1] || ''
                const hasSep = /^\s*\|?\s*:?-{3,}\s*(\|\s*:?-{3,}\s*)+\|?\s*$/.test(next)
                if (!hasSep){
                  const cols = line.split('|').filter(Boolean).length
                  if (cols > 1){ out.push('|' + Array(cols).fill(' --- ').join('|') + '|') }
                }
                continue
              } else {
                out.push(line)
                continue
              }
            } else {
              inTable = false
              out.push(line)
            }
          }
          const normalized = out.join('\n')
          
          return normalized
        }catch{ return String(text||'') }
      }

      const processEvent = (dataLine)=>{
        try{
          const json = JSON.parse(dataLine)
          const t = json?.type
          
          if (t === 'response.created' || t === 'response_id'){
            const rid = json?.id
            if (rid) setResponseId(rid)
          } else if (t === 'response.output_text.delta'){
            commitAppend(json?.delta?.text || '')
          } else if (t === 'response.tool'){
            const name = json?.name
            if (name === 'response.render'){
              const md = json?.output?.markdown || json?.output?.md || json?.output?.text || ''
              if (md){
                const normalized = normalizeMarkdownOnFinalize(md)
                { try{ window.__lastOnboarding = normalized }catch{} }
                setMessages(prev => prev.map(m => m.id === aid ? ({ ...m, content: normalized, finalized: true }) : m))
              }
            }
          } else if (t === 'response.completed'){
            setMessages(prev => prev.map(m => {
              if (m.id !== aid) return m
              const normalized = normalizeMarkdownOnFinalize(m.content)
              if (debug){ try{ window.__lastOnboarding = normalized }catch{} }
              return { ...m, finalized: true, content: normalized }
            }))
          } else if (t === 'text'){
            commitAppend(json?.content || '')
          } else if (t === 'password_request'){
            if (json?.is_password_request){
              passwordRequested = true
            }
          } else if (t === 'error'){
            throw new Error(json?.message || 'Stream error')
          }
        }catch(e){ /* ignore single-line parse issues */ }
      }

      // Read SSE stream
      while (true){
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1){
          const chunk = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          const lines = chunk.split('\n')
          for (const line of lines){
            const trimmed = line.trim()
            if (trimmed.startsWith('data: ')){
              const data = trimmed.slice(6)
              if (data) processEvent(data)
            }
          }
        }
        if (passwordRequested){
          try{ controller.abort() }catch{}
          break
        }
      }

      if (passwordRequested){
        setShowPassword(true)
      }
      // Finalize if stream closed without explicit completed
      setMessages(prev => prev.map(m => {
        if (m.id !== aid) return m
        if (m.finalized) return m
        const normalized = normalizeMarkdownOnFinalize(m.content)
        if (debug){ try{ window.__lastOnboarding = normalized }catch{} }
        return { ...m, finalized: true, content: normalized }
      }))

    } catch (e){
      if (e?.name !== 'AbortError'){
        setError(e)
        setMessages(prev => prev.map(m => (m.id === aid && !m.content) ? { ...m, content: 'Sorry, something went wrong. Please try again.' } : m))
      }
    } finally {
      setIsStreaming(false)
      setAborter(null)
      // Safety finalize on unexpected termination
      setMessages(prev => prev.map(m => (m.role === 'assistant' && !m.finalized) ? ({ ...m, finalized: true }) : m))
    }
  }

  async function completeRegistration(e){
    e?.preventDefault?.()
    if (!guestId) return
    const p = pw.trim()
    const p2 = pw2.trim()
    if (p.length < 8 || p !== p2) return
    setPwSubmitting(true)
    try{
      const resp = await api.post('/auth/api/secure-onboarding-complete/', { guest_id: guestId, password: p }, { skipUserId: true })
      const data = resp?.data || {}
      if (data?.access || data?.refresh){
        try{ setTokens({ access: data.access, refresh: data.refresh }) }catch{}
      }
      try{ await refreshUser() }catch{}
      // Clear onboarding state and navigate
      localStorage.removeItem('onboarding_guest_id')
      setShowPassword(false)
      setPw(''); setPw2('')
      nav('/chat')
    } catch (e){
      const msg = buildErrorMessage(e?.response?.data, 'Registration failed. Please try again.', e?.response?.status)
      window.dispatchEvent(new CustomEvent('global-toast', { detail: { text: msg, tone:'error' } }))
    } finally {
      setPwSubmitting(false)
    }
  }

  const onKeyDown = (e)=>{
    if (e.key === 'Enter' && !e.shiftKey){
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="page-chat">
      <div className="chat-header">
        <div className="left">
          <h2>Onboarding Assistant</h2>
          <div className="sub muted">Create your account by chatting with our assistant.</div>
        </div>
        <div className="right">
          <button className="btn btn-outline" onClick={resetConversation} disabled={isStreaming}>Restart</button>
        </div>
      </div>

      <div className="chat-surface card">
        <div className="messages" role="log" aria-live="polite">
          {messages.map(m => (
            <MessageBubble key={m.id} role={m.role} content={m.content} finalized={m.finalized} />
          ))}
          {isStreaming && (
            <div className="typing-row"><span className="dot" /><span className="dot" /><span className="dot" /></div>
          )}
          <div ref={endRef} />
        </div>

        <div className="composer">
          <textarea
            className="textarea"
            rows={1}
            placeholder={guestId ? 'Tell us your preferences…' : 'Starting…'}
            value={input}
            onChange={(e)=> setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={isStreaming || !guestId}
          />
          <div className="composer-actions">
            {isStreaming ? (
              <button className="btn btn-outline" onClick={()=> aborter?.abort()}>Stop</button>
            ) : (
              <button className="btn btn-primary" onClick={send} disabled={!guestId || !input.trim()}>Send</button>
            )}
          </div>
        </div>
        {error && <div className="error-text">{String(error?.message || error)}</div>}
      </div>

      {showPassword && (
        <PasswordModal
          pw={pw}
          pw2={pw2}
          setPw={setPw}
          setPw2={setPw2}
          busy={pwSubmitting}
          onCancel={()=>{ setShowPassword(false) }}
          onSubmit={completeRegistration}
        />
      )}
    </div>
  )
}

function MessageBubble({ role, content, finalized }){
  const isUser = role === 'user'
  return (
    <div className={`msg-row ${isUser ? 'right' : 'left'}`}>
      <div className={`bubble ${isUser ? 'user' : 'assistant'}`}>
        <div className="bubble-content">
          {isUser || !finalized ? (
            content
          ) : (
            <ResponseView>{content}</ResponseView>
          )}
        </div>
      </div>
    </div>
  )
}

function PasswordModal({ pw, pw2, setPw, setPw2, busy, onCancel, onSubmit }){
  const validLen = (pw||'').length >= 8
  const matches = (pw||'') && (pw2||'') && pw === pw2
  const canSubmit = validLen && matches && !busy
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Complete Registration">
      <div className="modal-card">
        <h3>Complete Your Registration</h3>
        <p className="muted">Create a secure password to finish setting up your account.</p>
        <div className="label">Password</div>
        <input className="input" type="password" value={pw} onChange={(e)=> setPw(e.target.value)} placeholder="At least 8 characters" />
        <div className="label">Confirm Password</div>
        <input className="input" type="password" value={pw2} onChange={(e)=> setPw2(e.target.value)} />
        {!validLen && pw && <div className="error-text">Password must be at least 8 characters.</div>}
        {pw2 && !matches && <div className="error-text">Passwords do not match.</div>}
        <div style={{display:'flex', gap:'.5rem', marginTop:'.75rem'}}>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={onSubmit}>{busy ? 'Submitting…' : 'Complete Registration'}</button>
          <button className="btn btn-outline" onClick={onCancel} disabled={busy}>Cancel</button>
        </div>
      </div>
    </div>
  )
}
