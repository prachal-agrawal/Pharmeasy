import { Link, useNavigate } from 'react-router-dom'
import { Trash2, ShoppingBag, ArrowRight, Tag } from 'lucide-react'
import { useCart } from '../context/CartContext'
import MedicineImage from '../components/MedicineImage'
import { useAuth } from '../context/AuthContext'

export default function Cart() {
  const { items, totals, updateQty, removeItem, loading } = useCart()
  const { user } = useAuth()
  const navigate = useNavigate()

  if (loading) return <div className="max-w-4xl mx-auto px-4 py-8 text-center text-gray-400">Loading cart...</div>

  if (!items.length) return (
    <div className="max-w-4xl mx-auto px-4 py-16 text-center page-enter">
      <ShoppingBag className="w-16 h-16 text-gray-200 mx-auto mb-4" />
      <h2 className="text-lg font-bold text-gray-400 mb-2">Your cart is empty</h2>
      <p className="text-sm text-gray-400 mb-6">Browse our catalog and add medicines</p>
      <Link to="/" className="btn-primary inline-flex items-center gap-2">
        Browse Medicines <ArrowRight className="w-4 h-4" />
      </Link>
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 page-enter">
      <h1 className="text-xl font-extrabold mb-6">Your Cart <span className="text-gray-400 font-normal text-base">({items.length} item{items.length > 1 ? 's' : ''})</span></h1>

      <div className="grid lg:grid-cols-3 gap-6 items-start">
        {/* Items */}
        <div className="lg:col-span-2 space-y-3">
          {items.map(item => (
            <div key={item.id} className="card p-4 flex gap-4 items-center">
              {/* Image */}
              <div className="w-16 h-16 rounded-lg overflow-hidden shrink-0">
                <MedicineImage
                  name={item.name}
                  src={item.image_url}
                  className="w-full h-full rounded-lg"
                  imgClassName="w-full h-full object-cover"
                  placeholderSize="md"
                />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-sm truncate">{item.name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">{item.label}</p>
                <span className={`${item.requires_rx ? 'badge-rx' : 'badge-otc'} mt-1 inline-block`}>
                  {item.requires_rx ? 'Rx' : 'OTC'}
                </span>
              </div>

              {/* Qty controls */}
              <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden shrink-0">
                <button onClick={() => updateQty(item.id, item.quantity - 1)}
                  className="px-2.5 py-1.5 hover:bg-gray-50 font-bold transition-colors text-sm">−</button>
                <span className="px-3 py-1.5 font-bold text-sm border-x border-gray-200">{item.quantity}</span>
                <button onClick={() => updateQty(item.id, item.quantity + 1)}
                  className="px-2.5 py-1.5 hover:bg-gray-50 font-bold transition-colors text-sm">+</button>
              </div>

              {/* Price */}
              <div className="text-right shrink-0 min-w-[60px]">
                <p className="font-extrabold text-brand">₹{(parseFloat(item.price) * item.quantity).toFixed(0)}</p>
                <p className="text-[10px] text-gray-400">₹{parseFloat(item.price).toFixed(0)} each</p>
              </div>

              {/* Remove */}
              <button onClick={() => removeItem(item.id)}
                className="text-gray-300 hover:text-danger transition-colors p-1 shrink-0">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        {/* Order summary */}
        <div className="card p-5 sticky top-20">
          <h2 className="font-bold text-base mb-4 text-brand">Order Summary</h2>

          <div className="space-y-3 text-sm">
            <Row label={`Subtotal (${items.length} item${items.length>1?'s':''})`} value={`₹${totals.subtotal.toFixed(0)}`} />
            <Row label="Delivery" value={totals.delivery === 0 ? <span className="text-brand font-bold">Free</span> : `₹${totals.delivery}`} />
            {totals.discount > 0 && (
              <Row label="Discount (5%)" value={<span className="text-brand font-bold">−₹{totals.discount}</span>} />
            )}
            <div className="border-t border-gray-100 pt-3 flex justify-between font-extrabold text-base">
              <span>Total</span>
              <span className="text-brand">₹{totals.total.toFixed(0)}</span>
            </div>
          </div>

          {totals.delivery > 0 && (
            <p className="text-[11px] text-gray-400 mt-2 bg-gray-50 rounded-lg p-2 text-center">
              Add ₹{(500 - totals.subtotal).toFixed(0)} more for free delivery
            </p>
          )}

          {/* Promo */}
          <div className="flex gap-2 mt-4">
            <div className="relative flex-1">
              <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
              <input placeholder="Promo code" className="input-field pl-8 text-xs" />
            </div>
            <button className="btn-outline text-xs px-3">Apply</button>
          </div>

          <button
            onClick={() => user ? navigate('/checkout') : navigate('/login')}
            className="w-full btn-primary mt-4 py-3 flex items-center justify-center gap-2"
          >
            {user ? 'Proceed to Checkout' : 'Login to Checkout'}
            <ArrowRight className="w-4 h-4" />
          </button>

          <p className="text-center text-[10px] text-gray-400 mt-3">🔒 Secure checkout · SSL Encrypted</p>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between text-gray-500">
      <span>{label}</span>
      <span className="text-gray-700 font-medium">{value}</span>
    </div>
  )
}
