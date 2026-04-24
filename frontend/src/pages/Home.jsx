import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams, useLocation } from 'react-router-dom'
import { SlidersHorizontal, Loader2, CheckCircle, X, GitCompareArrows, Package, Truck } from 'lucide-react'
import { medicinesAPI } from '../utils/api'
import MedicineCard from '../components/MedicineCard'
import MedicineImage from '../components/MedicineImage'
import DeliveryEstimateWidget from '../components/DeliveryEstimateWidget'
import HomePromoCarousel from '../components/HomePromoCarousel'
import toast from 'react-hot-toast'
import { useAuth } from '../context/AuthContext'

export default function Home() {
  const { user }                           = useAuth()
  const displayName                        = user?.name || 'Guest'
  const [searchParams]                     = useSearchParams()
  const location                           = useLocation()
  // Catalog search comes only from the navbar via ?search= (single source of truth)
  const committedSearch                    = (searchParams.get('search') || '').trim()
  const [meds,         setMeds]            = useState([])
  const [cats,         setCats]            = useState([])
  const [loading,      setLoading]         = useState(true)
  const [activeCat,    setActiveCat]       = useState('')
  const [sort,         setSort]            = useState('name')

  // Online-fetch state
  const [fetchingOnline, setFetchingOnline] = useState(false)
  const [fetchedMed,     setFetchedMed]     = useState(null)

  // Comparison state — up to 3 medicines
  const [compareList, setCompareList] = useState([])

  const toggleCompare = useCallback((med) => {
    setCompareList(prev => {
      const exists = prev.find(m => m.id === med.id)
      if (exists) return prev.filter(m => m.id !== med.id)
      if (prev.length >= 3) {
        toast.error('You can compare up to 3 medicines at a time.')
        return prev
      }
      return [...prev, med]
    })
  }, [])

  // Tracks which queries were already auto-fetched this session (avoids duplicate requests)
  const autoFetchedRef = useRef(new Set())

  const fetchCats = async () => {
    const { data } = await medicinesAPI.categories()
    setCats(data)
  }

  const fetchMeds = useCallback(async () => {
    setLoading(true)
    setFetchedMed(null)
    try {
      const { data } = await medicinesAPI.list({
        search:   committedSearch || undefined,
        category: activeCat || undefined,
        sort,
      })
      setMeds(data)
    } catch { setMeds([]) }
    finally { setLoading(false) }
  }, [committedSearch, activeCat, sort])

  // Runs the 1mg scrape, inserts ALL matching medicines (with variants +
  // alternatives), then refreshes the local list so all cards appear in the grid.
  const runOnlineFetch = useCallback(async (q) => {
    setFetchingOnline(true)
    console.group(`[fetch-online] query="${q}"`)
    console.log('▶ Calling POST /api/medicines/fetch-online ...')
    try {
      const { data } = await medicinesAPI.fetchOnline(q)
      console.log(`✓ Response — source="${data.source}"  count=${data.count}`)
      console.table((data.medicines ?? []).map(m => ({ id: m.id, name: m.name, price: m.min_price })))

      // API now returns { source, medicines: [...], count }
      // Gracefully handle old single-medicine shape too ({ medicine: {...} })
      const medicines = data.medicines ?? (data.medicine ? [data.medicine] : [])
      const count     = data.count ?? medicines.length

      if (medicines.length > 0) setFetchedMed(medicines[0])

      const isScraped = data.source === 'scraped' || data.source === 'mixed'
      toast.success(
        count === 1
          ? isScraped
            ? `'${medicines[0].name}' fetched from system and added to catalogue!`
            : `'${medicines[0].name}' found in catalogue.`
          : isScraped
            ? `${count} medicines fetched from system and added to catalogue!`
            : `${count} medicines found in catalogue.`
      )

      // Refresh list so all newly inserted medicines appear in the grid
      console.log('↻ Refreshing medicine list ...')
      const { data: fresh } = await medicinesAPI.list({ search: q })
      console.log(`✓ List refreshed — ${fresh.length} medicine(s) now showing`)
      setMeds(fresh)
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Medicine not found on 1mg. Try a more specific name.'
      console.error('✗ fetch-online error:', err?.response?.data ?? err)
      toast.error(msg)
    } finally {
      console.groupEnd()
      setFetchingOnline(false)
    }
  }, [])

  // When ?search= changes, clear the “added to catalogue” banner
  useEffect(() => {
    setFetchedMed(null)
  }, [committedSearch])

  // Auto-trigger online fetch when local search returns nothing
  useEffect(() => {
    const q = committedSearch.trim()
    if (
      !loading &&
      meds.length === 0 &&
      q.length >= 2 &&
      !fetchingOnline &&
      !autoFetchedRef.current.has(q)
    ) {
      console.log(`[auto-fetch] 0 local results for "${q}" — triggering online fetch`)
      autoFetchedRef.current.add(q)
      runOnlineFetch(q)
    }
  }, [loading, meds.length, committedSearch]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchCats() }, [])
  useEffect(() => { fetchMeds() }, [fetchMeds])

  // Scroll to in-page target when URL hash changes (e.g. promo CTAs: /#home-catalog)
  useEffect(() => {
    const id = (location.hash || '').replace('#', '')
    if (!id) return
    const el = document.getElementById(id)
    if (!el) return
    const t = requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => cancelAnimationFrame(t)
  }, [location.hash, location.pathname])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 page-enter">
      <HomePromoCarousel />

      {/* Delivery Pincode Checker */}
      <div id="home-delivery-check" className="card p-5 mb-5 scroll-mt-24">
        <div className="flex items-center gap-2 mb-3">
          <Truck className="w-4 h-4 text-brand" />
          <h2 className="font-bold text-sm text-gray-700">Check Delivery to Your Location</h2>
        </div>
        <DeliveryEstimateWidget />
      </div>

      <div id="home-how-rx" className="card p-5 mb-5 scroll-mt-24">
        <h2 className="font-bold text-sm text-gray-700 mb-2">How prescriptions work</h2>
        <ol className="text-sm text-gray-600 space-y-1.5 list-decimal list-inside max-w-2xl">
          <li>Add items to your cart. Some require a valid prescription (Rx).</li>
          <li>At checkout, upload a clear photo or PDF of your doctor&apos;s prescription.</li>
          <li>We verify it quickly, then process and deliver your order.</li>
        </ol>
      </div>

      {/* Below-hero: two-column layout — Comparison panel (left) + main content (right) */}
      <div className="flex gap-5 items-start">

        {/* ── Left: Comparison Panel ── */}
        <ComparisonPanel compareList={compareList} onRemove={toggleCompare} onClear={() => setCompareList([])} />

        {/* ── Right: Category pills + Sort + Grid ── */}
        <div id="home-catalog" className="flex-1 min-w-0 scroll-mt-24">
          {/* Category pills */}
          <div className="flex gap-2 flex-wrap mb-4">
            <Pill active={!activeCat} onClick={() => setActiveCat('')}>All</Pill>
            {cats.map(c => (
              <Pill key={c.id} active={activeCat === c.slug} onClick={() => setActiveCat(activeCat === c.slug ? '' : c.slug)}>
                {c.icon} {c.name}
              </Pill>
            ))}
          </div>

          {/* Sort + count */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-gray-500 flex items-center gap-1.5">
              {loading
                ? <><Loader2 className="w-3.5 h-3.5 animate-spin text-brand" />Searching…</>
                : fetchingOnline
                  ? <><Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />Checking system for &quot;{committedSearch}&quot; · {displayName}…</>
                  : fetchedMed
                    ? <><CheckCircle className="w-3.5 h-3.5 text-green-600" /><span className="text-green-700 font-medium">{meds.length === 1 ? `'${fetchedMed.name}' added` : `${meds.length} medicines added`} to catalogue</span></>
                    : null
              }
            </p>
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-gray-400" />
              <select
                value={sort}
                onChange={e => setSort(e.target.value)}
                className="text-sm border border-gray-200 rounded-md px-2 py-1.5 outline-none focus:border-brand bg-white"
              >
                <option value="name">Name A–Z</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
              </select>
            </div>
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {Array(10).fill(0).map((_, i) => (
                <div key={i} className="card animate-pulse h-56">
                  <div className="bg-gray-100 h-36 rounded-t-xl" />
                  <div className="p-3 space-y-2">
                    <div className="h-3 bg-gray-100 rounded w-3/4" />
                    <div className="h-3 bg-gray-100 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : fetchingOnline ? (
            /* ── Auto-fetch in progress ── */
            <div className="flex flex-col items-center justify-center py-20 gap-5">
              <div className="relative">
                <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="text-3xl">💊</span>
                </div>
                <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                  <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
                </div>
              </div>
              <div className="text-center">
                <p className="font-extrabold text-gray-800 text-base">
                  Checking system for &quot;{committedSearch}&quot;
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Hey <span className="font-semibold text-brand">{displayName}</span> · fetching details · adding to catalogue…
                </p>
              </div>
              <div className="flex gap-2 text-[11px] text-gray-400">
                <span className="bg-blue-50 text-blue-600 px-2.5 py-1 rounded-full font-semibold">Variants</span>
                <span className="bg-blue-50 text-blue-600 px-2.5 py-1 rounded-full font-semibold">Alternatives</span>
                <span className="bg-blue-50 text-blue-600 px-2.5 py-1 rounded-full font-semibold">Pricing</span>
              </div>
            </div>
          ) : meds.length === 0 ? (
            /* ── Nothing found even after online fetch ── */
            <div className="text-center py-16 text-gray-400">
              <p className="text-5xl mb-3">🔍</p>
              <p className="font-bold text-gray-600 text-base">No medicines found</p>
              <p className="text-sm mt-1 text-gray-400">
                {committedSearch.length >= 2
                  ? `"${committedSearch}" was not found in our catalogue or on 1mg.`
                  : 'Type a medicine name and press Enter or click Search.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {meds.map(m => (
                <MedicineCard
                  key={m.id}
                  med={m}
                  isCompared={!!compareList.find(c => c.id === m.id)}
                  onCompare={toggleCompare}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
        active ? 'bg-brand text-white border-brand' : 'bg-white text-gray-500 border-gray-200 hover:border-brand hover:text-brand'
      }`}
    >
      {children}
    </button>
  )
}

/** Comparison attribute row shown inside the panel */
function CompareRow({ label, values, highlight }) {
  const nums = values.map(v => parseFloat(v) || 0)
  const best = highlight === 'low' ? Math.min(...nums.filter(n => n > 0)) : Math.max(...nums.filter(n => n > 0))

  return (
    <tr className="border-t border-gray-100">
      <td className="py-2 pr-3 text-[11px] text-gray-500 font-semibold whitespace-nowrap">{label}</td>
      {values.map((val, i) => {
        const n = parseFloat(val) || 0
        const isBest = n > 0 && n === best
        return (
          <td key={i} className={`py-2 px-1 text-center text-[11px] font-bold rounded ${isBest ? 'text-green-700 bg-green-50' : 'text-gray-700'}`}>
            {val || '—'}
          </td>
        )
      })}
      {/* Empty slots */}
      {Array(3 - values.length).fill(0).map((_, i) => (
        <td key={`empty-${i}`} className="py-2 px-1 text-center text-[11px] text-gray-300">—</td>
      ))}
    </tr>
  )
}

/**
 * Left-sidebar comparison panel.
 * Shows up to 3 medicine slots and a comparison table once at least one is added.
 */
function ComparisonPanel({ compareList, onRemove, onClear }) {
  const MAX = 3
  const slots = [...compareList, ...Array(MAX - compareList.length).fill(null)]

  const attr = (med, key) => {
    if (!med) return ''
    switch (key) {
      case 'price':   return med.min_price   ? `₹${parseFloat(med.min_price).toFixed(0)}`   : ''
      case 'mrp':     return med.min_mrp     ? `₹${parseFloat(med.min_mrp).toFixed(0)}`     : ''
      case 'rating':  return med.rating      ? parseFloat(med.rating).toFixed(1)             : ''
      case 'stock':   return med.total_stock ? `${parseFloat(med.total_stock).toFixed(0)}`   : '0'
      case 'rx':      return med.requires_rx ? 'Rx' : 'OTC'
      default:        return ''
    }
  }

  return (
    <aside className="w-64 shrink-0 sticky top-20 self-start">
      {/* Panel card */}
      <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-brand text-white">
          <div className="flex items-center gap-2">
            <GitCompareArrows className="w-4 h-4" />
            <span className="text-sm font-bold">Compare</span>
            <span className="bg-white/20 text-white text-[10px] font-extrabold px-1.5 py-0.5 rounded-full">
              {compareList.length}/{MAX}
            </span>
          </div>
          {compareList.length > 0 && (
            <button
              onClick={onClear}
              className="text-white/70 hover:text-white text-[10px] font-semibold underline underline-offset-2 transition-colors"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Medicine slots */}
        <div className="divide-y divide-gray-100">
          {slots.map((med, i) => (
            <div key={med ? med.id : `slot-${i}`} className="flex items-center gap-2.5 px-3 py-2.5 min-h-[52px]">
              {med ? (
                <>
                  {/* Thumbnail */}
                  <div className="w-9 h-9 shrink-0 rounded-lg overflow-hidden">
                    <MedicineImage
                      name={med.name}
                      src={med.image_url}
                      className="w-full h-full"
                      imgClassName="w-full h-full object-cover"
                      placeholderSize="sm"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-bold text-gray-800 leading-tight line-clamp-2">{med.name}</p>
                    <p className="text-[10px] text-brand font-semibold mt-0.5">₹{parseFloat(med.min_price).toFixed(0)}</p>
                  </div>
                  <button
                    onClick={() => onRemove(med)}
                    className="shrink-0 w-5 h-5 rounded-full bg-gray-100 hover:bg-red-100 hover:text-red-500 flex items-center justify-center transition-colors"
                    aria-label="Remove from comparison"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </>
              ) : (
                <div className="flex items-center gap-2 text-gray-300">
                  <div className="w-9 h-9 rounded-lg border-2 border-dashed border-gray-200 flex items-center justify-center text-lg text-gray-200">+</div>
                  <p className="text-[11px] text-gray-300 italic">Add medicine {i + 1}</p>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Comparison table — only when ≥2 medicines */}
        {compareList.length >= 2 && (
          <div className="border-t border-gray-100 px-3 pb-3 pt-2">
            <p className="text-[10px] font-extrabold text-gray-400 uppercase tracking-wider mb-2">Side-by-side</p>
            <table className="w-full">
              <thead>
                <tr>
                  <th className="text-left text-[10px] text-gray-300 font-normal pb-1 w-16" />
                  {compareList.map(m => (
                    <th key={m.id} className="text-center pb-1">
                      <span className="text-[9px] font-bold text-gray-500 line-clamp-1 block">{m.name.split(' ')[0]}</span>
                    </th>
                  ))}
                  {Array(3 - compareList.length).fill(0).map((_, i) => (
                    <th key={`eh-${i}`} />
                  ))}
                </tr>
              </thead>
              <tbody>
                <CompareRow label="Price"  values={compareList.map(m => attr(m, 'price'))}  highlight="low"  />
                <CompareRow label="MRP"    values={compareList.map(m => attr(m, 'mrp'))}    highlight="low"  />
                <CompareRow label="Rating" values={compareList.map(m => attr(m, 'rating'))} highlight="high" />
                <CompareRow label="Stock"  values={compareList.map(m => attr(m, 'stock'))}  highlight="high" />
                <tr className="border-t border-gray-100">
                  <td className="py-2 pr-3 text-[11px] text-gray-500 font-semibold">Type</td>
                  {compareList.map(m => (
                    <td key={m.id} className="py-2 px-1 text-center">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${m.requires_rx ? 'bg-orange-50 text-orange-600' : 'bg-green-50 text-green-700'}`}>
                        {attr(m, 'rx')}
                      </span>
                    </td>
                  ))}
                  {Array(3 - compareList.length).fill(0).map((_, i) => (
                    <td key={`et-${i}`} className="py-2 px-1 text-center text-[11px] text-gray-300">—</td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* Hint when panel is empty */}
        {compareList.length === 0 && (
          <div className="px-4 py-5 text-center border-t border-gray-100">
            <Package className="w-7 h-7 text-gray-200 mx-auto mb-2" />
            <p className="text-[11px] text-gray-400 leading-snug">
              Tap <span className="font-bold text-brand">Compare</span> on any medicine card to compare up to 3 medicines side-by-side.
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}
