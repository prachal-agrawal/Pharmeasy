import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { cartAPI } from '../utils/api'
import { useAuth } from './AuthContext'
import toast from 'react-hot-toast'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  const { user } = useAuth()
  const [items,   setItems]   = useState([])
  const [loading, setLoading] = useState(false)

  const fetchCart = useCallback(async () => {
    if (!user) { setItems([]); return }
    try {
      setLoading(true)
      const { data } = await cartAPI.get()
      setItems(data)
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [user])

  useEffect(() => { fetchCart() }, [fetchCart])

  const addToCart = async (variantId, quantity = 1, medName = '') => {
    if (!user) { toast.error('Please login to add items'); return false }
    try {
      await cartAPI.add(variantId, quantity)
      await fetchCart()
      toast.success(`${medName || 'Item'} added to cart`)
      return true
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not add to cart')
      return false
    }
  }

  const updateQty = async (itemId, quantity) => {
    try {
      await cartAPI.update(itemId, quantity)
      setItems(prev =>
        quantity < 1
          ? prev.filter(i => i.id !== itemId)
          : prev.map(i => i.id === itemId ? { ...i, quantity } : i)
      )
    } catch { toast.error('Could not update cart') }
  }

  const removeItem = async (itemId) => {
    try {
      await cartAPI.remove(itemId)
      setItems(prev => prev.filter(i => i.id !== itemId))
      toast.success('Item removed')
    } catch { toast.error('Could not remove item') }
  }

  const clearCart = async () => {
    try { await cartAPI.clear(); setItems([]) } catch { /* silent */ }
  }

  const totals = (() => {
    const subtotal = items.reduce((s, i) => s + parseFloat(i.price) * i.quantity, 0)
    const delivery = subtotal >= 500 ? 0 : 49
    const discount = subtotal >= 1000 ? Math.round(subtotal * 0.05) : 0
    return { subtotal, delivery, discount, total: subtotal + delivery - discount }
  })()

  const count = items.reduce((s, i) => s + i.quantity, 0)

  return (
    <CartContext.Provider value={{ items, loading, count, totals, addToCart, updateQty, removeItem, clearCart, fetchCart }}>
      {children}
    </CartContext.Provider>
  )
}

export const useCart = () => useContext(CartContext)
