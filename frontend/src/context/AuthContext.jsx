import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../utils/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('mathurapharmeasy_user')
    const token  = localStorage.getItem('mathurapharmeasy_token')
    if (stored && token) {
      setUser(JSON.parse(stored))
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const { data } = await authAPI.login({ email, password })
    localStorage.setItem('mathurapharmeasy_token', data.token)
    localStorage.setItem('mathurapharmeasy_user',  JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }

  const register = async (name, email, password, phone) => {
    const { data } = await authAPI.register({ name, email, password, phone })
    localStorage.setItem('mathurapharmeasy_token', data.token)
    localStorage.setItem('mathurapharmeasy_user',  JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }

  const logout = () => {
    localStorage.removeItem('mathurapharmeasy_token')
    localStorage.removeItem('mathurapharmeasy_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
