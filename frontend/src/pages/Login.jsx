// ─── Login.jsx ──────────────────────────────────────────────
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

export function Login() {
  const { login } = useAuth()
  const navigate   = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handle = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const user = await login(form.email, form.password)
      toast.success(`Welcome back, ${user.name.split(' ')[0]}!`)
      navigate(user.role === 'admin' ? '/admin' : '/')
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Invalid credentials')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 page-enter">
      <div className="card p-8 w-full max-w-sm">
        <div className="text-2xl font-extrabold text-brand mb-1">Bharat<span className="text-amber">Medical</span></div>
        <h2 className="font-bold text-lg mb-1">Welcome back</h2>
        <p className="text-sm text-gray-400 mb-6">Login to your account</p>

        <form onSubmit={handle} className="space-y-4">
          <div>
            <label className="text-xs font-bold text-gray-500 block mb-1">Email</label>
            <input className="input-field" type="email" required placeholder="you@example.com"
              value={form.email} onChange={e => setForm(p => ({...p, email: e.target.value}))} />
          </div>
          <div>
            <label className="text-xs font-bold text-gray-500 block mb-1">Password</label>
            <input className="input-field" type="password" required placeholder="Your password"
              value={form.password} onChange={e => setForm(p => ({...p, password: e.target.value}))} />
          </div>
          <button type="submit" disabled={loading} className="w-full btn-primary py-3">
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-4">
          New here?{' '}
          <Link to="/register" className="text-brand font-bold hover:underline">Create account</Link>
        </p>

        <div className="mt-4 bg-gray-50 rounded-lg p-3 text-xs text-gray-400">
          <p className="font-bold text-gray-500 mb-1">Admin demo:</p>
          <p>Email: admin@mathurapharmeasy.in</p>
          <p>Password: Admin@123</p>
        </div>
      </div>
    </div>
  )
}

// ─── Register.jsx ────────────────────────────────────────────
export function Register() {
  const { register } = useAuth()
  const navigate      = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', phone: '', password: '' })
  const [loading, setLoading] = useState(false)

  const handle = async (e) => {
    e.preventDefault()
    if (form.password.length < 6) return toast.error('Password must be at least 6 characters')
    setLoading(true)
    try {
      await register(form.name, form.email, form.password, form.phone)
      toast.success('Account created!')
      navigate('/')
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Registration failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 page-enter">
      <div className="card p-8 w-full max-w-sm">
        <div className="text-2xl font-extrabold text-brand mb-1">Bharat<span className="text-amber">Medical</span></div>
        <h2 className="font-bold text-lg mb-1">Create Account</h2>
        <p className="text-sm text-gray-400 mb-6">Join Bharat Medical for faster checkout</p>

        <form onSubmit={handle} className="space-y-4">
          {[
            { key:'name',     label:'Full Name',    type:'text',     placeholder:'Your full name' },
            { key:'email',    label:'Email',         type:'email',    placeholder:'you@example.com' },
            { key:'phone',    label:'Phone *',       type:'tel',      placeholder:'10-digit mobile number' },
            { key:'password', label:'Password',      type:'password', placeholder:'Min 6 characters' },
          ].map(f => (
            <div key={f.key}>
              <label className="text-xs font-bold text-gray-500 block mb-1">{f.label}</label>
              <input
                className="input-field"
                type={f.type}
                placeholder={f.placeholder}
                required
                pattern={f.key === 'phone' ? '[0-9+\\s\\-]{7,15}' : undefined}
                title={f.key === 'phone' ? 'Enter a valid 10-digit mobile number' : undefined}
                value={form[f.key]}
                onChange={e => setForm(p => ({...p, [f.key]: e.target.value}))}
              />
              {f.key === 'phone' && (
                <p className="text-[11px] text-gray-400 mt-1">
                  📱 Required to receive order updates via SMS
                </p>
              )}
            </div>
          ))}
          <button type="submit" disabled={loading} className="w-full btn-primary py-3">
            {loading ? 'Creating account...' : 'Create Account'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-4">
          Already have an account?{' '}
          <Link to="/login" className="text-brand font-bold hover:underline">Login</Link>
        </p>
      </div>
    </div>
  )
}

export default Login
