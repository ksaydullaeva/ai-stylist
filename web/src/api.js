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

  /** POST /api/v1/validate-images — check item is garment, user_photo is full-body person */
  async validateImages(itemFile, userPhotoFile) {
    const form = new FormData();
    form.append('item', itemFile);
    form.append('user_photo', userPhotoFile);
    const res = await fetch(`${getBase()}/api/v1/validate-images`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Validation failed');
    return res.json();
  },

  /** POST /api/v1/validate-item — Step 1 validation only */
  async validateItem(itemFile) {
    const form = new FormData();
    form.append('item', itemFile);
    const res = await fetch(`${getBase()}/api/v1/validate-item`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Validation failed');
    return res.json();
  },

  /** POST /api/v1/validate-user-photo — Step 2 validation only */
  async validateUserPhoto(userPhotoFile) {
    const form = new FormData();
    form.append('user_photo', userPhotoFile);
    const res = await fetch(`${getBase()}/api/v1/validate-user-photo`, { method: 'POST', body: form });
    if (!res.ok) throw new Error('Validation failed');
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
      let message = `Server error (${res.status}).`;
      try {
        const j = JSON.parse(text);
        message = j.detail || message;
      } catch {
        if (text.startsWith('<')) {
          message = `Server error (${res.status}). Backend may be unavailable or returned an error page.`;
        } else if (text && text.length <= 300) message = text;
      }
      throw new Error(message);
    }
    return res.json();
  },

  /**
   * POST /api/v1/full-pipeline-stream — analyze + suggest + generate item images, streams NDJSON progress.
   * onProgress(percent, message) is called for each progress event; resolves with result data.
   * userPhoto: optional File for context-aware suggestions (skin tone, hairstyle, etc.).
   */
  async fullPipelineStream(file, occasions = 'casual,smart-casual,date night', onProgress, userPhoto = null, onSuggestionsReady = null, onOutfitReady = null) {
    const form = new FormData();
    form.append('file', file);
    form.append('occasions', occasions ?? '');
    if (userPhoto && userPhoto instanceof File) {
      form.append('user_photo', userPhoto);
    }
    const res = await fetch(`${getBase()}/api/v1/full-pipeline-stream`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      let message = `Server error (${res.status}).`;
      try {
        const j = JSON.parse(text);
        message = j.detail || message;
      } catch {
        if (text.startsWith('<')) {
          message = `Server error (${res.status}). Backend may be unavailable or returned an error page.`;
        } else if (text && text.length <= 300) {
          message = text;
        }
      }
      throw new Error(message);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let firstLine = true;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (firstLine && trimmed.startsWith('<')) {
          throw new Error('Server returned an error page instead of data. Backend may be down or misconfigured.');
        }
        firstLine = false;
        let obj;
        try {
          obj = JSON.parse(trimmed);
        } catch {
          continue;
        }
        if (obj.type === 'progress' && typeof obj.percent === 'number' && onProgress) {
          onProgress(obj.percent, obj.message ?? '');
        } else if (obj.type === 'suggestions_ready' && obj.data != null && onSuggestionsReady) {
          onSuggestionsReady(obj.data);
        } else if (obj.type === 'outfit_ready' && obj.data != null && onOutfitReady) {
          onOutfitReady(obj.data);
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

  /** Full URL for an image served by /outputs/{filename} */
  imageUrl(pathOrFilename) {
    if (!pathOrFilename) return '';
    // If it's already a full URL, return it
    if (pathOrFilename.startsWith('http')) return pathOrFilename;
    // Prepend /outputs/ if it's just a filename or path that doesn't have it
    let path = pathOrFilename;
    if (!path.startsWith('/')) {
      path = `/outputs/${path}`;
    } else if (!path.startsWith('/outputs/') && !path.startsWith('/uploads/')) {
      // If it starts with /api/v1/images/, we still handle it for legacy DB records
      if (path.startsWith('/api/v1/images/')) {
        path = path.replace('/api/v1/images/', '/outputs/');
      } else {
        path = `/outputs${path}`;
      }
    }
    return `${getBase()}${path}`;
  },

  /**
   * POST /api/v1/try-on — generate image of person wearing the outfit (Gemini 2.5 Flash).
   * userPhoto: File (image of the person).
   * outfit: { items: [{ type, color, image_url }], style_title? } — same shape as pipeline result outfit.
   * garmentImage: optional File — source garment = the initial clothing item image the user sent
   *   (with their optional self image) at the start; improves try-on by including the actual piece.
   * outfitId: optional number — DB outfit ID to save the try-on image for later reference.
   * Returns { try_on_url: "/outputs/xxx.jpg" }.
   */
  async tryOn(userPhoto, outfit, garmentImage = null, outfitId = null) {
    const form = new FormData();
    if (userPhoto && userPhoto instanceof File) {
      form.append('user_photo', userPhoto);
    }
    form.append('outfit', JSON.stringify(outfit));
    if (garmentImage && garmentImage instanceof File) {
      form.append('garment_image', garmentImage);
    }
    if (outfitId != null && typeof outfitId === 'number') {
      form.append('outfit_id', String(outfitId));
    }
    const res = await fetch(`${getBase()}/api/v1/try-on`, { method: 'POST', body: form });
    if (!res.ok) {
      const text = await res.text();
      let message = `Server error (${res.status}).`;
      try {
        const j = JSON.parse(text);
        if (typeof j.detail === 'string') {
          message = j.detail;
        } else if (Array.isArray(j.detail)) {
          message = j.detail.map((d) => d?.msg || d?.message || JSON.stringify(d)).join('; ');
        } else if (j.detail && typeof j.detail === 'object') {
          message = j.detail.message || JSON.stringify(j.detail);
        } else {
          message = j.message || message;
        }
      } catch {
        if (text.startsWith('<')) {
          message = `Server error (${res.status}). Backend may be unavailable or returned an error page.`;
        } else if (text && text.length <= 300) message = text;
      }
      throw new Error(message);
    }
    return res.json();
  },

  /** GET /api/v1/outfits — list all saved looks for later reference */
  async getSavedOutfits(limit = 50) {
    const res = await fetch(`${getBase()}/api/v1/outfits?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to load saved looks');
    return res.json();
  },

  /** POST /api/v1/outfits — save a single look for later reference. tryOnUrl: optional /outputs/xxx if try-on was already generated. */
  async saveOutfit(outfit, imageResult, imageId, attributes, tryOnUrl = null) {
    const payload = {
      outfit,
      image_result: imageResult,
      image_id: imageId,
      attributes: attributes || {},
    };
    if (tryOnUrl) payload.try_on_url = tryOnUrl;
    const res = await fetch(`${getBase()}/api/v1/outfits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text();
      let message = 'Failed to save look';
      try {
        const j = JSON.parse(text);
        message = j.detail || message;
      } catch {
        if (text && text.length <= 200) message = text;
      }
      throw new Error(message);
    }
    return res.json();
  },

  async deleteOutfit(id) {
    const res = await fetch(`${getBase()}/api/v1/outfits/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || 'Failed to delete outfit');
    }
    return res.json();
  },

  /**
   * POST /api/v1/load-demo — load test outfits with placeholder images (no Gemini).
   * Returns same shape as full-pipeline for testing lookbook, try-on, and saved looks without using tokens.
   */
  async loadDemo() {
    const res = await fetch(`${getBase()}/api/v1/load-demo`, { method: 'POST' });
    if (!res.ok) {
      const text = await res.text();
      let message = `Demo failed (${res.status}).`;
      try {
        const j = JSON.parse(text);
        message = j.detail || message;
      } catch {
        if (text && text.length <= 300) message = text;
      }
      throw new Error(message);
    }
    return res.json();
  },

  async deleteAllOutfits() {
    try {
      const resp = await fetch(`${getBase()}/api/v1/outfits`, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error('Delete all failed')
      return await resp.json()
    } catch (err) {
      console.error(err)
      throw err
    }
  },
};
