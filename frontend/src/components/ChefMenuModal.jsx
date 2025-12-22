import React, { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { useCart } from '../context/CartContext'

/**
 * ChefMenuModal - Browse chef's menu (dishes, meal shares, services)
 * 
 * Slide-out modal showing the chef's full catalog with tabs for:
 * - Dishes (chef's signature dishes)
 * - Meal Shares (upcoming bookable group meals)
 * - Services (service offerings with pricing tiers)
 */
export default function ChefMenuModal({ isOpen, onClose, chefId, chefUsername }) {
  const { addToCart, openCart } = useCart()
  const [activeTab, setActiveTab] = useState('dishes')
  const [catalog, setCatalog] = useState({ dishes: [], meal_events: [], services: [] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [addingItem, setAddingItem] = useState(null)

  const fetchCatalog = useCallback(async () => {
    if (!chefId) return
    setLoading(true)
    setError(null)
    try {
      const resp = await api.get(`/customer_dashboard/api/my-chefs/${chefId}/catalog/`)
      setCatalog(resp.data || { dishes: [], meal_events: [], services: [] })
    } catch (err) {
      console.error('Failed to fetch catalog:', err)
      setError('Unable to load menu. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [chefId])

  useEffect(() => {
    if (isOpen && chefId) {
      fetchCatalog()
    }
  }, [isOpen, chefId, fetchCatalog])

  const handleAddMealEvent = async (event) => {
    setAddingItem(`event-${event.id}`)
    try {
      const item = {
        type: 'meal_event',
        event_id: event.id,
        mealName: event.meal_name,
        eventDate: event.event_date,
        eventTime: event.event_time,
        price: Math.round(event.current_price * 100), // Convert to cents
        quantity: 1,
      }
      await addToCart(item, { username: chefUsername, id: chefId })
      openCart()
      showToast('Added to cart!', 'success')
    } catch (err) {
      showToast('Failed to add to cart', 'error')
    } finally {
      setAddingItem(null)
    }
  }

  const handleAddService = async (service, tier) => {
    setAddingItem(`service-${service.id}-${tier.id}`)
    try {
      const item = {
        type: 'service_tier',
        offering_id: service.id,
        tier_id: tier.id,
        offeringTitle: service.title,
        tierLabel: tier.name,
        price: tier.price_cents,
        householdSize: tier.household_min,
        requiresDateTime: service.service_type === 'home_chef',
        needsScheduleNotes: tier.is_recurring,
        tierRecurring: tier.is_recurring,
        serviceType: service.service_type,
      }
      await addToCart(item, { username: chefUsername, id: chefId })
      openCart()
      showToast('Added to cart!', 'success')
    } catch (err) {
      showToast('Failed to add to cart', 'error')
    } finally {
      setAddingItem(null)
    }
  }

  const showToast = (text, tone) => {
    try {
      window.dispatchEvent(new CustomEvent('global-toast', { detail: { text, tone } }))
    } catch {}
  }

  const formatPrice = (cents) => {
    if (typeof cents !== 'number') return '$0.00'
    return `$${(cents / 100).toFixed(2)}`
  }

  const formatPriceDollars = (dollars) => {
    if (typeof dollars !== 'number') return '$0.00'
    return `$${dollars.toFixed(2)}`
  }

  if (!isOpen) return null

  const tabs = [
    { id: 'dishes', label: 'Dishes', count: catalog.dishes?.length || 0 },
    { id: 'meal-shares', label: 'Meal Shares', count: catalog.meal_events?.length || 0 },
    { id: 'services', label: 'Services', count: catalog.services?.length || 0 },
  ]

  return (
    <>
      <div className="menu-modal-overlay" onClick={onClose} />
      <aside className="menu-modal" role="dialog" aria-label="Browse Menu">
        <div className="menu-modal-header">
          <div className="menu-modal-title">
            <i className="fa-solid fa-book-open"></i>
            Browse Menu
          </div>
          <button className="menu-modal-close" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-times"></i>
          </button>
        </div>

        {/* Tabs */}
        <div className="menu-modal-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`menu-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {tab.count > 0 && <span className="tab-count">{tab.count}</span>}
            </button>
          ))}
        </div>

        <div className="menu-modal-body">
          {loading && (
            <div className="menu-loading">
              <div className="spinner" style={{ width: 32, height: 32 }} />
              <p>Loading menu...</p>
            </div>
          )}

          {error && (
            <div className="menu-error">
              <i className="fa-solid fa-triangle-exclamation"></i>
              <p>{error}</p>
              <button className="btn btn-outline" onClick={fetchCatalog}>Try Again</button>
            </div>
          )}

          {!loading && !error && (
            <>
              {/* Dishes Tab */}
              {activeTab === 'dishes' && (
                <div className="menu-section">
                  {catalog.dishes.length === 0 ? (
                    <div className="menu-empty">
                      <i className="fa-solid fa-utensils"></i>
                      <p>No dishes available yet.</p>
                    </div>
                  ) : (
                    <div className="menu-grid">
                      {catalog.dishes.map(dish => (
                        <div key={dish.id} className="menu-card">
                          {dish.photo && (
                            <div className="menu-card-image">
                              <img src={dish.photo} alt={dish.name} />
                            </div>
                          )}
                          <div className="menu-card-content">
                            <h4 className="menu-card-title">
                              {dish.name}
                              {dish.featured && <span className="featured-badge">★ Featured</span>}
                            </h4>
                            {dish.description && (
                              <p className="menu-card-description">{dish.description}</p>
                            )}
                            {(dish.calories || dish.protein) && (
                              <div className="menu-card-nutrition">
                                {dish.calories && <span>{dish.calories} cal</span>}
                                {dish.protein && <span>{dish.protein}g protein</span>}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Meal Shares Tab */}
              {activeTab === 'meal-shares' && (
                <div className="menu-section">
                  {catalog.meal_events.length === 0 ? (
                    <div className="menu-empty">
                      <i className="fa-solid fa-calendar"></i>
                      <p>No upcoming meal shares.</p>
                    </div>
                  ) : (
                    <div className="menu-list">
                      {catalog.meal_events.map(event => (
                        <div key={event.id} className="menu-event-card">
                          <div className="event-card-main">
                            {event.photo && (
                              <div className="event-card-image">
                                <img src={event.photo} alt={event.meal_name} />
                              </div>
                            )}
                            <div className="event-card-info">
                              <h4 className="event-card-title">{event.meal_name}</h4>
                              <div className="event-card-datetime">
                                <i className="fa-regular fa-calendar"></i>
                                {new Date(event.event_date).toLocaleDateString('en-US', { 
                                  weekday: 'short', 
                                  month: 'short', 
                                  day: 'numeric' 
                                })}
                                {event.event_time && ` at ${event.event_time}`}
                              </div>
                              {event.description && (
                                <p className="event-card-description">{event.description}</p>
                              )}
                              <div className="event-card-pricing">
                                <span className="current-price">{formatPriceDollars(event.current_price)}</span>
                                {event.current_price > event.min_price && (
                                  <span className="price-note">
                                    Price drops to {formatPriceDollars(event.min_price)} with more orders
                                  </span>
                                )}
                              </div>
                              {event.spots_remaining !== null && (
                                <div className="event-card-spots">
                                  {event.spots_remaining > 0 
                                    ? `${event.spots_remaining} spots left`
                                    : 'Sold out'}
                                </div>
                              )}
                            </div>
                          </div>
                          <button
                            className="btn btn-primary event-add-btn"
                            onClick={() => handleAddMealEvent(event)}
                            disabled={addingItem === `event-${event.id}` || event.spots_remaining === 0}
                          >
                            {addingItem === `event-${event.id}` ? (
                              <><span className="spinner-sm"></span> Adding...</>
                            ) : event.spots_remaining === 0 ? (
                              'Sold Out'
                            ) : (
                              <><i className="fa-solid fa-cart-plus"></i> Add to Cart</>
                            )}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Services Tab */}
              {activeTab === 'services' && (
                <div className="menu-section">
                  {catalog.services.length === 0 ? (
                    <div className="menu-empty">
                      <i className="fa-solid fa-concierge-bell"></i>
                      <p>No services available in your area.</p>
                      {!catalog.user_in_service_area && (
                        <p className="muted">This chef doesn't currently serve your location.</p>
                      )}
                    </div>
                  ) : (
                    <div className="menu-list">
                      {catalog.services.map(service => (
                        <div key={service.id} className="menu-service-card">
                          <div className="service-card-header">
                            <div className="service-card-type">
                              <i className={`fa-solid ${service.service_type === 'home_chef' ? 'fa-house-user' : 'fa-bowl-food'}`}></i>
                              {service.service_type_display}
                            </div>
                            {service.is_personalized && (
                              <span className="personalized-badge">
                                <i className="fa-solid fa-star"></i> For You
                              </span>
                            )}
                          </div>
                          <h4 className="service-card-title">{service.title}</h4>
                          {service.description && (
                            <p className="service-card-description">{service.description}</p>
                          )}
                          {service.default_duration_minutes && (
                            <div className="service-card-duration">
                              <i className="fa-regular fa-clock"></i>
                              ~{service.default_duration_minutes} min
                            </div>
                          )}
                          <div className="service-tiers">
                            {service.tiers.map(tier => (
                              <div key={tier.id} className={`service-tier${tier.ready_for_checkout === false ? ' tier-unavailable' : ''}`}>
                                <div className="tier-info">
                                  <span className="tier-name">{tier.name}</span>
                                  <span className="tier-price">
                                    {formatPrice(tier.price_cents)}
                                    {tier.is_recurring && <span className="tier-recurring">/{tier.recurrence_interval}</span>}
                                  </span>
                                </div>
                                <button
                                  className="btn btn-outline btn-sm tier-add-btn"
                                  onClick={() => handleAddService(service, tier)}
                                  disabled={addingItem === `service-${service.id}-${tier.id}` || tier.ready_for_checkout === false}
                                  title={tier.ready_for_checkout === false ? 'This option is being set up' : ''}
                                >
                                  {addingItem === `service-${service.id}-${tier.id}` ? (
                                    <span className="spinner-sm"></span>
                                  ) : tier.ready_for_checkout === false ? (
                                    <span className="tier-pending">Setting up...</span>
                                  ) : (
                                    <i className="fa-solid fa-plus"></i>
                                  )}
                                </button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </aside>
    </>
  )
}


