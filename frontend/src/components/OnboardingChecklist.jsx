/**
 * OnboardingChecklist Component
 * 
 * Guides new chefs through the activation process with a clear checklist.
 * Shows progress, highlights next action, and celebrates completion.
 */

import React, { useState, useEffect, useMemo } from 'react'

// Step configuration
const STEPS = [
  {
    id: 'profile',
    title: 'Complete Your Profile',
    description: 'Add bio, experience, and a profile photo',
    tab: 'profile',
    icon: '👤',
    actionLabel: 'Edit Profile'
  },
  {
    id: 'kitchen',
    title: 'Build Your Kitchen',
    description: 'Create at least one meal to offer',
    tab: 'kitchen',
    icon: '🍳',
    actionLabel: 'Create Meal'
  },
  {
    id: 'services',
    title: 'Create a Service',
    description: 'Define an offering with pricing tiers',
    tab: 'services',
    icon: '📋',
    actionLabel: 'Add Service'
  },
  {
    id: 'photos',
    title: 'Add Photos',
    description: 'Upload at least 3 gallery photos',
    tab: 'photos',
    icon: '📸',
    actionLabel: 'Upload Photos'
  },
  {
    id: 'payouts',
    title: 'Set Up Payouts',
    description: 'Connect Stripe to receive payments',
    tab: 'dashboard',
    icon: '💳',
    actionLabel: 'Connect Stripe',
    isStripe: true
  }
]

const STORAGE_KEY = 'chef_onboarding_dismissed'

