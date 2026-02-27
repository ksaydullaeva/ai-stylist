import { useState, useCallback, useEffect } from 'react'
import { api } from './api'
import './App.css'

const DEFAULT_OCCASIONS = ''

const LOADING_PHRASES = [
  'Good things take a moment…',
  'Your looks are worth the wait.',
  'Hang tight — we’re putting it all together.',
  'Great style doesn’t rush. Neither do we.',
  'Almost there. Your outfits are taking shape.',
  'Thanks for waiting. We’re making it good.',
  'Just a little longer…',
  'We’re working on something you’ll like.',
  'Sit back — we’ve got you.',
  'Worth the wait, we promise.',
  'Almost ready…',
  'We’re on it. Thanks for your patience.',
  'Good things are loading.',
  'Just a few more seconds…',
  'Your patience is appreciated.',
]

export default function App() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [occasions, setOccasions] = useState(DEFAULT_OCCASIONS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [backendOk, setBackendOk] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)
  const [loadingPhraseIndex, setLoadingPhraseIndex] = useState(0)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!loading) return
    setProgress(0)
    setLoadingPhraseIndex(0)
  }, [loading])

  useEffect(() => {
    if (!loading && progress > 0) setProgress(100)
  }, [loading, progress])

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
    setResult(null)
    const reader = new FileReader()
    reader.onload = () => setPreview(reader.result)
    reader.readAsDataURL(f)
  }

  const runPipeline = async () => {
    if (!file) {
      setError('Please select an image first.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    setProgress(0)
    try {
      const data = await api.fullPipelineStream(file, occasions, (percent) => {
        setProgress(percent)
        setLoadingPhraseIndex((i) => (i + 1) % LOADING_PHRASES.length)
      })
      setResult(data)
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setProgress(100)
      setLoading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
    setSelectedItem(null)
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="title">Your Personal AI Stylist</h1>
        <p className="tagline">Upload a clothing item — get outfit suggestions and flat lay previews</p>
        {backendOk === false && (
          <div className="banner error">
            Backend not reachable. Start it with: <code>cd backend && uvicorn main:app --reload</code>
          </div>
        )}
        {backendOk === null && (
          <button type="button" className="linkButton" onClick={checkBackend}>
            {/* Check backend connection */}
          </button>
        )}
      </header>

      <main className="main">
        {loading ? (
          <section className="loadingSection">
            <div className="progressBarWrap">
              <div
                className="progressBarTrack"
                role="progressbar"
                aria-valuenow={Math.round(progress)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Loading"
              >
                <div className="progressBarFill" style={{ width: `${progress}%` }} />
              </div>
              <p className="progressPercent">{Math.round(progress)}%</p>
            </div>
            <p className="loadingPhrase">{LOADING_PHRASES[loadingPhraseIndex]}</p>
            <p className="loadingHint">Creating your looks…</p>
          </section>
        ) : !result ? (
          <section className="uploadSection">
            <div
              className={`dropZone ${preview ? 'hasPreview' : ''}`}
              onClick={() => document.getElementById('fileInput').click()}
            >
              <input
                id="fileInput"
                type="file"
                accept="image/*"
                onChange={onFileChange}
                className="hiddenInput"
              />
              {preview ? (
                <div className="previewWrap">
                  <img src={preview} alt="Your item" className="previewImg" />
                  <span className="changeText">Click to change image</span>
                </div>
              ) : (
                <span className="dropText">Drop an image here or click to choose</span>
              )}
            </div>
            <label className="label">
              Occasions (comma-separated, or leave blank to auto-detect from image)
              <input
                type="text"
                value={occasions}
                onChange={(e) => setOccasions(e.target.value)}
                className="input"
                placeholder="e.g. casual, smart-casual, date night"
              />
            </label>
            {error && <div className="message error">{error}</div>}
            <div className="actions">
              <button
                type="button"
                className="button primary"
                onClick={runPipeline}
                disabled={loading || !file}
              >
                Get outfit suggestions
              </button>
              {file && (
                <button type="button" className="button secondary" onClick={reset}>
                  Clear
                </button>
              )}
            </div>
          </section>
        ) : (
          <section className="resultSection">
            <div className="resultHeader">
              <h2>Here are your outfit suggestions</h2>
              <button type="button" className="button secondary" onClick={reset}>
                Start over
              </button>
            </div>

            {result.outfits?.outfits?.length > 0 && (
              <div className="card">
                <div className="outfitsGrid">
                  {result.outfits.outfits.map((outfit, i) => {
                    const items = outfit?.items ?? []
                    const isSelected = selectedItem?.outfitIndex === i
                    return (
                      <div key={i} className="outfitCard">
                        {outfit && (
                          <>
                            <span className="outfitLabel">
                              {outfit.style_title} — {outfit.occasion}
                            </span>
                            {outfit.style_notes && (
                              <p className="outfitDescription">{outfit.style_notes}</p>
                            )}
                            {outfit.color_palette?.length > 0 && (
                              <p className="outfitPalette">Palette: {outfit.color_palette.join(', ')}</p>
                            )}
                          </>
                        )}
                        {items.length > 0 && (
                          <div className="flatlayItemsRow">
                            {items.map((item, j) => {
                              const active = isSelected && selectedItem?.itemIndex === j
                              const label = [item.color, item.type].filter(Boolean).join(' ') || item.category || 'Item'
                              const itemImgSrc = item.image_url
                                ? api.imageUrl(item.image_url)
                                : null
                              return (
                                <button
                                  key={j}
                                  type="button"
                                  className={`itemThumb ${active ? 'active' : ''}`}
                                  onClick={() => setSelectedItem(active ? null : { outfitIndex: i, itemIndex: j })}
                                  title="Click for description"
                                >
                                  {itemImgSrc ? (
                                    <img src={itemImgSrc} alt={label} className="itemThumbImg" />
                                  ) : (
                                    <span className="itemThumbLabel">{label}</span>
                                  )}
                                </button>
                              )
                            })}
                          </div>
                        )}
                        {isSelected && items[selectedItem.itemIndex] && (
                          <div className="itemDescription">
                            {(() => {
                              const item = items[selectedItem.itemIndex]
                              return (
                                <>
                                  <span className="itemDescriptionCategory">{item.category}</span>
                                  {item.enrichment && (
                                    <p className="itemDescriptionEnrichment">{item.enrichment}</p>
                                  )}
                                  {/* <p className="itemDescriptionText">{item.description}</p> */}
                                  {item.shopping_keywords && (
                                    <p className="itemDescriptionKeywords">You can find similar items by searching for: {item.shopping_keywords}</p>
                                  )}
                                </>
                              )
                            })()}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        <p></p>
      </footer>
    </div>
  )
}
