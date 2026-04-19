import { Link } from 'react-router-dom'
import { ShoppingCart, Star, GitCompareArrows } from 'lucide-react'
import { useCart } from '../context/CartContext'
import MedicineImage from './MedicineImage'

export default function MedicineCard({ med, isCompared = false, onCompare }) {
  const { addToCart } = useCart()
  const hasStock = parseFloat(med.total_stock) > 0

  const handleAdd = async (e) => {
    e.preventDefault()
    await addToCart(null, 1, med.name)
  }

  return (
    <Link to={`/medicine/${med.id}`} className="card hover:border-brand hover:shadow-md transition-all duration-200 block group relative">
      {/* Image */}
      <div className="relative">
        <MedicineImage
          name={med.name}
          src={med.image_url}
          className="w-full h-36 rounded-t-xl"
          imgClassName="w-full h-36 object-cover rounded-t-xl"
          placeholderSize="card"
        />

        {/* Rx badge */}
        <span className={`absolute top-2 right-2 ${med.requires_rx ? 'badge-rx' : 'badge-otc'}`}>
          {med.requires_rx ? 'Rx' : 'OTC'}
        </span>

        {/* Compare toggle badge */}
        {onCompare && (
          <button
            onClick={e => { e.preventDefault(); e.stopPropagation(); onCompare(med) }}
            title={isCompared ? 'Remove from comparison' : 'Add to comparison'}
            className={`absolute top-2 left-2 flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded-full border transition-all ${
              isCompared
                ? 'bg-brand text-white border-brand shadow'
                : 'bg-white/90 text-gray-500 border-gray-200 hover:border-brand hover:text-brand'
            }`}
          >
            <GitCompareArrows className="w-3 h-3" />
            {isCompared ? 'Added' : 'Compare'}
          </button>
        )}

        {!hasStock && (
          <div className="absolute inset-0 bg-white/70 rounded-t-xl flex items-center justify-center">
            <span className="text-xs font-bold text-gray-400 bg-white px-2 py-1 rounded-full">Out of Stock</span>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="p-3">
        <p className="text-[11px] text-gray-400 mb-0.5">{med.category_name}</p>
        <h3 className="font-bold text-sm leading-snug mb-0.5 group-hover:text-brand transition-colors line-clamp-2">{med.name}</h3>
        <p className="text-[11px] text-gray-500 mb-2">{med.brand}</p>

        {med.rating > 0 && (
          <div className="flex items-center gap-1 mb-2">
            <span className="bg-green-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-0.5">
              <Star className="w-2.5 h-2.5 fill-white" /> {parseFloat(med.rating).toFixed(1)}
            </span>
            <span className="text-[10px] text-gray-400">{med.rating_count} ratings</span>
          </div>
        )}

        <div className="flex items-end justify-between mt-2">
          <div>
            <div className="flex items-baseline gap-1.5">
              <p className="text-brand font-bold text-base">₹{parseFloat(med.min_price).toFixed(0)}</p>
              {med.min_mrp && parseFloat(med.min_mrp) > parseFloat(med.min_price) && (
                <p className="text-[11px] text-gray-400 line-through">₹{parseFloat(med.min_mrp).toFixed(2)}</p>
              )}
            </div>
            {med.min_mrp && parseFloat(med.min_mrp) > parseFloat(med.min_price) && (
              <span className="inline-block bg-green-50 text-green-700 text-[10px] font-extrabold px-1.5 py-0.5 rounded mt-0.5">
                15% OFF
              </span>
            )}
            <p className="text-[10px] text-gray-400 mt-0.5">{parseFloat(med.total_stock)} in stock</p>
          </div>
          {hasStock ? (
            <button
              onClick={e => { e.preventDefault(); window.location.href=`/medicine/${med.id}` }}
              className="flex items-center gap-1 bg-brand-light text-brand text-xs font-bold px-2.5 py-1.5 rounded-md hover:bg-brand hover:text-white transition-colors"
            >
              <ShoppingCart className="w-3 h-3" /> Add
            </button>
          ) : (
            <span className="text-xs text-gray-300 font-medium">Unavailable</span>
          )}
        </div>
      </div>
    </Link>
  )
}
