/**
 * API client for StyleAI backend (FastAPI).
 * In dev, Vite proxies /api and /health to the backend; in production set VITE_API_BASE.
 */

const getBase = () => import.meta.env?.VITE_API_BASE ?? '';

export const api = {
  async health() {
    const res = await fetch(`${getBase()}/health`);
    if (!res.ok) throw new Error('Backend unreachable');
    return res.json();
  },

  /** POST /api/v1/analyze — upload image, get item attributes */
  async analyze(file) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${getBase()}/api/v1/analyze`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Analysis failed');
    }
    return res.json();
  },

  /** POST /api/v1/outfit-suggestions — get outfit suggestions from attributes */
  async getOutfitSuggestions(itemAttributes, occasions = ['casual', 'smart-casual']) {
    const res = await fetch(`${getBase()}/api/v1/outfit-suggestions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item_attributes: itemAttributes, occasions }),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Outfit suggestions failed');
    }
    return res.json();
  },

  /** POST /api/v1/full-pipeline — analyze + suggest + generate item images in one shot. userPhoto optional. */
  async fullPipeline(file, occasions = 'casual,smart-casual,date night', userPhoto = null) {
    const form = new FormData();
    form.append('file', file);
    form.append('occasions', occasions);
    if (userPhoto && userPhoto instanceof File) form.append('user_photo', userPhoto);
    const res = await fetch(`${getBase()}/api/v1/full-pipeline`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      try {
        const j = JSON.parse(text);
        throw new Error(j.detail || text || 'Pipeline failed');
      } catch (e) {
        if (e instanceof Error && e.message !== text) throw e;
        throw new Error(text || 'Pipeline failed');
      }
    }
    return res.json();
  },

  /**
   * POST /api/v1/full-pipeline-stream — analyze + suggest + generate item images, streams NDJSON progress.
   * onProgress(percent, message) is called for each progress event; resolves with result data.
   * userPhoto: optional File for context-aware suggestions (skin tone, hairstyle, etc.).
   */
  async fullPipelineStream(file, occasions = 'casual,smart-casual,date night', onProgress, userPhoto = null) {
    const form = new FormData();
    form.append('file', file);
    form.append('occasions', occasions ?? '');
    if (userPhoto && userPhoto instanceof File) {
      form.append('user_photo', userPhoto);
    }
    const res = await fetch(`${getBase()}/api/v1/full-pipeline-stream`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      try {
        const j = JSON.parse(text);
        throw new Error(j.detail || text || 'Pipeline failed');
      } catch (e) {
        if (e instanceof Error && e.message !== text) throw e;
        throw new Error(text || 'Pipeline failed');
      }
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let obj;
        try {
          obj = JSON.parse(trimmed);
        } catch {
          continue;
        }
        if (obj.type === 'progress' && typeof obj.percent === 'number' && onProgress) {
          onProgress(obj.percent, obj.message ?? '');
        } else if (obj.type === 'result' && obj.data != null) {
          return obj.data;
        } else if (obj.type === 'error') {
          throw new Error(obj.detail ?? 'Pipeline failed');
        }
      }
    }
    if (buffer.trim()) {
      try {
        const obj = JSON.parse(buffer.trim());
        if (obj.type === 'result' && obj.data != null) return obj.data;
        if (obj.type === 'error') throw new Error(obj.detail ?? 'Pipeline failed');
      } catch (e) {
        if (e instanceof Error) throw e;
      }
    }
    throw new Error('Pipeline did not return a result');
  },

  /** Full URL for an image served by GET /api/v1/images/{filename} */
  imageUrl(pathOrFilename) {
    const path = pathOrFilename.startsWith('/') ? pathOrFilename : `/api/v1/images/${pathOrFilename}`;
    return `${getBase()}${path}`;
  },

  /**
   * POST /api/v1/try-on — generate image of person wearing the outfit (Gemini 2.5 Flash).
   * userPhoto: File (image of the person).
   * outfit: { items: [{ type, color, image_url }], style_title? } — same shape as pipeline result outfit.
   * garmentImage: optional File — source garment = the initial clothing item image the user sent
   *   (with their optional self image) at the start; improves try-on by including the actual piece.
   * Returns { try_on_url: "/api/v1/images/xxx.jpg" }.
   */
  async tryOn(userPhoto, outfit, garmentImage = null) {
    const form = new FormData();
    form.append('user_photo', userPhoto);
    form.append('outfit', JSON.stringify(outfit));
    if (garmentImage && garmentImage instanceof File) {
      form.append('garment_image', garmentImage);
    }
    const res = await fetch(`${getBase()}/api/v1/try-on`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      try {
        const j = JSON.parse(text);
        throw new Error(j.detail || text || 'Try-on failed');
      } catch (e) {
        if (e instanceof Error && e.message !== text) throw e;
        throw new Error(text || 'Try-on failed');
      }
    }
    return res.json();
  },
};
