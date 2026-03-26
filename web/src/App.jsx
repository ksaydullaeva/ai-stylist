import { useState, useCallback, useEffect, useMemo } from 'react'
import { api } from './api'
import './App.css'

// Internal Components
import LoadingOverlay from './components/LoadingOverlay'
import TryOnModal from './components/TryOnModal'
import Header from './components/Header'

// Pages
import StudioPage from './pages/StudioPage'
import LookbookPage from './pages/LookbookPage'
import PastLookbooksPage from './pages/PastLookbooksPage'
import LensPage from './pages/LensPage'

function BottomNav({ activeTab, onHome, onMatch, onLens }) {
  return (
    <nav className="bottom-nav" aria-label="Primary">
      <button type="button" className={`bottom-nav-item ${activeTab === 'home' ? 'active' : ''}`} onClick={onHome}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M3 10.5 12 4l9 6.5" />
          <path d="M5.5 10v9h13v-9" />
        </svg>
        <span>Home</span>
      </button>
      <button type="button" className={`bottom-nav-item ${activeTab === 'match' ? 'active' : ''}`} onClick={onMatch}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <rect x="5" y="5" width="14" height="14" rx="2" />
          <path d="M9 12h6" />
          <path d="M12 9v6" />
        </svg>
        <span>Match</span>
      </button>
      <button type="button" className={`bottom-nav-item ${activeTab === 'lens' ? 'active' : ''}`} onClick={onLens}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M11 4a7 7 0 1 0 4.95 11.95L20 20" />
          <path d="M11 8v3l2.2 1.2" />
        </svg>
        <span>Lens</span>
      </button>
      <button type="button" className="bottom-nav-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M19.4 15a1.6 1.6 0 0 0 .32 1.76l.05.05a2 2 0 1 1-2.83 2.83l-.05-.05a1.6 1.6 0 0 0-1.76-.32 1.6 1.6 0 0 0-.97 1.46V21a2 2 0 1 1-4 0v-.08a1.6 1.6 0 0 0-.97-1.46 1.6 1.6 0 0 0-1.76.32l-.05.05a2 2 0 1 1-2.83-2.83l.05-.05A1.6 1.6 0 0 0 4.6 15a1.6 1.6 0 0 0-1.46-.97H3a2 2 0 1 1 0-4h.08a1.6 1.6 0 0 0 1.46-.97 1.6 1.6 0 0 0-.32-1.76l-.05-.05a2 2 0 1 1 2.83-2.83l.05.05a1.6 1.6 0 0 0 1.76.32H8.8a1.6 1.6 0 0 0 .97-1.46V3a2 2 0 1 1 4 0v.08a1.6 1.6 0 0 0 .97 1.46h.01a1.6 1.6 0 0 0 1.76-.32l.05-.05a2 2 0 1 1 2.83 2.83l-.05.05a1.6 1.6 0 0 0-.32 1.76v.01a1.6 1.6 0 0 0 1.46.97H21a2 2 0 1 1 0 4h-.08a1.6 1.6 0 0 0-1.52 1.21" />
        </svg>
        <span>Settings</span>
      </button>
    </nav>
  )
}

