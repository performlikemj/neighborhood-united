/**
 * ScaffoldPreview Component
 * 
 * Displays a visual tree of a meal scaffold for preview and editing.
 * Allows chefs to review AI-generated meal structures before creating.
 */

import React, { useState, useCallback } from 'react'
import './ScaffoldPreview.css'

/**
 * IngredientChip - Small removable chip for ingredients
 */
function IngredientChip({ name, isExisting, isRemoved, onRemove, onRestore }) {
  return (
    <span className={`ingredient-chip ${isExisting ? 'ingredient-chip--exists' : ''} ${isRemoved ? 'ingredient-chip--removed' : ''}`}>
      <span className="ingredient-chip__name">{name}</span>
      {isRemoved ? (
        <button 
          className="ingredient-chip__action"
          onClick={onRestore}
          title="Restore"
        >
          ↩
        </button>
      ) : (
        <button 
          className="ingredient-chip__action"
          onClick={onRemove}
          title="Remove"
        >
          ×
        </button>
      )}
    </span>
  )
}

/**
 * IngredientList - Collapsible list of ingredient chips
 */
function IngredientList({ ingredients, isExpanded, onToggle, onRemove, onRestore, isLoading }) {
  const activeIngredients = ingredients.filter(i => i.status !== 'removed')
  const count = activeIngredients.length
  
  if (isLoading) {
    return (
      <div className="ingredient-list ingredient-list--loading">
        <div className="ingredient-skeleton" />
        <div className="ingredient-skeleton" />
        <div className="ingredient-skeleton" />
      </div>
    )
  }
  
  if (ingredients.length === 0) {
    return null
  }
  
  return (
    <div className="ingredient-list">
      {!isExpanded ? (
        <button className="ingredient-list__toggle" onClick={onToggle}>
          {count} ingredient{count !== 1 ? 's' : ''} ▶
        </button>
      ) : (
        <>
          <button className="ingredient-list__toggle ingredient-list__toggle--expanded" onClick={onToggle}>
            Ingredients ▼
          </button>
          <div className="ingredient-list__chips">
            {ingredients.map(ing => (
              <IngredientChip
                key={ing.id}
                name={ing.data.name}
                isExisting={ing.status === 'exists'}
                isRemoved={ing.status === 'removed'}
                onRemove={() => onRemove(ing.id)}
                onRestore={() => onRestore(ing.id)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/**
 * ScaffoldPreview - Main component for displaying and editing scaffold trees
 */
export default function ScaffoldPreview({ 
  scaffold, 
  onUpdate, 
  onExecute, 
  onCancel,
  isExecuting = false,
  includeIngredients = false,
  onToggleIngredients,
  isFetchingIngredients = false
}) {
  const [expandedItems, setExpandedItems] = useState(new Set(['root']))
  const [expandedIngredients, setExpandedIngredients] = useState(new Set())
  const [editingItem, setEditingItem] = useState(null)
  
  // Count active items
  const countActiveItems = useCallback((item) => {
    if (!item || item.status === 'removed') return { meals: 0, dishes: 0, ingredients: 0 }
    
    let counts = { meals: 0, dishes: 0, ingredients: 0 }
    
    if (item.type === 'meal' && item.status !== 'exists') counts.meals = 1
    if (item.type === 'dish' && item.status !== 'exists') counts.dishes = 1
    if (item.type === 'ingredient' && item.status !== 'exists') counts.ingredients = 1
    
    for (const child of (item.children || [])) {
      const childCounts = countActiveItems(child)
      counts.meals += childCounts.meals
      counts.dishes += childCounts.dishes
      counts.ingredients += childCounts.ingredients
    }
    
    return counts
  }, [])
  
  const counts = countActiveItems(scaffold)
  const totalNew = counts.dishes + counts.ingredients // Don't count meal since we don't create it
  
  // Toggle expand/collapse for items
  const toggleExpand = useCallback((itemId) => {
    setExpandedItems(prev => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }, [])
  
  // Toggle ingredient expansion for a dish
  const toggleIngredientExpand = useCallback((dishId) => {
    setExpandedIngredients(prev => {
      const next = new Set(prev)
      if (next.has(dishId)) {
        next.delete(dishId)
      } else {
        next.add(dishId)
      }
      return next
    })
  }, [])
  
  // Expand all ingredients
  const expandAllIngredients = useCallback(() => {
    if (!scaffold) return
    const dishIds = scaffold.children
      ?.filter(c => c.type === 'dish' && c.children?.length > 0)
      .map(d => d.id) || []
    setExpandedIngredients(new Set(dishIds))
  }, [scaffold])
  
  // Update an item's data
  const updateItem = useCallback((itemId, field, value) => {
    const updateRecursive = (item) => {
      if (item.id === itemId) {
        return {
          ...item,
          data: { ...item.data, [field]: value },
          status: item.status === 'suggested' ? 'edited' : item.status
        }
      }
      return {
        ...item,
        children: (item.children || []).map(updateRecursive)
      }
    }
    onUpdate(updateRecursive(scaffold))
  }, [scaffold, onUpdate])
  
  // Remove an item (mark as removed)
  const removeItem = useCallback((itemId) => {
    const removeRecursive = (item) => {
      if (item.id === itemId) {
        return { ...item, status: 'removed' }
      }
      return {
        ...item,
        children: (item.children || []).map(removeRecursive)
      }
    }
    onUpdate(removeRecursive(scaffold))
  }, [scaffold, onUpdate])
  
  // Restore a removed item
  const restoreItem = useCallback((itemId) => {
    const restoreRecursive = (item) => {
      if (item.id === itemId) {
        return { ...item, status: 'suggested' }
      }
      return {
        ...item,
        children: (item.children || []).map(restoreRecursive)
      }
    }
    onUpdate(restoreRecursive(scaffold))
  }, [scaffold, onUpdate])
  
  // Render a single scaffold item
  const renderItem = (item, depth = 0) => {
    if (!item) return null
    
    const isExpanded = expandedItems.has(item.id) || expandedItems.has('root')
    const isRemoved = item.status === 'removed'
    const isExisting = item.status === 'exists'
    const isEditing = editingItem === item.id
    const hasChildren = item.children && item.children.length > 0
    const hasDishChildren = item.type === 'meal' && item.children?.some(c => c.type === 'dish')
    const hasIngredientChildren = item.type === 'dish' && item.children?.some(c => c.type === 'ingredient')
    
    const typeIcons = {
      meal: '🍽️',
      dish: '🍳',
      ingredient: '🥕'
    }
    
    const typeLabels = {
      meal: 'Meal',
      dish: 'Dish',
      ingredient: 'Ingredient'
    }
    
    return (
      <div 
        key={item.id} 
        className={`scaffold-item scaffold-item--${item.type} ${isRemoved ? 'scaffold-item--removed' : ''} ${isExisting ? 'scaffold-item--exists' : ''}`}
        style={{ marginLeft: depth * 20 }}
      >
        <div className="scaffold-item__header">
          {/* Expand/Collapse toggle for dishes under meal */}
          {hasDishChildren && (
            <button 
              className="scaffold-item__toggle"
              onClick={() => toggleExpand(item.id)}
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? '▼' : '▶'}
            </button>
          )}
          {!hasDishChildren && item.type !== 'ingredient' && <span className="scaffold-item__toggle-placeholder" />}
          
          {/* Type icon */}
          <span className="scaffold-item__icon">{typeIcons[item.type]}</span>
          
          {/* Item name (editable or display) */}
          {isEditing ? (
            <input
              type="text"
              className="scaffold-item__name-input"
              value={item.data.name || ''}
              onChange={(e) => updateItem(item.id, 'name', e.target.value)}
              onBlur={() => setEditingItem(null)}
              onKeyDown={(e) => e.key === 'Enter' && setEditingItem(null)}
              autoFocus
            />
          ) : (
            <span 
              className="scaffold-item__name"
              onClick={() => !isRemoved && item.type !== 'ingredient' && setEditingItem(item.id)}
            >
              {item.data.name || `Unnamed ${typeLabels[item.type]}`}
            </span>
          )}
          
          {/* Status badges */}
          {isExisting && (
            <span className="scaffold-item__badge scaffold-item__badge--exists">
              Already exists
            </span>
          )}
          {isRemoved && (
            <span className="scaffold-item__badge scaffold-item__badge--removed">
              Removed
            </span>
          )}
          
          {/* Action buttons */}
          <div className="scaffold-item__actions">
            {!isRemoved && !isEditing && item.type !== 'ingredient' && (
              <button 
                className="scaffold-item__btn scaffold-item__btn--edit"
                onClick={() => setEditingItem(item.id)}
                title="Edit"
              >
                ✏️
              </button>
            )}
            {item.type !== 'meal' && (
              isRemoved ? (
                <button 
                  className="scaffold-item__btn scaffold-item__btn--restore"
                  onClick={() => restoreItem(item.id)}
                  title="Restore"
                >
                  ↩️
                </button>
              ) : (
                <button 
                  className="scaffold-item__btn scaffold-item__btn--remove"
                  onClick={() => removeItem(item.id)}
                  title="Remove"
                >
                  ✕
                </button>
              )
            )}
          </div>
        </div>
        
        {/* Extra details for meal type */}
        {item.type === 'meal' && !isRemoved && (
          <div className="scaffold-item__details">
            {item.data.price && (
              <span className="scaffold-item__detail">
                ${item.data.price}
              </span>
            )}
            {item.data.meal_type && (
              <span className="scaffold-item__detail">
                {item.data.meal_type}
              </span>
            )}
            {item.data.cuisine_hint && (
              <span className="scaffold-item__detail scaffold-item__detail--cuisine">
                {item.data.cuisine_hint}
              </span>
            )}
            {item.data.description && (
              <span className="scaffold-item__detail scaffold-item__detail--desc">
                {item.data.description.substring(0, 100)}
                {item.data.description.length > 100 ? '...' : ''}
              </span>
            )}
          </div>
        )}
        
        {/* Ingredient list for dishes (shown as chips) */}
        {item.type === 'dish' && !isRemoved && includeIngredients && (
          <IngredientList
            ingredients={item.children?.filter(c => c.type === 'ingredient') || []}
            isExpanded={expandedIngredients.has(item.id)}
            onToggle={() => toggleIngredientExpand(item.id)}
            onRemove={removeItem}
            onRestore={restoreItem}
            isLoading={isFetchingIngredients}
          />
        )}
        
        {/* Dish children (not ingredients - those are shown as chips) */}
        {hasDishChildren && isExpanded && !isRemoved && (
          <div className="scaffold-item__children">
            {item.children
              .filter(child => child.type === 'dish')
              .map(child => renderItem(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }
  
  return (
    <div className="scaffold-preview">
      <div className="scaffold-preview__header">
        <h3 className="scaffold-preview__title">
          ✨ Scaffold Preview
        </h3>
        <button 
          className="scaffold-preview__close"
          onClick={onCancel}
          aria-label="Close"
        >
          ✕
        </button>
      </div>
      
      {/* Ingredient toggle */}
      {onToggleIngredients && (
        <div className="scaffold-preview__options">
          <label className="scaffold-preview__toggle-label">
            <input
              type="checkbox"
              checked={includeIngredients}
              onChange={(e) => onToggleIngredients(e.target.checked)}
              disabled={isFetchingIngredients}
            />
            <span>Include ingredient suggestions</span>
            {isFetchingIngredients && <span className="scaffold-preview__loading-dot" />}
          </label>
          {includeIngredients && counts.ingredients > 0 && (
            <button 
              className="scaffold-preview__expand-all"
              onClick={expandAllIngredients}
            >
              Expand all
            </button>
          )}
        </div>
      )}
      
      <div className="scaffold-preview__content">
        {scaffold ? (
          renderItem(scaffold)
        ) : (
          <p className="scaffold-preview__empty">No scaffold to display</p>
        )}
      </div>
      
      <div className="scaffold-preview__footer">
        <div className="scaffold-preview__summary">
          {totalNew > 0 ? (
            <span>
              Will create: {counts.dishes > 0 && `${counts.dishes} dish${counts.dishes > 1 ? 'es' : ''}`}
              {counts.dishes > 0 && counts.ingredients > 0 && ', '}
              {counts.ingredients > 0 && `${counts.ingredients} ingredient${counts.ingredients > 1 ? 's' : ''}`}
            </span>
          ) : (
            <span>All items already exist or removed</span>
          )}
        </div>
        <div className="scaffold-preview__actions">
          <button 
            className="btn btn-outline"
            onClick={onCancel}
            disabled={isExecuting}
          >
            Cancel
          </button>
          <button 
            className="btn btn-primary"
            onClick={onExecute}
            disabled={isExecuting || totalNew === 0}
          >
            {isExecuting ? 'Creating...' : `Create All (${totalNew})`}
          </button>
        </div>
      </div>
    </div>
  )
}



