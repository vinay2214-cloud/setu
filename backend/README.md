# Setu backend

From this directory, create and activate a virtual environment, install `requirements.txt`, then run:

```bash
uvicorn app.main:app --reload --port 8000
```

The SQLite schema is initialized from `db/schema.sql` on startup. The API defaults to the offline mock provider.
