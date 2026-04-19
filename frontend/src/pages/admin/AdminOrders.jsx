import { useState, useEffect } from 'react'
import { FileText, ChevronDown, X, ZoomIn } from 'lucide-react'
import { adminAPI, ordersAPI } from '../../utils/api'
import toast from 'react-hot-toast'

/**
 * Resolve all prescription image URLs for an order row.
 *
 * Priority:
 *  1. `rx_urls`  — GROUP_CONCAT string from the new order_prescriptions table
 *                  (e.g. "/uploads/rx_1.jpg|||/uploads/rx_2.jpg")
 *  2. `prescription_url` — legacy column (plain string or JSON array) kept for
 *                          orders created before migration 004.
 */
function parseRxUrls(order) {
  // ── New mapping table (preferred) ──────────────────────────────────────
  if (order.rx_urls) {
    return order.rx_urls.split('|||').filter(Boolean)
  }

  // ── Legacy fallback: JSON blob or plain string in prescription_url ──────
  const raw = order.prescription_url
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [String(parsed)]
  } catch {
    return [raw]
  }
}

const STATUSES = ['pending','confirmed','dispatched','delivered','cancelled']
const STATUS_CLASS = {
  pending:'status-pending', confirmed:'status-confirmed',
  dispatched:'status-dispatched', delivered:'status-delivered', cancelled:'status-cancelled'
}

