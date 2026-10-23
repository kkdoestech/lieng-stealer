# 16 — Deployment

> **Goal:** run the backend with a production server, build the frontend into static files, and
> understand how the two are configured to find each other on the internet.
> **You will build:** `backend/Procfile`.
> **Time:** ~45 minutes.
> **Prerequisites:** [15](16-building-the-ui.md).

---

## The big picture

On your laptop you run two development servers (`python app.py` and `npm run dev`). Development servers
are built for convenience (auto-reload, helpful errors), not for real traffic. In production:

```
                       https://your-frontend.vercel.app                https://your-api.onrender.com
 user's browser ──────► static files (index.html, JS, CSS) ──fetch──► gunicorn ──► Flask app (app.py)
                        built once by `npm run build`                  2 worker processes, each with
                        served by a CDN, no Python needed              its own WinRateDB in memory
```

| Part | Development | Production |
|------|-------------|------------|
| Backend server | Flask dev server (`python app.py`) | **gunicorn** (`Procfile`) |
| Frontend | Vite dev server, compiles on the fly | **`npm run build`** → static files in `dist/` |
| API address | `http://127.0.0.1:5000` (default) | set by **`VITE_API_URL`** at build time |
| Secrets | your shell | the hosting platform's environment-variable settings |

The project's README suggests **Render or Railway** for the backend and **Vercel** for the frontend. The
steps below are the same idea on any platform.

---

## Concepts you need

### WSGI and gunicorn

Python web apps talk to web servers through a standard interface called **WSGI**. Flask's `app` object
is a WSGI application. **gunicorn** is a production WSGI server: it starts several **worker processes**
(remember chapter 7: separate processes can work in parallel), each running a copy of your app, and
spreads incoming requests among them. If a worker crashes, gunicorn starts a new one.

### Build-time vs run-time configuration

The frontend's `import.meta.env.VITE_API_URL` is **replaced by its value when you run `npm run build`**.
The value is baked into the JavaScript file. Changing it later on the server does nothing; you must
rebuild. And because it ends up in a file anyone can download, **never put secrets in `VITE_`
variables**. The OpenRouter key stays on the backend for exactly this reason.

---

## Step 16.1 — The Procfile

📄 **File:** `backend/Procfile` — *create this file*

```text
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

**How it works**

- A **Procfile** (a Heroku convention also used by Railway, Render and others) lists the processes to
  run. `web:` is the one that receives HTTP traffic.
- `app:app` = "module `app` (the file `app.py`), object `app` (the Flask instance)".
- `--bind 0.0.0.0:$PORT`: listen on all interfaces, on the port the platform assigns in `$PORT`.
- `--workers 2`: two processes. Each loads the 455-record database (~150 KB) at start-up, so memory is
  no concern. Our requests are short and CPU-bound, so a rule of thumb is about 1–2 workers per CPU core.
- `--timeout 120`: kill a worker stuck for more than 120 s. `/api/analyze` may wait up to 20 s for the
  LLM, well within that.

> 💡 The README's deployment table says `gunicorn -w 4 …` while the Procfile says `--workers 2`. The
> Procfile is what actually runs.

🧪 **Mini-check** (Linux/macOS; gunicorn does not run on Windows, where `waitress` is a common alternative:
`pip install waitress` then `waitress-serve --port=8000 app:app`). From `backend/`:

```bash
PORT=8000 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

Expected output (dates and process numbers differ):

```
[INFO] Starting gunicorn 22.0.0
[INFO] Listening at: http://0.0.0.0:8000 (35382)
[INFO] Using worker: sync
[INFO] Booting worker with pid: 35384
[INFO] Booting worker with pid: 35385
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/health
```

