import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapPin, CreditCard, CheckCircle, Plus, FileText, Upload, X, ImagePlus, Truck } from 'lucide-react'
import { addressesAPI, ordersAPI } from '../utils/api'
import DeliveryEstimateWidget from '../components/DeliveryEstimateWidget'
import { initiateRazorpayPayment } from '../utils/razorpay'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

const STEPS = ['Address', 'Payment', 'Review']

export default function Checkout() {
  const navigate = useNavigate()
  const { items, totals, clearCart, loading: cartLoading } = useCart()
  const { subtotal: cartSubtotal, canCheckout } = totals
  const { user } = useAuth()

  const [step,      setStep]      = useState(0)
  const [addresses, setAddresses] = useState([])
  const [selAddr,   setSelAddr]   = useState(null)
  const [placing,   setPlacing]   = useState(false)
  const [showForm,  setShowForm]  = useState(false)
  const [success,   setSuccess]   = useState(null)

  // New address form
  const [newAddr, setNewAddr] = useState({ label:'Home', name:'', phone:'', line1:'', line2:'', city:'', state:'Uttar Pradesh', pin:'' })

  // Prescription upload — supports multiple files
  const rxRequired = items.some(i => i.requires_rx)
  const [rxFiles,     setRxFiles]     = useState([])   // File[]
  const [rxPreviews,  setRxPreviews]  = useState([])   // blob URLs[]
  const [rxUrls,      setRxUrls]      = useState([])   // server URLs[] (null = not yet uploaded)
  const [uploadingRx, setUploadingRx] = useState(false)
  const rxRef = useRef()

  const handleRxFiles = (e) => {
    const selected = Array.from(e.target.files)
    if (!selected.length) return
    setRxFiles(prev    => [...prev, ...selected])
    setRxPreviews(prev => [...prev, ...selected.map(f => URL.createObjectURL(f))])
    setRxUrls(prev     => [...prev, ...selected.map(() => null)])
    e.target.value = ''  // allow re-selecting the same file
  }

  const removeRxFile = (i) => {
    setRxFiles(prev    => prev.filter((_, idx) => idx !== i))
    setRxPreviews(prev => prev.filter((_, idx) => idx !== i))
    setRxUrls(prev     => prev.filter((_, idx) => idx !== i))
  }

  // Upload all pending (not-yet-uploaded) files in parallel and return the full URL list
  const uploadAllRx = async () => {
    setUploadingRx(true)
    try {
      const results = await Promise.all(
        rxFiles.map((file, i) =>
          rxUrls[i]
            ? Promise.resolve(rxUrls[i])
            : ordersAPI.uploadPrescription(file).then(r => r.data.url)
        )
      )
      setRxUrls(results)
      toast.success(`${results.length} prescription${results.length > 1 ? 's' : ''} uploaded`)
      return results
    } catch {
      toast.error('Failed to upload one or more prescriptions. Please try again.')
      return null
    } finally {
      setUploadingRx(false)
    }
  }

  useEffect(() => {
    if (cartLoading) return
    if (!items.length) {
      navigate('/cart')
      return
    }
    if (!canCheckout || cartSubtotal < 500) {
      toast.error('Minimum order value is ₹500')
      navigate('/cart')
      return
    }
    fetchAddresses()
  }, [cartLoading, items.length, canCheckout, cartSubtotal, navigate])

  const fetchAddresses = async () => {
    const { data } = await addressesAPI.list()
    setAddresses(data)
    if (data.length) setSelAddr(data.find(a => a.is_default) || data[0])
  }

  const saveNewAddress = async () => {
    if (!newAddr.name || !newAddr.line1 || !newAddr.city || !newAddr.pin || !newAddr.phone)
      return toast.error('Fill all required fields including phone number')
    const { data } = await addressesAPI.add(newAddr)
    await fetchAddresses()
    setShowForm(false)
    toast.success('Address saved')
  }

  // ── Razorpay only (UPI, cards, netbanking inside Razorpay checkout) ──
  const placeOnlineOrder = (rxUrlList) => {
    setPlacing(true)
    initiateRazorpayPayment({
      amount: totals.total,
      orderPayload: {
        address_id:        selAddr.id,
        payment_method:    'razorpay',
        items:             items.map(i => ({ variant_id: i.variant_id, quantity: i.quantity })),
        prescription_urls: rxUrlList?.length ? rxUrlList : null,
      },
      userInfo: { name: user?.name, email: user?.email, phone: selAddr?.phone },
      onSuccess: async (order) => {
        await clearCart()
        setSuccess(order)
        setPlacing(false)
      },
      onFailure: () => setPlacing(false),
    })
  }

  const handlePlaceOrder = async () => {
    if (!selAddr) return toast.error('Please select a delivery address')

    let finalUrls = rxUrls.filter(Boolean)

    if (rxRequired) {
      if (rxFiles.length === 0) {
        return toast.error('Please upload at least one prescription — one or more medicines require it')
      }
      // Upload any files that haven't been uploaded yet
      const hasPending = rxFiles.some((_, i) => !rxUrls[i])
      if (hasPending) {
        const uploaded = await uploadAllRx()
        if (!uploaded) return   // upload failed, error already shown
        finalUrls = uploaded
      }
    }

    placeOnlineOrder(finalUrls)
  }

  if (cartLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center text-gray-500 text-sm">Loading checkout…</div>
    )
  }

  // ── Success screen ────────────────────────────────────────
  if (success) return (
    <div className="max-w-lg mx-auto px-4 py-16 text-center page-enter">
      <div className="card p-8">
        <div className="w-16 h-16 bg-brand-light rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-8 h-8 text-brand" />
        </div>
        <h2 className="text-xl font-extrabold text-brand mb-2">Order Placed!</h2>
        <p className="text-gray-500 text-sm mb-1">Order <strong className="text-gray-700">{success.order_number}</strong></p>
        <p className="text-gray-500 text-sm mb-1">Estimated delivery: 3–5 business days to {selAddr?.city}</p>
        <div className="bg-gray-50 rounded-xl p-4 text-left mb-6">
          <p className="text-xs text-gray-400 mb-1">Amount paid (Razorpay)</p>
          <p className="text-2xl font-extrabold text-brand">₹{parseFloat(success.total).toFixed(0)}</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => navigate('/orders')} className="flex-1 btn-primary">Track Order</button>
          <button
            onClick={async () => {
              try {
                await ordersAPI.downloadInvoice(success.order_id, success.order_number)
              } catch {
                alert('Invoice not ready yet. Download it from My Orders.')
              }
            }}
            className="flex-1 btn-outline text-center py-2 rounded-md font-semibold text-sm"
          >
            📄 Download Invoice
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 page-enter">
      <h1 className="text-xl font-extrabold mb-6">Checkout</h1>

      {/* Step bar */}
      <div className="flex mb-8">
        {STEPS.map((s, i) => (
          <div key={s} className="flex items-center">
            <div className={`flex items-center gap-2 text-sm font-bold ${i === step ? 'text-brand' : i < step ? 'text-brand/60' : 'text-gray-300'}`}>
              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-extrabold border-2 ${
                i < step ? 'bg-brand border-brand text-white' : i === step ? 'border-brand text-brand' : 'border-gray-200 text-gray-300'
              }`}>{i < step ? '✓' : i+1}</span>
              {s}
            </div>
            {i < STEPS.length - 1 && <div className={`w-12 h-0.5 mx-2 ${i < step ? 'bg-brand' : 'bg-gray-200'}`} />}
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2">

          {/* STEP 0 — ADDRESS */}
          {step === 0 && (
            <div className="space-y-3">
              <h2 className="font-bold text-base flex items-center gap-2"><MapPin className="w-4 h-4 text-brand" /> Delivery Address</h2>
              {addresses.map(a => (
                <div key={a.id} className={`card p-4 transition-all ${selAddr?.id===a.id ? 'border-brand ring-1 ring-brand' : ''}`}>
                  <label className="flex gap-3 cursor-pointer">
                    <input type="radio" name="addr" checked={selAddr?.id===a.id} onChange={() => setSelAddr(a)} className="mt-1 accent-brand" />
                    <div className="flex-1">
                      <p className="font-bold text-sm">{a.name} <span className="text-[10px] bg-brand-light text-brand px-2 py-0.5 rounded-full ml-1">{a.label}</span></p>
                      <p className="text-xs text-gray-500 mt-1 leading-relaxed">{a.line1}{a.line2 ? ', '+a.line2 : ''}, {a.city}, {a.state} - {a.pin}</p>
                      {a.phone && <p className="text-xs text-gray-400 mt-0.5">📞 {a.phone}</p>}
                    </div>
                  </label>
                  {/* Show delivery estimate inline when this address is selected */}
                  {selAddr?.id === a.id && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-[10px] font-bold text-gray-400 uppercase mb-1.5 flex items-center gap-1">
                        <Truck className="w-3 h-3" /> Delivery Estimate
                      </p>
                      <DeliveryEstimateWidget pin={a.pin} compact={false} />
                    </div>
                  )}
                </div>
              ))}

              {/* Add new address */}
              <button onClick={() => setShowForm(v => !v)}
                className="w-full border-2 border-dashed border-gray-200 rounded-xl p-4 flex items-center justify-center gap-2 text-sm text-gray-400 hover:border-brand hover:text-brand transition-colors">
                <Plus className="w-4 h-4" /> Add New Address
              </button>

              {showForm && (
                <div className="card p-5 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">Full Name *</label>
                      <input className="input-field" value={newAddr.name} onChange={e => setNewAddr(p => ({...p, name: e.target.value}))} placeholder="Your full name" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">Phone *</label>
                      <input className="input-field" required value={newAddr.phone} onChange={e => setNewAddr(p => ({...p, phone: e.target.value}))} placeholder="10-digit mobile" pattern="[0-9+\s\-]{7,15}" title="Enter a valid mobile number" />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-gray-500 block mb-1">Address Line 1 *</label>
                    <input className="input-field" value={newAddr.line1} onChange={e => setNewAddr(p => ({...p, line1: e.target.value}))} placeholder="House no, Street, Area" />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-gray-500 block mb-1">Address Line 2</label>
                    <input className="input-field" value={newAddr.line2} onChange={e => setNewAddr(p => ({...p, line2: e.target.value}))} placeholder="Landmark (optional)" />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">City *</label>
                      <input className="input-field" value={newAddr.city} onChange={e => setNewAddr(p => ({...p, city: e.target.value}))} placeholder="City" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">PIN *</label>
                      <input className="input-field" value={newAddr.pin} onChange={e => setNewAddr(p => ({...p, pin: e.target.value}))} placeholder="6 digits" maxLength={6} />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">State</label>
                      <select className="input-field" value={newAddr.state} onChange={e => setNewAddr(p => ({...p, state: e.target.value}))}>
                        {['Uttar Pradesh','Delhi','Maharashtra','Karnataka','Tamil Nadu','Rajasthan','Haryana','Punjab','Bihar','Gujarat','West Bengal','Madhya Pradesh'].map(s => <option key={s}>{s}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-gray-500 block mb-1">Label</label>
                      <select className="input-field" value={newAddr.label} onChange={e => setNewAddr(p => ({...p, label: e.target.value}))}>
                        {['Home','Office','Other'].map(l => <option key={l}>{l}</option>)}
                      </select>
                    </div>
                  </div>
                  <button onClick={saveNewAddress} className="btn-primary w-full py-2.5">Save Address</button>
                </div>
              )}

              {/* Prescription upload — shown only when cart has Rx medicines */}
              {rxRequired && (
                <div className="card p-5 border-2 border-amber-200 bg-amber-50 space-y-3">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-amber-600 shrink-0" />
                    <div>
                      <p className="font-bold text-sm text-amber-800">Prescription Required</p>
                      <p className="text-xs text-amber-600">
                        Upload one or more photos/scans of your doctor's prescription.
                        Multiple pages? Add each as a separate image.
                      </p>
                    </div>
                  </div>

                  {/* Thumbnail grid of selected prescriptions */}
                  {rxFiles.length > 0 && (
                    <div className="grid grid-cols-3 gap-2">
                      {rxFiles.map((file, i) => (
                        <div key={i} className="relative group">
                          <img
                            src={rxPreviews[i]}
                            alt={`Prescription ${i + 1}`}
                            className="w-full h-24 object-cover rounded-xl border-2 border-amber-200 bg-white"
                          />
                          {/* Upload status badge */}
                          <span className={`absolute top-1.5 left-1.5 text-[9px] font-extrabold px-1.5 py-0.5 rounded-full ${
                            rxUrls[i] ? 'bg-green-500 text-white' : 'bg-amber-400 text-white'
                          }`}>
                            {rxUrls[i] ? '✓' : `${i + 1}`}
                          </span>
                          {/* Remove button */}
                          <button
                            onClick={() => removeRxFile(i)}
                            className="absolute top-1 right-1 w-5 h-5 bg-white rounded-full shadow flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            <X className="w-3 h-3 text-red-500" />
                          </button>
                          <p className="text-[9px] text-gray-400 truncate mt-0.5 px-0.5">{file.name}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Upload / Add-more button */}
                  <button
                    type="button"
                    onClick={() => rxRef.current.click()}
                    className={`w-full border-2 border-dashed rounded-xl p-3 flex items-center justify-center gap-2 text-sm transition-colors ${
                      rxFiles.length > 0
                        ? 'border-amber-300 text-amber-600 hover:border-amber-500 hover:bg-amber-100'
                        : 'border-amber-300 rounded-xl p-4 flex-col text-amber-700 hover:border-amber-500 hover:bg-amber-100'
                    }`}
                  >
                    {rxFiles.length > 0 ? (
                      <><ImagePlus className="w-4 h-4" /><span className="font-semibold">Add more prescriptions</span></>
                    ) : (
                      <><Upload className="w-5 h-5" /><span className="font-semibold">Upload Prescription</span><span className="text-xs text-amber-500 block">JPEG, PNG, WebP or GIF · multiple pages supported</span></>
                    )}
                  </button>

                  <input
                    ref={rxRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    multiple
                    className="hidden"
                    onChange={handleRxFiles}
                  />
                </div>
              )}

              <button
                onClick={() => {
                  if (!selAddr) return toast.error('Select an address')
                  if (rxRequired && rxFiles.length === 0)
                    return toast.error('Please upload at least one prescription before continuing')
                  setStep(1)
                }}
                className="w-full btn-primary py-3 mt-2"
              >
                Continue to Payment →
              </button>
            </div>
          )}

          {/* STEP 1 — PAYMENT */}
          {step === 1 && (
            <div className="space-y-3">
              <h2 className="font-bold text-base flex items-center gap-2"><CreditCard className="w-4 h-4 text-brand" /> Payment</h2>

              <div className="card p-5 border-2 border-brand/20 bg-brand-light/20">
                <div className="flex items-start gap-3">
                  <div className="w-12 h-12 rounded-xl bg-white border border-gray-100 flex items-center justify-center shrink-0">
                    <CreditCard className="w-6 h-6 text-brand" />
                  </div>
                  <div>
                    <p className="font-bold text-gray-900">Pay with Razorpay</p>
                    <p className="text-sm text-gray-600 mt-1">
                      UPI, cards, net banking and wallets — all processed securely by Razorpay. Cash on delivery is not available.
                    </p>
                    <p className="text-xs text-gray-500 mt-2">
                      Minimum order ₹500 · Delivery ₹69 (free on orders ₹2000+)
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button onClick={() => setStep(0)} className="btn-outline py-3 px-5">← Back</button>
                <button onClick={() => setStep(2)} className="flex-1 btn-primary py-3">Review Order →</button>
              </div>
            </div>
          )}

          {/* STEP 2 — CONFIRM */}
          {step === 2 && (
            <div className="space-y-4">
              <h2 className="font-bold text-base">Review Your Order</h2>

              <div className="card p-4">
                <p className="text-xs font-bold text-gray-400 uppercase mb-2">Delivery To</p>
                {selAddr && (
                  <div>
                    <p className="font-bold text-sm">{selAddr.name} <span className="text-[10px] bg-brand-light text-brand px-2 py-0.5 rounded-full ml-1">{selAddr.label}</span></p>
                    <p className="text-xs text-gray-500 mt-0.5">{selAddr.line1}, {selAddr.city} - {selAddr.pin}</p>
                    {selAddr.phone && <p className="text-xs text-gray-400">📞 {selAddr.phone}</p>}
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <DeliveryEstimateWidget pin={selAddr.pin} compact />
                    </div>
                  </div>
                )}
              </div>

              <div className="card p-4">
                <p className="text-xs font-bold text-gray-400 uppercase mb-2">Items ({items.length})</p>
                <div className="space-y-2">
                  {items.map(i => (
                    <div key={i.id} className="flex justify-between text-sm">
                      <span className="text-gray-600">{i.name} · {i.label} × {i.quantity}</span>
                      <span className="font-bold">₹{(parseFloat(i.price)*i.quantity).toFixed(0)}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card p-4">
                <p className="text-xs font-bold text-gray-400 uppercase mb-2">Payment</p>
                <p className="text-sm font-medium">Razorpay (UPI / card / net banking)</p>
              </div>

              {rxRequired && (
                <div className="card p-4 border border-amber-200 bg-amber-50">
                  <p className="text-xs font-bold text-amber-600 uppercase mb-2 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    Prescription{rxFiles.length > 1 ? 's' : ''} ({rxFiles.length || 0})
                  </p>
                  {rxFiles.length > 0 ? (
                    <div className="flex gap-2 flex-wrap">
                      {rxPreviews.map((src, i) => (
                        <div key={i} className="relative">
                          <img src={src} alt={`Rx ${i + 1}`}
                            className="w-14 h-14 rounded-lg object-cover border border-amber-300" />
                          {rxUrls[i] && (
                            <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center text-[8px] text-white font-bold">✓</span>
                          )}
                        </div>
                      ))}
                      <p className="w-full text-xs text-green-700 font-semibold mt-1">
                        ✓ {rxFiles.length} prescription{rxFiles.length > 1 ? 's' : ''} attached
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-red-500 font-semibold">⚠ No prescription uploaded — go back to add one</p>
                  )}
                </div>
              )}

              <div className="flex gap-3">
                <button onClick={() => setStep(1)} className="btn-outline py-3 px-5">← Back</button>
                <button
                  onClick={handlePlaceOrder}
                  disabled={placing}
                  className="flex-1 btn-primary py-3 text-base font-extrabold"
                >
                  {placing ? 'Processing...' : `Place Order & Pay ₹${totals.total.toFixed(0)}`}
                </button>
              </div>
              <p className="text-center text-[10px] text-gray-400">🔒 256-bit SSL · PCI-DSS Compliant · Powered by Razorpay</p>
            </div>
          )}
        </div>

        {/* Summary sidebar */}
        <div className="card p-5 sticky top-20">
          <h3 className="font-bold text-sm mb-3 text-brand">Order Summary</h3>
          <div className="space-y-2 text-xs text-gray-500 mb-3">
            {items.map(i => (
              <div key={i.id} className="flex justify-between">
                <span className="truncate mr-2">{i.name} ×{i.quantity}</span>
                <span className="font-medium text-gray-700 shrink-0">₹{(parseFloat(i.price)*i.quantity).toFixed(0)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-gray-100 pt-3 space-y-1.5 text-xs">
            <div className="flex justify-between text-gray-500"><span>Subtotal</span><span>₹{totals.subtotal.toFixed(0)}</span></div>
            <div className="flex justify-between text-gray-500"><span>Delivery</span><span>{totals.delivery===0?'Free':'₹'+totals.delivery}</span></div>
            {totals.discount>0 && <div className="flex justify-between text-brand"><span>Discount</span><span>−₹{totals.discount}</span></div>}
            <div className="flex justify-between font-extrabold text-base pt-1 border-t border-gray-100 text-gray-800">
              <span>Total</span><span className="text-brand">₹{totals.total.toFixed(0)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
