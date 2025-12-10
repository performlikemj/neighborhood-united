/**
 * Chef Prep Planning Component
 * 
 * Provides intelligent shopping lists and prep planning for chefs:
 * - Generate prep plans for upcoming commitments
 * - View shopping lists organized by purchase date or category
 * - Track purchased items
 * - Batch cooking suggestions
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  getPrepPlans,
  getPrepPlanDetail,
  quickGeneratePrepPlan,
  createPrepPlan,
  updatePrepPlan,
  deletePrepPlan,
  regeneratePrepPlan,
  getShoppingList,
  markItemsPurchased,
  unmarkItemsPurchased,
  getPrepPlanSummary
} from '../api/chefPrepPlanClient'

// Helper: format date for display
function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr + 'T00:00:00')
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    }).format(date)
  } catch {
    return dateStr
  }
}

// Helper: get today's date in YYYY-MM-DD format
function getTodayISO() {
  return new Date().toISOString().slice(0, 10)
}

// Helper: add days to a date
function addDays(dateStr, days) {
  const date = new Date(dateStr + 'T00:00:00')
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

// Timing status badge colors
const TIMING_COLORS = {
  optimal: { bg: 'rgba(24,180,24,.15)', color: '#168516' },
  tight: { bg: 'rgba(200,160,20,.15)', color: '#8a6d00' },
  problematic: { bg: 'rgba(200,100,40,.15)', color: '#a14500' },
  impossible: { bg: 'rgba(200,40,40,.18)', color: '#a11919' }
}

// Storage type icons
const STORAGE_ICONS = {
  refrigerated: '🧊',
  frozen: '❄️',
  pantry: '🏠',
  counter: '🍌'
}

function StatusBadge({ status }) {
  const colors = TIMING_COLORS[status] || { bg: 'rgba(60,60,60,.12)', color: '#2f2f2f' }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '12px',
        fontSize: '0.75rem',
        fontWeight: 500,
        background: colors.bg,
        color: colors.color,
        textTransform: 'capitalize'
      }}
    >
      {status}
    </span>
  )
}

function SummaryCard({ title, value, subtitle, icon }) {
  return (
    <div className="card" style={{ padding: '1rem', textAlign: 'center' }}>
      {icon && <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>{icon}</div>}
      <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--color-primary)' }}>{value}</div>
      <div style={{ fontWeight: 500 }}>{title}</div>
      {subtitle && <div className="muted" style={{ fontSize: '0.85rem' }}>{subtitle}</div>}
    </div>
  )
}

export default function ChefPrepPlanning() {
  // State
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [plans, setPlans] = useState([])
  const [selectedPlan, setSelectedPlan] = useState(null)
  const [shoppingList, setShoppingList] = useState(null)
  const [listGroupBy, setListGroupBy] = useState('date')
  
  // Form state
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState({
    start_date: getTodayISO(),
    end_date: addDays(getTodayISO(), 6),
    notes: ''
  })
  const [creating, setCreating] = useState(false)
  const [quickGenerating, setQuickGenerating] = useState(false)

  // Compute unique clients from selected plan
  const uniqueClients = useMemo(() => {
    if (!selectedPlan?.commitments) return []
    const clientNames = new Set()
    selectedPlan.commitments.forEach(c => {
      if (c.customer_name) clientNames.add(c.customer_name)
    })
    return Array.from(clientNames)
  }, [selectedPlan?.commitments])

  // Group commitments by client for display
  const commitmentsByClient = useMemo(() => {
    if (!selectedPlan?.commitments) return {}
    const grouped = {}
    selectedPlan.commitments.forEach(c => {
      const client = c.customer_name || 'Other'
      if (!grouped[client]) grouped[client] = []
      grouped[client].push(c)
    })
    return grouped
  }, [selectedPlan?.commitments])

  // Load initial data
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, plansData] = await Promise.all([
        getPrepPlanSummary(),
        getPrepPlans()
      ])
      setSummary(summaryData)
      setPlans(Array.isArray(plansData) ? plansData : [])
    } catch (err) {
      console.error('Failed to load prep planning data:', err)
      setError('Failed to load prep planning data. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Load plan details when selected
  useEffect(() => {
    if (!selectedPlan?.id) {
      setShoppingList(null)
      return
    }

    const loadPlanDetails = async () => {
      try {
        const [planDetail, listData] = await Promise.all([
          getPrepPlanDetail(selectedPlan.id),
          getShoppingList(selectedPlan.id, listGroupBy)
        ])
        setSelectedPlan(planDetail)
        setShoppingList(listData)
      } catch (err) {
        console.error('Failed to load plan details:', err)
      }
    }

    loadPlanDetails()
  }, [selectedPlan?.id, listGroupBy])

  // Quick generate (7 days)
  const handleQuickGenerate = async () => {
    setQuickGenerating(true)
    try {
      const newPlan = await quickGeneratePrepPlan({ days: 7 })
      setPlans(prev => [newPlan, ...prev])
      setSelectedPlan(newPlan)
      await loadData()
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Prep plan generated!', tone: 'success' }
      }))
    } catch (err) {
      console.error('Failed to generate prep plan:', err)
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Failed to generate plan', tone: 'error' }
      }))
    } finally {
      setQuickGenerating(false)
    }
  }

  // Create custom plan
  const handleCreatePlan = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const newPlan = await createPrepPlan(createForm)
      setPlans(prev => [newPlan, ...prev])
      setSelectedPlan(newPlan)
      setShowCreateForm(false)
      setCreateForm({
        start_date: getTodayISO(),
        end_date: addDays(getTodayISO(), 6),
        notes: ''
      })
      await loadData()
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Prep plan created!', tone: 'success' }
      }))
    } catch (err) {
      console.error('Failed to create prep plan:', err)
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Failed to create plan', tone: 'error' }
      }))
    } finally {
      setCreating(false)
    }
  }

  // Toggle item purchased
  const handleTogglePurchased = async (item) => {
    if (!selectedPlan?.id) return
    
    try {
      if (item.is_purchased) {
        await unmarkItemsPurchased(selectedPlan.id, [item.id])
      } else {
        await markItemsPurchased(selectedPlan.id, [item.id])
      }
      // Refresh shopping list
      const listData = await getShoppingList(selectedPlan.id, listGroupBy)
      setShoppingList(listData)
    } catch (err) {
      console.error('Failed to update item:', err)
    }
  }

  // Delete plan
  const handleDeletePlan = async (planId) => {
    if (!window.confirm('Delete this prep plan?')) return
    
    try {
      await deletePrepPlan(planId)
      setPlans(prev => prev.filter(p => p.id !== planId))
      if (selectedPlan?.id === planId) {
        setSelectedPlan(null)
        setShoppingList(null)
      }
      await loadData()
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Plan deleted', tone: 'success' }
      }))
    } catch (err) {
      console.error('Failed to delete plan:', err)
    }
  }

  // Regenerate plan
  const handleRegeneratePlan = async (planId) => {
    if (!window.confirm('Regenerate this plan? This will refresh all data.')) return
    
    try {
      const updatedPlan = await regeneratePrepPlan(planId)
      setPlans(prev => prev.map(p => p.id === planId ? updatedPlan : p))
      setSelectedPlan(updatedPlan)
      await loadData()
      window.dispatchEvent(new CustomEvent('global-toast', {
        detail: { text: 'Plan regenerated!', tone: 'success' }
      }))
    } catch (err) {
      console.error('Failed to regenerate plan:', err)
    }
  }

  // Render shopping list items
  const renderShoppingItems = () => {
    if (!shoppingList?.shopping_list) {
      return <div className="muted">No shopping items</div>
    }

    const groupedItems = shoppingList.shopping_list
    const groupKeys = Object.keys(groupedItems).sort()

    if (groupKeys.length === 0) {
      return <div className="muted">No items to purchase</div>
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {groupKeys.map(groupKey => {
          const items = groupedItems[groupKey]
          const groupLabel = listGroupBy === 'date'
            ? formatDate(groupKey)
            : groupKey.charAt(0).toUpperCase() + groupKey.slice(1)

          return (
            <div key={groupKey}>
              <h4 style={{ margin: '0 0 0.75rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                {listGroupBy === 'category' && STORAGE_ICONS[groupKey]}
                {groupLabel}
                <span className="muted" style={{ fontWeight: 400, fontSize: '0.85rem' }}>
                  ({items.length} item{items.length !== 1 ? 's' : ''})
                </span>
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {items.map(item => (
                  <div
                    key={item.id}
                    className="card"
                    style={{
                      padding: '0.75rem 1rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      opacity: item.is_purchased ? 0.6 : 1,
                      background: item.is_purchased ? 'rgba(0,0,0,0.02)' : undefined
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={item.is_purchased}
                      onChange={() => handleTogglePurchased(item)}
                      style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{
                        fontWeight: 500,
                        textDecoration: item.is_purchased ? 'line-through' : 'none'
                      }}>
                        {item.ingredient}
                      </div>
                      <div className="muted" style={{ fontSize: '0.85rem' }}>
                        {item.quantity} {item.unit}
                        {item.meals && item.meals.length > 0 && (
                          <span> • {item.meals.length} meal{item.meals.length !== 1 ? 's' : ''}</span>
                        )}
                      </div>
                      {/* Show which meals/clients use this ingredient */}
                      {item.meals && item.meals.length > 0 && (
                        <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                          {item.meals.slice(0, 3).map((meal, mIdx) => (
                            <span
                              key={mIdx}
                              style={{
                                fontSize: '0.7rem',
                                padding: '1px 6px',
                                borderRadius: '8px',
                                background: 'rgba(0,0,0,0.06)',
                                color: 'inherit'
                              }}
                            >
                              {meal.name?.split(' - ')[0] || meal.name}
                            </span>
                          ))}
                          {item.meals.length > 3 && (
                            <span style={{ fontSize: '0.7rem', opacity: 0.7 }}>
                              +{item.meals.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <StatusBadge status={item.timing_status} />
                      <div className="muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                        {STORAGE_ICONS[item.storage]} {item.shelf_life_days}d shelf life
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  // Render batch suggestions
  const renderBatchSuggestions = () => {
    const suggestions = selectedPlan?.batch_suggestions?.suggestions || []
    const tips = selectedPlan?.batch_suggestions?.general_tips || []

    if (suggestions.length === 0 && tips.length === 0) {
      return <div className="muted">No batch suggestions available</div>
    }

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {suggestions.map((sug, idx) => (
          <div key={idx} className="card" style={{ padding: '1rem' }}>
            <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>
              {sug.ingredient} • {sug.total_quantity} {sug.unit}
            </div>
            <div style={{ marginBottom: '0.5rem' }}>{sug.suggestion}</div>
            <div className="muted" style={{ fontSize: '0.85rem' }}>
              Prep day: {sug.prep_day} • Covers: {sug.meals_covered.join(', ')}
            </div>
          </div>
        ))}
        
        {tips.length > 0 && (
          <div className="card" style={{ padding: '1rem', background: 'rgba(100,150,200,0.08)' }}>
            <div style={{ fontWeight: 500, marginBottom: '0.5rem' }}>General Tips</div>
            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
              {tips.map((tip, idx) => (
                <li key={idx} style={{ marginBottom: '0.25rem' }}>{tip}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <div className="muted">Loading prep planning...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card" style={{ padding: '2rem', textAlign: 'center', borderColor: '#f0d000' }}>
        <div>{error}</div>
        <button className="btn btn-outline" onClick={loadData} style={{ marginTop: '1rem' }}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <header style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ margin: '0 0 0.25rem 0' }}>Prep Planning</h1>
        <p className="muted">Optimize your shopping and reduce food waste</p>
      </header>

      {/* Summary Cards */}
      <div className="grid grid-4" style={{ marginBottom: '1.5rem' }}>
        <SummaryCard
          icon="👥"
          title="Clients"
          value={selectedPlan ? uniqueClients.length : (summary?.active_plans_count || 0)}
          subtitle={selectedPlan ? "In this plan" : "Active plans"}
        />
        <SummaryCard
          icon="🍽️"
          title="Meals"
          value={selectedPlan?.total_meals || plans[0]?.total_meals || 0}
          subtitle={`${selectedPlan?.total_servings || 0} servings`}
        />
        <SummaryCard
          icon="🛒"
          title="Ingredients"
          value={selectedPlan?.unique_ingredients || summary?.items_to_purchase_today || 0}
          subtitle="To purchase"
        />
        <SummaryCard
          icon="📅"
          title="Time Span"
          value={selectedPlan ? `${selectedPlan.duration_days || 7}d` : '—'}
          subtitle={selectedPlan ? `${formatDate(selectedPlan.plan_start_date)}` : "Select a plan"}
        />
      </div>

      {/* Actions */}
      <div className="card" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <button
            className="btn btn-primary"
            onClick={handleQuickGenerate}
            disabled={quickGenerating}
          >
            {quickGenerating ? 'Generating...' : '⚡ Quick Plan (7 days)'}
          </button>
          <button
            className="btn btn-outline"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            {showCreateForm ? 'Cancel' : '📅 Custom Date Range'}
          </button>
        </div>

        {/* Custom Create Form */}
        {showCreateForm && (
          <form onSubmit={handleCreatePlan} style={{ marginTop: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label className="label">Start Date</label>
              <input
                type="date"
                className="input"
                value={createForm.start_date}
                onChange={e => setCreateForm(prev => ({ ...prev, start_date: e.target.value }))}
                min={getTodayISO()}
                required
              />
            </div>
            <div>
              <label className="label">End Date</label>
              <input
                type="date"
                className="input"
                value={createForm.end_date}
                onChange={e => setCreateForm(prev => ({ ...prev, end_date: e.target.value }))}
                min={createForm.start_date}
                required
              />
            </div>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label className="label">Notes (optional)</label>
              <input
                type="text"
                className="input"
                value={createForm.notes}
                onChange={e => setCreateForm(prev => ({ ...prev, notes: e.target.value }))}
                placeholder="e.g., Holiday prep"
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={creating}>
              {creating ? 'Creating...' : 'Create Plan'}
            </button>
          </form>
        )}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-2">
        {/* Plans List */}
        <div className="card">
          <div style={{ padding: '1rem', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
            <h3 style={{ margin: 0 }}>Your Plans</h3>
          </div>
          <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {plans.length === 0 ? (
              <div className="muted" style={{ padding: '2rem', textAlign: 'center' }}>
                No plans yet. Generate your first prep plan!
              </div>
            ) : (
              plans.map(plan => (
                <div
                  key={plan.id}
                  style={{
                    padding: '1rem',
                    borderBottom: '1px solid rgba(0,0,0,0.05)',
                    cursor: 'pointer',
                    background: selectedPlan?.id === plan.id ? 'rgba(100,150,200,0.08)' : undefined
                  }}
                  onClick={() => setSelectedPlan(plan)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 500 }}>
                        {formatDate(plan.plan_start_date)} - {formatDate(plan.plan_end_date)}
                      </div>
                      <div className="muted" style={{ fontSize: '0.85rem' }}>
                        {plan.total_meals} meals • {plan.unique_ingredients} ingredients
                      </div>
                    </div>
                    <StatusBadge status={plan.status} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Selected Plan Details */}
        <div className="card">
          {selectedPlan ? (
            <>
              <div style={{ padding: '1rem', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ margin: '0 0 0.25rem 0' }}>
                      {formatDate(selectedPlan.plan_start_date)} - {formatDate(selectedPlan.plan_end_date)}
                    </h3>
                    <div className="muted" style={{ fontSize: '0.85rem' }}>
                      {selectedPlan.total_meals} meals • {selectedPlan.total_servings} servings • {selectedPlan.unique_ingredients} ingredients
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleRegeneratePlan(selectedPlan.id)}
                      title="Refresh plan data"
                    >
                      🔄
                    </button>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleDeletePlan(selectedPlan.id)}
                      title="Delete plan"
                      style={{ color: '#a11919' }}
                    >
                      🗑️
                    </button>
                  </div>
                </div>
                
                {/* Client breakdown chips */}
                {uniqueClients.length > 0 && (
                  <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {uniqueClients.map(client => {
                      const clientMeals = commitmentsByClient[client] || []
                      const totalServings = clientMeals.reduce((sum, c) => sum + c.servings, 0)
                      return (
                        <span
                          key={client}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            padding: '4px 10px',
                            borderRadius: '16px',
                            fontSize: '0.8rem',
                            background: 'rgba(76,175,80,0.12)',
                            color: '#2e7d32',
                            fontWeight: 500
                          }}
                        >
                          👤 {client}
                          <span style={{ opacity: 0.7, fontWeight: 400 }}>
                            ({clientMeals.length} meals, {totalServings} servings)
                          </span>
                        </span>
                      )
                    })}
                  </div>
                )}
              </div>
              
              {/* Tabs */}
              <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid rgba(0,0,0,0.08)', display: 'flex', gap: '1rem' }}>
                <button
                  className={`btn btn-sm ${listGroupBy === 'date' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setListGroupBy('date')}
                >
                  By Date
                </button>
                <button
                  className={`btn btn-sm ${listGroupBy === 'category' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setListGroupBy('category')}
                >
                  By Category
                </button>
              </div>

              <div style={{ padding: '1rem', maxHeight: '400px', overflowY: 'auto' }}>
                {renderShoppingItems()}
              </div>
            </>
          ) : (
            <div className="muted" style={{ padding: '3rem', textAlign: 'center' }}>
              Select a plan to view shopping list
            </div>
          )}
        </div>
      </div>

      {/* Batch Suggestions */}
      {selectedPlan && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
            <h3 style={{ margin: 0 }}>Batch Cooking Suggestions</h3>
            <p className="muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem' }}>
              Prep smarter by cooking ingredients in batches
            </p>
          </div>
          <div style={{ padding: '1rem' }}>
            {renderBatchSuggestions()}
          </div>
        </div>
      )}

      {/* Commitments by Client */}
      {selectedPlan?.commitments && selectedPlan.commitments.length > 0 && (
        <div className="card" style={{ marginTop: '1.5rem' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
            <h3 style={{ margin: 0 }}>Meals to Prepare</h3>
            <p className="muted" style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem' }}>
              {uniqueClients.length > 1 
                ? `Serving ${uniqueClients.length} clients this period`
                : 'All your upcoming meal commitments'
              }
            </p>
          </div>
          <div style={{ padding: '1rem' }}>
            {/* Group by client if multiple clients */}
            {uniqueClients.length > 1 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {Object.entries(commitmentsByClient).map(([clientName, clientCommitments]) => (
                  <div key={clientName}>
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '0.5rem',
                      marginBottom: '0.75rem',
                      paddingBottom: '0.5rem',
                      borderBottom: '2px solid rgba(76,175,80,0.3)'
                    }}>
                      <span style={{ fontSize: '1.1rem' }}>👤</span>
                      <span style={{ fontWeight: 600, fontSize: '1rem' }}>{clientName}</span>
                      <span className="muted" style={{ fontSize: '0.85rem' }}>
                        ({clientCommitments.length} meals, {clientCommitments.reduce((s, c) => s + c.servings, 0)} servings)
                      </span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingLeft: '0.5rem' }}>
                      {clientCommitments.map((c, idx) => {
                        const typeColors = {
                          'client_meal_plan': { bg: 'rgba(76,175,80,0.15)', color: '#2e7d32', dot: '#4caf50' },
                          'meal_event': { bg: 'rgba(74,144,217,0.15)', color: '#2d5a8a', dot: '#4a90d9' },
                          'service_order': { bg: 'rgba(233,160,58,0.15)', color: '#8a5a10', dot: '#e9a03a' }
                        }
                        const colors = typeColors[c.commitment_type] || typeColors.service_order
                        
                        return (
                          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 0', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                            <div style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              background: colors.dot,
                              flexShrink: 0
                            }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {c.meal_name}
                              </div>
                              <div className="muted" style={{ fontSize: '0.85rem' }}>
                                {formatDate(c.service_date)} • {c.servings} servings
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              /* Single client or no client grouping */
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {selectedPlan.commitments.map((c, idx) => {
                  const typeColors = {
                    'client_meal_plan': { bg: 'rgba(76,175,80,0.15)', color: '#2e7d32', dot: '#4caf50' },
                    'meal_event': { bg: 'rgba(74,144,217,0.15)', color: '#2d5a8a', dot: '#4a90d9' },
                    'service_order': { bg: 'rgba(233,160,58,0.15)', color: '#8a5a10', dot: '#e9a03a' }
                  }
                  const colors = typeColors[c.commitment_type] || typeColors.service_order
                  const typeLabel = c.commitment_type === 'client_meal_plan' ? 'Client Plan' 
                    : c.commitment_type === 'meal_event' ? 'Meal Event' : 'Service'
                  
                  return (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.5rem 0', borderBottom: '1px solid rgba(0,0,0,0.04)' }}>
                      <div style={{
                        width: '12px',
                        height: '12px',
                        borderRadius: '50%',
                        background: colors.dot,
                        flexShrink: 0
                      }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.meal_name}
                        </div>
                        <div className="muted" style={{ fontSize: '0.85rem' }}>
                          {formatDate(c.service_date)} • {c.servings} servings
                          {c.customer_name && <span> • <strong>{c.customer_name}</strong></span>}
                        </div>
                      </div>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        background: colors.bg,
                        color: colors.color,
                        flexShrink: 0
                      }}>
                        {typeLabel}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Empty state when no commitments */}
      {selectedPlan && (!selectedPlan.commitments || selectedPlan.commitments.length === 0) && (
        <div className="card" style={{ marginTop: '1.5rem', padding: '2rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📅</div>
          <h3 style={{ margin: '0 0 0.5rem 0' }}>No Meals Scheduled</h3>
          <p className="muted">
            This prep plan has no meal commitments for the selected date range.
            Create meal plans for your clients to see them here.
          </p>
        </div>
      )}
    </div>
  )
}


