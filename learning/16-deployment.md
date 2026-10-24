# Lesson 16 — Deployment

> **Goal:** understand what it takes to run this project outside your laptop: the one-line
> `Procfile`, the split requirements, the environment variables and their defaults, CORS and the
> rate limit, and the frontend build that bakes the API address into a public JavaScript file. Then
> run the whole "production" pair locally.
> **Files:** [`backend/Procfile`](../backend/Procfile), [`backend/requirements.txt`](../backend/requirements.txt),
> [`backend/requirements-dev.txt`](../backend/requirements-dev.txt), [`backend/.env.example`](../backend/.env.example),
> [`frontend/package.json`](../frontend/package.json), [`frontend/vite.config.js`](../frontend/vite.config.js),
> [`frontend/src/App.jsx:6-8`](../frontend/src/App.jsx#L6-L8), README "Configuration and deployment".
> **Time:** ~40 min. **Before this:** [15 — Tests and performance](15-tests-and-performance.md).

---

## Where this fits

```
 DEVELOPMENT (lessons 10–13)                    PRODUCTION (this lesson)
 ───────────────────────────                    ────────────────────────
 python app.py   → Werkzeug dev server,         gunicorn app:app, 2 workers × 4 threads,
                   127.0.0.1:5000                 tables built once (--preload), $PORT
 npm run dev     → Vite dev server :5173        npm run build → dist/ (HTML + 1 JS + 1 CSS file)
 API address     → /api, proxied by Vite        VITE_API_URL at build time, or /api on the same host
 settings        → defaults in app.py           the hosting platform's environment settings

      browser ──GET──► static host (dist/) ─── index.html, assets/index-….js
         │
         └──fetch(VITE_API_URL + "/api/solve")──► gunicorn master (imports app.py once)
            CORS: page origin must be in              ├► worker 1: 4 threads ┐ share the tables'
                  CORS_ORIGINS                        └► worker 2: 4 threads ┘ memory pages
```

The repository contains one deployment file, the `Procfile`, plus `backend/.env.example`, which
documents the settings, and a CI workflow (lesson 15). Everything else is configuration you pass
in (environment variables) or a build step you run. README's "Configuration and deployment"
section names example platforms (Render or Railway for the backend, Vercel or Netlify for the
frontend); nothing in the repo is specific to any of them.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [Procfile:1](../backend/Procfile#L1) | The production start command, token by token. |
| 2 | [app.py:574](../backend/app.py#L574) and [app.py:99-144](../backend/app.py#L99-L144) | What gunicorn imports: `app = create_app()`, which loads the DB, builds the tables, sets up CORS and the limiter. |
| 3 | [app.py:50-60](../backend/app.py#L50-L60) and [app.py:147-160](../backend/app.py#L147-L160) | Every setting with its default, and how the environment overrides it. |
| 4 | [app.py:577-579](../backend/app.py#L577-L579) | The development entry point, which gunicorn never runs. |
| 5 | [requirements.txt:1-6](../backend/requirements.txt#L1-L6) and [requirements-dev.txt](../backend/requirements-dev.txt) | Five runtime pins; the tools stay in the dev file. |
| 6 | [App.jsx:6-8](../frontend/src/App.jsx#L6-L8) | `VITE_API_URL` and its same-origin default. |
| 7 | [package.json:6-12](../frontend/package.json#L6-L12) | `build` and `preview`. |
| 8 | [.gitignore:12-15](../.gitignore#L12-L15) | Secret files git ignores, and the one example it keeps. |

---

## Walkthrough

### 1. The `Procfile`, token by token

📍 [`backend/Procfile:1`](../backend/Procfile#L1)
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class gthread --threads 4 --timeout 60 --preload
```

A `Procfile` is a convention from Heroku that several platforms read: one line per process type,
`name: command`. The platform runs the command from the folder that holds the file (`backend/`).

| Token | Meaning |
|-------|---------|
| `web:` | The process type that receives HTTP traffic. |
| `gunicorn` | A production WSGI server (see the 💡 box). It replaces Flask's development server. |
| `app:app` | "Import the module `app` (`app.py`) and serve the variable `app` in it": `app = create_app()` at [app.py:574](../backend/app.py#L574). |
| `--bind 0.0.0.0:$PORT` | Listen on every network interface, on the port the platform assigns in `$PORT`. |
| `--workers 2` | Start two worker *processes*. |
| `--worker-class gthread --threads 4` | Each worker runs four threads, so up to 8 requests are handled at once. |
| `--timeout 60` | Restart a worker whose main loop has been silent for 60 seconds. With threaded workers this catches a hung process; it does not cut off a single slow request. |
| `--preload` | Import `app.py` once in the master process, *before* forking the workers. |

Because `app:app` names an object, the `if __name__ == "__main__":` block at
[app.py:577-579](../backend/app.py#L577-L579) never runs under gunicorn. That block is only for
`python app.py`, and it now listens on `127.0.0.1` unless `HOST` says otherwise.

### 2. Two workers, one build

Each worker is a separate Python process. Without `--preload`, gunicorn imports `app.py` **inside
each worker**, after forking, so `create_app()` runs twice: two `WinRateDB` loads, two
`CallingRangeModel` builds (about 60 ms each), two `RangeFinder` strength maps. With `--preload` the
master runs it once, then forks, and the workers start with the tables already built, sharing those
memory pages until something writes to them.

Measured locally on port 5055 (RSS is the memory a process can see; PSS divides shared pages among
the processes that share them, so the PSS values add up to the real total):

| Mode | Master | Each worker | Total PSS |
|------|--------|-------------|-----------|
| without `--preload` | 24.7 MB RSS (10.7 MB PSS) | 41.4 MB RSS (28.1–28.2 MB PSS) | about 67 MB |
| with `--preload` (the Procfile) | 44.1 MB RSS (15.1 MB PSS) | 36.4–36.9 MB RSS (13.5–14.8 MB PSS) | about 43 MB |

Without `--preload` the master never imports the app (24.7 MB is just gunicorn), and each worker
holds a full private copy. Sharing erodes slowly, because CPython writes reference counts into
objects it touches. Either way, nothing is shared *logically*: the tables are read-only, and requests
carry all their inputs, so it does not matter which worker or thread answers (lesson 11). That is
what makes adding workers, or machines, safe.

The threads are there for `/api/analyze`. With a key it waits for OpenRouter for up to
`OPENROUTER_TIMEOUT` seconds (15 by default, [app.py:59](../backend/app.py#L59), used at
[app.py:490](../backend/app.py#L490)). While one thread waits, the other three in that worker keep
answering `/api/solve`. With the old single-threaded `sync` workers, two slow analyses occupied
both workers and every solve behind them waited. Solves are CPU-bound but take 1–2 ms, so the GIL
costs little here.

### 3. The requirements

📍 [`backend/requirements.txt:1-6`](../backend/requirements.txt#L1-L6)
```
# Runtime dependencies for the API server (installed in production).
flask==3.0.3
flask-cors==4.0.1
flask-limiter==4.1.1
gunicorn==22.0.0
requests==2.31.0
```

| Package | Used by | Where it is listed |
|---------|---------|--------------------|
| `flask` | `app.py` | `requirements.txt` |
| `flask-cors` | CORS headers, [app.py:130-131](../backend/app.py#L130-L131) | `requirements.txt` |
| `flask-limiter` | the `/api/analyze` rate limit, [app.py:133-139](../backend/app.py#L133-L139) | `requirements.txt` |
| `gunicorn` | the `Procfile` | `requirements.txt` |
| `requests` | `/api/analyze` → OpenRouter ([app.py:473](../backend/app.py#L473)) | `requirements.txt` |
| `pytest`, `rich`, `ruff`, `mypy`, `types-requests` | tests, the CLI's colours, lint, types | [requirements-dev.txt](../backend/requirements-dev.txt), which starts with `-r requirements.txt` |

A production install gets only the five runtime packages. On a developer machine
`pip install -r requirements-dev.txt` installs both. The CLI still works without `rich`: it prints a
plain-text report instead (lesson 09; lesson 15 notes that no test runs that branch).

Every version is pinned exactly (`==`), so a fresh install today gets what the code was tested
with. What is not pinned: the dependencies of these packages (Werkzeug, Jinja2, …; the dev server
reports `Werkzeug/3.1.9`), file hashes, and the Python version. README says Python 3.11+, CI tests
on 3.12, the course machine's venv runs 3.12.3, and no `runtime.txt` or `.python-version` tells a
platform which one to use.

### 4. Environment variables

Every backend setting has a default in code:

📍 [`backend/app.py:50-60`](../backend/app.py#L50-L60)
```python
# Settings and their defaults. create_app() reads each one from the environment when it is set,
# and an explicit ``config`` argument overrides both (tests use that).
DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    "ANALYZE_RATE_LIMIT": "10 per minute",
    "RATELIMIT_STORAGE_URI": "memory://",
    "RATELIMIT_ENABLED": True,
    "OPENROUTER_API_KEY": "",
    "OPENROUTER_MODEL": "meta-llama/llama-3.1-8b-instruct:free",
    "OPENROUTER_TIMEOUT": 15.0,
}
```

`_settings_from_env` ([app.py:147-160](../backend/app.py#L147-L160)) reads each of these names
from the environment and converts it to the default's type: `"1"`, `"true"`, `"yes"` or `"on"` for a
bool, `float()` for a number, the raw text otherwise. So there are three layers, each overriding
the one before: the defaults, the environment, and `create_app(config=…)`, which is what tests use.

| Variable | Read at | When | Default |
|----------|---------|------|---------|
| `PORT` | [Procfile:1](../backend/Procfile#L1), [app.py:579](../backend/app.py#L579) | server start | 5000 for `python app.py`; gunicorn needs it set |
| `HOST` | [app.py:579](../backend/app.py#L579) | `python app.py` only | `127.0.0.1` |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT` | `create_app` | **start-up** | empty (→ rule-based text, lesson 10), Llama 3.1 8B, 15 s |
| `CORS_ORIGINS` | `create_app` | start-up | the two Vite dev origins |
| `ANALYZE_RATE_LIMIT`, `RATELIMIT_STORAGE_URI`, `RATELIMIT_ENABLED` | `create_app` | start-up | `10 per minute`, `memory://`, on |
| `VITE_API_URL` | [App.jsx:8](../frontend/src/App.jsx#L8) | **`npm run build`** | empty: `/api` on the page's own origin |

All backend settings are read **once, when the app is created**. With `--preload` that is the
master, before the fork. Changing a variable therefore needs a restart, which platforms do anyway
when you edit their settings.

[backend/.env.example](../backend/.env.example) lists the variables with their defaults and a
comment each. Note what git ignores:

📍 [`.gitignore:12-15`](../.gitignore#L12-L15)
```
# Secrets: never commit real environment files (backend/.env.example documents the variables)
.env
.env.*
!.env.example
```

`git check-ignore` confirms that `.env`, `backend/.env`, `frontend/.env`, `frontend/.env.production`
and `frontend/.env.local` are all ignored, and `backend/.env.example` is not: the `!` line un-ignores
it. But nothing in the backend *reads* a `.env` file (there is no `python-dotenv`), although the
example's first line says "Copy to backend/.env for local use". Its values reach the app only if
you export them, for example `set -a; . ./.env; set +a` before `python app.py` (weak spot 3). Vite,
on the other hand, automatically reads `frontend/.env` and `frontend/.env.production` during a build
if they exist; the repo has none.

### 5. `VITE_API_URL` is baked into the bundle

📍 [`frontend/src/App.jsx:6-8`](../frontend/src/App.jsx#L6-L8)
```jsx
// Empty by default: requests go to /api on the page's own origin, which the Vite dev server
// proxies to Flask (vite.config.js). Set VITE_API_URL at build time when the API lives elsewhere.
const API_BASE = import.meta.env.VITE_API_URL ?? "";
```

`import.meta.env.VITE_…` looks like a run-time lookup, but it is not. During `vite build`, Vite
replaces the expression with the *text* of the variable, then minifies. The browser later receives
a finished file with the URL written into it. Proof, from two builds into a scratch folder (never
into `frontend/dist`):

```bash
cd frontend
npx vite build --outDir /tmp/…/scratchpad/dist-default --emptyOutDir
VITE_API_URL=https://api.example.invalid npx vite build --outDir /tmp/…/scratchpad/dist-url --emptyOutDir
```

The first build's summary (paths shortened):

```
dist/index.html                   0.41 kB │ gzip:  0.29 kB
dist/assets/index-C6PIeJn2.css    7.87 kB │ gzip:  2.19 kB
dist/assets/index-FK4GEu6c.js   210.10 kB │ gzip: 66.11 kB
✓ built in 134ms
```

Searching the two JavaScript bundles (excerpts of the minified code):

```
default build:     …,_=``,v=`lieng-scope-lang`,…
with VITE_API_URL: …,_=`https://api.example.invalid`,v=`lieng-scope-lang`,…
```

Neither bundle contains the string `VITE_API_URL`. Three consequences:

1. **Changing the backend URL means rebuilding the frontend.** Setting the variable on the static
   host after the build does nothing.
2. **Anything in a `VITE_` variable is public.** Anyone can read it in the downloaded JavaScript.
   That is why the OpenRouter key lives on the backend, never in the frontend.
3. **Without the variable, the page calls `/api/solve` on its own host.** That is right when
   something on that host routes `/api` to Flask (a reverse proxy, or a platform rewrite rule). On a
   plain static host the request reaches the file server instead, which typically answers 404 or 405
   with an HTML page, and the UI says "Check your inputs: HTTP 404" (lesson 13, weak spot 1). The old
   default, `http://127.0.0.1:5000`, pointed every visitor at their own computer.

The proxy in [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) (forward `/api` to
`127.0.0.1:5000`) exists only in Vite's own servers: `npm run dev`, and `npm run preview`, whose
`preview.proxy` defaults to the same setting. A static host has no proxy.

### 6. CORS and the rate limit in production

If the page and the API live on different origins (the usual split: static host + Python host),
the browser reads an API answer only if it carries `Access-Control-Allow-Origin` for the page's
origin. Flask-CORS sends it only for the origins in `CORS_ORIGINS`
([app.py:130-131](../backend/app.py#L130-L131)), so in production you set it to your frontend's URL.
Measured on a local gunicorn started with `CORS_ORIGINS=http://localhost:4180`:

```
OPTIONS /api/solve, Origin http://localhost:4180 → 200, Access-Control-Allow-Origin: http://localhost:4180
OPTIONS /api/solve, Origin http://localhost:5173 → 200, no Access-Control-Allow-Origin header
```

Forget to set it, and the browser blocks every response from a perfectly healthy API. `fetch`
rejects, and the page shows "Can't reach the solver. Start the backend on port 5000 and try again."
(checked in headless Chromium against the same gunicorn, started with the default `CORS_ORIGINS`):
a development hint for a production configuration problem (weak spot 4).

CORS only stops *browsers on other sites* from reading answers. It does not stop a script calling
the API directly, so `/api/analyze`, the one endpoint that can spend money, also has a rate limit:
Flask-Limiter allows `ANALYZE_RATE_LIMIT` (10 per minute) per client, on that blueprint only
([app.py:133-139](../backend/app.py#L133-L139)). Two details matter once it runs under gunicorn:

- **`memory://` counts per worker.** Each worker process keeps its own counters. 25 requests from
  one client within a minute, against the two-worker gunicorn: 18 answered 200 and 7 answered 429
  (plus one more 200 from the page load just before), not 10. README says so; a shared store such
  as `RATELIMIT_STORAGE_URI=redis://…` makes it one limit.
- **"Per client" means "per connecting address"** (`get_remote_address`). Behind a platform's
  router every request arrives from the router, so all visitors share one bucket. With a 2-per-minute
  limit, three visitors with different `X-Forwarded-For` headers from the same `REMOTE_ADDR` got
  `200, 200, 429` (weak spot 1, exercise 6).

### 7. What is (and is not) in the repository

`git ls-files` shows three files that concern running the project elsewhere:
`backend/Procfile`, `backend/.env.example` and `.github/workflows/ci.yml`, whose three jobs (backend,
frontend, course) run on every push and pull request (lesson 15). There is still no:

- **frontend host config** (`vercel.json`, `netlify.toml`): the platform must be told the build
  command (`npm run build`), the output folder (`dist`), `VITE_API_URL` and any `/api` rewrite by
  hand;
- **container** (`Dockerfile`) or **backend host config** (`render.yaml`, `railway.json`);
- **runtime pins** for the platform: `runtime.txt`, `.python-version`, `.nvmrc`.
  `package.json`'s `engines` (`>=22.22.2`) is advisory, and CI asks for Python `3.12` and Node `22`.

### 8. A full local "production" run

You can rehearse a deployment on one machine. This exact sequence was run for this lesson, on
free ports (5055 for the API, 4180 for the static files), and stopped afterwards. It uses the
cross-origin setup, so it needs both `VITE_API_URL` and `CORS_ORIGINS`.

```bash
# terminal 1: the API, as the Procfile runs it (from backend/, venv active)
PORT=5055 CORS_ORIGINS=http://localhost:4180 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class gthread --threads 4 --timeout 60 --preload

# terminal 2: build the frontend for that API, then serve the static files (from frontend/)
VITE_API_URL=http://127.0.0.1:5055 npm run build
npm run preview -- --port 4180
```

gunicorn's log (timestamps removed):

```
[13960] [INFO] Starting gunicorn 22.0.0
[13960] [INFO] Listening at: http://0.0.0.0:5055 (13960)
[13960] [INFO] Using worker: gthread
[13963] [INFO] Booting worker with pid: 13963
[13964] [INFO] Booting worker with pid: 13964
```

Then, checked with curl and a headless browser (the course build went to a scratch folder):

```
GET  http://127.0.0.1:5055/health → {"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.1.0"}
GET  http://localhost:4180/        → 200, and its bundle contains _=`http://127.0.0.1:5055`
POST /api/solve (the default click) → "ev":131876.0, in 3.6–5.3 ms per request
page load in Chromium               → OPTIONS + POST /api/solve, OPTIONS + POST /api/analyze; "Raise / all-in" on screen
```

The `OPTIONS` requests are CORS **preflights**: a cross-origin `POST` with a JSON body makes the
browser ask first. Open http://localhost:4180 and the page works exactly as in development, but from
minified files and two gunicorn workers. Stop both with Ctrl+C. Note that `npm run build` writes to
`frontend/dist/`, which git ignores ([.gitignore:19](../.gitignore#L19)).

---

## 💡 Concept: WSGI, and why not `python app.py` in production

WSGI is Python's standard interface between a web server and a web app: the server calls
`app(environ, start_response)` for each request. Flask's `app` object is such a callable, so any
WSGI server can run it. `app.run()` starts Werkzeug's development server, which is meant for one
developer. gunicorn starts several worker processes (here each with a thread pool), restarts
crashed or hung ones (`--timeout`), and handles signals for clean shutdowns, which is what a
platform expects.

## 💡 Concept: build-time versus run-time configuration

The backend reads its configuration when it starts (`create_app` reads the environment once), so
changing a variable and restarting is enough. The frontend has no server of its own in production:
its configuration must be decided when the files are generated. Hence the rule of thumb: backend
variables can be secret and changed with a restart; frontend `VITE_` variables are public and need
a rebuild.

---

## Design decisions

- **Two deployables.** Static files for the UI (cheap, cacheable, served by a CDN) and a small
  Python service for the maths. Neither needs to know how the other is hosted, only one URL and,
  for the API, one allowed origin.
- **A stateless API.** No sessions, no database writes, read-only tables: any worker or thread can
  answer any request, so scaling is "more workers or more machines". The rate limiter's counters are
  the one piece of state, which is why they are per worker unless you give them a shared store.
- **Build once, fork.** `--preload` builds the tables in the master and lets the workers share the
  pages. The cost: code changes need a full restart, not a graceful reload.
- **Threads for waiting, processes for work.** Threads let slow OpenRouter calls wait without
  blocking solves; two processes keep one crash from taking everything down.
- **Defaults in code, overrides from the environment.** The app runs with no configuration at all,
  `.env.example` documents what can change, and tests override settings without touching the
  environment.
- **Same origin by default.** A build without `VITE_API_URL` assumes the host routes `/api`, the
  arrangement that needs no CORS. The cost: on a plain static host you must remember the variable.
- **Platform-neutral.** A `Procfile` and README notes instead of platform files keep the repo free
  of vendor configuration, at the cost of manual set-up on whichever host you choose.
- **The LLM is optional.** Without `OPENROUTER_API_KEY` the deployment still works fully; the key
  only upgrades the notes drawer.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: test tools shipped to production.** `pytest` and `rich` were in `requirements.txt`. The
  runtime file now has the five server packages ([requirements.txt:1-6](../backend/requirements.txt#L1-L6));
  everything else is in [requirements-dev.txt](../backend/requirements-dev.txt).
- ✅ **Fixed: every worker rebuilt the tables.** `--preload` in the [Procfile](../backend/Procfile#L1)
  builds them once (section 2).
- ✅ **Fixed: slow LLM calls blocked solves.** Threaded workers (`--worker-class gthread --threads 4`)
  and a 15-second OpenRouter timeout instead of 20 (section 2).
- ✅ **Fixed: CORS `"*"` with a paid key.** Origins come from `CORS_ORIGINS`
  ([app.py:130-131](../backend/app.py#L130-L131)) and `/api/analyze` is rate-limited
  ([app.py:133-139](../backend/app.py#L133-L139)). Pinned by `test_cors_allows_only_configured_origins`
  and `test_analyze_is_rate_limited` ([test_api.py:363-380](../backend/tests/test_api.py#L363-L380)).
- ✅ **Fixed: a silent localhost fallback.** A build without `VITE_API_URL` now calls `/api` on its
  own origin ([App.jsx:8](../frontend/src/App.jsx#L8)) instead of each visitor's `127.0.0.1:5000`.
- ✅ **Fixed: `.env` files were not ignored.** [.gitignore:12-15](../.gitignore#L12-L15) ignores
  `.env` and `.env.*`, and [backend/.env.example](../backend/.env.example) documents the variables.
- ✅ **Fixed: no CI.** [ci.yml](../.github/workflows/ci.yml) (lesson 15).
- ✅ **Fixed: an unused proxy.** The dev proxy is now how development reaches Flask (lesson 12).
- ✅ **Fixed: the development server listened everywhere.** `python app.py` binds `127.0.0.1` unless
  `HOST` is set ([app.py:577-579](../backend/app.py#L577-L579)).
- ✅ **Fixed: unused files shipped.** `public/` was deleted, so `dist/` holds only the page, one
  JS and one CSS file.

Still open:

1. **The rate limit can't see clients behind a proxy.** `get_remote_address`
   ([app.py:134](../backend/app.py#L134)) keys on the connecting address, which on most platforms is
   the router's, so all visitors share one bucket (section 6). *Fix:* wrap the app in Werkzeug's
   `ProxyFix` with the number of trusted proxies, and only then (exercise 6).
2. **The limit is per worker.** With `memory://`, two workers allow about twice the configured rate
   (18 of 25 in one minute, section 6). README mentions it. *Fix:* `RATELIMIT_STORAGE_URI` pointing at
   a shared store such as Redis.
3. **`backend/.env` is never loaded.** [.env.example:1](../backend/.env.example#L1) says to copy it to
   `backend/.env`, but nothing reads that file. *Fix:* reword the comment ("export these, or set them
   on your platform"), or load the file in development with `python-dotenv`.
4. **A CORS mistake looks like an outage.** With the page's origin missing from `CORS_ORIGINS`, the UI
   says "Can't reach the solver. Start the backend on port 5000…" while the backend is healthy.
   *Fix:* a production-specific hint in the offline message, or a startup log line listing the
   allowed origins.
5. **One setting is undocumented.** `RATELIMIT_ENABLED` is read from the environment like the
   others ([app.py:56](../backend/app.py#L56)), but neither `.env.example` nor README lists it, so
   `RATELIMIT_ENABLED=0` on a platform would silently switch the limit off (exercise 4).
6. **No platform files, no runtime pins** (section 7). A platform may pick a different Python or
   Node than the one CI tests.

---

## 🧪 Try it

Run the command from the Procfile on a free port (from `backend/`, venv active), and in a second
terminal ask it for its health:

```bash
PORT=5055 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --worker-class gthread --threads 4 --timeout 60 --preload
curl -s http://127.0.0.1:5055/health
```

```
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.1.0"}
```

See the master and its two workers, with their memory (Linux; replace `<PID>` with the number after
"Listening at"):

```bash
ps -o pid,ppid,rss,cmd --ppid <PID> -p <PID>
for p in <PID> $(pgrep -P <PID>); do grep '^Pss:' /proc/$p/smaps_rollup; done
```

Prove that the API address is baked in. Build into a folder outside the repo (from `frontend/`):

```bash
VITE_API_URL=https://api.example.invalid npx vite build --outDir /tmp/lieng-build --emptyOutDir > /dev/null
grep -o -E '[a-zA-Z_$]+=`[^`]*`,[a-zA-Z_$]+=`lieng-scope-lang`' /tmp/lieng-build/assets/*.js
npx vite build --outDir /tmp/lieng-build --emptyOutDir > /dev/null
grep -o -E '[a-zA-Z_$]+=`[^`]*`,[a-zA-Z_$]+=`lieng-scope-lang`' /tmp/lieng-build/assets/*.js
```

```
_=`https://api.example.invalid`,v=`lieng-scope-lang`
_=``,v=`lieng-scope-lang`
```

(The one-letter names come from the minifier and can change between builds.)

Check which secret files git would ignore (from the repo root):

```bash
git check-ignore -v .env backend/.env frontend/.env frontend/.env.local frontend/.env.production backend/.env.example
```

```
.gitignore:13:.env	.env
.gitignore:13:.env	backend/.env
.gitignore:13:.env	frontend/.env
frontend/.gitignore:13:*.local	frontend/.env.local
.gitignore:14:.env.*	frontend/.env.production
```

Every file is listed except `backend/.env.example`, the one meant to be committed.

See the rate limit share one bucket behind a proxy (from `backend/`):

```bash
python -c '
from app import create_app
app = create_app(config={"TESTING": True, "RATELIMIT_ENABLED": True, "ANALYZE_RATE_LIMIT": "2 per minute", "OPENROUTER_API_KEY": ""})
c = app.test_client()
for user in ["203.0.113.1", "203.0.113.2", "203.0.113.3"]:
    r = c.post("/api/analyze", json={"hand": "As Kh Qd"}, headers={"X-Forwarded-For": user}, environ_base={"REMOTE_ADDR": "10.0.0.5"})
    print(user, r.status_code)
'
```

```
203.0.113.1 200
203.0.113.2 200
203.0.113.3 429
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You deploy the backend with `OPENROUTER_API_KEY` set. Then you remove the
variable from the process environment without restarting (pretend your platform allowed that). What
does `/api/analyze` return? And after a restart?

<details><summary>Solution</summary>

Without a restart: still the LLM's answer. `create_app` copied the key into `app.config` at start-up
(with `--preload`, in the master before the fork), and `/api/analyze` reads `app.config`
([app.py:467](../backend/app.py#L467)), not the environment. After a restart: the rule-based text,
with `"model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"`. (In the first version
of this code the key was read on every request, so the change would have applied at once.)
</details>

**🟢 2. Predict.** You build the frontend without `VITE_API_URL`, upload `dist/` to a plain static
host, and only then set `VITE_API_URL` there. Does the page reach your API?

<details><summary>Solution</summary>

No. The URL was fixed when the bundle was built, as an empty string, so the page posts to
`/api/solve` on the static host. That host is not Flask: it typically answers 404 or 405 with an
HTML page, and the UI shows "Check your inputs: HTTP 404" (or 405). Rebuild with the variable set,
and add the page's origin to `CORS_ORIGINS` on the backend.
</details>

**🟢 3. Predict.** With the Procfile as it is, how many times is `CallingRangeModel()` built when
gunicorn starts? And if you remove `--preload`?

<details><summary>Solution</summary>

Once with `--preload` (in the master, before the fork), twice without it (once per worker, after
the fork). The memory table in section 2 shows it: without `--preload` the master stays at about
24.7 MB because it never imports the app, and the total PSS grows from about 43 MB to about 67 MB.
</details>

**🟡 4. Catch documentation drift.** Write a test that compares the settings the app reads
(`DEFAULT_CONFIG` plus `HOST` and `PORT`) with the names in `backend/.env.example`. Predict whether
it passes today.

<details><summary>Solution</summary>

```python
from pathlib import Path

from app import DEFAULT_CONFIG


def test_env_example_lists_every_setting() -> None:
    example = Path(__file__).resolve().parent.parent / ".env.example"
    documented = {line.split("=", 1)[0] for line in example.read_text().splitlines() if line and not line.startswith("#")}
    assert documented == set(DEFAULT_CONFIG) | {"HOST", "PORT"}
```

It fails: `RATELIMIT_ENABLED` is read but not documented (weak spot 5). Add it to `.env.example`
(`RATELIMIT_ENABLED=true`, with a comment saying `false` turns the limit off) and the test passes.
From then on, a new setting without documentation fails the suite. Undo with
`git checkout -- backend/.env.example` and delete the test.
</details>

**🟡 5. Break CORS on purpose.** Repeat the rehearsal of section 8, but start gunicorn **without**
`CORS_ORIGINS`. Predict the message on the page, and what the browser's Network tab and console show.

<details><summary>Solution</summary>

The page says "Can't reach the solver. Start the backend on port 5000 and try again." The Network
tab shows the `OPTIONS` preflight to `/api/solve` answered with 200 but without
`Access-Control-Allow-Origin` (the default allows only the two Vite dev origins), and the console
reports a CORS error; the `POST` is never sent. `fetch` rejects with a `TypeError`, which
`fetchSolveAndAnalysis` reports as `solverOffline`. Restart with `CORS_ORIGINS=http://localhost:4180`
and the page works. Nothing to undo.
</details>

**🔴 6. Trust the proxy, carefully.** Add a `TRUSTED_PROXIES` setting (default `"0"`) and, when it is
above 0, wrap the app in Werkzeug's `ProxyFix` so the rate limit sees the client address from
`X-Forwarded-For`. Check with the 🧪 script, extended to five requests (users 1, 2, 3, 1, 1): with
`TRUSTED_PROXIES` 0 you get `[200, 200, 429, 429, 429]`, with 1 `[200, 200, 200, 200, 429]`.

<details><summary>Solution</summary>

In `DEFAULT_CONFIG` add `"TRUSTED_PROXIES": "0",`. In `create_app`, right after
`app.config.update(overrides)`:

```python
    proxies = int(app.config["TRUSTED_PROXIES"])
    if proxies:
        # Behind a platform's router, take the client address from X-Forwarded-For (that many hops).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies)  # type: ignore[method-assign]
```

and `from werkzeug.middleware.proxy_fix import ProxyFix` next to the other `werkzeug` import (ruff
sorts imports). The 40 API tests, ruff and mypy still pass. Why "carefully": `X-Forwarded-For` is
just a header. Without a proxy in front, any client can send a different value on each request and
get a fresh bucket every time, which is why the default stays 0 and you set it to the number of
proxies your platform documents. Add `TRUSTED_PROXIES` to `.env.example` too (exercise 4 will remind
you). Undo with `git checkout -- backend/app.py backend/.env.example`.
</details>

**🔴 7. Pin the runtimes.** Add `backend/.python-version` and `frontend/.nvmrc`, and make CI read
them, so the platform, CI and your machine agree on one Python and one Node.

<details><summary>Hints</summary>

`.python-version` holds one line such as `3.12`; many platforms (and `pyenv`) read it, and
`actions/setup-python` accepts `python-version-file: backend/.python-version` instead of
`python-version`. `.nvmrc` holds `22`; `actions/setup-node` accepts
`node-version-file: frontend/.nvmrc`. Keep `engines` in `package.json` as the lower bound
(`>=22.22.2`): a bare `22` in `.nvmrc` could resolve to an older 22.x on a machine that has one, so
`22.22` is the safer pin. Check your platform's documentation for the file it actually reads; some
use `runtime.txt`. Undo by deleting the two files and `git checkout -- .github/workflows/ci.yml`.
</details>

---

## ❓ Quiz

1. In `gunicorn app:app`, what do the two `app`s refer to?
2. Why does the `if __name__ == "__main__":` block in `app.py` not run under gunicorn, and which
   setting therefore only matters for `python app.py`?
3. Why can a secret never go into a `VITE_` variable?
4. Why is it safe for two workers with four threads each to answer requests from the same user, and
   what is the one thing they do not share?
5. Which packages does a production install get, and where did `pytest` and `rich` go?

<details><summary>Answers</summary>

1. The first is the module `app.py`; the second is the variable `app` inside it, the Flask object
   that `create_app()` returns ([app.py:574](../backend/app.py#L574)).
2. gunicorn imports the module, so `__name__` is `"app"`, not `"__main__"`. It then serves the `app`
   object itself. `HOST` is read only in that block; gunicorn takes its address from `--bind`.
3. Vite writes its value into the JavaScript bundle at build time, and every visitor downloads that
   bundle.
4. The API keeps no per-user state: each request carries all its inputs, and the tables are
   read-only. The rate limiter's counters are the exception: with `memory://` each worker keeps its
   own, so the limit is per worker.
5. The five packages in `requirements.txt`: flask, flask-cors, flask-limiter, gunicorn and requests.
   `pytest`, `rich`, `ruff`, `mypy` and `types-requests` are in `requirements-dev.txt`, which
   includes the runtime file with `-r`.
</details>

---

## Recap

- Production is two pieces: static files from `npm run build`, and gunicorn running `app:app` with
  two threaded workers on `$PORT`, the tables built once in the master (`--preload`).
- Every backend setting has a default in `DEFAULT_CONFIG`, can be overridden by the environment at
  start-up, and by `create_app(config=…)` in tests. `.env.example` documents them, though nothing
  loads a `.env` file.
- `VITE_API_URL` is written into the public bundle at build time; without it the page calls `/api`
  on its own origin, which needs something on that host to route `/api` to Flask.
- Cross-origin deployments need `CORS_ORIGINS`; a missing origin looks like an outage in the UI.
- `/api/analyze` is rate-limited, but per worker and per connecting address, which behind a proxy is
  everyone at once.
- Runtime requirements are pinned and separate from the dev tools; CI runs everything on every push;
  the Python and Node versions are still not pinned for a platform.

**Next:** [17 — Weak spots and next steps](17-weak-spots-and-next-steps.md)
