/**
 * DeliveryEstimateWidget
 *
 * Shows estimated delivery time based on:
 *   1. The user's current GPS location (via browser Geolocation API), OR
 *   2. A manually entered 6-digit PIN code.
 *
 * No delivery-partner API key required — ETA is calculated server-side using
 * straight-line distance from the store.
 *
 * Props:
 *   pin      {string}  - Pre-filled PIN (auto-checks on mount, e.g. from saved address).
 *   compact  {boolean} - Render a single-line summary (for checkout review step).
 *   className {string} - Additional CSS classes on root element.
 */

import { useState, useEffect } from 'react'
import {
  MapPin, Truck, Loader2, XCircle,
  AlertCircle, Navigation, Package,
} from 'lucide-react'
import { deliveryAPI } from '../utils/api'

/* ── Status → UI style mapping ─────────────────────────────────────────── */
function statusStyle(minDays) {
  if (minDays <= 3)
    return { icon: <Package     className="w-4 h-4" />, color: 'text-brand',     bg: 'bg-brand-light', border: 'border-brand/30' }
  return   { icon: <AlertCircle className="w-4 h-4" />, color: 'text-amber-700', bg: 'bg-amber-50',  border: 'border-amber-200' }
}

/* ── Component ──────────────────────────────────────────────────────────── */
export default function DeliveryEstimateWidget({ pin: pinProp, compact = false, className = '' }) {
  const [pin,       setPin]       = useState(pinProp || '')
  const [result,    setResult]    = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [gpsLoading,setGpsLoad]   = useState(false)
  const [error,     setError]     = useState('')
  const [gpsError,  setGpsError]  = useState('')

  // Auto-check when a pin is passed from outside (address selected in Checkout)
  useEffect(() => {
    if (pinProp && /^\d{6}$/.test(pinProp)) {
      setPin(pinProp)
      runPinCheck(pinProp)
    }
  }, [pinProp]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-detect location on mount (only when no pin is pre-supplied)
  useEffect(() => {
    if (!pinProp) handleDetectLocation()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── GPS flow ─────────────────────────────────────────────── */
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setGpsError('Your browser does not support location access.')
      return
    }
    setGpsError('')
    setError('')
    setResult(null)
    setGpsLoad(true)

    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const { data } = await deliveryAPI.etaByCoords(coords.latitude, coords.longitude)
          setResult(data)
          if (data.pincode) setPin(data.pincode)
        } catch {
          setGpsError('Could not estimate delivery for your location. Try entering your PIN.')
        } finally {
          setGpsLoad(false)
        }
      },
      (err) => {
        setGpsLoad(false)
        switch (err.code) {
          case err.PERMISSION_DENIED:
            setGpsError('Location permission denied. Please enter your PIN code instead.')
            break
          case err.POSITION_UNAVAILABLE:
            setGpsError('Location unavailable. Please enter your PIN code.')
            break
          default:
            setGpsError('Could not get your location. Please enter your PIN code.')
        }
      },
      { timeout: 10_000, maximumAge: 60_000 }
    )
  }

  /* ── PIN flow ─────────────────────────────────────────────── */
  const runPinCheck = async (override) => {
    const code = (override || pin).trim()
    if (!/^\d{6}$/.test(code)) {
      setError('Enter a valid 6-digit PIN code')
      return
    }
    setError('')
    setGpsError('')
    setResult(null)
    setLoading(true)
    try {
      const { data } = await deliveryAPI.etaByPin(code)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not check delivery. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const style = result ? statusStyle(result.min_days) : null

  /* ── Compact variant (one-liner for checkout review) ───────── */
  if (compact) {
    if (loading || gpsLoading) {
      return (
        <span className={`flex items-center gap-1.5 text-xs text-gray-400 ${className}`}>
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Checking delivery…
        </span>
      )
    }
    if (result) {
      return (
        <div className={`flex items-start gap-1.5 text-xs ${style.color} ${className}`}>
          {style.icon}
          <div>
            <span className="font-semibold">{result.message}</span>
            {result.distance_km > 0 && (
              <span className="text-gray-400 ml-1.5">~{result.distance_km} km from store</span>
            )}
          </div>
        </div>
      )
    }
    return (
      <button
        onClick={handleDetectLocation}
        className={`flex items-center gap-1 text-xs text-brand underline underline-offset-2 ${className}`}
      >
        <Navigation className="w-3 h-3" /> Check delivery estimate
      </button>
    )
  }

  /* ── Full variant ───────────────────────────────────────────── */
  return (
    <div className={`space-y-3 ${className}`}>

      {/* Primary CTA — detect location */}
      <button
        onClick={handleDetectLocation}
        disabled={gpsLoading || loading}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border-2 border-brand text-brand font-semibold text-sm hover:bg-brand-light transition-colors disabled:opacity-50"
      >
        {gpsLoading
          ? <><Loader2 className="w-4 h-4 animate-spin" /> Detecting your location…</>
          : <><Navigation className="w-4 h-4" /> Use My Current Location</>
        }
      </button>

      {/* GPS error */}
      {gpsError && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{gpsError}
        </p>
      )}

      {/* Divider */}
      <div className="flex items-center gap-2 text-[11px] text-gray-400">
        <div className="flex-1 h-px bg-gray-100" />
        or enter PIN code
        <div className="flex-1 h-px bg-gray-100" />
      </div>

      {/* Manual PIN input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <MapPin className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            value={pin}
            onChange={e => {
              const v = e.target.value.replace(/\D/g, '').slice(0, 6)
              setPin(v)
              setResult(null)
              setError('')
            }}
            onKeyDown={e => e.key === 'Enter' && runPinCheck()}
            placeholder="6-digit PIN code"
            className="input-field pl-8 py-2 text-sm w-full"
          />
        </div>
        <button
          onClick={() => runPinCheck()}
          disabled={loading || pin.length !== 6}
          className="btn-primary px-4 py-2 text-sm shrink-0 disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Check'}
        </button>
      </div>

      {/* PIN error */}
      {error && (
        <p className="text-xs text-red-600 flex items-center gap-1">
          <XCircle className="w-3.5 h-3.5 shrink-0" />{error}
        </p>
      )}

      {/* Result card */}
      {result && style && (
        <div className={`rounded-xl border px-4 py-3.5 space-y-2 ${style.bg} ${style.border}`}>
          {/* Main message */}
          <div className={`flex items-center gap-2 font-bold text-sm ${style.color}`}>
            {style.icon}
            <span>{result.message}</span>
          </div>

          {/* Detail chips */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
            {result.city && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3 text-gray-400" />
                <span className="font-medium text-gray-700">
                  {result.city}{result.state ? `, ${result.state}` : ''}
                </span>
              </span>
            )}
            {result.distance_km > 0 && (
              <span>
                ~<span className="font-medium text-gray-700">{result.distance_km} km</span> from store
              </span>
            )}
            <span>
              COD:{' '}
              <span className="font-medium text-green-700">Available</span>
            </span>
          </div>

          {/* Delivery window badge */}
          <div className={`inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full ${style.bg} border ${style.border} ${style.color}`}>
            <Truck className="w-3 h-3" />
            {result.label} · by {result.estimated_delivery_date}
          </div>
        </div>
      )}
    </div>
  )
}
