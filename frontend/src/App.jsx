import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import ProductDetail from './pages/ProductDetail'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Orders from './pages/Orders'
import Login from './pages/Login'
import Register from './pages/Register'
import AdminLayout from './pages/admin/AdminLayout'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminMedicines from './pages/admin/AdminMedicines'
import AdminOrders from './pages/admin/AdminOrders'

function ProtectedRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-64 text-brand">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'admin') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      {/* Admin routes — no navbar */}
      <Route path="/admin" element={<ProtectedRoute adminOnly><AdminLayout /></ProtectedRoute>}>
        <Route index       element={<AdminDashboard />} />
        <Route path="medicines" element={<AdminMedicines />} />
        <Route path="orders"    element={<AdminOrders />} />
      </Route>

      {/* Customer routes — with navbar */}
      <Route path="/*" element={<CustomerLayout />} />
    </Routes>
  )
}

function CustomerLayout() {
  return (
    <div className="min-h-screen bg-[#f7faf8]">
      <Navbar />
      <Routes>
        <Route path="/"              element={<Home />} />
        <Route path="/medicine/:id"  element={<ProductDetail />} />
        <Route path="/cart"          element={<Cart />} />
        <Route path="/login"         element={<Login />} />
        <Route path="/register"      element={<Register />} />
        <Route path="/checkout"      element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
        <Route path="/orders"        element={<ProtectedRoute><Orders /></ProtectedRoute>} />
        <Route path="*"              element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
