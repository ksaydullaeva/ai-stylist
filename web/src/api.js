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

  /** POST /api/analyze — upload image, get item attributes */
  async analyze(file) {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${getBase()}/api/analyze`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || 'Analysis failed');
    }
    return res.json();
  },

  /** POST /api/outfit-suggestions — get outfit suggestions from attributes */
  async getOutfitSuggestions(itemAttributes, occasions = ['casual', 'smart-casual']) {
    const res = await fetch(`${getBase()}/api/outfit-suggestions`, {
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

  /** POST /api/full-pipeline — analyze + suggest + generate all flatlays in one shot */
  async fullPipeline(file, occasions = 'casual,smart-casual,date night') {
    const form = new FormData();
    form.append('file', file);
    form.append('occasions', occasions);
    const res = await fetch(`${getBase()}/api/full-pipeline`, { method: 'POST', body: form });
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
   * POST /api/full-pipeline-stream — analyze + suggest + generate, streams NDJSON progress.
   * onProgress(percent, message) is called for each progress event; resolves with result data.
   */
  async fullPipelineStream(file, occasions = 'casual,smart-casual,date night', onProgress) {
    const form = new FormData();
    form.append('file', file);
    form.append('occasions', occasions ?? '');
    const res = await fetch(`${getBase()}/api/full-pipeline-stream`, { method: 'POST', body: form });
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

  /** Full URL for an image served by GET /api/image/{filename} */
  imageUrl(pathOrFilename) {
    const path = pathOrFilename.startsWith('/') ? pathOrFilename : `/api/image/${pathOrFilename}`;
    return `${getBase()}${path}`;
  },
};
