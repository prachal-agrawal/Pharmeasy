/**
 * Infer a coarse product form from the medicine display name for placeholder icons.
 *
 * @param {string} name - Medicine name (e.g. from API).
 * @returns {'tablet' | 'gel' | 'spray' | 'bottle'} Visual category for placeholders.
 */
export function getMedicineFormType(name) {
  const n = String(name || '').toLowerCase()

  if (/\b(spray|inhaler|aerosol|nasal\s+spray|transdermal\s+spray|puff)\b/.test(n)) {
    return 'spray'
  }
  if (/\b(gel|cream|ointment|lotion)\b/.test(n)) {
    return 'gel'
  }
  if (
    /\b(syrup|suspension|drops|solution|elixir|mixture|emulsion|oral\s+liquid|injection|injectable|ampoule|vial|infusion)\b/.test(
      n
    )
  ) {
    return 'bottle'
  }
  if (/\b(tablet|capsule|cap\b|tab\b|strip|pill|chewable|dispersible|sachet)\b/.test(n)) {
    return 'tablet'
  }
  return 'tablet'
}
