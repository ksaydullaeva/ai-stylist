import React, { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import homeFeedFallback from '../data/homeFeed.json'

function HomeTrendRail({ children }) {
  const railRef = useRef(null)
  const [canLeft, setCanLeft] = useState(false)
  const [canRight, setCanRight] = useState(false)

  const updateArrows = useCallback(() => {
    const el = railRef.current
    if (!el) return
    const { scrollLeft, scrollWidth, clientWidth } = el
    const max = scrollWidth - clientWidth
    setCanLeft(scrollLeft > 4)
    setCanRight(max > 4 && scrollLeft < max - 4)
  }, [])

  useEffect(() => {
    const el = railRef.current
    if (!el) return
    updateArrows()
    el.addEventListener('scroll', updateArrows, { passive: true })
    const ro = new ResizeObserver(updateArrows)
    ro.observe(el)
    window.addEventListener('resize', updateArrows)
    return () => {
      el.removeEventListener('scroll', updateArrows)
      ro.disconnect()
      window.removeEventListener('resize', updateArrows)
    }
  }, [updateArrows, children])

  const scrollAmount = useCallback(() => {
    const el = railRef.current
    if (!el) return 294
    const item = el.querySelector('.home-trend-rail-item')
    const step = item ? item.getBoundingClientRect().width + 14 : 294
    return Math.min(el.clientWidth * 0.88, step)
  }, [])

  const goLeft = () => {
    railRef.current?.scrollBy({ left: -scrollAmount(), behavior: 'smooth' })
  }
  const goRight = () => {
    railRef.current?.scrollBy({ left: scrollAmount(), behavior: 'smooth' })
  }

  return (
    <div className="home-trend-rail-wrap">
      <div className="home-trend-rail" ref={railRef} role="list">
        {children}
      </div>
      <div className="home-trend-rail-nav">
        <button
          type="button"
          className="home-trend-rail-arrow home-trend-rail-arrow--prev"
          onClick={goLeft}
          disabled={!canLeft}
          aria-label="Previous items"
        >
          <span className="home-trend-rail-arrow-icon" aria-hidden>
            ‹
          </span>
        </button>
        <button
          type="button"
          className="home-trend-rail-arrow home-trend-rail-arrow--next"
          onClick={goRight}
          disabled={!canRight}
          aria-label="Next items"
        >
          <span className="home-trend-rail-arrow-icon" aria-hidden>
            ›
          </span>
        </button>
      </div>
    </div>
  )
}

function TrendCard({ tag, title, gradient, accent, imageUrl, imageAlt }) {
  const [imgFailed, setImgFailed] = useState(false)

  return (
    <article
      className="home-trend-card"
      style={{
        ...(accent ? { ['--card-accent']: accent } : {}),
        ...(gradient ? { ['--card-gradient']: gradient } : {}),
      }}
    >
      <div className="home-trend-card-visual">
        {imageUrl && !imgFailed ? (
          <img
            className="home-trend-card-img"
            src={imageUrl}
            alt={imageAlt || ''}
            loading="lazy"
            decoding="async"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="home-trend-card-fallback" aria-hidden />
        )}
      </div>
      <div className="home-trend-card-body">
        <span className="home-trend-card-tag">{tag}</span>
        <h3 className="home-trend-card-title">{title}</h3>
        <div className="home-trend-card-footer">
          <button
            type="button"
            className="home-trend-readmore home-trend-readmore--inactive"
            aria-disabled="true"
            tabIndex={-1}
            onClick={(e) => e.preventDefault()}
          >
            Read more
          </button>
        </div>
      </div>
    </article>
  )
}

export default function HomePage() {
  const [trending, setTrending] = useState([])
  const [spotlight, setSpotlight] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .homeTrendFeed()
      .then((data) => {
        if (cancelled) return
        setTrending(Array.isArray(data.trending) ? data.trending : [])
        setSpotlight(Array.isArray(data.spotlight) ? data.spotlight : [])
      })
      .catch(() => {
        if (cancelled) return
        setTrending(homeFeedFallback.trending || [])
        setSpotlight(homeFeedFallback.spotlight || [])
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="home-page">
      <div className="home-feed">
        <div className="home-feed-section">
          <div className="home-feed-head">
            <h2 className="home-feed-title">Trending now</h2>
          </div>
          <HomeTrendRail>
            {trending.map((item) => (
              <div key={item.id} className="home-trend-rail-item" role="listitem">
                <TrendCard {...item} />
              </div>
            ))}
          </HomeTrendRail>
        </div>

        <div className="home-feed-section">
          <div className="home-feed-head">
            <h2 className="home-feed-title">In the spotlight</h2>
          </div>
          <HomeTrendRail>
            {spotlight.map((item) => (
              <div key={item.id} className="home-trend-rail-item" role="listitem">
                <TrendCard {...item} />
              </div>
            ))}
          </HomeTrendRail>
        </div>
      </div>
    </section>
  )
}
