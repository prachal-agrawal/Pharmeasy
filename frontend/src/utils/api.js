import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('mathurapharmeasy_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Global error handler
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('mathurapharmeasy_token')
      localStorage.removeItem('mathurapharmeasy_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ─────────────────────────────────────────────────────
export const authAPI = {
  register: (data)  => api.post('/auth/register', data),
  login:    (data)  => api.post('/auth/login', data),
  me:       ()      => api.get('/auth/me'),
}

// ── Medicines ─────────────────────────────────────────────────
export const medicinesAPI = {
  list:       (params) => api.get('/medicines', { params }),
  categories: ()       => api.get('/medicines/categories'),
  get:        (id)     => api.get(`/medicines/${id}`),

  /**
   * Search for a medicine on 1mg when it is not found locally.
   * The backend scrapes, rewrites, inserts, and returns the result.
   * This call can take 15–45 seconds.
   *
   * @param {string} q - Medicine name to search (min 2 chars).
   * @returns {Promise<{source: string, medicine: object}>}
   */
  fetchOnline: (q) => api.post('/medicines/fetch-online', { q }, { timeout: 60_000 }),
}

// ── Cart ─────────────────────────────────────────────────────
export const cartAPI = {
  get:    ()                     => api.get('/cart'),
  add:    (variant_id, quantity) => api.post('/cart/add', { variant_id, quantity }),
  update: (item_id, quantity)    => api.put(`/cart/${item_id}`, { quantity }),
  remove: (item_id)              => api.delete(`/cart/${item_id}`),
  clear:  ()                     => api.delete('/cart'),
}

// ── Addresses ────────────────────────────────────────────────
export const addressesAPI = {
  list:   ()        => api.get('/addresses'),
  add:    (data)    => api.post('/addresses', data),
  update: (id, data)=> api.put(`/addresses/${id}`, data),
  remove: (id)      => api.delete(`/addresses/${id}`),
}

// ── Orders ───────────────────────────────────────────────────
export const ordersAPI = {
  list:    ()       => api.get('/orders'),
  get:     (id)     => api.get(`/orders/${id}`),
  place:   (data)   => api.post('/orders', data),

  /**
   * Upload a prescription image before placing an Rx order.
   * Returns { url: "/uploads/rx_..." } for use in the order payload.
   *
   * @param {File} file - Image file to upload.
   * @returns {Promise<{url: string}>}
   */
  uploadPrescription: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/orders/upload-prescription', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  /** Returns a URL for the invoice PDF using the ?token= query param so it can be used in <a href>. */
  invoice: (id) => {
    const token = localStorage.getItem('mathurapharmeasy_token')
    return `/api/orders/${id}/invoice${token ? `?token=${token}` : ''}`
  },

  /** Authenticated PDF download — returns a blob URL for the invoice. */
  downloadInvoice: async (orderId, orderNumber) => {
    const token = localStorage.getItem('mathurapharmeasy_token')
    const res   = await fetch(`/api/orders/${orderId}/invoice`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) throw new Error('Invoice not available')
    const blob    = await res.blob()
    const url     = URL.createObjectURL(blob)
    const anchor  = document.createElement('a')
    anchor.href     = url
    anchor.download = `Invoice-${orderNumber}.pdf`
    anchor.click()
    URL.revokeObjectURL(url)
  },
}

// ── Delivery ETA ──────────────────────────────────────────────
export const deliveryAPI = {
  /**
   * Get delivery ETA from the customer's GPS coordinates (browser geolocation).
   * Public endpoint — no auth required.
   *
   * @param {number} lat - Latitude (WGS-84 decimal degrees).
   * @param {number} lng - Longitude (WGS-84 decimal degrees).
   * @returns {Promise<DeliveryETA>}
   */
  etaByCoords: (lat, lng) => api.get('/delivery/eta', { params: { lat, lng } }),

  /**
   * Get delivery ETA for a 6-digit Indian PIN code.
   * Public endpoint — no auth required.
   *
   * @param {string} pin - 6-digit Indian PIN code.
   * @returns {Promise<DeliveryETA>}
   *
   * @typedef {object} DeliveryETA
   * @property {string}  city
   * @property {string}  state
   * @property {string}  pincode
   * @property {number}  distance_km
   * @property {number}  min_days
   * @property {number}  max_days
   * @property {string}  label
   * @property {string}  estimated_delivery_date
   * @property {string}  message
   * @property {boolean} cod_available
   */
  etaByPin: (pin) => api.get('/delivery/check', { params: { pin } }),
}

// ── Payment ──────────────────────────────────────────────────
export const paymentAPI = {
  createOrder: (amount)  => api.post('/payment/create-order', { amount }),
  verify:      (data)    => api.post('/payment/verify', data),
  refund:      (data)    => api.post('/payment/refund', data),
}

// ── Admin ────────────────────────────────────────────────────
export const adminAPI = {
  stats:              ()              => api.get('/admin/stats'),
  orders:             ()              => api.get('/admin/orders'),
  updateStatus:       (id, status)    => api.put(`/admin/orders/${id}/status`, { status }),
  medicines:          ()              => api.get('/admin/medicines'),
  getMedicine:        (id)            => api.get(`/admin/medicines/${id}`),
  categories:         ()              => api.get('/admin/categories'),
  addMedicine:        (formData)      => api.post('/admin/medicines', formData, { headers: { 'Content-Type': 'multipart/form-data' }}),
  updateMedicine:     (id, fd)        => api.put(`/admin/medicines/${id}`, fd, { headers: { 'Content-Type': 'multipart/form-data' }}),
  deleteMedicine:     (id)            => api.delete(`/admin/medicines/${id}`),

  // Generic alternatives management
  alternatives:       ()              => api.get('/admin/alternatives'),
  addAlternative:     (src, alt)      => api.post('/admin/alternatives', { source_medicine_id: src, alternative_medicine_id: alt }),
  toggleAlternative:  (id, isActive)  => api.put(`/admin/alternatives/${id}`, { is_active: isActive }),
  deleteAlternative:  (id)            => api.delete(`/admin/alternatives/${id}`),
}