export default function App() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [userPhoto, setUserPhoto] = useState(null)
  const [userPhotoPreview, setUserPhotoPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [backendOk, setBackendOk] = useState(null)
  const [progress, setProgress] = useState(0)
  const [activeTag, setActiveTag] = useState('All')
  const [activeView, setActiveView] = useState('match') // match | home | lens
  const [headerOverride, setHeaderOverride] = useState(null)
  const [lensResetKey, setLensResetKey] = useState(0)

  // Try-on state
  const [tryOnOutfitIndex, setTryOnOutfitIndex] = useState(null)
  const [tryOnLoading, setTryOnLoading] = useState(false)
  const [tryOnResultUrl, setTryOnResultUrl] = useState(null)
  const [tryOnError, setTryOnError] = useState(null)
  // Per-outfit try-on result URLs (current session): outfit id or `i-${index}` -> url
  const [outfitTryOnUrls, setOutfitTryOnUrls] = useState({})

  // Saved looks (user chooses which outfits to save for later reference)
  const [savedOutfitsView, setSavedOutfitsView] = useState(false)
  const [savedOutfits, setSavedOutfits] = useState([])
  const [savedOutfitsLoading, setSavedOutfitsLoading] = useState(false)

  // Phase tracking: 0 = Studio, 1 = Lookbook
  const stage = result ? 1 : 0

  // Load saved looks on mount for the Saved looks page
  useEffect(() => {
    let cancelled = false
    api.getSavedOutfits().then((data) => {
      if (!cancelled) setSavedOutfits(data.outfits || [])
    }).catch(() => { if (!cancelled) setSavedOutfits([]) })
    return () => { cancelled = true }
  }, [])

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
    // Reset pipeline/try-on state so streaming updates render cleanly.
    setResult(null)
    setTryOnOutfitIndex(null)
    setTryOnResultUrl(null)
    setTryOnError(null)
    setOutfitTryOnUrls({})
    try {
      const data = await api.fullPipelineStream(
        file,
        'casual,smart-casual,business casual,date night',
        (percent) => {
          setProgress(percent)
        },
        userPhoto,
        // Sent once: all outfit cards (text) are ready.
        (suggestions) => {
          setResult(suggestions)
        },
        // Sent multiple times: each outfit images get generated.
        (payload) => {
          const { index, outfit, image_result } = payload || {}
          if (index == null || !outfit) return
          setResult((prev) => {
            if (!prev) return prev
            const prevOutfits = prev.outfits?.outfits
            if (!Array.isArray(prevOutfits)) return prev

            const nextOutfitsArr = [...prevOutfits]
            nextOutfitsArr[index] = outfit

            const prevImageResults = Array.isArray(prev.image_results) ? prev.image_results : []
            const nextImageResults = [...prevImageResults]
            nextImageResults[index] = image_result

            return {
              ...prev,
              outfits: { ...prev.outfits, outfits: nextOutfitsArr },
              image_results: nextImageResults,
            }
          })
        }
      )
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

    const items = outfit.items ?? []
    const allItemImagesReady = items.length > 0 && items.every((it) => Boolean(it?.image_url))
    if (!allItemImagesReady) {
      setTryOnError('This outfit is still generating images. Please wait a moment.')
      return
    }

    setTryOnOutfitIndex(index)
    setTryOnLoading(true)
    setTryOnError(null)
    setTryOnResultUrl(null)

    try {
      const outfitPayload = {
        items: outfit.items ?? [],
        style_title: outfit.style_title,
        gender_context: result?.outfits?.gender_context ?? undefined,
        anchor_item: result?.outfits?.anchor_item ?? undefined,
      }
      const data = await api.tryOn(
        userPhoto || null,
        outfitPayload,
        file,
        outfit.id != null ? outfit.id : undefined
      )
      setTryOnResultUrl(data.try_on_url)
      const key = outfit.id != null ? outfit.id : `i-${index}`
      setOutfitTryOnUrls(prev => ({ ...prev, [key]: data.try_on_url }))
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
    setOutfitTryOnUrls({})
    setSavedOutfitsView(false)
    setActiveView('match')
    api.getSavedOutfits().then((data) => setSavedOutfits(data.outfits || [])).catch(() => setSavedOutfits([]))
  }

  const loadSavedOutfits = useCallback(async () => {
    setSavedOutfitsLoading(true)
    try {
      const data = await api.getSavedOutfits()
      setSavedOutfits(data.outfits || [])
      setSavedOutfitsView(true)
      setActiveView('home')
    } catch {
      setSavedOutfits([])
      setSavedOutfitsView(true)
      setActiveView('home')
    } finally {
      setSavedOutfitsLoading(false)
    }
  }, [])

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
      <LoadingOverlay loading={loading} progress={progress} />

      <TryOnModal
        outfit={result?.outfits?.outfits?.[tryOnOutfitIndex]}
        tryOnLoading={tryOnLoading}
        tryOnError={tryOnError}
        tryOnResultUrl={tryOnResultUrl}
        onClose={() => setTryOnOutfitIndex(null)}
      />

      <Header
        backendOk={backendOk}
        title={headerOverride?.title}
        tagline={headerOverride?.tagline}
      />

      <main>
        {activeView === 'lens' ? (
          <LensPage key={lensResetKey} onHeader={setHeaderOverride} />
        ) : savedOutfitsView ? (
          <PastLookbooksPage
            savedOutfits={savedOutfits}
            onBack={() => { setSavedOutfitsView(false); setActiveView('match') }}
            onDeleted={loadSavedOutfits}
          />
        ) : stage === 0 ? (
          <StudioPage
            preview={preview}
            userPhotoPreview={userPhotoPreview}
            userPhoto={userPhoto}
            onFileChange={onFileChange}
            onUserPhotoChange={onUserPhotoChange}
            onRemoveItem={() => { setFile(null); setPreview(null); }}
            onRemoveUserPhoto={() => { setUserPhoto(null); setUserPhotoPreview(null); }}
            runPipeline={runPipeline}
            loading={loading}
            file={file}
            error={error}
          />
        ) : (
          <LookbookPage
            result={result}
            preview={preview}
            styleTags={styleTags}
            activeTag={activeTag}
            setActiveTag={setActiveTag}
            loadSavedOutfits={loadSavedOutfits}
            savedOutfitsLoading={savedOutfitsLoading}
            reset={reset}
            runTryOn={runTryOn}
            outfitTryOnUrls={outfitTryOnUrls}
            filteredOutfits={filteredOutfits}
          />
        )}
      </main>

      <BottomNav
        activeTab={activeView}
        onHome={loadSavedOutfits}
        onMatch={reset}
        onLens={() => {
          setSavedOutfitsView(false)
          setHeaderOverride(null)
          setLensResetKey((k) => k + 1)
          setActiveView('lens')
        }}
      />

    </div>
  )
}
