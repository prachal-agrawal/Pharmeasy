import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Pill, ShoppingBag, LogOut, ExternalLink } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const links = [
  { to: '/admin',            label: 'Dashboard',  icon: LayoutDashboard, end: true },
  { to: '/admin/medicines',  label: 'Medicines',  icon: Pill },
  { to: '/admin/orders',     label: 'Orders',     icon: ShoppingBag },
]

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen bg-[#f0f4f2]">
      {/* Sidebar */}
      <aside className="w-56 bg-brand min-h-screen flex flex-col fixed left-0 top-0 z-40">
        <div className="p-5 border-b border-white/10">
          <div className="text-xl font-extrabold text-white tracking-tight">
            Mathura<span className="opacity-60">Pharmeasy</span>
          </div>
          <div className="text-xs text-white/50 mt-0.5">Admin Panel</div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to} to={to} end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive ? 'bg-white/20 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4" /> {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-white/10 space-y-1">
          <a href="/" target="_blank" rel="noreferrer"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-white/50 hover:text-white hover:bg-white/10 transition-all">
            <ExternalLink className="w-3.5 h-3.5" /> View Store
          </a>
          <div className="px-3 py-2 text-xs text-white/40 truncate">👤 {user?.name}</div>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-white/50 hover:text-white hover:bg-white/10 transition-all"
          >
            <LogOut className="w-3.5 h-3.5" /> Logout
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-56 flex-1 p-6 min-h-screen">
        <Outlet />
      </main>
    </div>
  )
}
