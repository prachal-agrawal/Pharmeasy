import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ShoppingCart, Star, AlertTriangle, Shield, ChevronLeft, ChevronRight, TrendingDown, Check, Pill, Truck, Loader2, MapPin } from 'lucide-react'
import { medicinesAPI, deliveryAPI } from '../utils/api'
import { useCart } from '../context/CartContext'
import toast from 'react-hot-toast'
import MedicineImage from '../components/MedicineImage'
import MedicineImagePlaceholder from '../components/MedicineImagePlaceholder'

// ─── Sidebar Alternatives Panel ────────────────────────────────────────────
// Compact left-column panel rendered BELOW the product image.
// Shows:
//   1. A highlighted card for the single cheapest alternative
//   2. A scrollable list of ALL alternatives sorted cheapest-first

function SidebarAlternatives({ current, alternatives, onAddAlt }) {
  if (!alternatives?.length) return null

  const cheapest    = alternatives[0]
  const srcVar      = current.variants?.find(v => v.stock > 0) || current.variants?.[0]
  const cheapestVar = cheapest.variants?.find(v => v.stock > 0) || cheapest.variants?.[0]
  const maxSavings  = cheapest.savings_pct || 0

  return (
    <div className="space-y-3">

      {/* ── Section header ── */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center shrink-0">
            <TrendingDown className="w-3.5 h-3.5 text-green-600" />
          </div>
          <p className="text-sm font-extrabold text-gray-800">
            {alternatives.length} Generic Alternative{alternatives.length > 1 ? 's' : ''}
          </p>
        </div>
        {maxSavings > 0 && (
          <span className="bg-green-600 text-white text-[10px] font-extrabold px-2 py-0.5 rounded-full">
            Save {maxSavings}%
          </span>
        )}
      </div>

      {/* ── Cheapest alternative highlight card ── */}
      <div className="rounded-xl border border-green-200 overflow-hidden shadow-sm">
        <div className="bg-green-600 px-3 py-1.5 flex items-center gap-1.5">
          <Check className="w-3 h-3 text-white shrink-0" />
          <span className="text-[10px] font-extrabold text-white uppercase tracking-wide">Cheapest Alternative</span>
          {maxSavings > 0 && (
            <span className="ml-auto text-[10px] font-bold text-green-200">⭐ {maxSavings}% lower</span>
          )}
        </div>
        <div className="p-3 flex gap-3 items-start bg-white">
          <div className="w-14 h-14 shrink-0 rounded-lg border border-gray-100 overflow-hidden bg-white">
            <MedicineImage
              name={cheapest.name}
              src={cheapest.image_url}
              className="w-full h-full"
              imgClassName="w-full h-full object-contain p-1"
              placeholderSize="lg"
            />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-extrabold text-gray-800 leading-tight line-clamp-2 mb-0.5">{cheapest.name}</p>
            <p className="text-[10px] text-gray-400 mb-1">{cheapest.brand}</p>
            {cheapest.salt_composition && (
              <div className="flex items-center gap-0.5 text-[9px] text-gray-400 mb-2">
                <Pill className="w-2.5 h-2.5 shrink-0" />
                <span className="line-clamp-1">{cheapest.salt_composition}</span>
              </div>
            )}
            <div className="flex items-center justify-between gap-1">
              <div>
                {cheapestVar && (
                  <p className="text-base font-extrabold text-green-700">₹{parseFloat(cheapestVar.price).toFixed(0)}</p>
                )}
                {srcVar && cheapestVar && parseFloat(srcVar.price) > parseFloat(cheapestVar.price) && (
                  <p className="text-[9px] text-gray-400 line-through">was ₹{parseFloat(srcVar.price).toFixed(0)}</p>
                )}
              </div>
              <button
                onClick={() => onAddAlt(cheapest, cheapestVar)}
                className="shrink-0 bg-green-600 hover:bg-green-700 text-white text-[10px] font-extrabold px-3 py-1.5 rounded-lg transition-colors"
              >
                ADD
              </button>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-center gap-1 py-1.5 bg-green-50 border-t border-green-100 text-[9px] text-green-700 font-semibold">
          <Check className="w-2.5 h-2.5" /> Same active ingredient · bioequivalent
        </div>
      </div>

      {/* ── All alternatives list ── */}
      {alternatives.length > 1 && (
        <div className="rounded-xl border border-gray-100 bg-white overflow-hidden shadow-sm">
          <div className="px-3 py-2 border-b border-gray-100 flex items-center gap-1.5 bg-gray-50">
            <TrendingDown className="w-3.5 h-3.5 text-green-600" />
            <span className="text-xs font-bold text-gray-600">
              All {alternatives.length} alternatives — cheapest first
            </span>
          </div>
          <div className="divide-y divide-gray-50 max-h-80 overflow-y-auto">
            {alternatives.map((alt, idx) => {
              const altVar = alt.variants?.find(v => v.stock > 0) || alt.variants?.[0]
              const isIn   = altVar?.stock > 0
              return (
                <div key={alt.id} className="p-3 flex gap-2 items-center hover:bg-green-50/50 transition-colors">
                  {/* Rank badge */}
                  <span className={`shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-extrabold
                    ${idx === 0 ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-500'}`}>
                    {idx + 1}
                  </span>

                  {/* Image */}
                  <div className="w-10 h-10 shrink-0 rounded-lg border border-gray-100 overflow-hidden bg-white">
                    <MedicineImage
                      name={alt.name}
                      src={alt.image_url}
                      className="w-full h-full"
                      imgClassName="w-full h-full object-contain p-0.5"
                      placeholderSize="md"
                    />
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-bold text-gray-800 truncate">{alt.name}</p>
                    <p className="text-[10px] text-gray-400 truncate">{alt.brand}</p>
                    {altVar && (
                      <div className="flex items-center gap-1 mt-0.5">
                        <p className="text-xs font-extrabold text-green-700">₹{parseFloat(altVar.price).toFixed(0)}</p>
                        {alt.savings_pct > 0 && (
                          <span className="text-[9px] font-bold text-green-600 bg-green-50 px-1 rounded-full">
                            {alt.savings_pct}% off
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Add button */}
                  <button
                    onClick={() => onAddAlt(alt, altVar)}
                    disabled={!isIn}
                    className={`shrink-0 text-[10px] font-extrabold px-2.5 py-1.5 rounded-lg transition-colors
                      ${isIn
                        ? 'bg-green-600 hover:bg-green-700 text-white'
                        : 'bg-gray-100 text-gray-400 cursor-not-allowed'}`}
                  >
                    {isIn ? 'ADD' : 'N/A'}
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main ProductDetail Page ─────────────────────────────────────────────────

export default function ProductDetail() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const { addToCart } = useCart()

  const [med,       setMed]       = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [selVar,    setSelVar]    = useState(null)
  const [qty,       setQty]       = useState(1)
  const [adding,    setAdding]    = useState(false)
  const [addingAlt, setAddingAlt] = useState(false)
  const [activeTab, setActiveTab] = useState('about')
  const [zoom,      setZoom]      = useState(false)
  const [zoomPos,   setZoomPos]   = useState({ x: 50, y: 50 })
  const [eta,       setEta]       = useState(null)     // delivery ETA result
  const [etaState,  setEtaState]  = useState('idle')   // idle | loading | done | error
  const [heroImgErr, setHeroImgErr] = useState(false)
  const [heroIdx, setHeroIdx] = useState(0)
  const imgRef = useRef(null)

  /** Ordered gallery URLs from API (`image_urls`) with legacy `image_url` fallback. */
  const galleryUrls = useMemo(() => {
    if (!med) return []
    let raw = med.image_urls
    if (typeof raw === 'string' && raw.trim()) {
      try {
        raw = JSON.parse(raw)
      } catch {
        raw = null
      }
    }
    if (Array.isArray(raw) && raw.length) {
      return raw.map((u) => String(u).trim()).filter(Boolean)
    }
    if (med.image_url) return [med.image_url]
    return []
  }, [med])

  const activeGalleryIdx = galleryUrls.length
    ? Math.min(heroIdx, galleryUrls.length - 1)
    : 0
  const heroSrc = galleryUrls[activeGalleryIdx] ?? null

  const handleMouseMove = (e) => {
    const rect = imgRef.current.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width)  * 100
    const y = ((e.clientY - rect.top)  / rect.height) * 100
    setZoomPos({ x, y })
  }

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await medicinesAPI.get(id)
        setMed(data)
        const first = data.variants.find(v => v.stock > 0) || data.variants[0]
        setSelVar(first)
      } catch { navigate('/') }
      finally { setLoading(false) }
    }
    load()
  }, [id])

  useEffect(() => {
    setHeroIdx(0)
  }, [id])

  useEffect(() => {
    setHeroImgErr(false)
  }, [id, heroSrc])

  // Auto-fetch delivery ETA using GPS on page load (same logic as DeliveryEstimateWidget)
  useEffect(() => {
    if (!navigator.geolocation) { setEtaState('error'); return }
    setEtaState('loading')
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const { data } = await deliveryAPI.etaByCoords(coords.latitude, coords.longitude)
          setEta(data)
          setEtaState('done')
        } catch { setEtaState('error') }
      },
      () => setEtaState('error'),
      { timeout: 10_000, maximumAge: 60_000 }
    )
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleAddToCart = async () => {
    if (!selVar) return
    setAdding(true)
    await addToCart(selVar.id, qty, med.name)
    setAdding(false)
  }

  const handleAddAlt = async (altMed, altVar) => {
    if (!altVar) return toast.error('This alternative is out of stock')
    setAddingAlt(true)
    await addToCart(altVar.id, 1, altMed.name)
    setAddingAlt(false)
  }

  if (loading) return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-pulse">
      <div className="grid md:grid-cols-2 gap-8">
        <div className="bg-gray-100 rounded-2xl h-80" />
        <div className="space-y-4">
          <div className="h-6 bg-gray-100 rounded w-3/4" />
          <div className="h-4 bg-gray-100 rounded w-1/2" />
          <div className="h-20 bg-gray-100 rounded" />
        </div>
      </div>
    </div>
  )

  if (!med) return null

  const FLAT_DISCOUNT_PCT = 15
  const discount = selVar && selVar.mrp > selVar.price
    ? Math.round((1 - selVar.price / selVar.mrp) * 100) : 0
  // Label shown on discount badge — shows exact % (always 15 when using flat discount)
  const discountLabel = discount === FLAT_DISCOUNT_PCT ? `${FLAT_DISCOUNT_PCT}% off MRP` : `${discount}% off`

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 page-enter">
      {/* Breadcrumb */}
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-brand mb-4 transition-colors">
        <ChevronLeft className="w-4 h-4" /> Back to catalog
      </button>

      <div className="grid md:grid-cols-5 gap-6">
        {/* Left — Image + Generic Alternatives */}
        <div className="md:col-span-2 space-y-4">
          <div className="card p-4 flex flex-col items-center sticky top-20">
            {heroSrc && !heroImgErr ? (
              <>
                {/* Thumbnail with lens indicator */}
                <div
                  ref={imgRef}
                  className="relative w-full rounded-xl mb-3 cursor-crosshair select-none"
                  onMouseEnter={() => setZoom(true)}
                  onMouseLeave={() => setZoom(false)}
                  onMouseMove={handleMouseMove}
                >
                  <img
                    src={heroSrc}
                    alt={med.name}
                    className="w-full max-h-64 object-contain rounded-xl"
                    onError={() => setHeroImgErr(true)}
                    draggable={false}
                  />

                  {zoom && (
                    <div
                      className="absolute border-2 border-brand bg-brand/10 pointer-events-none rounded"
                      style={{
                        width: 80,
                        height: 80,
                        left: `calc(${zoomPos.x}% - 40px)`,
                        top:  `calc(${zoomPos.y}% - 40px)`,
                      }}
                    />
                  )}

                  {!zoom && (
                    <div className="absolute bottom-2 right-2 bg-black/40 text-white text-[10px] px-2 py-0.5 rounded-full">
                      🔍 Hover to zoom
                    </div>
                  )}
                </div>

                {galleryUrls.length > 1 && (
                  <div className="flex items-center justify-center gap-3 mb-2 w-full">
                    <button
                      type="button"
                      aria-label="Previous product image"
                      onClick={() => {
                        setHeroIdx((i) => (i - 1 + galleryUrls.length) % galleryUrls.length)
                        setHeroImgErr(false)
                      }}
                      className="p-1.5 rounded-full border border-gray-200 bg-white shadow-sm hover:bg-gray-50 text-gray-600"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-[11px] font-semibold text-gray-500 tabular-nums min-w-[3rem] text-center">
                      {activeGalleryIdx + 1} / {galleryUrls.length}
                    </span>
                    <button
                      type="button"
                      aria-label="Next product image"
                      onClick={() => {
                        setHeroIdx((i) => (i + 1) % galleryUrls.length)
                        setHeroImgErr(false)
                      }}
                      className="p-1.5 rounded-full border border-gray-200 bg-white shadow-sm hover:bg-gray-50 text-gray-600"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                )}

                {galleryUrls.length > 1 && (
                  <div className="flex gap-2 justify-center flex-wrap w-full mb-3 px-1">
                    {galleryUrls.map((url, i) => (
                      <button
                        key={`${url}-${i}`}
                        type="button"
                        aria-label={`Show product image ${i + 1}`}
                        onClick={() => {
                          setHeroIdx(i)
                          setHeroImgErr(false)
                        }}
                        className={`w-14 h-14 rounded-lg border-2 overflow-hidden bg-white shrink-0 transition-all ${
                          i === activeGalleryIdx
                            ? 'border-brand ring-2 ring-brand/25 shadow-sm'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <img src={url} alt="" className="w-full h-full object-contain p-0.5" />
                      </button>
                    ))}
                  </div>
                )}

                {/* Full-screen zoom overlay */}
                {zoom && (
                  <div
                    className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
                    style={{ background: 'rgba(0,0,0,0.55)' }}
                  >
                    <div className="bg-white rounded-2xl shadow-2xl overflow-hidden flex items-center justify-center"
                      style={{ width: 480, height: 480 }}
                    >
                      <img
                        src={heroSrc}
                        alt={med.name}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'contain',
                          transformOrigin: `${zoomPos.x}% ${zoomPos.y}%`,
                          transform: 'scale(2.5)',
                          transition: 'transform-origin 0.05s linear',
                        }}
                        draggable={false}
                        onError={() => setHeroImgErr(true)}
                      />
                    </div>
                    <div className="absolute bottom-8 text-white/70 text-sm">Move mouse on image to explore</div>
                  </div>
                )}
              </>
            ) : (
              <MedicineImagePlaceholder
                name={med.name}
                size="xl"
                className="w-full min-h-56 rounded-xl mb-4"
              />
            )}

            <span className={`${med.requires_rx ? 'badge-rx' : 'badge-otc'} mb-2`}>
              {med.requires_rx ? 'Prescription Required' : 'Over the Counter'}
            </span>
            {med.rating > 0 && (
              <div className="flex items-center gap-2 mt-1">
                <span className="bg-green-600 text-white text-xs font-bold px-2 py-0.5 rounded flex items-center gap-1">
                  <Star className="w-3 h-3 fill-white" /> {parseFloat(med.rating).toFixed(1)}
                </span>
                <span className="text-xs text-gray-400">{med.rating_count} ratings & reviews</span>
              </div>
            )}

          </div>

          {/* Alternatives panel — below the sticky image card */}
          {med.generic_alternatives?.length > 0 && (
            <SidebarAlternatives
              current={med}
              alternatives={med.generic_alternatives}
              onAddAlt={handleAddAlt}
            />
          )}
        </div>

        {/* Right — Details */}
        <div className="md:col-span-3 space-y-5">
          <div>
            <p className="text-xs text-brand font-semibold uppercase tracking-wide mb-1">{med.category_name}</p>
            <h1 className="text-xl font-extrabold leading-snug mb-1">{med.name}</h1>
            <p className="text-sm text-gray-500">{med.brand}</p>
            {med.salt_composition && (
              <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
                <Pill className="w-3 h-3" /> {med.salt_composition}
              </p>
            )}
          </div>

          {/* ── Pack Size Selector ── */}
          {med.variants.length > 0 && (
            <div>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">
                Pack Size ({med.variants.length})
              </p>
              <div className="grid grid-cols-3 gap-2">
                {med.variants.map(v => (
                  <button
                    key={v.id}
                    onClick={() => setSelVar(v)}
                    className={`border-2 rounded-lg p-2.5 text-left transition-all ${
                      selVar?.id === v.id
                        ? 'border-brand bg-brand-light'
                        : 'border-gray-200 hover:border-brand/50'
                    } ${v.stock === 0 ? 'opacity-40 cursor-not-allowed' : ''}`}
                    disabled={v.stock === 0}
                  >
                    <p className="text-xs font-bold text-gray-700">{v.label}</p>
                    <p className="text-sm font-extrabold text-brand mt-0.5">₹{parseFloat(v.price).toFixed(0)}</p>
                    {v.mrp > v.price ? (
                      <div className="flex items-center gap-1 mt-0.5">
                        <p className="text-[10px] text-gray-400 line-through">₹{parseFloat(v.mrp).toFixed(2)}</p>
                        <span className="text-[9px] font-extrabold text-green-600 bg-green-50 px-1 rounded">
                          {Math.round((1 - v.price / v.mrp) * 100)}% off
                        </span>
                      </div>
                    ) : null}
                    <p className="text-[10px] mt-0.5" style={{ color: v.stock > 0 ? '#0F6E56' : '#A32D2D' }}>
                      {v.stock > 0 ? `${v.stock} left` : 'Out of stock'}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Price + discount */}
          {selVar && (
            <div>
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-extrabold text-brand">₹{parseFloat(selVar.price).toFixed(0)}</span>
                {selVar.mrp > selVar.price && (
                  <>
                    <span className="text-base text-gray-400 line-through">MRP ₹{parseFloat(selVar.mrp).toFixed(2)}</span>
                    <span className="bg-green-600 text-white text-xs font-extrabold px-2 py-0.5 rounded-full">
                      {discountLabel}
                    </span>
                  </>
                )}
              </div>
              {selVar.mrp > selVar.price && (
                <p className="text-[11px] text-green-700 font-semibold mt-0.5">
                  You save ₹{(parseFloat(selVar.mrp) - parseFloat(selVar.price)).toFixed(2)} on this item
                </p>
              )}
            </div>
          )}

          {/* Quantity + Add to cart */}
          <div className="flex items-center gap-3">
            <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
              <button onClick={() => setQty(q => Math.max(1, q-1))}
                className="px-3 py-2 hover:bg-gray-50 font-bold text-lg transition-colors">−</button>
              <span className="px-4 py-2 font-bold border-x border-gray-200">{qty}</span>
              <button onClick={() => setQty(q => Math.min(selVar?.stock || 99, q+1))}
                className="px-3 py-2 hover:bg-gray-50 font-bold text-lg transition-colors">+</button>
            </div>
            <button
              onClick={handleAddToCart}
              disabled={!selVar || selVar.stock === 0 || adding}
              className="flex-1 btn-primary flex items-center justify-center gap-2 py-3"
            >
              <ShoppingCart className="w-4 h-4" />
              {adding ? 'Adding...' : selVar?.stock === 0 ? 'Out of Stock' : 'Add to Cart'}
            </button>
          </div>

          {/* ── Delivery ETA strip ── */}
          <div className="rounded-xl border border-gray-100 bg-gray-50/70 px-4 py-3">
            {etaState === 'loading' && (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                Estimating delivery to your location…
              </div>
            )}
            {etaState === 'done' && eta && (
              <div className="flex items-start gap-2">
                <Truck className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-brand leading-snug">{eta.label} · by {eta.estimated_delivery_date}</p>
                  <p className="text-[11px] text-gray-500 mt-0.5 leading-snug">
                    {eta.city ? `To ${eta.city}${eta.state ? `, ${eta.state}` : ''}` : 'To your location'}
                    {eta.distance_km > 0 && <span className="ml-1 text-gray-400">(~{eta.distance_km} km from store)</span>}
                  </p>
                </div>
              </div>
            )}
            {(etaState === 'error' || etaState === 'idle') && (
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                <span>
                  Delivery available · <span className="font-medium">2–7 days</span> depending on location
                </span>
              </div>
            )}
          </div>

          {/* Highlights */}
          <div className="grid grid-cols-3 gap-3 py-3 border-y border-gray-100">
            {[
              {
                icon: <Truck className="w-4 h-4 text-amber-500" />,
                label: 'Fast Delivery',
                sub: etaState === 'done' && eta ? eta.label : '2–7 days',
              },
              { icon: <Shield className="w-4 h-4 text-brand" />, label: 'Genuine', sub: '100% authentic' },
              { icon: <ShoppingCart className="w-4 h-4 text-info" />, label: 'Easy Returns', sub: '7-day policy' },
            ].map((h, i) => (
              <div key={i} className="flex flex-col items-center text-center gap-1">
                {h.icon}
                <p className="text-xs font-bold">{h.label}</p>
                <p className="text-[10px] text-gray-400">{h.sub}</p>
              </div>
            ))}
          </div>

          {/* Tabbed info */}
          <div>
            <div className="flex border-b border-gray-100 mb-4 overflow-x-auto">
              {[
                { key: 'about',       label: 'About',        show: !!med.description },
                { key: 'uses',        label: 'Uses',         show: true },
                { key: 'side_effects',label: 'Side Effects', show: true },
                { key: 'safety',      label: 'Safety',       show: true },
              ].filter(t => t.show).map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`shrink-0 px-4 py-2 text-xs font-bold border-b-2 transition-colors ${
                    activeTab === tab.key
                      ? 'border-brand text-brand'
                      : 'border-transparent text-gray-400 hover:text-gray-600'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'about' && (
              <div className="space-y-3">
                {med.description ? (
                  <p className="text-sm text-gray-700 leading-relaxed">{med.description}</p>
                ) : (
                  <p className="text-sm text-gray-400 italic">No product introduction available.</p>
                )}
                {/* Manufacturer / salt summary below intro */}
                <div className="grid grid-cols-2 gap-3 mt-4">
                  {med.salt_composition && (
                    <div className="bg-gray-50 rounded-xl p-3">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Salt Composition</p>
                      <p className="text-xs text-gray-700 font-medium">{med.salt_composition}</p>
                    </div>
                  )}
                  {med.manufacturer && (
                    <div className="bg-gray-50 rounded-xl p-3">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Manufacturer</p>
                      <p className="text-xs text-gray-700 font-medium">{med.manufacturer}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'uses' && (
              <p className="text-sm text-gray-600 leading-relaxed">{med.uses || 'Not specified.'}</p>
            )}

            {activeTab === 'side_effects' && (
              <ul className="space-y-2">
                {(med.side_effects || []).length > 0
                  ? (med.side_effects || []).map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="w-1.5 h-1.5 rounded-full bg-danger mt-2 shrink-0" />
                        {s}
                      </li>
                    ))
                  : <p className="text-sm text-gray-400 italic">No side effects listed.</p>
                }
              </ul>
            )}

            {activeTab === 'safety' && (
              <>
                <ul className="space-y-2 mb-4">
                  {(med.safety_points || []).length > 0
                    ? (med.safety_points || []).map((s, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <span className="w-1.5 h-1.5 rounded-full bg-brand mt-2 shrink-0" />
                          {s}
                        </li>
                      ))
                    : <p className="text-sm text-gray-400 italic mb-4">No safety points listed.</p>
                  }
                </ul>
                {med.warning && (
                  <div className="bg-danger-light border-l-4 border-danger rounded-r-lg p-3 flex gap-2">
                    <AlertTriangle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
                    <p className="text-xs text-danger leading-relaxed">{med.warning}</p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

    </div>
  )
}
