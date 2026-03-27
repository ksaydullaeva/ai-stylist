import React from 'react'
import { api } from '../api'

export default function LensPage({ onHeader }) {
  const [file, setFile] = React.useState(null)
  const [preview, setPreview] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [bounceKey, setBounceKey] = React.useState(0)
  const [error, setError] = React.useState(null)
  const [results, setResults] = React.useState([])
  const [step, setStep] = React.useState('upload') // upload | results | map
  const [selected, setSelected] = React.useState(null)

  const onPick = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setError(null)
    setResults([])
    setSelected(null)
    setStep('upload')
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(f)
  }

  const runSearch = async () => {
    if (!file) return
    // Remount the hint dots so the animation restarts every SEARCH click.
    setBounceKey((k) => k + 1)
    setLoading(true)
    setError(null)
    try {
      // Keep a short deliberate loading state for better UX.
      const minDelayMs = 3500 + Math.floor(Math.random() * 1500) // 3.5s - 5.0s
      const [data] = await Promise.all([
        api.lensSearch(file, 12, null),
        new Promise((resolve) => setTimeout(resolve, minDelayMs)),
      ])
      setResults(data.results || [])
      setSelected(null)
      setStep('results')
    } catch (e) {
      setError(e?.message || 'Lens search failed')
    } finally {
      setLoading(false)
    }
  }

  const openMap = (r) => {
    setSelected(r || null)
    setStep('map')
  }

  const backFromMap = () => {
    setSelected(null)
    setStep('results')
  }

  const shortDescription = (r) => {
    const doc = (r?.document || '').trim()
    if (!doc) return ''
    const parts = doc.split('\n').map(s => s.trim()).filter(Boolean)
    // Typical stored doc: NAME \n category \n description...
    if (parts.length >= 3) return parts.slice(2).join(' ')
    if (parts.length === 2) return parts[1]
    return ''
  }

  React.useEffect(() => {
    if (!onHeader) return
    if (step === 'map') {
      onHeader({
        title: 'Find Your Way',
        tagline: 'Follow the path to reach your selected store inside the mall.',
      })
    } else if (step === 'results') {
      onHeader({
        title: 'Clothing Lens',
        tagline: 'Here are the closest matches we found. Tap MAP to navigate to a store.',
      })
    } else {
      onHeader({
        title: 'Clothing Lens',
        tagline: 'Upload a clothing photo to find similar items and get directions to the matching store.',
      })
    }
  }, [step, onHeader])

  return (
    <section className="lens-container">
      {step === 'upload' && (
        <div className="lens-upload-screen">
          <div className="lens-upload-card">
            <div className="lens-dropzone" onClick={() => document.getElementById('lens-input').click()}>
              <input id="lens-input" type="file" className="hidden" accept="image/*" onChange={onPick} />
              <div className={`lens-dropzone-inner${preview ? '' : ' lens-dropzone-inner--empty'}`}>
                {preview ? (
                  <div className="lens-query-preview">
                    <img src={preview} alt="Lens query" />
                    {/* Visual hint circles (matches your design mockups; not actual detections) */}
                    {loading && (
                      <>
                        <span key={`lens-dot-${bounceKey}-c1`} className="lens-circle c1 lens-bounce" />
                        <span key={`lens-dot-${bounceKey}-c2`} className="lens-circle c2 lens-bounce" />
                        <span key={`lens-dot-${bounceKey}-c3`} className="lens-circle c3 lens-bounce" />
                        <span key={`lens-dot-${bounceKey}-c4`} className="lens-circle c4 lens-bounce" />
                        <span key={`lens-dot-${bounceKey}-c5`} className="lens-circle c5 lens-bounce" />
                        <span key={`lens-dot-${bounceKey}-c6`} className="lens-circle c6 lens-bounce" />
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="lens-dropzone-icon" aria-hidden>
                      <img className="lens-upload-icon" src="/icons/clothing-upload.png" alt="" />
                    </div>
                    <div className="lens-dropzone-text">Drop the item you want to find.</div>
                    <div className="lens-dropzone-hint">JPEG, JPG, and PNG formats, up to 5 MB</div>
                  </>
                )}
              </div>
            </div>

            <button className="btn-primary lens-search-btn" type="button" onClick={runSearch} disabled={!file || loading}>
              {loading ? 'Searching…' : 'SEARCH'}
            </button>

            {error && <div className="banner error lens-error" style={{ width: '100%', marginBottom: 0 }}>{error}</div>}
          </div>
        </div>
      )}

      {step === 'results' && (
        <div className="lens-results-screen">
          <div className="lens-results-grid">
            {results.map((r) => (
              <div key={r.id} className="lens-store-card">
                <div className="lens-store-img">
                  {r.image_url ? (
                    <div className="lens-store-img-inner">
                      <img src={r.image_url} alt={r.name || r.product_id || 'Zara item'} />
                    </div>
                  ) : null}
                </div>

                <div className="lens-store-body">
                  <div className="lens-store-brand">ZARA</div>
                  <div className="lens-store-title">{r.name || 'Zara item'}</div>
                  <div className="lens-store-desc">{shortDescription(r) || (r.zara_category || '')}</div>

                  <div className="lens-store-price">Price unavailable</div>

                  <button className="btn-secondary lens-map-btn" type="button" onClick={() => openMap(r)}>
                    <span className="lens-map-icon" aria-hidden>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.75" />
                        <path d="M12 3v3M12 18v3M3 12h3M18 12h3" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
                      </svg>
                    </span>
                    <span className="lens-map-label">MAP</span>
                  </button>
                </div>
              </div>
            ))}
          </div>

          {results.length === 0 && (
            <p className="saved-outfits-empty" style={{ marginTop: 20 }}>
              Upload an image and run search.
            </p>
          )}
        </div>
      )}

      {step === 'map' && (
        <div className="lens-map-screen">
          <div className="lens-map-visual" aria-hidden>
            <img className="lens-map-img" src="/map-mock.png" alt="Mall map" />
          </div>

          <button className="lens-back-btn btn-primary" type="button" onClick={backFromMap}>
            BACK
          </button>
        </div>
      )}
    </section>
  )
}

