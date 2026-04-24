import { useState, useEffect } from 'react'
import {
  Package,
  FileText,
  ChevronDown,
  ChevronUp,
  Truck,
  X,
  Copy,
  Check,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { ordersAPI } from '../utils/api'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const STATUS_STEPS = ['pending', 'confirmed', 'dispatched', 'delivered']
const STATUS_LABELS = {
  pending: 'Order placed',
  confirmed: 'Confirmed',
  dispatched: 'Out for delivery',
  delivered: 'Delivered',
  cancelled: 'Cancelled',
}
const STATUS_CLASS = {
  pending: 'status-pending',
  confirmed: 'status-confirmed',
  dispatched: 'status-dispatched',
  delivered: 'status-delivered',
  cancelled: 'status-cancelled',
}

function payLabel(method) {
  if (!method) return '—'
  const m = String(method).toLowerCase()
  if (m === 'razorpay') return 'Paid online'
  return method.replace(/_/g, ' ')
}

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)
  const [downloading, setDownloading] = useState(null)
  const [trackModalId, setTrackModalId] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const { user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!user) navigate('/login', { replace: true })
  }, [user, navigate])

  useEffect(() => {
    ordersAPI
      .list()
      .then((r) => setOrders(r.data))
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

  const copyOrderNumber = (orderNumber, id) => {
    navigator.clipboard.writeText(orderNumber)
    setCopiedId(id)
    toast.success('Order number copied')
    setTimeout(() => setCopiedId(null), 2000)
  }

  const trackOrder = orders.find((o) => o.id === trackModalId) || null
  const trackIdx = trackOrder ? STATUS_STEPS.indexOf(trackOrder.status) : -1

  if (loading) {
    return (
      <div className="min-h-[50vh] max-w-3xl mx-auto px-4 flex items-center justify-center text-gray-500 text-sm">
        Loading your orders…
      </div>
    )
  }

  if (!orders.length) {
    return (
      <div className="min-h-[60vh] max-w-lg mx-auto px-4 flex flex-col items-center justify-center text-center page-enter">
        <div className="w-20 h-20 rounded-full bg-brand-light/50 flex items-center justify-center mb-4">
          <Package className="w-9 h-9 text-brand" strokeWidth={1.5} />
        </div>
        <h2 className="text-lg font-extrabold text-gray-800">No orders yet</h2>
        <p className="text-sm text-gray-500 mt-1 mb-6">When you place an order, it will show up here with tracking.</p>
        <button type="button" onClick={() => navigate('/')} className="btn-primary px-6 py-2.5 text-sm font-bold rounded-xl">
          Browse medicines
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 pb-12 page-enter">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">My orders</h1>
        <p className="text-sm text-gray-500 mt-0.5">{orders.length} order{orders.length !== 1 ? 's' : ''} placed</p>
      </div>

      <ul className="space-y-4">
        {orders.map((order) => {
          const isOpen = expanded === order.id

          return (
            <li
              key={order.id}
              className="rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden transition-shadow hover:shadow-md"
            >
              <div className="p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider mb-1.5">Order no.</p>
                    <div className="flex flex-wrap items-center gap-2 gap-y-1">
                      <span className="text-lg sm:text-xl font-extrabold text-gray-900 font-mono tracking-tight">
                        {order.order_number}
                      </span>
                      <button
                        type="button"
                        onClick={() => copyOrderNumber(order.order_number, order.id)}
                        className="inline-flex items-center gap-1 text-[11px] font-bold text-brand hover:underline p-0.5 rounded"
                        title="Copy order number"
                      >
                        {copiedId === order.id ? (
                          <Check className="w-3.5 h-3.5 text-green-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        Copy
                      </button>
                      <span
                        className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                          STATUS_CLASS[order.status] || 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {STATUS_LABELS[order.status] || order.status}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Placed on{' '}
                      {new Date(order.created_at).toLocaleString('en-IN', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}{' '}
                      · {order.item_count} item{order.item_count > 1 ? 's' : ''}
                    </p>
                  </div>
                  <div className="text-left sm:text-right shrink-0 pt-0 sm:pt-6 sm:pl-4">
                    <p className="text-lg font-extrabold text-brand">₹{parseFloat(order.total).toFixed(0)}</p>
                    <p className="text-xs text-gray-500 capitalize mt-0.5">{payLabel(order.payment_method)}</p>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-100 flex w-full min-w-0 items-center gap-3">
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                    {order.status !== 'cancelled' && (
                      <button
                        type="button"
                        onClick={() => setTrackModalId(order.id)}
                        className="inline-flex items-center gap-1.5 text-sm font-bold text-brand hover:text-brand/90"
                      >
                        <Truck className="w-4 h-4" />
                        Track order
                      </button>
                    )}
                    {order.status !== 'cancelled' && (
                      <span className="text-gray-200 hidden sm:inline" aria-hidden>
                        |
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleInvoiceDownload(order.id, order.order_number)}
                      disabled={downloading === order.id}
                      className="inline-flex items-center gap-1.5 text-sm font-semibold text-gray-600 hover:text-brand disabled:opacity-50"
                    >
                      <FileText className="w-4 h-4" />
                      {downloading === order.id ? 'Preparing…' : 'Download invoice'}
                    </button>
                  </div>
                  <div className="shrink-0 self-center text-right">
                    <button
                      type="button"
                      onClick={() => setExpanded(isOpen ? null : order.id)}
                      className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800"
                    >
                      {isOpen ? 'Hide details' : 'View details'}
                      {isOpen ? <ChevronUp className="w-4" /> : <ChevronDown className="w-4" />}
                    </button>
                  </div>
                </div>
              </div>

              {isOpen && (
                <div className="border-t border-gray-100 bg-gradient-to-b from-gray-50/80 to-white px-4 sm:px-5 py-4">
                  <OrderDetail orderId={order.id} />
                </div>
              )}
            </li>
          )
        })}
      </ul>

      {trackOrder && trackOrder.status !== 'cancelled' && (
        <div
          className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="track-order-title"
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px] z-0"
            onClick={() => setTrackModalId(null)}
            aria-label="Close"
          />
          <div
            className="relative z-10 w-full sm:max-w-md bg-white sm:rounded-2xl rounded-t-2xl shadow-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-white sm:rounded-t-2xl">
              <h2 id="track-order-title" className="text-base font-extrabold text-gray-900">
                Order tracking
              </h2>
              <button
                type="button"
                onClick={() => setTrackModalId(null)}
                className="p-2 rounded-full text-gray-500 hover:bg-gray-100 transition-colors"
                aria-label="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-5 py-2 pb-1">
              <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">Order no.</p>
              <p className="text-lg font-mono font-extrabold text-gray-900">{trackOrder.order_number}</p>
            </div>
            <div className="px-5 pb-6">
              <p className="text-sm text-gray-600 mb-5">Follow each step of your order until delivery.</p>
              <div className="flex items-center">
                {STATUS_STEPS.map((s, i) => (
                  <div key={s} className="flex items-center flex-1 min-w-0 last:flex-none last:min-w-0">
                    <div className="flex flex-col items-center w-full min-w-0">
                      <div
                        className={`w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                          i < trackIdx
                            ? 'bg-brand border-brand text-white'
                            : i === trackIdx
                              ? 'border-brand bg-white ring-2 ring-brand/20'
                              : 'border-gray-200 bg-white'
                        }`}
                      >
                        {i < trackIdx && (
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path
                              fillRule="evenodd"
                              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                              clipRule="evenodd"
                            />
                          </svg>
                        )}
                        {i === trackIdx && <div className="w-2.5 h-2.5 rounded-full bg-brand" />}
                      </div>
                      <p
                        className={`text-[9px] sm:text-[10px] font-bold mt-1.5 text-center leading-tight px-0.5 ${
                          i <= trackIdx ? 'text-brand' : 'text-gray-300'
                        }`}
                      >
                        {STATUS_LABELS[s]}
                      </p>
                    </div>
                    {i < STATUS_STEPS.length - 1 && (
                      <div
                        className={`flex-1 h-0.5 mx-0.5 sm:mx-1 mb-6 -translate-y-3 ${
                          i < trackIdx ? 'bg-brand' : 'bg-gray-200'
                        }`}
                      />
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 text-center mt-2">
                Current status: <span className="font-bold text-gray-800">{STATUS_LABELS[trackOrder.status]}</span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function OrderDetail({ orderId }) {
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    ordersAPI
      .get(orderId)
      .then((r) => setDetail(r.data))
      .catch(() => {})
  }, [orderId])

  if (!detail) {
    return <div className="text-sm text-gray-400 py-3">Loading line items…</div>
  }

  const addr = detail.address_snapshot || {}

  return (
    <div className="space-y-4">
      <div>
        <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider mb-2">Items in this order</p>
        <ul className="rounded-xl border border-gray-100 bg-white overflow-hidden divide-y divide-gray-50">
          {detail.items.map((i) => (
            <li key={i.id} className="flex justify-between gap-3 px-3 py-2.5 text-sm">
              <span className="text-gray-700 min-w-0">
                {i.name}{' '}
                <span className="text-gray-400 font-normal">({i.variant_label})</span>
                <span className="text-gray-500"> × {i.quantity}</span>
              </span>
              <span className="font-extrabold text-gray-900 shrink-0">₹{parseFloat(i.subtotal).toFixed(0)}</span>
            </li>
          ))}
        </ul>
      </div>
      {addr.line1 && (
        <div>
          <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider mb-1">Ship to</p>
          <p className="text-sm text-gray-600 leading-relaxed">
            {addr.name} — {addr.line1}
            {addr.line2 ? `, ${addr.line2}` : ''}, {addr.city} {addr.pin}
          </p>
        </div>
      )}
    </div>
  )
}
