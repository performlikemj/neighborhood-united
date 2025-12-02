import React, { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const TIMEZONES_FALLBACK = ['UTC','America/New_York','America/Chicago','America/Los_Angeles','Europe/London','Europe/Paris','Asia/Tokyo']
const MEASUREMENT_LABEL = { US: 'US Customary (oz, lb, cups)', METRIC: 'Metric (g, kg, ml, l)' }

export default function Register(){
  const { register } = useAuth()
  const nav = useNavigate()

  const browserTz = (()=>{
    try{ return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC' }catch{ return 'UTC' }
  })()

  const [form, setForm] = useState({ username:'', email:'', password:'', confirm:'', timezone: browserTz, measurement_system:'METRIC', auto_meal_plans_enabled: true })
  const [timezones, setTimezones] = useState(TIMEZONES_FALLBACK)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(()=>{
    try{
      const iana = (Intl && Intl.supportedValuesOf) ? Intl.supportedValuesOf('timeZone') : []
      if (Array.isArray(iana) && iana.length){
        const sorted = Array.from(new Set(iana)).sort((a,b)=> a.localeCompare(b))
        setTimezones(sorted)
        if (!sorted.includes(form.timezone)) setForm(f=>({...f, timezone:'UTC'}))
      }
    }catch{}
  }, [])

  const set = (k)=>(e)=> setForm({...form, [k]: e.target.value})

  const submit = async (e) => {
    e.preventDefault()
    setError(null)
    if (form.password !== form.confirm){ setError('Passwords do not match.'); return }
    if ((form.password||'').length < 8){ setError('Password must be at least 8 characters.'); return }
    setLoading(true)
    try{
      const body = {
        user: {
          username: form.username,
          email: form.email,
          password: form.password,
          timezone: form.timezone,
          measurement_system: form.measurement_system,
          auto_meal_plans_enabled: form.auto_meal_plans_enabled,
          preferred_language: 'en',
          allergies: [],
          custom_allergies: [],
          dietary_preferences: [],
          custom_dietary_preferences: [],
          household_member_count: 1,
          household_members: []
        }
      }
      await register(body)
      nav('/meal-plans')
    }catch(err){
      setError('Registration failed. Try a different username/email.')
    }finally{
      setLoading(false)
    }
  }

  return (
    <div style={{maxWidth:520, margin:'1rem auto'}}>
      <h2>Create your account</h2>
      <div className="muted" style={{marginBottom:'.5rem'}}>We only need the basics to get started. You can add the rest in your profile later.</div>
      <div className="muted" style={{marginBottom:'.75rem'}}>
        Prefer a guided chat? <a href="/onboarding">Try the onboarding assistant</a>.
      </div>
      {error && <div className="card" style={{borderColor:'#d9534f'}}>{error}</div>}
      <form onSubmit={submit}>
        <div className="label">Username</div>
        <input className="input" value={form.username} onChange={set('username')} required />
        <div className="label">Email</div>
        <input className="input" type="email" value={form.email} onChange={set('email')} required />
        <div className="label">Password</div>
        <input className="input" type="password" value={form.password} onChange={set('password')} required />
        <div className="label">Confirm Password</div>
        <input className="input" type="password" value={form.confirm} onChange={set('confirm')} required />
        <div className="label">Time Zone</div>
        <select className="select" value={form.timezone} onChange={set('timezone')}>
          {timezones.map(tz => <option key={tz} value={tz}>{tz}</option>)}
        </select>
        <div className="label" style={{marginTop:'.6rem'}}>Units</div>
        <div role="radiogroup" aria-label="Measurement system" style={{display:'flex', gap:'.75rem', alignItems:'center', marginBottom:'.5rem'}}>
          <label className="radio" style={{display:'flex', alignItems:'center', gap:'.35rem'}}>
            <input type="radio" name="measurement_system" checked={(form.measurement_system||'METRIC')==='US'} onChange={()=> setForm({...form, measurement_system:'US'})} />
            <span>{MEASUREMENT_LABEL.US}</span>
          </label>
          <label className="radio" style={{display:'flex', alignItems:'center', gap:'.35rem'}}>
            <input type="radio" name="measurement_system" checked={(form.measurement_system||'METRIC')==='METRIC'} onChange={()=> setForm({...form, measurement_system:'METRIC'})} />
            <span>{MEASUREMENT_LABEL.METRIC}</span>
          </label>
        </div>
        <label className="radio" style={{display:'flex', alignItems:'center', gap:'.35rem', marginTop:'.5rem'}}>
          <input
            type="checkbox"
            checked={Boolean(form.auto_meal_plans_enabled)}
            onChange={(e)=> setForm({...form, auto_meal_plans_enabled: e.target.checked})}
          />
          <span>Automatically create weekly meal plans</span>
        </label>
        <div className="muted" style={{marginTop:'.25rem'}}>Turn off if you only want chef-created or manually planned meals.</div>
        <div style={{marginTop:'.75rem'}}>
          <button className="btn btn-primary" disabled={loading}>{loading?'Creating…':'Create Account'}</button>
          <Link to="/login" className="btn btn-outline" style={{marginLeft:'.5rem'}}>I have an account</Link>
        </div>
      </form>
    </div>
  )
}
