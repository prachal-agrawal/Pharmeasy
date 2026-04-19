import { useState, useEffect } from 'react'
import { adminAPI } from '../../utils/api'
import { TrendingUp, ShoppingBag, Users, AlertTriangle } from 'lucide-react'

export default function AdminDashboard() {
  const [stats,  setStats]  = useState(null)
  const [orders, setOrders] = useState([])

  useEffect(() => {
    adminAPI.stats().then(r  => setStats(r.data)).catch(() => {})
    adminAPI.orders().then(r => setOrders(r.data.slice(0,8))).catch(() => {})
  }, [])

  const STATUS_CLASS = { pending:'status-pending', confirmed:'status-confirmed', dispatched:'status-dispatched', delivered:'status-delivered', cancelled:'status-cancelled' }

  return (
    <div className="page-enter">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-extrabold">Dashboard</h1>
        <p className="text-sm text-gray-400">{new Date().toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long', year:'numeric' })}</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label:"Today's Orders",   value: stats?.todayOrders   ?? '—', icon: ShoppingBag,   color:'text-brand',  bg:'bg-brand-light' },
          { label:"Today's Revenue",  value: stats ? `₹${Number(stats.todayRevenue).toFixed(0)}` : '—', icon: TrendingUp, color:'text-amber', bg:'bg-amber-light' },
          { label:'Pending Orders',   value: stats?.pendingOrders ?? '—', icon: ShoppingBag,   color:'text-info',   bg:'bg-info-light'  },
          { label:'Low Stock Items',  value: stats?.lowStock      ?? '—', icon: AlertTriangle, color:'text-danger', bg:'bg-danger-light' },
        ].map((s,i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">{s.label}</p>
              <div className={`w-8 h-8 ${s.bg} rounded-lg flex items-center justify-center`}>
                <s.icon className={`w-4 h-4 ${s.color}`} />
              </div>
            </div>
            <p className={`text-2xl font-extrabold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Recent orders */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="font-bold text-sm">Recent Orders</h2>
          <a href="/admin/orders" className="text-xs text-brand font-bold hover:underline">View all →</a>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs font-bold text-gray-400 uppercase">
              <tr>
                {['Order','Customer','Items','Total','Payment','Status','Date'].map(h => (
                  <th key={h} className="px-4 py-3 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {orders.map(o => (
                <tr key={o.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-bold text-brand">#{o.order_number}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium">{o.user_name}</p>
                    <p className="text-xs text-gray-400">{o.email}</p>
                  </td>
                  <td className="px-4 py-3 text-center">{o.item_count}</td>
                  <td className="px-4 py-3 font-bold">₹{parseFloat(o.total).toFixed(0)}</td>
                  <td className="px-4 py-3 capitalize text-gray-500">{o.payment_method}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[10px] font-bold px-2 py-1 rounded-full capitalize ${STATUS_CLASS[o.status]}`}>
                      {o.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {new Date(o.created_at).toLocaleDateString('en-IN')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