export default function OnboardingChecklist({
  completionState = {},
  onNavigate,
  onStartStripeOnboarding,
  className = ''
}) {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })
  const [collapsed, setCollapsed] = useState(false)
  const [celebrateShown, setCelebrateShown] = useState(false)

  // Compute step completion
  const steps = useMemo(() => {
    return STEPS.map(step => ({
      ...step,
      complete: Boolean(completionState[step.id])
    }))
  }, [completionState])

  const completedCount = steps.filter(s => s.complete).length
  const totalCount = steps.length
  const progressPercent = Math.round((completedCount / totalCount) * 100)
  const isComplete = completedCount === totalCount

  // Find next incomplete step
  const nextStep = steps.find(s => !s.complete)

  // Show celebration when just completed
  useEffect(() => {
    if (isComplete && !celebrateShown) {
      setCelebrateShown(true)
    }
  }, [isComplete, celebrateShown])

  // Persist dismissal
  const handleDismiss = () => {
    setDismissed(true)
    try {
      localStorage.setItem(STORAGE_KEY, 'true')
    } catch {}
  }

  const handleReset = () => {
    setDismissed(false)
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }

  const handleStepClick = (step) => {
    if (step.isStripe && onStartStripeOnboarding) {
      onStartStripeOnboarding()
    } else if (onNavigate) {
      onNavigate(step.tab)
    }
  }

  // Don't show if dismissed (unless incomplete)
  if (dismissed && isComplete) {
    return null
  }

  // Collapsed summary bar for returning users
  if (collapsed && !isComplete) {
    return (
      <div className={`onboarding-collapsed ${className}`}>
        <div className="collapsed-content">
          <div className="collapsed-progress">
            <div className="progress-ring">
              <svg viewBox="0 0 36 36">
                <path
                  className="progress-ring-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="progress-ring-fill"
                  strokeDasharray={`${progressPercent}, 100`}
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="progress-text">{completedCount}/{totalCount}</span>
            </div>
          </div>
          <div className="collapsed-info">
            <span className="collapsed-title">Setup Progress</span>
            {nextStep && (
              <span className="collapsed-next">Next: {nextStep.title}</span>
            )}
          </div>
        </div>
        <button 
          className="btn btn-sm btn-primary"
          onClick={() => setCollapsed(false)}
        >
          Continue Setup
        </button>
        <style>{collapsedStyles}</style>
      </div>
    )
  }

  // Celebration state when complete
  if (isComplete) {
    return (
      <div className={`onboarding-complete ${className}`}>
        <div className="complete-header">
          <div className="complete-icon">🎉</div>
          <div className="complete-content">
            <h3>You're Ready to Accept Orders!</h3>
            <p>Your chef profile is fully set up. Customers can now discover and book your services.</p>
          </div>
        </div>
        <div className="complete-actions">
          <button 
            className="btn btn-outline btn-sm"
            onClick={handleDismiss}
          >
            Dismiss
          </button>
          <button 
            className="btn btn-primary btn-sm"
            onClick={() => onNavigate && onNavigate('dashboard')}
          >
            View Dashboard
          </button>
        </div>
        <style>{completeStyles}</style>
      </div>
    )
  }

  // Main checklist view
  return (
    <div className={`onboarding-checklist ${className}`}>
      <div className="checklist-header">
        <div className="header-title">
          <h3>Get Started</h3>
          <p className="muted">Complete these steps to activate your chef profile</p>
        </div>
        <div className="header-actions">
          <button 
            className="collapse-btn"
            onClick={() => setCollapsed(true)}
            aria-label="Collapse checklist"
            title="Minimize"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 15l-6-6-6 6"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="checklist-progress">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="progress-label">
          <span>{completedCount} of {totalCount} complete</span>
          <span className="progress-percent">{progressPercent}%</span>
        </div>
      </div>

      {/* Steps list */}
      <div className="checklist-steps">
        {steps.map((step, index) => {
          const isNext = nextStep?.id === step.id
          return (
            <div 
              key={step.id}
              className={`checklist-step ${step.complete ? 'complete' : ''} ${isNext ? 'next' : ''}`}
            >
              <div className="step-indicator">
                {step.complete ? (
                  <div className="step-check">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <path d="M20 6L9 17l-5-5"/>
                    </svg>
                  </div>
                ) : (
                  <div className="step-number">{index + 1}</div>
                )}
              </div>
              <div className="step-content">
                <div className="step-header">
                  <span className="step-icon">{step.icon}</span>
                  <span className="step-title">{step.title}</span>
                </div>
                <p className="step-description">{step.description}</p>
              </div>
              <div className="step-action">
                {!step.complete && (
                  <button
                    className={`btn btn-sm ${isNext ? 'btn-primary' : 'btn-outline'}`}
                    onClick={() => handleStepClick(step)}
                  >
                    {step.actionLabel}
                  </button>
                )}
                {step.complete && (
                  <span className="step-done">Done</span>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <style>{mainStyles}</style>
    </div>
  )
}

const mainStyles = `
  .onboarding-checklist {
    background: linear-gradient(135deg, rgba(92, 184, 92, 0.08), rgba(92, 184, 92, 0.02));
    border: 1.5px solid rgba(92, 184, 92, 0.25);
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
  }

  .checklist-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
  }

  .header-title h3 {
    margin: 0 0 0.25rem 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text);
  }

  .header-title .muted {
    margin: 0;
    font-size: 0.9rem;
  }

  .collapse-btn {
    background: none;
    border: none;
    padding: 0.35rem;
    cursor: pointer;
    color: var(--muted);
    border-radius: 6px;
    transition: all 0.15s ease;
  }

  .collapse-btn:hover {
    background: rgba(0, 0, 0, 0.05);
    color: var(--text);
  }

  .checklist-progress {
    margin-bottom: 1.25rem;
  }

  .progress-bar {
    height: 8px;
    background: rgba(0, 0, 0, 0.08);
    border-radius: 4px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary, #5cb85c), var(--primary-700, #3E8F3E));
    border-radius: 4px;
    transition: width 0.4s ease;
  }

  .progress-label {
    display: flex;
    justify-content: space-between;
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: var(--muted);
  }

  .progress-percent {
    font-weight: 600;
    color: var(--primary, #5cb85c);
  }

  .checklist-steps {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .checklist-step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--surface, #fff);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 12px;
    transition: all 0.2s ease;
  }

  .checklist-step.complete {
    background: rgba(92, 184, 92, 0.05);
    border-color: rgba(92, 184, 92, 0.2);
  }

  .checklist-step.next {
    border-color: var(--primary, #5cb85c);
    box-shadow: 0 0 0 3px rgba(92, 184, 92, 0.1);
  }

  .step-indicator {
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .step-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--surface-2, #f3f4f6);
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .checklist-step.next .step-number {
    background: var(--primary, #5cb85c);
    color: white;
  }

  .step-check {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--primary, #5cb85c);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: checkPop 0.3s ease;
  }

  @keyframes checkPop {
    0% { transform: scale(0); }
    50% { transform: scale(1.2); }
    100% { transform: scale(1); }
  }

  .step-content {
    flex: 1;
    min-width: 0;
  }

  .step-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.15rem;
  }

  .step-icon {
    font-size: 1rem;
  }

  .step-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text);
  }

  .checklist-step.complete .step-title {
    color: var(--muted);
  }

  .step-description {
    margin: 0;
    font-size: 0.8rem;
    color: var(--muted);
    line-height: 1.4;
  }

  .step-action {
    flex-shrink: 0;
  }

  .step-done {
    font-size: 0.8rem;
    color: var(--primary, #5cb85c);
    font-weight: 500;
  }

  @media (max-width: 640px) {
    .onboarding-checklist {
      padding: 1rem;
    }

    .checklist-step {
      flex-wrap: wrap;
      padding: 0.75rem;
    }

    .step-content {
      flex: 1 1 calc(100% - 40px);
    }

    .step-action {
      flex: 1 1 100%;
      margin-top: 0.5rem;
      margin-left: 36px;
    }
  }
`

const collapsedStyles = `
  .onboarding-collapsed {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: linear-gradient(135deg, rgba(92, 184, 92, 0.08), rgba(92, 184, 92, 0.02));
    border: 1.5px solid rgba(92, 184, 92, 0.25);
    border-radius: 12px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
  }

  .collapsed-content {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .progress-ring {
    width: 40px;
    height: 40px;
    position: relative;
  }

  .progress-ring svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }

  .progress-ring-bg {
    fill: none;
    stroke: rgba(0, 0, 0, 0.1);
    stroke-width: 3;
  }

  .progress-ring-fill {
    fill: none;
    stroke: var(--primary, #5cb85c);
    stroke-width: 3;
    stroke-linecap: round;
    transition: stroke-dasharray 0.4s ease;
  }

  .progress-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text);
  }

  .collapsed-info {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .collapsed-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--text);
  }

  .collapsed-next {
    font-size: 0.8rem;
    color: var(--muted);
  }

  @media (max-width: 480px) {
    .onboarding-collapsed {
      flex-direction: column;
      align-items: stretch;
      gap: 0.75rem;
    }
    
    .onboarding-collapsed .btn {
      width: 100%;
    }
  }
`

const completeStyles = `
  .onboarding-complete {
    background: linear-gradient(135deg, rgba(52, 211, 153, 0.12), rgba(16, 185, 129, 0.06));
    border: 1.5px solid rgba(16, 185, 129, 0.35);
    border-radius: 16px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    animation: celebrateFade 0.5s ease;
  }

  @keyframes celebrateFade {
    0% { opacity: 0; transform: translateY(-10px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  .complete-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .complete-icon {
    font-size: 2.5rem;
    animation: bounce 0.6s ease;
  }

  @keyframes bounce {
    0%, 100% { transform: translateY(0); }
    40% { transform: translateY(-8px); }
    60% { transform: translateY(-4px); }
  }

  .complete-content h3 {
    margin: 0 0 0.35rem 0;
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--text);
  }

  .complete-content p {
    margin: 0;
    font-size: 0.9rem;
    color: var(--muted);
    line-height: 1.5;
  }

  .complete-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 480px) {
    .onboarding-complete {
      padding: 1rem;
    }
    
    .complete-header {
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    
    .complete-actions {
      justify-content: center;
    }
  }
`

