import React from 'react'
import { useCart } from '../context/CartContext'

export default function CartButton() {
  const { getItemCount, toggleCart } = useCart()
  const itemCount = getItemCount()

  if (itemCount === 0) return null

  return (
    <button 
      className="cart-button-float" 
      onClick={toggleCart}
      aria-label={`Shopping cart with ${itemCount} items`}
    >
      <i className="fa-solid fa-shopping-cart"></i>
      {itemCount > 0 && (
        <span className="cart-badge">{itemCount}</span>
      )}
    </button>
  )
}



