import { useState, useCallback, useEffect, useMemo } from 'react'
import { api } from './api'
import './App.css'

const LOADING_PHRASES = [
  'Curating your personal lookbook...',
  'Analyzing the details of your item...',
  'Finding the perfect match...',
  'Crafting your style profile...',
  'Almost ready to reveal your looks...',
  'Selecting complementary pieces...',
  'Designing with precision...',
]

const HangerIcon = () => (
  <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2v2m0 0a2 2 0 0 0-2 2v1h4V6a2 2 0 0 0-2-2zM4 19l8-12 8 12H4z" />
  </svg>
)

const PersonIcon = () => (
  <svg className="dropzone-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
)

export default function App() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [userPhoto, setUserPhoto] = useState(null)
  const [userPhotoPreview, setUserPhotoPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [backendOk, setBackendOk] = useState(null)
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0)
  const [progress, setProgress] = useState(0)
  const [activeTag, setActiveTag] = useState('All')

  // Try-on state
  const [tryOnOutfitIndex, setTryOnOutfitIndex] = useState(null)
  const [tryOnLoading, setTryOnLoading] = useState(false)
  const [tryOnResultUrl, setTryOnResultUrl] = useState(null)
  const [tryOnError, setTryOnError] = useState(null)

  // Phase tracking: 0 = Studio, 1 = Lookbook
  const stage = result ? 1 : 0

  useEffect(() => {
    if (!loading) return
    const interval = setInterval(() => {
      setLoadingPhraseIndex((i) => (i + 1) % LOADING_PHRASES.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [loading])

  const checkBackend = useCallback(async () => {
    try {
      await api.health()
      setBackendOk(true)
    } catch {
      setBackendOk(false)
    }
  }, [])

  const onFileChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setFile(f)
    setError(null)
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(f)
  }

  const onUserPhotoChange = (e) => {
    const f = e.target.files?.[0]
    if (!f) return
    setUserPhoto(f)
    const reader = new FileReader()
    reader.onload = () => setUserPhotoPreview(reader.result)
    reader.readAsDataURL(f)
  }

  const runPipeline = async () => {
    if (!file) {
      setError('Drop the item you want to style first.')
      return
    }
    setLoading(true)
    setError(null)
    setProgress(0)
    try {
      const data = await api.fullPipelineStream(file, '', (percent) => {
        setProgress(percent)
      }, userPhoto)
      setResult(data)
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  const runTryOn = async (index) => {
    const outfit = result?.outfits?.outfits?.[index]
    if (!outfit) return

    setTryOnOutfitIndex(index)
    setTryOnLoading(true)
    setTryOnError(null)
    setTryOnResultUrl(null)

    try {
      const data = await api.tryOn(userPhoto || null, { items: outfit.items ?? [] }, file)
      setTryOnResultUrl(data.try_on_url)
    } catch (err) {
      setTryOnError(err.message || 'Try-on failed.')
    } finally {
      setTryOnLoading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setUserPhoto(null)
    setUserPhotoPreview(null)
    setResult(null)
    setError(null)
    setTryOnOutfitIndex(null)
    setTryOnResultUrl(null)
  }

  const styleTags = useMemo(() => {
    if (!result?.outfits?.outfits) return ['All']
    const tags = new Set(['All'])
    result.outfits.outfits.forEach(o => {
      if (o.occasion) tags.add(o.occasion)
    })
    return Array.from(tags)
  }, [result])

  const filteredOutfits = useMemo(() => {
    if (!result?.outfits?.outfits) return []
    if (activeTag === 'All') return result.outfits.outfits
    return result.outfits.outfits.filter(o => o.occasion === activeTag)
  }, [result, activeTag])

  return (
    <div className="app">
      {loading && (
        <div className="loading-overlay">
          <div className="loading-container">
            <h2 className="loading-phrase">{LOADING_PHRASES[loadingPhraseIndex]}</h2>
            <div className="progress-bar-wrap">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
            <p className="loading-progress">{Math.round(progress)}%</p>
          </div>
        </div>
      )}

      {tryOnOutfitIndex !== null && (
        <div className="modal-overlay" onClick={() => setTryOnOutfitIndex(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Virtual Try-On</h3>
              <button className="modal-close" onClick={() => setTryOnOutfitIndex(null)}>×</button>
            </div>
            <div className="modal-body">
              {tryOnLoading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>
                  <div className="loading-spinner" style={{ margin: '0 auto 20px' }} />
                  <p>Merging the look with your photo...</p>
                </div>
              ) : tryOnError ? (
                <div className="banner error">{tryOnError}</div>
              ) : (
                <>
                  <p className="look-occasion" style={{ marginBottom: 0 }}>
                    {result.outfits.outfits[tryOnOutfitIndex].style_title}
                  </p>
                  {tryOnResultUrl ? (
                    <img src={api.imageUrl(tryOnResultUrl)} alt="Try-on result" className="try-on-result-img" />
                  ) : (
                    <div style={{ textAlign: 'center', padding: '40px' }}>
                      <p>Something went wrong. Please try again.</p>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <header className="header">
        <h1 className="title title-gradient">Style Studio</h1>
        <p className="tagline">Personalized AI styling for your unique wardrobe.</p>
        {backendOk === false && (
          <div className="banner error">
            Offline: Start backend with <code>uvicorn main:app --reload</code>
          </div>
        )}
      </header>

      <main>
        {stage === 0 ? (
          <section className="studio-container">
            <div className="dropzone-wrapper">
              <span className="dropzone-label">The Hero</span>
              <div
                className={`dropzone ${preview ? 'active' : ''}`}
                onClick={() => document.getElementById('item-input').click()}
              >
                <input id="item-input" type="file" className="hidden" accept="image/*" onChange={onFileChange} />
                {preview ? (
                  <div className="preview-container">
                    <img src={preview} alt="Item" className="preview-img item-preview" />
                    <button className="remove-photo-btn" onClick={e => { e.stopPropagation(); setFile(null); setPreview(null); }}>×</button>
                  </div>
                ) : (
                  <>
                    <HangerIcon />
                    <span className="dropzone-text">Drop the item you want to style.</span>
                  </>
                )}
              </div>
            </div>

            <div className="dropzone-wrapper">
              <span className="dropzone-label">The Model</span>
              <div
                className={`dropzone ${userPhotoPreview ? 'active' : ''}`}
                onClick={() => document.getElementById('user-input').click()}
              >
                <input id="user-input" type="file" className="hidden" accept="image/*" onChange={onUserPhotoChange} />
                {userPhotoPreview ? (
                  <div className="preview-container">
                    <img src={userPhotoPreview} alt="You" className="preview-img" />
                    <button className="remove-photo-btn" onClick={e => { e.stopPropagation(); setUserPhoto(null); setUserPhotoPreview(null); }}>×</button>
                  </div>
                ) : (
                  <>
                    <PersonIcon />
                    <span className="dropzone-text">Drop a photo of yourself.</span>
                  </>
                )}
              </div>
            </div>

            <div className="studio-footer">
              <p className="micro-copy">
                Optional: We’ll use a professional model if skipped.
              </p>
              {error && <div className="banner error" style={{ width: '100%', marginBottom: '0' }}>{error}</div>}
              <button
                className="btn-primary"
                onClick={runPipeline}
                disabled={!file || loading}
              >
                Create My Lookbook
              </button>
            </div>
          </section>
        ) : (
          <section className="lookbook-container">
            <div className="lookbook-header">
              <h2 className="lookbook-title">The Lookbook</h2>
              <div className="tags-container">
                {styleTags.map(tag => (
                  <button
                    key={tag}
                    className={`tag-pill ${activeTag === tag ? 'active' : ''}`}
                    onClick={() => setActiveTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
                <button className="tag-pill" onClick={reset}>New Session</button>
              </div>
            </div>

            <div className="masonry-grid">
              {filteredOutfits.map((outfit, i) => (
                <div key={i} className="look-card">
                  <div className="look-card-left">
                    <div className="look-card-img-wrap">
                      <img src={preview} alt="Your Item" className="look-card-img" />
                      <button className="fab-tryon" onClick={() => runTryOn(i)}>
                        Virtual Try-On
                      </button>
                    </div>
                  </div>

                  <div className="look-card-right">
                    <div className="look-card-info">
                      <h3 className="look-title">{outfit.style_title}</h3>
                      <p className="look-occasion">{outfit.occasion}</p>

                      <div className="suggestions-container">
                        <span className="suggestions-label">Pairs well with:</span>
                        <div className="look-items-list">
                          {outfit.items?.filter((_, idx) => idx > 0).map((item, j) => (
                            <div key={j} className="look-item-row">
                              <div className="look-item-thumb-small">
                                {item.image_url ? (
                                  <img src={api.imageUrl(item.image_url)} alt={item.category} />
                                ) : (
                                  <div className="look-item-placeholder" />
                                )}
                              </div>
                              <div className="look-item-details">
                                <span className="look-item-name">{item.color || ''} {item.type || item.category || 'Item'}</span>
                                {item.enrichment && <p className="look-item-desc">{item.enrichment}</p>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="look-notes-section">
                        <span className="suggestions-label">Stylist Notes:</span>
                        <p className="look-notes">{outfit.style_notes}</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer style={{ marginTop: '80px', textAlign: 'center', opacity: 0.5 }}>
        &copy; {new Date().getFullYear()} StyleAI. Built for SSENSE.
      </footer>
    </div>
  )
}
