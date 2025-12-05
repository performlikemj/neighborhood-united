import React, { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../context/AuthContext.jsx'
import { getRandomChefEmoji } from '../utils/emojis.js'

/**
 * AllOrders - Combined orders view with chef filter
 * 
 * Shows all orders from all connected chefs with ability to filter by chef.
 */
export default function AllOrders() {
  const { connectedChefs } = useAuth()
  
  // Random chef emoji - stable for the component lifecycle
  const chefEmoji = useMemo(() => getRandomChefEmoji(), [])
  
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Filter state
  const [selectedChefId, setSelectedChefId] = useState('')
  const [selectedStatus, setSelectedStatus] = useState('')
  
  // Pagination
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 20
  
  useEffect(() => {
    fetchOrders()
  }, [selectedChefId, selectedStatus, offset])
  
  const fetchOrders = async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        offset: offset.toString(),
      })
      if (selectedStatus) params.set('status', selectedStatus)
      
      const resp = await api.get(`/meals/api/my-orders/?${params}`)
      let allOrders = resp.data?.orders || resp.data || []
      
      // Client-side chef filter
      if (selectedChefId) {
        allOrders = allOrders.filter(order => {
          return order.chef_id == selectedChefId || 
                 order.chef?.id == selectedChefId ||
                 order.meal_event?.chef_id == selectedChefId
        })
      }
      
      setOrders(allOrders)
      setTotal(resp.data?.total || allOrders.length)
    } catch (e) {
      console.error('Failed to fetch orders:', e)
      setError('Failed to load orders.')
    } finally {
      setLoading(false)
    }
  }
  
  const handleChefChange = (e) => {
    setSelectedChefId(e.target.value)
    setOffset(0)
  }
  
  const handleStatusChange = (e) => {
    setSelectedStatus(e.target.value)
    setOffset(0)
  }
  
  const clearFilters = () => {
    setSelectedChefId('')
    setSelectedStatus('')
    setOffset(0)
  }
  
  const hasMore = offset + limit < total
  const hasPrev = offset > 0
  const hasFilters = selectedChefId || selectedStatus
  
  return (
    <div className="page-all-orders">
      {/* Hero Section */}
      <div className="orders-hero">
        <div className="orders-hero-content">
          <h1 className="orders-hero-title">
            <i className="fa-solid fa-receipt"></i>
            My Orders
          </h1>
          <p className="orders-hero-subtitle">
            Track and manage all your meal orders in one place
          </p>
        </div>
      </div>
      
      {/* Filters Bar */}
      <div className="orders-filters-bar">
        <div className="orders-filters-content">
          {connectedChefs.length > 1 && (
            <div className="orders-filter-group">
              <label htmlFor="chef-filter">Chef:</label>
              <select 
                id="chef-filter"
                value={selectedChefId}
                onChange={handleChefChange}
                className="orders-filter-select"
              >
                <option value="">All Chefs</option>
                {connectedChefs.map(chef => (
                  <option key={chef.id} value={chef.id}>
                    {chef.display_name}
                  </option>
                ))}
              </select>
            </div>
          )}
          
          <div className="orders-filter-group">
            <label htmlFor="status-filter">Status:</label>
            <select 
              id="status-filter"
              value={selectedStatus}
              onChange={handleStatusChange}
              className="orders-filter-select"
            >
              <option value="">All Statuses</option>
              <option value="placed">Placed</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          
          {hasFilters && (
            <button 
              className="btn btn-text"
              onClick={clearFilters}
              style={{ marginLeft: 'auto' }}
            >
              Clear Filters
            </button>
          )}
        </div>
      </div>
      
      {/* Main Content */}
      <div className="orders-main">
        {/* Loading State */}
        {loading && (
          <div className="orders-loading">
            <div className="spinner" />
            <p>Loading your orders...</p>
          </div>
        )}
        
        {/* Error State */}
        {error && !loading && (
          <div className="orders-error">
            <p>{error}</p>
            <button onClick={fetchOrders} className="btn btn-primary">
              Try Again
            </button>
          </div>
        )}
        
        {/* Empty State */}
        {!loading && !error && (orders?.length ?? 0) === 0 && (
          <div className="orders-empty">
            {hasFilters ? (
              <>
                <div className="orders-empty-icon">🔍</div>
                <h2>No Matching Orders</h2>
                <p>No orders match your current filters. Try adjusting your selection.</p>
                <button className="btn btn-outline" onClick={clearFilters}>
                  Clear Filters
                </button>
              </>
            ) : connectedChefs.length > 0 ? (
              <>
                <div className="orders-empty-icon">🍽️</div>
                <h2>Ready to Order?</h2>
                <p>
                  You're connected with {connectedChefs.length === 1 ? 'a chef' : `${connectedChefs.length} chefs`}! 
                  Browse their menus to place your first order.
                </p>
                <Link to="/my-chefs" className="btn btn-primary">
                  Browse Chef Menus
                </Link>
              </>
            ) : (
              <>
                <div className="orders-empty-icon">{chefEmoji}</div>
                <h2>Welcome to Your Orders</h2>
                <p>
                  This is where you'll see all your meal orders. 
                  Start by finding a chef in your area.
                </p>
                <div className="orders-empty-actions">
                  <Link to="/chefs" className="btn btn-primary">
                    Find a Chef
                  </Link>
                  <Link to="/get-ready" className="btn btn-outline">
                    Set Up Preferences
                  </Link>
                </div>
              </>
            )}
          </div>
        )}
        
        {/* Orders List */}
        {!loading && !error && (orders?.length ?? 0) > 0 && (
          <>
            <div className="orders-list">
              {orders.map(order => (
                <OrderCard key={order.id} order={order} />
              ))}
            </div>
            
            {/* Pagination */}
            {total > limit && (
              <div className="orders-pagination">
                <button 
                  className="btn btn-outline"
                  disabled={!hasPrev}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                >
                  ← Previous
                </button>
                <span className="orders-pagination-info">
                  {offset + 1} - {Math.min(offset + limit, total)} of {total}
                </span>
                <button 
                  className="btn btn-outline"
                  disabled={!hasMore}
                  onClick={() => setOffset(offset + limit)}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Order card component
 */
function OrderCard({ order }) {
  const statusClass = {
    placed: 'status-placed',
    confirmed: 'status-confirmed',
    completed: 'status-completed',
    cancelled: 'status-cancelled',
    refunded: 'status-refunded',
  }[order.status] || ''
  
  const chefName = order.chef?.display_name || 
                   order.chef?.username ||
                   order.meal_event?.chef?.display_name ||
                   'Chef'
  
  const mealName = order.meal_name ||
                   order.meal?.name ||
                   order.meal_event?.meal?.name ||
                   'Order'
  
  const orderDate = order.event_date ||
                    order.created_at ||
                    order.order_date
  
  return (
    <div className="order-card">
      <div className="order-card-main">
        <h3 className="order-card-title">{mealName}</h3>
        <p className="order-card-chef">from {chefName}</p>
        <p className="order-card-date">{formatDate(orderDate)}</p>
      </div>
      
      <div className="order-card-meta">
        <span className={`order-status-badge ${statusClass}`}>
          {order.status}
        </span>
        {order.price && (
          <span className="order-card-price">${formatPrice(order.price)}</span>
        )}
        {order.quantity > 1 && (
          <span className="order-card-quantity">×{order.quantity}</span>
        )}
      </div>
      
      <Link to={`/orders/${order.id}`} className="order-card-link">
        View Details →
      </Link>
    </div>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric',
    year: 'numeric'
  })
}

function formatPrice(price) {
  if (typeof price === 'number') return price.toFixed(2)
  if (typeof price === 'string') {
    const num = parseFloat(price)
    return isNaN(num) ? price : num.toFixed(2)
  }
  return price
}
