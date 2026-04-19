import { Pill, Droplets, SprayCan, PillBottle } from 'lucide-react'
import { getMedicineFormType } from '../utils/medicineFormType'

const ICONS = {
  tablet: Pill,
  gel: Droplets,
  spray: SprayCan,
  bottle: PillBottle,
}

/** @typedef {'sm' | 'md' | 'lg' | 'xl' | 'card'} PlaceholderSize */

const SIZE_STYLES = {
  sm: { icon: 'w-4 h-4', text: 'text-[7px] leading-tight', pad: 'p-0.5', gap: 'gap-0.5', lineClamp: 'line-clamp-2' },
  md: { icon: 'w-7 h-7', text: 'text-[10px] leading-tight', pad: 'p-1.5', gap: 'gap-1', lineClamp: 'line-clamp-3' },
  lg: { icon: 'w-10 h-10', text: 'text-xs', pad: 'p-2', gap: 'gap-1.5', lineClamp: 'line-clamp-3' },
  xl: { icon: 'w-16 h-16', text: 'text-sm', pad: 'p-4', gap: 'gap-3', lineClamp: 'line-clamp-4' },
  card: { icon: 'w-12 h-12', text: 'text-[11px]', pad: 'p-3', gap: 'gap-2', lineClamp: 'line-clamp-3' },
}

/**
 * Default artwork when no product photo: form icon + medicine name.
 *
 * @param {object} props
 * @param {string} props.name - Medicine name to show.
 * @param {PlaceholderSize} [props.size='md'] - Layout density.
 * @param {string} [props.className] - Extra classes on the outer container.
 * @param {'tablet'|'gel'|'spray'|'bottle'} [props.form] - Override inferred form.
 */
export default function MedicineImagePlaceholder({ name, size = 'md', className = '', form: formOverride }) {
  const form = formOverride || getMedicineFormType(name)
  const Icon = ICONS[form] ?? Pill
  const st = SIZE_STYLES[size] ?? SIZE_STYLES.md

  return (
    <div
      className={`flex flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-brand-light/90 text-brand text-center overflow-hidden ${st.pad} ${className}`}
    >
      <div className={`flex flex-col items-center justify-center ${st.gap} w-full min-h-0 flex-1`}>
        <Icon className={`${st.icon} shrink-0 opacity-90`} strokeWidth={1.75} aria-hidden />
        <p className={`${st.text} font-bold text-brand/90 ${st.lineClamp} px-1 break-words w-full`}>
          {name || 'Medicine'}
        </p>
      </div>
    </div>
  )
}
