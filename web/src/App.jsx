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

  // Try-on state
  const [tryOnOutfitIndex, setTryOnOutfitIndex] = useState(null)
  const [tryOnLoading, setTryOnLoading] = useState(false)
  const [tryOnResultUrl, setTryOnResultUrl] = useState(null)
  const [tryOnError, setTryOnError] = useState(null)
  // Per-outfit try-on result URLs (current session): outfit id or `i-${index}` -> url
  const [outfitTryOnUrls, setOutfitTryOnUrls] = useState({})

  // Past lookbooks (saved outfits for later reference)
  const [savedOutfitsView, setSavedOutfitsView] = useState(false)
  const [savedOutfits, setSavedOutfits] = useState([])
  const [savedOutfitsLoading, setSavedOutfitsLoading] = useState(false)

  // Phase tracking: 0 = Studio, 1 = Lookbook
  const stage = result ? 1 : 0

  // Load saved outfits on mount so we can show recent lookbooks on Studio and Past lookbooks
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

  const loadDemo = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.loadDemo()
      setResult(data)
      setPreview(api.imageUrl(data.image_id))
    } catch (err) {
      setError(err.message || 'Failed to load demo.')
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
      const data = await api.tryOn(
        userPhoto || null,
        { items: outfit.items ?? [] },
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
    api.getSavedOutfits().then((data) => setSavedOutfits(data.outfits || [])).catch(() => setSavedOutfits([]))
  }

  const loadSavedOutfits = useCallback(async () => {
    setSavedOutfitsLoading(true)
    try {
      const data = await api.getSavedOutfits()
      setSavedOutfits(data.outfits || [])
      setSavedOutfitsView(true)
    } catch {
      setSavedOutfits([])
      setSavedOutfitsView(true)
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
        onToggleSaved={loadSavedOutfits}
        onReset={reset}
        savedOutfitsLoading={savedOutfitsLoading}
        backendOk={backendOk}
      />

      <main>
        {savedOutfitsView ? (
          <PastLookbooksPage
            savedOutfits={savedOutfits}
            onBack={() => setSavedOutfitsView(false)}
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
            loadDemo={loadDemo}
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

      <footer style={{ marginTop: '80px', textAlign: 'center', opacity: 0.5 }}>
        &copy; {new Date().getFullYear()} Style Studio.
      </footer>
    </div>
  )
}
