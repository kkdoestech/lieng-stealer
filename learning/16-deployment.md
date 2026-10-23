# Lesson 16 — Deployment

> **Goal:** understand what it takes to run this project outside your laptop: the one-line
> `Procfile`, the pinned requirements, the three environment variables, and the frontend build
> that bakes the API address into a public JavaScript file. Then run the whole "production" pair
> locally.
> **Files:** [`backend/Procfile`](../backend/Procfile), [`backend/requirements.txt`](../backend/requirements.txt),
> [`frontend/package.json`](../frontend/package.json), [`frontend/vite.config.js`](../frontend/vite.config.js),
> [`frontend/src/App.jsx:6`](../frontend/src/App.jsx#L6), README "Configuration and deployment".
> **Time:** ~40 min. **Before this:** [15 — Tests and performance](15-tests-and-performance.md).

---

## Where this fits

```
 DEVELOPMENT (lessons 10–13)                    PRODUCTION (this lesson)
 ───────────────────────────                    ────────────────────────
 python app.py   → Werkzeug dev server :5000    gunicorn app:app, 2 worker processes, $PORT
 npm run dev     → Vite dev server :5173        npm run build → dist/ (HTML + 1 JS + 1 CSS file)
 API address     → default 127.0.0.1:5000       VITE_API_URL, read once, at build time
 secrets         → your shell                   the hosting platform's environment settings

      browser ──GET──► static host (dist/) ─── index.html, assets/index-….js
         │
         └──fetch(VITE_API_URL + "/api/solve")──► gunicorn ──► worker 1: app.py (own DB + tables)
                                                            └► worker 2: app.py (own DB + tables)
```

The repository contains exactly one deployment file, the `Procfile`. Everything else here is
either configuration you pass in (environment variables) or a build step you run. README's
"Configuration and deployment" section names example platforms (Render or Railway for the backend,
Vercel or Netlify for the frontend); nothing in the repo is specific to any of them.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [Procfile:1](../backend/Procfile#L1) | The production start command, token by token. |
| 2 | [app.py:26-36](../backend/app.py#L26-L36) | What every gunicorn worker runs when it imports `app`. |
| 3 | [app.py:443-445](../backend/app.py#L443-L445) | The development entry point, which gunicorn never runs. |
| 4 | [requirements.txt:1-6](../backend/requirements.txt#L1-L6) | Six exact pins, including one that should not ship. |
| 5 | [App.jsx:6](../frontend/src/App.jsx#L6) | `VITE_API_URL` and its fallback. |
| 6 | [package.json:6-12](../frontend/package.json#L6-L12) | `build` and `preview`. |
| 7 | [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) | A dev proxy that the app does not use. |
| 8 | [.gitignore:15-18](../.gitignore#L15-L18) | Which build and secret files git ignores (and which it does not). |

---

## Walkthrough

### 1. The `Procfile`, token by token

📍 [`backend/Procfile:1`](../backend/Procfile#L1)
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

A `Procfile` is a convention from Heroku that several platforms read: one line per process type,
`name: command`. The platform runs the command from the folder that holds the file (`backend/`).

| Token | Meaning |
|-------|---------|
| `web:` | The process type that receives HTTP traffic. |
| `gunicorn` | A production WSGI server (see the 💡 box). It replaces Flask's development server. |
| `app:app` | "Import the module `app` (`app.py`) and serve the variable `app` in it", the `Flask(__name__)` object at [app.py:26](../backend/app.py#L26). |
| `--bind 0.0.0.0:$PORT` | Listen on every network interface, on the port the platform assigns in `$PORT`. |
| `--workers 2` | Start two worker *processes*. Each handles one request at a time (gunicorn's default `sync` worker). |
| `--timeout 120` | Kill and restart a worker that is silent for more than 120 seconds on one request. |

Because `app:app` names an object, the `if __name__ == "__main__":` block at
[app.py:443-445](../backend/app.py#L443-L445) never runs under gunicorn. That block is only for
`python app.py`.

### 2. Two workers, two copies of everything

Each worker is a separate Python process, and by default gunicorn imports `app.py` **inside each
worker**, after forking. So the start-up code from lesson 10 runs twice: two `WinRateDB` loads, two
`CallingRangeModel` builds (54–67 ms each on the course machine), two `RangeFinder` strength maps.

You can see it in the memory of a local run on port 5055 (machine-dependent):

| Mode | Master process | Each worker |
|------|----------------|-------------|
| default (`app:app --workers 2`) | 24.5 MB resident | 37.3 MB resident |
| with `--preload` | 39.8 MB resident | 32–33 MB resident, of which only 12.5 MB its own (PSS) |

By default the master never imports the app (24.5 MB is just gunicorn), and each worker holds a
full private copy. With `--preload`, the master imports `app.py` once and then forks, so the
workers start with the tables already built and share those memory pages until they write to
them. Either way, nothing is shared *logically*: the tables are read-only, and requests carry all
their inputs, so it does not matter which worker answers (lesson 11). That is what makes adding
workers, or machines, safe.

The `sync` worker model has one cost here. `/api/analyze` with a key waits up to 20 seconds for
OpenRouter ([app.py:422](../backend/app.py#L422)). Two slow analyses in a row occupy both workers,
and every `/api/solve` behind them waits (weak spot 3).

### 3. The requirements

📍 [`backend/requirements.txt:1-6`](../backend/requirements.txt#L1-L6)
```
flask==3.0.3
flask-cors==4.0.1
gunicorn==22.0.0
requests==2.31.0
rich==13.7.1
pytest==9.1.1
```

| Package | Used by | Needed in production? |
|---------|---------|-----------------------|
| `flask` | `app.py` | yes |
| `flask-cors` | `app.py:28` | yes |
| `gunicorn` | the `Procfile` | yes |
| `requests` | `/api/analyze` → OpenRouter ([app.py:418](../backend/app.py#L418)) | yes (imported at the top of `app.py`) |
| `rich` | `cli.py` only, and optional there | no |
| `pytest` | the tests | **no** |

Every version is pinned exactly (`==`), so a fresh install today gets what the code was tested
with. What is not pinned: the dependencies of these packages (Werkzeug, Jinja2, …; the dev server
reports `Werkzeug/3.1.9`), file hashes, and the Python version. README says Python 3.11+, the
course machine's venv runs 3.12.3, and no `runtime.txt` or `.python-version` tells a platform
which one to use.

### 4. Environment variables

| Variable | Read at | When | Default |
|----------|---------|------|---------|
| `PORT` | [Procfile:1](../backend/Procfile#L1), [app.py:444](../backend/app.py#L444) | server start | 5000 for `python app.py`; gunicorn needs it set |
| `OPENROUTER_API_KEY` | [app.py:334](../backend/app.py#L334) | **every `/api/analyze` request** | unset → rule-based text (lesson 10) |
| `VITE_API_URL` | [App.jsx:6](../frontend/src/App.jsx#L6) | **`npm run build`** | `http://127.0.0.1:5000` |

The backend never loads a `.env` file (there is no `python-dotenv`), so its variables must come
from the shell or the platform's settings. Vite, on the other hand, automatically reads
`frontend/.env` and `frontend/.env.production` during a build if they exist; the repo has none.
Note what git ignores:

📍 [`.gitignore:15-18`](../.gitignore#L15-L18)
```
frontend/dist/
frontend/node_modules/
.env.local
.env.*.local
```

`git check-ignore` confirms that `frontend/.env.local` is ignored, but a plain `.env`,
`backend/.env` or `frontend/.env.production` is **not**. A frontend file only holds public `VITE_`
values, so committing it is fine. Put the OpenRouter key in `backend/.env`, though, and `git add .`
would commit it (weak spot 6).

### 5. `VITE_API_URL` is baked into the bundle

📍 [`frontend/src/App.jsx:6`](../frontend/src/App.jsx#L6)
```jsx
const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";
```

`import.meta.env.VITE_…` looks like a run-time lookup, but it is not. During `vite build`, Vite
replaces the expression with the *text* of the variable, then minifies. The browser later receives
a finished file with the URL written into it. Proof, from two builds into a scratch folder (never
into `frontend/dist`):

```bash
cd frontend
npx vite build --outDir /tmp/…/scratchpad/writer-c/dist --emptyOutDir
VITE_API_URL=https://api.example.com npx vite build --outDir /tmp/…/scratchpad/writer-c/dist-prod --emptyOutDir
```

The first build's summary (paths shortened):

```
dist/index.html                   0.41 kB │ gzip:  0.29 kB
dist/assets/index-D2Sg5JNI.css    7.68 kB │ gzip:  2.15 kB
dist/assets/index-D-7Ktmhb.js   210.48 kB │ gzip: 65.75 kB
✓ built in 116ms
```

Searching the two JavaScript bundles (excerpts of the minified code):

```
default build:     …,_=`http://127.0.0.1:5000`,v=`lieng-scope-lang`,…
with VITE_API_URL: …,_=`https://api.example.com`,v=`lieng-scope-lan…
```

The second bundle contains no `127.0.0.1:5000` at all, and neither bundle contains the string
`VITE_API_URL`. Three consequences:

1. **Changing the backend URL means rebuilding the frontend.** Setting the variable on the static
   host after the build does nothing.
2. **Anything in a `VITE_` variable is public.** Anyone can read it in the downloaded JavaScript.
   That is why the OpenRouter key lives on the backend, never in the frontend.
3. **Forgetting the variable fails silently.** The production bundle then calls `127.0.0.1:5000`,
   the *visitor's own computer*, and every visitor sees "Can't reach the solver" (weak spot 5).

The dev proxy in [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) (forward `/api` to
`127.0.0.1:5000`) only exists in `npm run dev`, and the app bypasses it anyway, because
`API_BASE` is an absolute URL (lesson 12). Production has no proxy: the browser calls the API
directly, cross-origin.

### 6. CORS in production

Because the page and the API live on different origins, every API call needs the CORS headers
from [app.py:28](../backend/app.py#L28) (the 💡 box in lesson 10). With `"origins": "*"`,
flask-cors echoes back any origin: your frontend works without knowing its final URL, and so does
any other website that decides to call your API from its visitors' browsers. For a free calculator
without accounts that is acceptable. It stops being acceptable as soon as the API has a cost: with
`OPENROUTER_API_KEY` set, any page on the internet can make your server spend your OpenRouter
quota through `/api/analyze`. *Fix:* `{"origins": ["https://your-frontend.example"]}`, plus rate
limiting.

### 7. What is not in the repository

`git ls-files` shows one deployment file (`backend/Procfile`). There is no:

- **CI** (no `.github/workflows/`): nothing runs the 93 + 6 tests on a push or a pull request;
- **frontend host config** (`vercel.json`, `netlify.toml`): the platform must be told the build
  command (`npm run build`), the output folder (`dist`) and `VITE_API_URL` by hand;
- **container** (`Dockerfile`) or **backend host config** (`render.yaml`, `railway.json`);
- **version pins** for the platform: `runtime.txt`, `.python-version`, `.nvmrc` (Vite 8 needs Node
  `^20.19.0 || >=22.12.0`, according to `package-lock.json`);
- **`.env.example`** documenting the three variables (README's table is the only list).

### 8. A full local "production" run

You can rehearse a deployment on one machine. This exact sequence was run for this lesson, on
free ports (5055 for the API, 4180 for the static files), and stopped afterwards.

```bash
# terminal 1: the API, as the Procfile runs it (from backend/, venv active)
PORT=5055 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

# terminal 2: build the frontend for that API, then serve the static files (from frontend/)
VITE_API_URL=http://127.0.0.1:5055 npm run build
npm run preview          # serves dist/ on http://localhost:4173 by default
```

gunicorn's log (timestamps removed):

```
[INFO] Starting gunicorn 22.0.0
[INFO] Listening at: http://0.0.0.0:5055 (10469)
[INFO] Using worker: sync
[INFO] Booting worker with pid: 10482
[INFO] Booting worker with pid: 10483
```

Then, checked with curl (the course build went to a scratch folder and was previewed on port 4180,
so the commands below use 4180):

```
GET  http://127.0.0.1:5055/health → {"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
GET  http://localhost:4180/        → 200, and its bundle contains _=`http://127.0.0.1:5055`
OPTIONS /api/solve, Origin http://localhost:4180 → 200, Access-Control-Allow-Origin: http://localhost:4180
POST /api/solve (the default click) → "ev":131876.0, in 2.8–3.6 ms per request
```

Open http://localhost:4173 (or your preview port) and the page works exactly as in development,
but from minified files and two gunicorn workers. Stop both with Ctrl+C. Note that `npm run build`
writes to `frontend/dist/`, which git ignores ([.gitignore:15](../.gitignore#L15)).

---

## 💡 Concept: WSGI, and why not `python app.py` in production

WSGI is Python's standard interface between a web server and a web app: the server calls
`app(environ, start_response)` for each request. Flask's `app` object is such a callable, so any
WSGI server can run it. `app.run()` starts Werkzeug's development server, which is single-process
and meant for one developer. gunicorn starts several worker processes, restarts crashed or hung
ones (`--timeout`), and handles signals for clean shutdowns, which is what a platform expects.

## 💡 Concept: build-time versus run-time configuration

The backend reads its configuration while it runs (`os.environ.get(...)` on each request or at
start-up), so changing a variable and restarting is enough. The frontend has no server of its own
in production: its configuration must be decided when the files are generated. Hence the rule of
thumb: backend variables can be secret and changed without a rebuild; frontend `VITE_` variables
are public and need a rebuild.

---

## Design decisions

- **Two deployables.** Static files for the UI (cheap, cacheable, served by a CDN) and a small
  Python service for the maths. Neither needs to know how the other is hosted, only one URL.
- **A stateless API.** No sessions, no database writes, read-only tables: any worker can answer
  any request, so scaling is "more workers or more machines".
- **Tables per worker.** Simple and isolated, at the price of building them once per worker
  (tens of milliseconds) and holding one copy each. `--preload` is the one-flag alternative.
- **Platform-neutral.** A `Procfile` and README notes instead of platform files keep the repo free
  of vendor configuration, at the cost of manual set-up on whichever host you choose.
- **The LLM is optional.** Without `OPENROUTER_API_KEY` the deployment still works fully; the key
  only upgrades the notes drawer.

---

## ⚠️ Weak spots

1. **Test tools ship to production.** [requirements.txt:6](../backend/requirements.txt#L6) installs
   `pytest` on every server, and [:5](../backend/requirements.txt#L5) `rich`, which only the CLI
   uses. *Fix:* `requirements.txt` for runtime and `requirements-dev.txt` (`-r requirements.txt`
   plus `pytest`).
2. **Every worker rebuilds the tables.** [Procfile:1](../backend/Procfile#L1) with
   [app.py:31-36](../backend/app.py#L31-L36): start-up work and memory are multiplied by the worker
   count. *Fix:* `--preload`, or save the calling-range tables to disk.
3. **Slow LLM calls block solves.** Sync workers ([Procfile:1](../backend/Procfile#L1)) and a
   20-second OpenRouter timeout ([app.py:422](../backend/app.py#L422)): two pending analyses stall
   the whole API. *Fix:* more workers or threaded workers (`--threads 4`), a shorter timeout, or
   moving analysis out of the request.
4. **CORS `"*"` with a paid key.** [app.py:28](../backend/app.py#L28): any website can use your
   `/api/analyze`. *Fix:* restrict origins in production and add rate limiting.
5. **A silent localhost fallback.** [App.jsx:6](../frontend/src/App.jsx#L6): a production build
   without `VITE_API_URL` points at the visitor's machine. *Fix:* fail the build when
   `import.meta.env.PROD` is true and the variable is missing, or use a relative `/api` URL behind
   a reverse proxy.
6. **`.env` files are not ignored.** [.gitignore:17-18](../.gitignore#L17-L18) only covers
   `.env.local` variants, so a `backend/.env` holding the OpenRouter key could be committed.
   *Fix:* add `.env` and `.env.*`, and commit a `.env.example` instead (exercise 5).
7. **No CI, no platform files, no runtime pins** (section 7). The tests exist but nothing runs them
   automatically, and a platform may pick a different Python or Node than the one tested.
8. **An unused proxy.** [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) suggests the app
   calls `/api` relatively; it does not. *Fix:* delete it, or make `API_BASE` default to `""` in
   development and use the proxy.
9. **The development server listens everywhere.** [app.py:445](../backend/app.py#L445) binds
   `0.0.0.0`, so `python app.py` is reachable from your local network. Harmless for a calculator,
   but `127.0.0.1` is the safer default for a dev server.
10. **Unused files ship.** `public/favicon.svg` and `public/icons.svg` are copied into `dist/`, but
    [index.html](../frontend/index.html) links neither (lesson 12).

---

## 🧪 Try it

Run the gunicorn command from the Procfile on a free port (from `backend/`, venv active), and in a
second terminal ask it for its health:

```bash
PORT=5055 gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
curl -s http://127.0.0.1:5055/health
```

```
{"classes_loaded":455,"database_loaded":true,"status":"healthy","version":"1.0.0"}
```

See the two workers and their memory (Linux; replace `<PID>` with the number after
"Listening at"):

```bash
ps -o pid,ppid,rss,cmd --ppid <PID> -p <PID>
```

Prove that the API address is baked in. Build into a folder outside the repo (from `frontend/`):

```bash
VITE_API_URL=https://api.example.com npx vite build --outDir /tmp/lieng-build --emptyOutDir
grep -o '_=`[^`]*`' /tmp/lieng-build/assets/*.js
grep -c "127.0.0.1:5000" /tmp/lieng-build/assets/*.js
```

```
_=`https://api.example.com`
0
```

(The variable name `_` comes from the minifier and can change between builds; grep for
`api.example.com` if it does.)

Check which secret files git would ignore (from the repo root):

```bash
git check-ignore -v .env backend/.env frontend/.env frontend/.env.local
```

```
frontend/.gitignore:13:*.local	frontend/.env.local
```

Only the last one is listed: the other three would be committed.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You deploy the backend with `OPENROUTER_API_KEY` set, then remove the variable
in the platform's settings, and the platform restarts the service. What does `/api/analyze`
return now? What if you could change the variable without a restart?

<details><summary>Solution</summary>

The rule-based text, with `"model": "rule-based-solver-engine (OPENROUTER_API_KEY not
configured)"`. The key is read on every request ([app.py:334](../backend/app.py#L334)), so even
without a restart the next request would see the change. Platforms restart anyway when variables
change.
</details>

**🟢 2. Predict.** You build the frontend, upload `dist/`, and only then set `VITE_API_URL` on the
static host. Does the page reach your API?

<details><summary>Solution</summary>

No. The URL was fixed when the bundle was built. Without the variable at build time the page calls
`http://127.0.0.1:5000` and shows "Can't reach the solver". You must rebuild with the variable set.
</details>

**🟢 3. Predict.** With `--workers 2`, how many times is `CallingRangeModel()` built when gunicorn
starts? And with `--workers 2 --preload`?

<details><summary>Solution</summary>

Twice by default (once per worker, after the fork), once with `--preload` (in the master, before
the fork). The memory table in section 2 shows it: without `--preload` the master stays at about
24.5 MB because it never imports the app.
</details>

**🟡 4. Split the requirements.** Move `pytest` (and `rich`, if you decide the CLI is a developer
tool) into `requirements-dev.txt` starting with `-r requirements.txt`. Check: in a fresh venv,
`pip install -r requirements.txt` then `python -c "import app"` works, and `pip install -r
requirements-dev.txt` then `python -m pytest -q` passes.

<details><summary>Solution</summary>

`requirements.txt`: flask, flask-cors, gunicorn, requests (and rich if you keep the CLI in
production). `requirements-dev.txt`:

```
-r requirements.txt
pytest==9.1.1
```

If you move `rich` out, the CLI still works thanks to the plain fallback (lesson 09), but update
README's setup commands to install the dev file.
</details>

**🟡 5. Ignore secret files.** Add `.env` and `.env.*` to the root `.gitignore`, keeping a way to
commit an example. Check: `git check-ignore -v .env backend/.env frontend/.env.production` lists all
three, and `git check-ignore .env.example` prints nothing.

<details><summary>Solution</summary>

```
.env
.env.*
!.env.example
```

The `!` line un-ignores the example file. Then create `.env.example` with the three variable names
and no values.
</details>

**🔴 6. Add CI.** Write `.github/workflows/test.yml` that runs the backend tests on Python 3.11 and
3.12 and the frontend tests on Node 22, on every push and pull request.

<details><summary>Hints</summary>

Two jobs. Backend: `actions/checkout`, `actions/setup-python` with a version matrix,
`pip install -r requirements.txt`, then `python -m pytest -q` with `working-directory: backend`.
Frontend: `actions/setup-node` with `node-version: 22`, `npm ci`, `npm test`, `npm run lint`,
`npm run build`, with `working-directory: frontend`. Do not set `OPENROUTER_API_KEY`: the tests
remove it anyway (lesson 15). Watch the two timing tests: shared CI machines are slower.
</details>

**🔴 7. Fail the build without an API URL.** Make `npm run build` fail with a clear message when
`VITE_API_URL` is unset, while `npm run dev` keeps the localhost default. Check: a build without
the variable exits non-zero; a build with it succeeds and the bundle contains the URL.

<details><summary>Hints</summary>

`vite.config.js` can export a function: `defineConfig(({ command }) => { … })`. When
`command === "build"` and `process.env.VITE_API_URL` is empty, `throw new Error("Set VITE_API_URL
to the backend URL")`. Vite only exposes `VITE_` variables to the app, but the config file sees the
full `process.env`. Keep the `||` fallback in `App.jsx` for development, or move it into the
config with `define`.
</details>

---

## ❓ Quiz

1. In `gunicorn app:app`, what do the two `app`s refer to?
2. Why does the `if __name__ == "__main__":` block in `app.py` not run under gunicorn?
3. Why can a secret never go into a `VITE_` variable?
4. Why is it safe for two workers to answer requests from the same user?
5. Which two lines of `requirements.txt` are not needed to serve the API?

<details><summary>Answers</summary>

1. The first is the module `app.py`; the second is the `Flask` object named `app` inside it.
2. gunicorn imports the module, so `__name__` is `"app"`, not `"__main__"`. It then serves the
   `app` object itself.
3. Vite writes its value into the JavaScript bundle at build time, and every visitor downloads that
   bundle.
4. The API keeps no per-user state: each request carries all its inputs, and the tables are
   read-only copies of the same data.
5. `pytest` (tests only) and `rich` (the CLI only).
</details>

---

## Recap

- Production is two pieces: static files from `npm run build`, and gunicorn running `app:app` with
  two sync workers on `$PORT`.
- Each worker imports `app.py` on its own and builds its own tables; `--preload` builds them once.
- Requirements are pinned exactly but include `pytest` (and `rich`), and the Python version is not
  pinned.
- `PORT` and `OPENROUTER_API_KEY` are read by the backend at run time; `VITE_API_URL` is written
  into the public bundle at build time, with a localhost fallback that fails silently.
- CORS `"*"` lets any site call the API, which matters once the LLM key costs money.
- Only the `Procfile` exists: no CI, no platform files, no `.env.example`, and plain `.env` files
  are not git-ignored.

**Next:** [17 — Weak spots and next steps](17-weak-spots-and-next-steps.md)
