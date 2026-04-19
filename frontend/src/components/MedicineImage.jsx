import { useState } from 'react'
import MedicineImagePlaceholder from './MedicineImagePlaceholder'

/**
 * Product image with automatic fallback to form + name placeholder on missing URL or load error.
 *
 * @param {object} props
 * @param {string} props.name - Medicine name (for alt + placeholder).
 * @param {string | null | undefined} props.src - Remote image URL.
 * @param {string} [props.className] - Wrapper / placeholder container classes.
 * @param {string} [props.imgClassName] - Classes for the `<img>` when shown.
 * @param {'sm'|'md'|'lg'|'xl'|'card'} [props.placeholderSize='md'] - Placeholder layout.
 */
export default function MedicineImage({ name, src, className = '', imgClassName = '', placeholderSize = 'md' }) {
  const [broken, setBroken] = useState(false)

  if (!src || broken) {
    return <MedicineImagePlaceholder name={name} size={placeholderSize} className={className} />
  }

  return (
    <img
      src={src}
      alt={name || 'Medicine'}
      className={imgClassName}
      onError={() => setBroken(true)}
    />
  )
}