export default function AdminOrders() {
  const [orders,   setOrders]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState('all')
  const [search,   setSearch]   = useState('')
  const [rxModal,  setRxModal]  = useState(null)   // null | { orderNum: string, urls: string[] }
  const [lightbox, setLightbox] = useState(null)   // null | url string

  useEffect(() => {
    adminAPI.orders().then(r => setOrders(r.data)).finally(() => setLoading(false))
  }, [])

  const updateStatus = async (id, status) => {
    try {
      await adminAPI.updateStatus(id, status)
      setOrders(prev => prev.map(o => o.id === id ? { ...o, status } : o))
      toast.success(`Order status updated to ${status}`)
    } catch { toast.error('Update failed') }
  }

  const filtered = orders.filter(o => {
    const matchFilter = filter === 'all' || o.status === filter
    const matchSearch = !search || o.order_number.includes(search) || (o.user_name||'').toLowerCase().includes(search.toLowerCase()) || (o.email||'').toLowerCase().includes(search.toLowerCase())
    return matchFilter && matchSearch
  })

  return (
    <div className="page-enter">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-extrabold">Orders <span className="text-gray-400 font-normal text-base">({orders.length})</span></h1>
        <div className="flex gap-2">
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by order # or customer..." className="input-field text-sm bg-white w-64" />
          <select value={filter} onChange={e => setFilter(e.target.value)}
            className="input-field text-sm bg-white w-36">
            <option value="all">All Status</option>
            {STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-bold text-gray-400 uppercase">
              <tr>
                {['Order','Customer','Items','Amount','Payment','Status','Date','Rx','Invoice'].map(h => (
                  <th key={h} className="px-4 py-3 text-left whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                Array(6).fill(0).map((_,i) => (
                  <tr key={i}><td colSpan={9} className="px-4 py-3"><div className="h-4 bg-gray-100 rounded animate-pulse" /></td></tr>
                ))
              ) : filtered.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">No orders found</td></tr>
              ) : filtered.map(o => {
                const rxUrls = parseRxUrls(o)
                return (
                  <tr key={o.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-extrabold text-brand">#{o.order_number}</td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{o.user_name}</p>
                      <p className="text-xs text-gray-400">{o.email}</p>
                    </td>
                    <td className="px-4 py-3 text-center text-gray-500">{o.item_count}</td>
                    <td className="px-4 py-3">
                      <p className="font-bold">₹{parseFloat(o.total).toFixed(0)}</p>
                      <p className={`text-[10px] font-bold capitalize ${o.payment_status==='paid'?'text-brand':'text-amber'}`}>{o.payment_status}</p>
                    </td>
                    <td className="px-4 py-3 capitalize text-gray-500 text-xs">{o.payment_method}</td>
                    <td className="px-4 py-3">
                      <div className="relative">
                        <select
                          value={o.status}
                          onChange={e => updateStatus(o.id, e.target.value)}
                          className={`text-[10px] font-bold px-2 py-1 rounded-full border-0 outline-none cursor-pointer appearance-none pr-5 ${STATUS_CLASS[o.status]}`}
                        >
                          {STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
                        </select>
                        <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 w-3 h-3 pointer-events-none opacity-60" />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(o.created_at).toLocaleDateString('en-IN', { day:'numeric', month:'short' })}
                    </td>

                    {/* Prescription column */}
                    <td className="px-4 py-3">
                      {rxUrls.length > 0 ? (
                        <button
                          onClick={() => setRxModal({ orderNum: o.order_number, urls: rxUrls })}
                          className="flex items-center gap-1 bg-amber-50 hover:bg-amber-100 text-amber-700 text-[10px] font-extrabold px-2 py-1 rounded-full transition-colors"
                        >
                          <FileText className="w-3 h-3" />
                          {rxUrls.length}
                        </button>
                      ) : (
                        <span className="text-gray-300 text-[10px]">—</span>
                      )}
                    </td>

                    <td className="px-4 py-3">
                      <a href={ordersAPI.invoice(o.id)} target="_blank" rel="noreferrer"
                        className="p-1.5 hover:bg-brand-light hover:text-brand rounded transition-colors text-gray-400 inline-flex">
                        <FileText className="w-4 h-4" />
                      </a>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Summary bar */}
        <div className="px-5 py-3 border-t border-gray-100 bg-gray-50 flex gap-6 text-xs text-gray-500">
          {STATUSES.map(s => {
            const count = orders.filter(o => o.status === s).length
            return count > 0 ? (
              <span key={s} className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-full inline-block ${STATUS_CLASS[s]}`} />
                {s.charAt(0).toUpperCase()+s.slice(1)}: <strong>{count}</strong>
              </span>
            ) : null
          })}
        </div>
      </div>

      {/* ── Prescription viewer modal ── */}
      {rxModal && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setRxModal(null)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <p className="font-extrabold text-gray-800">Prescriptions</p>
                <p className="text-xs text-gray-400">
                  Order #{rxModal.orderNum} · {rxModal.urls.length} image{rxModal.urls.length > 1 ? 's' : ''}
                </p>
              </div>
              <button
                onClick={() => setRxModal(null)}
                className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Image grid */}
            <div className="overflow-y-auto p-5">
              <div className={`grid gap-3 ${rxModal.urls.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                {rxModal.urls.map((url, i) => (
                  <div key={i} className="relative group rounded-xl overflow-hidden border border-gray-100 bg-gray-50">
                    <img
                      src={url}
                      alt={`Prescription ${i + 1}`}
                      className="w-full object-contain max-h-72"
                    />
                    {/* Zoom / open in new tab */}
                    <button
                      onClick={() => setLightbox(url)}
                      className="absolute inset-0 bg-black/0 group-hover:bg-black/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
                    >
                      <ZoomIn className="w-8 h-8 text-white drop-shadow" />
                    </button>
                    <p className="text-[10px] text-gray-400 text-center py-1.5">Page {i + 1}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Download all */}
            <div className="px-5 py-3 border-t border-gray-100 flex justify-end gap-2">
              {rxModal.urls.map((url, i) => (
                <a
                  key={i}
                  href={url}
                  download
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-brand font-semibold hover:underline"
                >
                  ⬇ Page {i + 1}
                </a>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Full-screen lightbox ── */}
      {lightbox && (
        <div
          className="fixed inset-0 z-[60] bg-black/90 flex items-center justify-center p-4"
          onClick={() => setLightbox(null)}
        >
          <button className="absolute top-4 right-4 text-white/80 hover:text-white">
            <X className="w-7 h-7" />
          </button>
          <img
            src={lightbox}
            alt="Prescription full view"
            className="max-w-full max-h-[95vh] object-contain rounded-lg"
          />
        </div>
      )}
    </div>
  )
}
