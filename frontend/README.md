# CorpusForge Dashboard

Next.js dashboard for CorpusForge operations.

```bash
cd frontend
npm install
npm run dev
```

By default the local dev server calls the backend at `http://localhost:8000`.
When run through Docker Compose, the container uses `INTERNAL_API_URL=http://api:8000`
and listens on `http://localhost:3001` unless `FRONTEND_PORT` is set.

The first screen is the working dashboard with overview, sources, documents, chat, retrieval debugging, evaluation, jobs, and settings surfaces.
