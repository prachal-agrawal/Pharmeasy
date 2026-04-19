import { useState, useEffect } from 'react'
import { Package, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { ordersAPI } from '../utils/api'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const STATUS_STEPS = ['pending','confirmed','dispatched','delivered']
const STATUS_LABELS = { pending:'Pending', confirmed:'Confirmed', dispatched:'Dispatched', delivered:'Delivered', cancelled:'Cancelled' }
const STATUS_CLASS  = { pending:'status-pending', confirmed:'status-confirmed', dispatched:'status-dispatched', delivered:'status-delivered', cancelled:'status-cancelled' }

export default function Orders() {
  const [orders,       setOrders]       = useState([])
  const [loading,      setLoading]      = useState(true)
  const [expanded,     setExpanded]     = useState(null)
  const [downloading,  setDownloading]  = useState(null)
  const { user }   = useAuth()
  const navigate   = useNavigate()

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!user) navigate('/login', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    ordersAPI.list()
      .then(r => setOrders(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleInvoiceDownload = async (orderId, orderNumber) => {
    setDownloading(orderId)
    try {
      await ordersAPI.downloadInvoice(orderId, orderNumber)
    } catch {
      alert('Invoice not available yet. Please try again in a moment.')
    } finally {
      setDownloading(null)
    }
  }

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-8 text-center text-gray-400">Loading orders...</div>

  if (!orders.length) return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-center page-enter">
      <Package className="w-16 h-16 text-gray-200 mx-auto mb-4" />
      <h2 className="text-lg font-bold text-gray-400 mb-2">No orders yet</h2>
      <p className="text-sm text-gray-400">Your order history will appear here</p>
    </div>
  )

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 page-enter">
      <h1 className="text-xl font-extrabold mb-6">My Orders <span className="text-gray-400 font-normal text-base">({orders.length})</span></h1>

      <div className="space-y-4">
        {orders.map(order => {
          const idx = STATUS_STEPS.indexOf(order.status)
          const isOpen = expanded === order.id

          return (
            <div key={order.id} className="card overflow-hidden">
              {/* Header */}
              <div className="p-4 flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-extrabold text-brand text-sm">#{order.order_number}</p>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${STATUS_CLASS[order.status]}`}>
                      {STATUS_LABELS[order.status]}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">
                    {new Date(order.created_at).toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' })}
                    {' · '}{order.item_count} item{order.item_count > 1 ? 's' : ''}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-extrabold text-base text-brand">₹{parseFloat(order.total).toFixed(0)}</p>
                  <p className="text-xs text-gray-400 capitalize">{order.payment_method}</p>
                </div>
              </div>

              {/* Progress tracker */}
              {order.status !== 'cancelled' && (
                <div className="px-4 pb-4">
                  <div className="flex items-center">
                    {STATUS_STEPS.map((s, i) => (
                      <div key={s} className="flex items-center flex-1 last:flex-none">
                        <div className="flex flex-col items-center">
                          <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${
                            i < idx ? 'bg-brand border-brand' : i === idx ? 'border-brand bg-white' : 'border-gray-200 bg-white'
                          }`}>
                            {i < idx && <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>}
                            {i === idx && <div className="w-2 h-2 rounded-full bg-brand" />}
                          </div>
                          <p className={`text-[9px] font-bold mt-1 whitespace-nowrap ${i <= idx ? 'text-brand' : 'text-gray-300'}`}>
                            {STATUS_LABELS[s]}
                          </p>
                        </div>
                        {i < STATUS_STEPS.length - 1 && (
                          <div className={`flex-1 h-0.5 mx-1 mb-3 ${i < idx ? 'bg-brand' : 'bg-gray-200'}`} />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="px-4 pb-4 flex gap-2">
                <button
                  onClick={() => handleInvoiceDownload(order.id, order.order_number)}
                  disabled={downloading === order.id}
                  className="flex items-center gap-1.5 text-xs font-bold text-brand bg-brand-light px-3 py-1.5 rounded-md hover:bg-brand hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <FileText className="w-3.5 h-3.5" />
                  {downloading === order.id ? 'Downloading…' : 'Invoice'}
                </button>
                <button
                  onClick={() => setExpanded(isOpen ? null : order.id)}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 ml-auto"
                >
                  {isOpen ? 'Less' : 'Details'}
                  {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Expanded detail */}
              {isOpen && (
                <div className="border-t border-gray-100 bg-gray-50 px-4 py-4">
                  <OrderDetail orderId={order.id} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function OrderDetail({ orderId }) {
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    ordersAPI.get(orderId).then(r => setDetail(r.data)).catch(() => {})
  }, [orderId])

  if (!detail) return <div className="text-xs text-gray-400 py-2">Loading...</div>

  const addr = detail.address_snapshot || {}

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-bold text-gray-400 uppercase mb-1">Items</p>
        {detail.items.map(i => (
          <div key={i.id} className="flex justify-between text-xs py-1 border-b border-gray-100 last:border-0">
            <span className="text-gray-600">{i.name} <span className="text-gray-400">({i.variant_label})</span> × {i.quantity}</span>
            <span className="font-bold">₹{parseFloat(i.subtotal).toFixed(0)}</span>
          </div>
        ))}
      </div>
      {addr.line1 && (
        <div>
          <p className="text-xs font-bold text-gray-400 uppercase mb-1">Delivered To</p>
          <p className="text-xs text-gray-600">{addr.name} · {addr.line1}, {addr.city} - {addr.pin}</p>
        </div>
      )}
    </div>
  )
}
