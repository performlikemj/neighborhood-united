import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../api'

export default function Home(){
  const { user } = useAuth()
  const [applyOpen, setApplyOpen] = useState(false)
  const [chefForm, setChefForm] = useState({ experience:'', bio:'', serving_areas:'', profile_pic:null })
  const [submitting, setSubmitting] = useState(false)
  const [applyMsg, setApplyMsg] = useState(null)

  return (
    <div className="page-home">
      {/* Hero - Chef Focused */}
      <section className="section">
        <div className="hero hero-split">
          <div className="hero-content">
            <div className="eyebrow">Chef CRM • Client Management • Growth</div>
            <h1 className="display"><span className="text-gradient">Grow Your Culinary Business</span></h1>
            <p>The all-in-one platform for independent chefs. Manage clients, services, and bookings — focus on cooking while we handle the business side.</p>
            <div className="hero-actions">
              {!user && <Link to="/register" className="btn btn-primary">Start Your Chef Profile</Link>}
              {user?.is_chef && <Link to="/chefs/dashboard" className="btn btn-primary">Go to Chef Hub</Link>}
              {user && !user?.is_chef && <button className="btn btn-primary" onClick={()=> setApplyOpen(true)}>Become a Chef</button>}
              {!user && <Link to="/chefs" className="btn btn-outline">Looking for a Chef?</Link>}
            </div>
          </div>
          <div className="hero-image">
            <img src="https://live.staticflickr.com/65535/54548860874_7569d1dbdc_b.jpg" alt="Professional chef at work" className="image-rounded" />
          </div>
        </div>
      </section>

      <div className="divider" />

      {applyOpen && (
        <>
          <div className="right-panel-overlay" onClick={()=> setApplyOpen(false)} />
          <aside className="right-panel" role="dialog" aria-label="Become a Chef">
            <div className="right-panel-head">
              <div className="slot-title">Become a Community Chef</div>
              <button className="icon-btn" onClick={()=> setApplyOpen(false)}>✕</button>
            </div>
            <div className="right-panel-body">
              {applyMsg && <div className="card" style={{marginBottom:'.6rem'}}>{applyMsg}</div>}
              <p className="muted">Share your experience and where you can serve. You can complete your profile later.</p>
              <div className="label">Experience</div>
              <textarea className="textarea" rows={3} value={chefForm.experience} onChange={e=> setChefForm({...chefForm, experience:e.target.value})} />
              <div className="label">Bio</div>
              <textarea className="textarea" rows={3} value={chefForm.bio} onChange={e=> setChefForm({...chefForm, bio:e.target.value})} />
              <div className="label">Serving areas (postal codes)</div>
              <input className="input" value={chefForm.serving_areas} onChange={e=> setChefForm({...chefForm, serving_areas:e.target.value})} />
              <div className="label">Profile picture (optional)</div>
              <div>
                <input id="homeProfilePic" type="file" accept="image/jpeg,image/png,image/webp" style={{display:'none'}} onChange={e=> setChefForm({...chefForm, profile_pic: e.target.files?.[0]||null})} />
                <label htmlFor="homeProfilePic" className="btn btn-outline">Choose file</label>
                {chefForm.profile_pic && <span className="muted" style={{marginLeft:'.5rem'}}>{chefForm.profile_pic.name}</span>}
              </div>
              <div className="actions-row" style={{marginTop:'.6rem'}}>
                 <button className="btn btn-primary" disabled={submitting} onClick={async ()=>{
                  setSubmitting(true); setApplyMsg(null)
                  try{
                    const fd = new FormData()
                     fd.append('experience', chefForm.experience)
                     fd.append('bio', chefForm.bio)
                     fd.append('serving_areas', chefForm.serving_areas)
                     // Best effort: attach city/country if we have them on the user object
                     try{
                       const city = (user?.address?.city||'').trim()
                       const country = (user?.address?.country||'').trim()
                       if (city) fd.append('city', city)
                       if (country) fd.append('country', country)
                     }catch{}
                    if (chefForm.profile_pic) fd.append('profile_pic', chefForm.profile_pic)
                    const resp = await api.post('/chefs/api/submit-chef-request/', fd, { headers:{'Content-Type':'multipart/form-data'} })
                    if (resp.status===200 || resp.status===201){
                      setApplyMsg('Application submitted. We will notify you when approved.')
                    } else {
                      setApplyMsg('Submission failed. Please try again later.')
                    }
                   }catch(e){ setApplyMsg(e?.response?.data?.error || 'Submission failed. Please try again.') }
                  finally{ setSubmitting(false) }
                }}>{submitting?'Submitting…':'Submit Application'}</button>
                <button className="btn btn-outline" onClick={()=> setApplyOpen(false)}>Close</button>
              </div>
            </div>
          </aside>
        </>
      )}

      {/* Chef Value Props */}
      <section className="section" aria-labelledby="why">
        <h2 id="why" className="section-title">Everything You Need to Run Your Business</h2>
        <p className="section-sub">From managing clients to getting paid — sautai handles the business so you can focus on the food.</p>
        <div className="intro-cards" style={{marginTop:'.75rem'}}>
          <div className="card">
            <h3>👥 Client Management</h3>
            <p>Keep track of families, dietary restrictions, allergies, and preferences. Build lasting relationships with organized client profiles.</p>
          </div>
          <div className="card">
            <h3>📋 Services & Booking</h3>
            <p>Create service offerings with custom pricing tiers. Let clients book directly and manage your schedule effortlessly.</p>
          </div>
          <div className="card">
            <h3>💳 Payments & Revenue</h3>
            <p>Get paid seamlessly with Stripe integration. Track your earnings, send invoices, and watch your business grow.</p>
          </div>
        </div>
      </section>

      <div className="divider" />

      {/* Chef Hub Preview */}
      <section className="section" aria-labelledby="hub">
        <h2 id="hub" className="section-title">Your Chef Hub — All in One Place</h2>
        <p className="section-sub">A professional dashboard designed for how you work. Everything organized, nothing overlooked.</p>
        <div className="intro-cards" style={{marginTop:'.75rem'}}>
          <div className="card">
            <h3>📊 Dashboard Overview</h3>
            <p>See your revenue, active clients, upcoming orders, and events at a glance. Know exactly where your business stands.</p>
          </div>
          <div className="card">
            <h3>🍳 Kitchen & Menu</h3>
            <p>Manage your dishes, ingredients, and complete meals. Showcase your culinary creations to potential clients.</p>
          </div>
          <div className="card">
            <h3>📅 Events & Orders</h3>
            <p>Track service orders, schedule events, and never miss a booking. Stay organized with your calendar view.</p>
          </div>
        </div>
      </section>

      <div className="divider" />

      {/* Steps for Chefs */}
      <section className="section" aria-labelledby="steps">
        <h2 id="steps" className="section-title">Get Started in Minutes</h2>
        <div className="steps-grid" style={{marginTop:'.5rem'}}>
          {[
            ["1", "Create Your Profile", "Set up your chef profile with your bio, photos, cuisine specialties, and service areas."],
            ["2", "Define Your Services", "Create service offerings with pricing tiers — weekly meal prep, private dinners, cooking classes, and more."],
            ["3", "Connect with Clients", "Local families discover you and request your services. Build your client base organically."],
            ["4", "Grow Your Business", "Manage orders, track revenue, and expand your culinary business with powerful tools."],
          ].map(([num, title, desc]) => (
            <div key={title} className="card step">
              <div className="num" aria-hidden>{num}</div>
              <div>
                <h3 style={{margin:'0 0 .15rem'}}>{title}</h3>
                <p style={{margin:0, color:'var(--muted)'}}>{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="divider" />

      {/* Global Chef Discovery Section - Featured for guests */}
      {!user && (
        <section className="section" aria-labelledby="discover">
          <h2 id="discover" className="section-title">
            <span style={{marginRight: '0.5rem'}}>🌍</span>
            Discover Chefs Worldwide
          </h2>
          <p className="section-sub">
            Explore talented chefs from around the world. Browse their profiles, see their culinary creations, and get inspired by global cuisines.
          </p>
          <div className="discover-regions" style={{marginTop:'1.25rem'}}>
            <div className="intro-cards" style={{gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))'}}>
              {[
                {flag: '🇺🇸', name: 'United States', code: 'US'},
                {flag: '🇬🇧', name: 'United Kingdom', code: 'GB'},
                {flag: '🇨🇦', name: 'Canada', code: 'CA'},
                {flag: '🇫🇷', name: 'France', code: 'FR'},
                {flag: '🇮🇹', name: 'Italy', code: 'IT'},
                {flag: '🇯🇵', name: 'Japan', code: 'JP'},
              ].map(region => (
                <Link 
                  key={region.code} 
                  to={`/chefs?country=${region.code}`} 
                  className="card" 
                  style={{textAlign: 'center', textDecoration: 'none', padding: '1.25rem 1rem', transition: 'all 0.2s ease'}}
                >
                  <span style={{fontSize: '2.5rem', display: 'block', marginBottom: '0.5rem'}}>{region.flag}</span>
                  <h4 style={{margin: 0, fontSize: '1rem'}}>{region.name}</h4>
                </Link>
              ))}
            </div>
          </div>
          <div style={{textAlign: 'center', marginTop: '1.5rem'}}>
            <Link to="/chefs" className="btn btn-primary" style={{fontSize: '1rem', padding: '0.75rem 1.5rem'}}>
              <span style={{marginRight: '0.5rem'}}>🗺️</span>
              Explore All Chefs
            </Link>
          </div>
        </section>
      )}

      <div className="divider" />

      {/* Customer Section */}
      <section className="section" aria-labelledby="customers">
        <div className="cta">
          <div className="card" style={{background:'linear-gradient(135deg, color-mix(in oklab, var(--primary) 8%, var(--surface)) 0%, var(--surface) 100%)'}}>
            <h2 id="customers" style={{marginTop:0}}>Looking for a Personal Chef?</h2>
            <p>Discover talented chefs in your area who specialize in home cooking, meal prep, private dinners, and more. From family recipes to modern cuisine — find the perfect chef for your household.</p>
            <div style={{display:'flex', gap:'.6rem', flexWrap:'wrap', marginTop:'1rem'}}>
              <Link to="/chefs" className="btn btn-primary">Browse Local Chefs</Link>
              {!user && <Link to="/register" className="btn btn-outline">Create Account</Link>}
            </div>
          </div>
        </div>
      </section>

      <div className="divider" />

      {/* Final CTA */}
      <section className="section" aria-labelledby="cta">
        <div className="cta">
          <div className="card">
            <h2 id="cta" style={{marginTop:0}}>Ready to Get Started?</h2>
            <p>Whether you're a chef looking to grow your business or a family searching for delicious home-cooked meals — sautai connects you with your community.</p>
          </div>
          <div className="actions">
            {!user && <Link to="/register" className="btn btn-primary" style={{textAlign:'center'}}>Create Chef Profile</Link>}
            {user?.is_chef && <Link to="/chefs/dashboard" className="btn btn-primary" style={{textAlign:'center'}}>Go to Chef Hub</Link>}
            {user && !user?.is_chef && <button className="btn btn-primary" style={{textAlign:'center'}} onClick={()=> setApplyOpen(true)}>Become a Chef</button>}
            <Link to="/chefs" className="btn btn-outline" style={{textAlign:'center'}}>Find a Chef</Link>
          </div>
        </div>
      </section>

      <section className="section" style={{paddingTop:0}}>
        <div style={{textAlign:'center'}}>
          <a href="https://www.buymeacoffee.com/sautai" target="_blank" rel="noreferrer">
            <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style={{height:60, width:217}} />
          </a>
        </div>
      </section>
    </div>
  )
}
