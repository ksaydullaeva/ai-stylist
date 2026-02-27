# StyleAI — React Web App

React (Vite) web app that talks to the StyleAI FastAPI backend: upload a clothing image, get outfit suggestions and flat lay previews.

## Prerequisites

- Node 18+
- Backend running (see project root / `backend`)

## Setup

```bash
cd web
npm install
```

## Run

1. Start the backend (from repo root or `backend`):

   ```bash
   cd backend
   source venv/bin/activate   # or: .\venv\Scripts\activate on Windows
   uvicorn main:app --reload
   ```

2. Start the web app:

   ```bash
   cd web
   npm run dev
   ```

3. Open [http://localhost:5173](http://localhost:5173). The dev server proxies `/api` and `/health` to `http://localhost:8000`.

## Build

```bash
npm run build
npm run preview   # serve production build
```

For production, set `VITE_API_BASE` to your backend URL (e.g. `https://api.example.com`) so API and image requests point to the right host.

## API integration

This app uses a single backend flow:

- **POST /api/full-pipeline** — Upload image + occasions → analyze item, suggest outfits, generate all flat lay images (one shot)
- **GET /api/image/{filename}** — Generated flat lay images
- **GET /health** — Backend health check
