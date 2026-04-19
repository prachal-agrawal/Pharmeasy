import { useState, useEffect, useRef } from 'react'
import { Plus, Edit2, EyeOff, Eye, X, Upload, Trash2, Link2, Unlink, TrendingDown } from 'lucide-react'
import { adminAPI } from '../../utils/api'
import toast from 'react-hot-toast'
import MedicineImage from '../../components/MedicineImage'

// ─── Alternatives Management Panel ──────────────────────────────────────────

function AlternativesPanel({ allMeds }) {
  const [alts,    setAlts]    = useState([])
  const [loading, setLoading] = useState(true)
  const [modal,   setModal]   = useState(false)
  const [form,    setForm]    = useState({ source: '', alternative: '' })
  const [saving,  setSaving]  = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await adminAPI.alternatives()
      setAlts(data)
    } catch { toast.error('Failed to load alternatives') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!form.source || !form.alternative) return toast.error('Select both medicines')
    if (form.source === form.alternative) return toast.error('Source and alternative must differ')
    setSaving(true)
    try {
      await adminAPI.addAlternative(parseInt(form.source), parseInt(form.alternative))
      toast.success('Alternative mapping created')
      setModal(false)
      setForm({ source: '', alternative: '' })
      await load()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to create')
    } finally { setSaving(false) }
  }

  const handleToggle = async (alt) => {
    try {
      await adminAPI.toggleAlternative(alt.id, alt.is_active ? 0 : 1)
      toast.success(alt.is_active ? 'Mapping deactivated' : 'Mapping activated')
      await load()
    } catch { toast.error('Failed to update') }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this alternative mapping permanently?')) return
    try {
      await adminAPI.deleteAlternative(id)
      toast.success('Mapping deleted')
      await load()
    } catch { toast.error('Failed to delete') }
  }

  const activeMeds = allMeds.filter(m => m.is_active)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-green-600" />
          <h2 className="font-extrabold text-base">Generic Alternatives
            <span className="text-gray-400 font-normal text-sm ml-1">({alts.length})</span>
          </h2>
        </div>
        <button onClick={() => setModal(true)} className="btn-primary flex items-center gap-2 text-sm">
          <Link2 className="w-3.5 h-3.5" /> Add Mapping
        </button>
      </div>

      <p className="text-xs text-gray-400 mb-4">
        Each mapping links a branded/pricier medicine to its cheaper generic alternative.
        On the product page, customers see a side-by-side comparison with savings %.
      </p>

      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading...</div>
        ) : alts.length === 0 ? (
          <div className="p-8 text-center">
            <TrendingDown className="w-8 h-8 text-gray-200 mx-auto mb-2" />
            <p className="text-sm text-gray-400">No alternative mappings yet.</p>
            <p className="text-xs text-gray-300">Click "Add Mapping" to create one.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs font-bold text-gray-400 uppercase">
                <tr>
                  {['Branded / Source', 'Salt Composition', '→', 'Generic Alternative', 'Savings', 'Status', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {alts.map(alt => {
                  const savings = alt.source_min_price > 0 && alt.alt_min_price < alt.source_min_price
                    ? Math.round((1 - alt.alt_min_price / alt.source_min_price) * 100)
                    : 0
                  return (
                    <tr key={alt.id} className={`hover:bg-gray-50 transition-colors ${!alt.is_active ? 'opacity-50' : ''}`}>
                      <td className="px-4 py-3">
                        <p className="font-bold text-gray-800">{alt.source_name}</p>
                        <p className="text-xs text-gray-400">{alt.source_brand}</p>
                        <p className="text-xs text-brand font-semibold">₹{parseFloat(alt.source_min_price).toFixed(0)}</p>
                      </td>
                      <td className="px-4 py-3 max-w-[160px]">
                        <p className="text-xs text-gray-500 truncate">{alt.source_salt || '—'}</p>
                      </td>
                      <td className="px-4 py-3 text-green-500 font-bold text-lg">→</td>
                      <td className="px-4 py-3">
                        <p className="font-bold text-gray-800">{alt.alt_name}</p>
                        <p className="text-xs text-gray-400">{alt.alt_brand}</p>
                        <p className="text-xs text-green-600 font-semibold">₹{parseFloat(alt.alt_min_price).toFixed(0)}</p>
                      </td>
                      <td className="px-4 py-3">
                        {savings > 0 ? (
                          <span className="bg-green-50 text-green-700 text-xs font-extrabold px-2 py-1 rounded-full">
                            {savings}% cheaper
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          alt.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'
                        }`}>
                          {alt.is_active ? 'Active' : 'Paused'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button
                            onClick={() => handleToggle(alt)}
                            title={alt.is_active ? 'Pause' : 'Activate'}
                            className={`p-1.5 rounded transition-colors ${
                              alt.is_active
                                ? 'hover:bg-amber-50 hover:text-amber-600 text-gray-400'
                                : 'hover:bg-green-50 hover:text-green-600 text-gray-400'
                            }`}
                          >
                            {alt.is_active ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                          <button
                            onClick={() => handleDelete(alt.id)}
                            className="p-1.5 hover:bg-red-50 hover:text-red-500 text-gray-400 rounded transition-colors"
                            title="Delete mapping"
                          >
                            <Unlink className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Mapping Modal */}
      {modal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={e => e.target === e.currentTarget && setModal(false)}>
          <div className="bg-white rounded-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Link2 className="w-4 h-4 text-green-600" />
                <h3 className="font-extrabold text-base">New Alternative Mapping</h3>
              </div>
              <button onClick={() => setModal(false)}><X className="w-5 h-5 text-gray-400 hover:text-gray-600" /></button>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-green-50 rounded-xl p-3 text-xs text-green-700">
                Select the <strong>branded/expensive</strong> medicine as source, and the
                <strong> generic/cheaper</strong> one as alternative. The savings % is
                calculated automatically from current prices.
              </div>

              <div>
                <label className="text-xs font-bold text-gray-500 block mb-1.5">
                  Source Medicine (branded / pricier)
                </label>
                <select className="input-field" value={form.source}
                  onChange={e => setForm(p => ({ ...p, source: e.target.value }))}>
                  <option value="">Select medicine...</option>
                  {activeMeds.map(m => (
                    <option key={m.id} value={m.id}>{m.name} — {m.brand}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-center">
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <div className="h-px w-16 bg-gray-200" />
                  <TrendingDown className="w-4 h-4 text-green-500" />
                  <span className="text-xs font-medium">cheaper alternative</span>
                  <div className="h-px w-16 bg-gray-200" />
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-gray-500 block mb-1.5">
                  Generic Alternative (cheaper)
                </label>
                <select className="input-field" value={form.alternative}
                  onChange={e => setForm(p => ({ ...p, alternative: e.target.value }))}>
                  <option value="">Select medicine...</option>
                  {activeMeds
                    .filter(m => m.id !== parseInt(form.source))
                    .map(m => (
                      <option key={m.id} value={m.id}>{m.name} — {m.brand}</option>
                    ))}
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={handleCreate} disabled={saving}
                  className="flex-1 btn-primary py-3 flex items-center justify-center gap-2">
                  <Link2 className="w-4 h-4" />
                  {saving ? 'Creating...' : 'Create Mapping'}
                </button>
                <button onClick={() => setModal(false)} className="btn-outline px-5 py-3">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main AdminMedicines Component ──────────────────────────────────────────

export default function AdminMedicines() {
  const [meds,    setMeds]    = useState([])
  const [cats,    setCats]    = useState([])
  const [search,  setSearch]  = useState('')
  const [loading, setLoading] = useState(true)
  const [modal,   setModal]   = useState(false)
  const [editing, setEditing] = useState(null)
  const [saving,  setSaving]  = useState(false)
  const [tab,     setTab]     = useState('medicines')  // 'medicines' | 'alternatives'
  const imgRef = useRef()

  const blank = {
    name: '', brand: '', category_id: '', requires_rx: 1, is_active: 1,
    salt_composition: '', manufacturer: '',
    uses: '', side_effects: '', safety_points: '', warning: '',
    variants: [{ label: '', mrp: '', price: '', stock: 0 }],
    imageUrls: [],
    pendingFiles: [],
  }
  const [form, setForm] = useState(blank)

  useEffect(() => {
    Promise.all([adminAPI.medicines(), adminAPI.categories()])
      .then(([m, c]) => { setMeds(m.data); setCats(c.data) })
      .finally(() => setLoading(false))
  }, [])

  const refresh = () => adminAPI.medicines().then(r => setMeds(r.data))

  const openCreate = () => { setForm(blank); setEditing(null); setModal(true) }

  const openEdit = async (med) => {
    const { data: detail } = await adminAPI.getMedicine(med.id)
    const urls = Array.isArray(detail.image_urls) && detail.image_urls.length
      ? [...detail.image_urls]
      : (detail.image_url ? [detail.image_url] : [])
    const to01 = (v, fallback = 0) => {
      if (v === null || v === undefined) return fallback
      return Number(v) ? 1 : 0
    }
    setForm({
      name:             detail.name || '',
      brand:            detail.brand || '',
      category_id:      detail.category_id ?? '',
      requires_rx:      to01(detail.requires_rx, 0),
      is_active:        detail.is_active == null ? 1 : to01(detail.is_active, 0),
      salt_composition: detail.salt_composition || '',
      manufacturer:     detail.manufacturer || '',
      uses:             detail.uses || '',
      side_effects:     (detail.side_effects || []).join('\n'),
      safety_points:    (detail.safety_points || []).join('\n'),
      warning:          detail.warning || '',
      variants:         detail.variants?.length
        ? detail.variants.map(v => ({ label: v.label, mrp: v.mrp, price: v.price, stock: v.stock }))
        : [{ label: '', mrp: '', price: '', stock: 0 }],
      imageUrls:        urls,
      pendingFiles:     [],
    })
    setEditing(med.id)
    setModal(true)
  }

  const addImageFiles = (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setForm(p => ({ ...p, pendingFiles: [...p.pendingFiles, ...files] }))
    e.target.value = ''
  }

  const removeSavedImage = (idx) => {
    setForm(p => ({ ...p, imageUrls: p.imageUrls.filter((_, i) => i !== idx) }))
  }

  const removePendingImage = (idx) => {
    setForm(p => ({ ...p, pendingFiles: p.pendingFiles.filter((_, i) => i !== idx) }))
  }

  const FLAT_DISCOUNT = 0.15 // 15% off MRP

  const addVariant    = () => setForm(p => ({ ...p, variants: [...p.variants, { label: '', mrp: '', price: '', stock: 0 }] }))
  const removeVariant = (i) => setForm(p => ({ ...p, variants: p.variants.filter((_, j) => j !== i) }))
  const setVariant    = (i, key, val) => setForm(p => {
    const variants = [...p.variants]
    variants[i] = { ...variants[i], [key]: val }
    // Auto-compute selling price when MRP is changed
    if (key === 'mrp' && val !== '') {
      const mrpNum = parseFloat(val)
      if (!isNaN(mrpNum) && mrpNum > 0) {
        variants[i].price = (mrpNum * (1 - FLAT_DISCOUNT)).toFixed(2)
      }
    }
    return { ...p, variants }
  })

  const handleSave = async () => {
    if (!form.name || !form.brand || !form.category_id) return toast.error('Name, brand and category are required')
    // Variants are optional; when provided, each one needs at least a label and a price
    const filledVariants = form.variants.filter(v => v.label || v.price)
    if (filledVariants.some(v => !v.label || !v.price)) return toast.error('Each variant needs both a label and a price')
    setSaving(true)
    try {
      const fd = new FormData()
      const catId = parseInt(form.category_id, 10)
      fd.append('name',             form.name)
      fd.append('brand',            form.brand)
      fd.append('category_id',      String(Number.isNaN(catId) ? 0 : catId))
      fd.append('requires_rx',      form.requires_rx ? '1' : '0')
      fd.append('is_active',        form.is_active ? '1' : '0')
      fd.append('salt_composition', form.salt_composition)
      fd.append('manufacturer',     form.manufacturer)
      fd.append('uses',             form.uses)
      fd.append('side_effects',     JSON.stringify(form.side_effects.split('\n').filter(Boolean).map(s => s.trim())))
      fd.append('safety_points',    JSON.stringify(form.safety_points.split('\n').filter(Boolean).map(s => s.trim())))
      fd.append('warning',          form.warning)
      // Only send variants that have at least a label + price filled in
      const validVariants = form.variants.filter(v => v.label && v.price)
      fd.append('variants', JSON.stringify(validVariants))
      if (editing) {
        fd.append('existing_image_urls', JSON.stringify(form.imageUrls || []))
      }
      form.pendingFiles.forEach(f => fd.append('images', f))

      if (editing) {
        await adminAPI.updateMedicine(editing, fd)
        toast.success('Medicine updated!')
      } else {
        await adminAPI.addMedicine(fd)
        toast.success('Medicine added!')
      }
      await refresh()
      setModal(false)
    } catch (err) {
      const d = err?.response?.data?.detail
      const msg = Array.isArray(d)
        ? d.map((e) => (typeof e === 'string' ? e : e?.msg || JSON.stringify(e))).join(' ')
        : (d || err?.message || 'Save failed')
      toast.error(msg)
    } finally { setSaving(false) }
  }

  const toggleActive = async (med) => {
    if (med.is_active) {
      await adminAPI.deleteMedicine(med.id)
      toast.success('Medicine hidden')
    } else {
      const fd = new FormData()
      fd.append('name', med.name); fd.append('brand', med.brand)
      fd.append('category_id', med.category_id); fd.append('requires_rx', med.requires_rx)
      fd.append('is_active', 1); fd.append('uses', med.uses || '')
      fd.append('side_effects', med.side_effects || '[]')
      fd.append('safety_points', med.safety_points || '[]')
      fd.append('warning', med.warning || ''); fd.append('variants', '[]')
      await adminAPI.updateMedicine(med.id, fd)
      toast.success('Medicine restored')
    }
    await refresh()
  }

  const filtered = meds.filter(m =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.brand.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="page-enter">
      {/* Page header + tab switcher */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-extrabold">Medicines</h1>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setTab('medicines')}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors ${
                tab === 'medicines' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Catalogue
            </button>
            <button
              onClick={() => setTab('alternatives')}
              className={`px-3 py-1.5 text-xs font-bold rounded-md transition-colors flex items-center gap-1 ${
                tab === 'alternatives' ? 'bg-white shadow-sm text-gray-800' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <TrendingDown className="w-3 h-3" /> Alternatives
            </button>
          </div>
          {tab === 'medicines' && (
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Medicine
            </button>
          )}
        </div>
      </div>

      {/* ── Alternatives tab ── */}
      {tab === 'alternatives' && (
        <AlternativesPanel allMeds={meds} />
      )}

      {/* ── Medicines tab ── */}
      {tab === 'medicines' && (
        <>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search medicines..." className="input-field mb-4 max-w-sm bg-white" />

          <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs font-bold text-gray-400 uppercase">
                  <tr>
                    {['Image', 'Name', 'Brand', 'Salt Composition', 'Category', 'Variants', 'Stock', 'Type', 'Status', 'Actions'].map(h => (
                      <th key={h} className="px-4 py-3 text-left whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {loading ? (
                    Array(5).fill(0).map((_, i) => (
                      <tr key={i}><td colSpan={10} className="px-4 py-3">
                        <div className="h-4 bg-gray-100 rounded animate-pulse" />
                      </td></tr>
                    ))
                  ) : filtered.map(med => (
                    <tr key={med.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <div className="w-10 h-10 rounded-lg overflow-hidden">
                          <MedicineImage
                            name={med.name}
                            src={med.image_url}
                            className="w-full h-full"
                            imgClassName="w-full h-full object-cover"
                            placeholderSize="sm"
                          />
                        </div>
                      </td>
                      <td className="px-4 py-3 font-bold max-w-[140px]">
                        <p className="truncate">{med.name}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{med.brand}</td>
                      <td className="px-4 py-3 text-gray-400 text-xs max-w-[160px]">
                        <p className="truncate">{med.salt_composition || '—'}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{med.category_name}</td>
                      <td className="px-4 py-3 text-center">{med.variant_count || 0}</td>
                      <td className={`px-4 py-3 font-bold ${parseFloat(med.total_stock) < 10 ? 'text-danger' : 'text-gray-700'}`}>
                        {parseFloat(med.total_stock || 0)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={med.requires_rx ? 'badge-rx' : 'badge-otc'}>
                          {med.requires_rx ? 'Rx' : 'OTC'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          med.is_active ? 'bg-brand-light text-brand' : 'bg-gray-100 text-gray-400'
                        }`}>
                          {med.is_active ? 'Active' : 'Hidden'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button onClick={() => openEdit(med)}
                            className="p-1.5 hover:bg-brand-light hover:text-brand rounded transition-colors text-gray-400">
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => toggleActive(med)}
                            className={`p-1.5 rounded transition-colors ${
                              med.is_active
                                ? 'hover:bg-danger-light hover:text-danger text-gray-400'
                                : 'hover:bg-brand-light hover:text-brand text-gray-400'
                            }`}>
                            {med.is_active ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ── Add / Edit Medicine MODAL ── */}
      {modal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={e => e.target === e.currentTarget && setModal(false)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white px-6 py-4 border-b border-gray-100 flex items-center justify-between z-10">
              <h2 className="font-extrabold text-base">{editing ? 'Edit Medicine' : 'Add Medicine'}</h2>
              <button onClick={() => setModal(false)}><X className="w-5 h-5 text-gray-400 hover:text-gray-600" /></button>
            </div>

            <div className="p-6 space-y-4">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Medicine Name *</label>
                  <input className="input-field" value={form.name}
                    onChange={e => setForm(p => ({ ...p, name: e.target.value }))}
                    placeholder="e.g. Paracetamol 500mg" />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Brand *</label>
                  <input className="input-field" value={form.brand}
                    onChange={e => setForm(p => ({ ...p, brand: e.target.value }))}
                    placeholder="e.g. Dolo / Calpol" />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Category *</label>
                  <select className="input-field" value={form.category_id}
                    onChange={e => setForm(p => ({ ...p, category_id: e.target.value }))}>
                    <option value="">Select category</option>
                    {cats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Prescription Required?</label>
                  <select className="input-field" value={form.requires_rx}
                    onChange={e => setForm(p => ({ ...p, requires_rx: parseInt(e.target.value) }))}>
                    <option value={1}>Yes (Rx) — Prescription Required</option>
                    <option value={0}>No (OTC) — Over the Counter</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Salt Composition</label>
                  <input className="input-field" value={form.salt_composition}
                    onChange={e => setForm(p => ({ ...p, salt_composition: e.target.value }))}
                    placeholder="e.g. Paracetamol (500mg)" />
                </div>
                <div>
                  <label className="text-xs font-bold text-gray-500 block mb-1">Manufacturer</label>
                  <input className="input-field" value={form.manufacturer}
                    onChange={e => setForm(p => ({ ...p, manufacturer: e.target.value }))}
                    placeholder="e.g. Micro Labs Ltd" />
                </div>
              </div>

              {/* Product images (gallery) */}
              <div>
                <label className="text-xs font-bold text-gray-500 block mb-2">Product images</label>
                <p className="text-[10px] text-gray-400 mb-2">Add several photos; remove any you do not want saved.</p>
                <div className="flex flex-wrap gap-3 mb-3">
                  {form.imageUrls.map((url, idx) => (
                    <div key={`u-${idx}-${url}`} className="relative group">
                      <img src={url} alt="" className="w-20 h-20 rounded-xl object-cover border border-gray-200" />
                      <button
                        type="button"
                        title="Remove image"
                        onClick={() => removeSavedImage(idx)}
                        className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center shadow opacity-90 hover:opacity-100"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {form.pendingFiles.map((file, idx) => (
                    <div
                      key={`p-${idx}-${file.name}`}
                      className="flex flex-col items-center gap-1 w-[5.75rem] shrink-0"
                    >
                      <div className="relative w-20 h-20 rounded-xl border-2 border-dashed border-brand bg-brand-light/30 flex items-center justify-center overflow-hidden">
                        <Upload className="w-5 h-5 text-brand shrink-0" aria-hidden />
                        <button
                          type="button"
                          title="Remove"
                          onClick={() => removePendingImage(idx)}
                          className="absolute top-0.5 right-0.5 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center shadow z-10"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <span
                        className="text-[8px] text-center text-gray-600 w-full max-w-full break-all line-clamp-3 leading-snug"
                        title={file.name}
                      >
                        {file.name}
                      </span>
                    </div>
                  ))}
                </div>
                <button type="button" onClick={() => imgRef.current.click()}
                  className="flex items-center gap-2 btn-outline text-sm px-4 py-2">
                  <Upload className="w-4 h-4" /> Add images
                </button>
                <input ref={imgRef} type="file" accept="image/*" multiple className="hidden" onChange={addImageFiles} />
              </div>

              {/* Text fields */}
              {[
                { key: 'uses',          label: 'Uses / Indications',          rows: 2, placeholder: 'What conditions does this treat?' },
                { key: 'side_effects',  label: 'Side Effects (one per line)',  rows: 3, placeholder: 'Nausea\nHeadache\nDizziness' },
                { key: 'safety_points', label: 'Safety Points (one per line)', rows: 3, placeholder: 'Take with food\nAvoid alcohol\nKeep away from children' },
                { key: 'warning',       label: 'Warning / Disclaimer',         rows: 2, placeholder: 'Important safety warning' },
              ].map(f => (
                <div key={f.key}>
                  <label className="text-xs font-bold text-gray-500 block mb-1">{f.label}</label>
                  <textarea className="input-field resize-none" rows={f.rows} placeholder={f.placeholder}
                    value={form[f.key]} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} />
                </div>
              ))}

              {/* Variants */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-gray-500 uppercase tracking-wide">Pack Sizes / Variants</label>
                  <button type="button" onClick={addVariant}
                    className="flex items-center gap-1 text-xs text-brand font-bold hover:underline">
                    <Plus className="w-3 h-3" /> Add Variant
                  </button>
                </div>
                <p className="text-[10px] text-green-600 font-semibold mb-2">
                  💡 Variants are optional. Entering MRP auto-calculates Price at 15% off.
                </p>
                <div className="grid grid-cols-5 gap-2 mb-1 text-[10px] font-bold text-gray-400 uppercase">
                  <span className="col-span-2">Label (e.g. 100gm Gel)</span>
                  <span>MRP (₹) <span className="text-gray-300 normal-case font-normal">optional</span></span>
                  <span>Price (₹) *</span>
                  <span>Stock</span>
                </div>
                {form.variants.map((v, i) => (
                  <div key={i} className="grid grid-cols-5 gap-2 mb-2 items-center bg-gray-50 rounded-lg p-2">
                    <input className="input-field col-span-2 text-xs bg-white" placeholder="e.g. 10gm Gel"
                      value={v.label} onChange={e => setVariant(i, 'label', e.target.value)} />
                    <div className="relative">
                      <input className="input-field text-xs bg-white pr-6" type="number" placeholder="MRP (opt.)"
                        value={v.mrp} onChange={e => setVariant(i, 'mrp', e.target.value)} />
                      {v.mrp && (
                        <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[8px] font-bold text-green-600 bg-green-50 px-1 rounded">
                          −15%
                        </span>
                      )}
                    </div>
                    <input className="input-field text-xs bg-white" type="number" placeholder="Price *"
                      value={v.price} onChange={e => setVariant(i, 'price', e.target.value)} />
                    <div className="flex items-center gap-1">
                      <input className="input-field text-xs bg-white" type="number" placeholder="Qty"
                        value={v.stock} onChange={e => setVariant(i, 'stock', e.target.value)} />
                      {form.variants.length > 1 && (
                        <button type="button" onClick={() => removeVariant(i)}
                          className="text-gray-300 hover:text-danger transition-colors">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {editing && (
                <div className="flex items-center gap-2">
                  <input type="checkbox" id="active" checked={!!form.is_active}
                    onChange={e => setForm(p => ({ ...p, is_active: e.target.checked ? 1 : 0 }))}
                    className="accent-brand" />
                  <label htmlFor="active" className="text-sm text-gray-600">Active (visible on store)</label>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button onClick={handleSave} disabled={saving} className="flex-1 btn-primary py-3">
                  {saving ? 'Saving...' : editing ? 'Update Medicine' : 'Add Medicine'}
                </button>
                <button onClick={() => setModal(false)} className="btn-outline px-5 py-3">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
