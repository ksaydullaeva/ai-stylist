# StyleAI Backend

FastAPI backend for outfit analysis, suggestions, and flat lay image generation.

## Database (PostgreSQL)

The app uses PostgreSQL. If the database does not exist, the server still starts but outfit persistence is skipped.

**Create the database** (default name: `styleai`):

```bash
# Using createdb (same user as in DATABASE_URL, e.g. postgres)
createdb styleai

# Or via psql
psql -U postgres -c "CREATE DATABASE styleai;"
```

Set `DATABASE_URL` in `.env` if you use different credentials, e.g.:

```
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/styleai
```

After the database exists, restart the server so tables are created on startup.

## Run

```bash
source venv/bin/activate
uvicorn main:app --reload
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs
