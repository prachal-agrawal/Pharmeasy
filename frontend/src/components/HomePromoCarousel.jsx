import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { PROMO_SLIDES } from '../data/promoSlides'

const INTERVAL_MS = 5500

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return reduced
}

const THEME_CLASS = {
  brand: 'bg-gradient-to-br from-brand to-brand-dark text-white',
  info: 'bg-info-light text-gray-800 border border-info/20',
  amber: 'bg-amber-light text-gray-900 border border-amber/25',
  light: 'bg-gradient-to-br from-brand-light to-white text-gray-800 border border-brand/15',
}

export default function HomePromoCarousel() {
  const slides = PROMO_SLIDES
  const reducedMotion = usePrefersReducedMotion()
  const [active, setActive] = useState(0)
  const [paused, setPaused] = useState(false)
  const regionRef = useRef(null)

  const go = useCallback(
    (dir) => {
      setActive((i) => {
        if (dir === 'next') return (i + 1) % slides.length
        if (dir === 'prev') return (i - 1 + slides.length) % slides.length
        return i
      })
    },
    [slides.length]
  )

  const goTo = useCallback((index) => {
    setActive(index)
  }, [])

  useEffect(() => {
    if (reducedMotion || paused) return
    const id = setInterval(() => {
      setActive((i) => (i + 1) % slides.length)
    }, INTERVAL_MS)
    return () => clearInterval(id)
  }, [reducedMotion, paused, slides.length, active])

  const onKeyDown = (e) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      go('prev')
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      go('next')
    }
  }

  return (
    <div
      ref={regionRef}
      tabIndex={0}
      onKeyDown={onKeyDown}
      role="region"
      aria-roledescription="carousel"
      aria-label="Promotional announcements"
      className="mb-6 rounded-2xl overflow-hidden shadow-md border border-gray-100/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
    >
      <div className="relative min-h-[200px] sm:min-h-[220px]">
        {slides.map((slide, i) => {
          const visible = i === active
          const theme = THEME_CLASS[slide.theme] || THEME_CLASS.brand
          return (
            <article
              key={slide.id}
              className={`absolute inset-0 flex flex-col justify-center px-5 py-6 sm:px-8 sm:py-8 transition-opacity duration-500 ease-out ${
                visible ? 'z-10 opacity-100' : 'z-0 opacity-0 pointer-events-none'
              } ${theme}`}
              aria-hidden={!visible}
            >
              <h2
                className="text-xl sm:text-2xl font-extrabold leading-tight pr-8 sm:pr-0 max-w-xl"
                id={`promo-slide-title-${slide.id}`}
              >
                {slide.title}
              </h2>
              <p
                className={`mt-2 text-sm sm:text-base max-w-lg leading-relaxed ${
                  slide.theme === 'brand' ? 'text-white/90' : 'text-gray-600'
                }`}
              >
                {slide.subtitle}
              </p>
              <div className="mt-4">
                {slide.ctaHash ? (
                  <Link
                    to={`/#${slide.ctaHash}`}
                    className={
                      slide.theme === 'brand'
                        ? 'inline-flex items-center justify-center font-semibold px-4 py-2.5 rounded-xl bg-white text-brand text-sm shadow-sm hover:bg-brand-light transition-colors'
                        : 'inline-flex items-center justify-center font-semibold px-4 py-2.5 rounded-xl btn-primary text-sm'
                    }
                  >
                    {slide.ctaLabel}
                  </Link>
                ) : (
                  <Link
                    to={slide.ctaTo || '/'}
                    className={
                      slide.theme === 'brand'
                        ? 'inline-flex items-center justify-center font-semibold px-4 py-2.5 rounded-xl bg-white text-brand text-sm shadow-sm hover:bg-brand-light transition-colors'
                        : 'inline-flex items-center justify-center font-semibold px-4 py-2.5 rounded-xl btn-primary text-sm'
                    }
                  >
                    {slide.ctaLabel}
                  </Link>
                )}
              </div>
            </article>
          )
        })}

        <div
          className="absolute right-0 top-0 w-32 h-full opacity-[0.08] text-[100px] flex items-center justify-end pr-2 pointer-events-none select-none"
          aria-hidden
        >
          💊
        </div>
      </div>

      <div
        className="flex items-center justify-center gap-2 sm:gap-3 px-3 py-3 bg-white/90 border-t border-gray-100"
        aria-label="Carousel controls"
      >
        <button
          type="button"
          onClick={() => go('prev')}
          className="p-2 rounded-full text-gray-500 hover:bg-gray-100 hover:text-brand transition-colors"
          aria-label="Previous slide"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center justify-center gap-1.5 flex-1 min-w-0 max-w-[200px] sm:max-w-xs">
          {slides.map((s, i) => {
            const isActive = i === active
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goTo(i)}
                aria-label={`Go to slide ${i + 1}: ${s.title}`}
                aria-current={isActive}
                className={`h-2 rounded-full transition-all ${
                  isActive ? 'w-7 bg-brand' : 'w-2 bg-gray-300 hover:bg-gray-400'
                }`}
              />
            )
          })}
        </div>

        {!reducedMotion && (
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            className="p-2 rounded-full text-gray-500 hover:bg-gray-100 hover:text-brand transition-colors"
            aria-label={paused ? 'Play automatic slide show' : 'Pause automatic slide show'}
            aria-pressed={paused}
          >
            {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
          </button>
        )}

        <button
          type="button"
          onClick={() => go('next')}
          className="p-2 rounded-full text-gray-500 hover:bg-gray-100 hover:text-brand transition-colors"
          aria-label="Next slide"
        >
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      <p className="sr-only" aria-live="polite">
        {reducedMotion
          ? `${slides[active].title}. Slide ${active + 1} of ${slides.length}. Automatic rotation is off.`
          : `${slides[active].title}. Slide ${active + 1} of ${slides.length}.`}
      </p>
    </div>
  )
}