```json
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

Stop it with Ctrl-C.

---

## Step 16.2 — Build the frontend

From `frontend/`, build with the address where your API will live (here a placeholder):

```bash
VITE_API_URL=https://api.example.com npm run build
```

> 🪟 **Windows PowerShell:** `$env:VITE_API_URL="https://api.example.com"; npm run build`

Expected output (file hashes differ):

```
✓ 17 modules transformed.
dist/index.html                   0.72 kB │ gzip:  0.41 kB
dist/assets/index-DqGmTrCk.css   12.43 kB │ gzip:  2.91 kB
dist/assets/index-BIOuCm5V.js   233.11 kB │ gzip: 72.24 kB
✓ built in 252ms
```

Vite has **bundled** all your JSX, React itself and the CSS into a few optimised files, with a hash in
each file name (so browsers re-download them only when they change). Prove the URL was baked in:

```bash
grep -o "https://api.example.com" dist/assets/*.js
```

```
dist/assets/index-BIOuCm5V.js:https://api.example.com
```

`npm run preview` serves `dist/` locally so you can test the production build. Instead of passing the
variable on the command line every time, you can create `frontend/.env.production` containing
`VITE_API_URL=https://your-api.onrender.com`. Vite reads it automatically during `npm run build`.

---

## Step 16.3 — Deploying (outline)

The exact clicks differ per platform and change over time, so here are the settings rather than
screenshots.

**Backend (e.g. Render "Web Service" or Railway):**

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | taken from the `Procfile` (or paste its command) |
| Environment variables | `OPENROUTER_API_KEY` (optional; without it the rule-based fallback is used) |
| Health check path | `/health` |

The server does **not** run the generator: it needs `backend/data/winrates.json` to be **committed**.
That's why `.gitignore` has the `!backend/data/winrates.json` exception (chapter 2).

**Frontend (e.g. Vercel or Netlify):**

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Environment variables | `VITE_API_URL` = your backend's public URL (no trailing slash) |

> ⚠️ **Pitfall: CORS wide open.** `app.py` allows **any** website to call the API (`"origins": "*"`).
> For a free, public, read-only calculator that's acceptable. But it also means any site can use your
> server (and your OpenRouter quota, via `/api/analyze`). In production, restrict it to your frontend:
>
> ```python
> FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
> CORS(app, resources={r"/api/*": {"origins": FRONTEND_ORIGIN}})
> ```
>
> Rate limiting (e.g. the `Flask-Limiter` extension) on `/api/analyze` would protect the LLM quota.

---

## ✅ Checkpoint: run everything locally

A full check, from a clean terminal session:

```bash
# 1. Backend tests
cd backend && source .venv/bin/activate
python -m pytest -q                                  # → 58 passed

# 2. Data is reproducible
python -m src.generator --exact --output /tmp/check.json
cmp /tmp/check.json data/winrates.json && echo IDENTICAL

# 3. CLI
python -m src.cli --hand "As Kh Qd" | tail -n 9      # → ACTION: RAISE / ALL-IN RECOMMENDED

# 4. Production backend (leave running)
PORT=5000 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

# 5. In a second terminal: production frontend against it
cd frontend
npm run build && npm run preview                      # → http://localhost:4173
```

Open http://localhost:4173. The dashboard should load and show **ACTION: RAISE / ALL-IN** for
`As Kh Qd`. (No `VITE_API_URL` was set for this build, so it uses the default `http://127.0.0.1:5000`,
which is our gunicorn.)

Commit:

```bash
git add backend/Procfile && git commit -m "chore: production Procfile"
```

**Congratulations: you have rebuilt the entire project.** Every file in the original repository (apart
from the documentation and the unused starter assets) now exists in your version, and the tests prove it
behaves the same.

## Recap

- Production backend = **gunicorn** with several worker processes, configured by the `Procfile`.
- Production frontend = static files from **`npm run build`**; `VITE_API_URL` is baked in **at build time**
  and must never contain secrets.
- Secrets (`OPENROUTER_API_KEY`) live in the hosting platform's environment variables.
- `winrates.json` must be committed, because servers don't regenerate it.
- Pitfall: CORS allows every origin; consider restricting it and rate-limiting the LLM endpoint.

**Next:** [17 — Pitfalls and next steps](18-pitfalls-and-next-steps.md)
