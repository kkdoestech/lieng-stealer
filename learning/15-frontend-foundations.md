# 15 — Frontend Foundations

> **Goal:** set up a React project with Vite, learn the handful of React ideas the dashboard uses, and
> make a first page that talks to the Flask API.
> **You will build:** `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`,
> `frontend/.oxlintrc.json`, `frontend/.gitignore`, `frontend/src/main.jsx` (+ a temporary `App.jsx`).
> **Time:** ~2 hours.
> **Prerequisites:** [13](13-flask-api.md). **Node.js 20.19+ or 22.12+** installed (`node --version`).

---

## The big picture

The backend speaks JSON over HTTP. People want buttons, sliders and colours. The **frontend** is a web
page that runs **in the browser**, written in JavaScript, which sends requests to our API and draws the
answers.

```
  ┌──────────────── browser (http://localhost:5173) ────────────────┐
  │  index.html ──loads──► src/main.jsx ──renders──► <App />          │
  │                                                     │             │
  │       user clicks "EXECUTE SOLVER" ──► fetch(POST /api/solve)     │
  └─────────────────────────────────────────────────────┼─────────────┘
                                                        │ HTTP + JSON
                                                        ▼
                                  Flask (http://127.0.0.1:5000)  ← chapter 13
```

The tools:

| Tool | What it is | Python equivalent |
|------|------------|-------------------|
| **Node.js** | runs JavaScript outside the browser (needed by the build tools) | the `python` program |
| **npm** | installs JavaScript packages listed in `package.json` | `pip` + `requirements.txt` |
| **Vite** | dev server with instant reload + production bundler | `flask run` + a packager |
| **React** | library for building UIs out of components | — |
| **oxlint** | a fast linter (finds likely bugs) | `ruff` / `flake8` |

---

## Concepts you need

You need just enough JavaScript to read the dashboard. If you know Python, map it like this:

| JavaScript | Python |
|---|---|
| `const x = 5;` (can't be reassigned) / `let y = 5;` | `x = 5` |
| `function add(a, b) { return a + b; }` | `def add(a, b): return a + b` |
| `const add = (a, b) => a + b;` (arrow function) | `add = lambda a, b: a + b` |
| `` `Pot: ${pot}` `` (template literal) | `f"Pot: {pot}"` |
| `{ pot: 100, hand: "As" }` (object) | `{"pot": 100, "hand": "As"}` |
| `[1, 2, 3].map(n => n * 2)` | `[n * 2 for n in [1, 2, 3]]` |
| `x === y` (strict equality; always use `===`) | `x == y` |
| `a && b`, `a \|\| b`, `!a` | `a and b`, `a or b`, `not a` |
| `obj?.summary?.pot` (optional chaining: `undefined` instead of crashing if missing) | `(obj or {}).get("summary", {}).get("pot")` |
| `cond ? a : b` | `a if cond else b` |
| `null` / `undefined` | `None` |
| `import x from './x.js'` / `export default x` | `from x import ...` |

### React in five ideas

**1. A component is a function that returns UI.** The HTML-like syntax is **JSX**; curly braces
`{ }` insert JavaScript values:

```jsx
function Greeting({ name }) {          // "props" = the component's inputs
  return <h1>Hello {name}!</h1>;
}
// used like a tag:  <Greeting name="Liêng" />
```

JSX differences from HTML: `className` instead of `class`; every tag must be closed (`<input />`);
event handlers are camelCase functions (`onClick={...}`).

**2. State is data the component remembers.** `useState` returns the current value and a function to
change it. **Changing state re-runs the component function**, and React updates the page to match:

```jsx
import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);          // initial value 0
  return <button onClick={() => setCount(count + 1)}>Clicked {count} times</button>;
}
```

Never modify state directly (`count = 5` does nothing visible). Always call the setter.

**3. Controlled inputs.** A form input shows a state value and updates it on every keystroke:

```jsx
const [hand, setHand] = useState("As Kh Qd");
<input value={hand} onChange={(e) => setHand(e.target.value)} />
```

The state is the "single source of truth"; the input just displays it.

**4. Effects run code after rendering.** `useEffect(fn, [])` with an **empty list** runs `fn` once,
after the first render. That's the place for "load data when the page opens":

```jsx
useEffect(() => {
  loadSomething();
}, []);   // [] = no dependencies → run only on mount
```

**5. Conditional rendering and lists.**

```jsx
{error && <div className="alert">{error}</div>}           // show only if error is truthy
{isLoading ? "Loading..." : "Ready"}                       // choose between two
{hands.map((h) => <li key={h.id}>{h.id}</li>)}            // one element per item; key must be unique
```

### `fetch` and `async`/`await`

`fetch` sends an HTTP request and returns a **Promise** (a value that arrives later). `await` waits for
it inside an `async` function:

```js
async function getHealth() {
  const res = await fetch("http://127.0.0.1:5000/health");   // wait for the response
  if (!res.ok) throw new Error(`HTTP ${res.status}`);        // res.ok is true for 200–299
  const data = await res.json();                             // wait for the body, parse JSON
  return data.classes_loaded;
}
```

POST with a JSON body:

```js
await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ pot: 100000 }),        // object → JSON text (like json.dumps)
});
```

---

## Step 15.1 — Create the Vite project

From the **project root** (`lieng-stealer/`, next to `backend/`):

```bash
npm create vite@latest frontend -- --template react
cd frontend
```

This generates a starter React app. (The `--` passes `--template react` to the create-vite tool rather
than to npm.) Depending on the create-vite version you may see slightly different starter files: a demo
`App.jsx`, `App.css`, some images in `src/assets/` and `public/`, maybe an ESLint config. We'll replace
or ignore them.

> 💡 The original repo still contains starter leftovers that the app never uses: `src/assets/hero.png`,
> `react.svg`, `vite.svg`, `public/icons.svg` and `public/favicon.svg` (not even linked from
> `index.html`), plus the template's `README.md`. Deleting unused files keeps a project easy to read.

---

## Step 15.2 — `package.json`: the project manifest

Replace the generated file so your versions match the original project:

📄 **File:** `frontend/package.json` — *create this file*

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint",
    "preview": "vite preview",
    "test": "node --test"
  },
  "dependencies": {
    "react": "^19.2.8",
    "react-dom": "^19.2.8"
  },
  "devDependencies": {
    "@types/react": "^19.2.18",
    "@types/react-dom": "^19.2.4",
    "@vitejs/plugin-react": "^6.1.0",
    "oxlint": "^1.79.0",
    "vite": "^8.2.2"
  }
}
```

**How it works**

- `"type": "module"` → files use modern `import`/`export` syntax.
- `"scripts"` are shortcuts: `npm run dev` runs `vite`, `npm run build` runs `vite build`, etc.
  `npm test` runs `node --test`: Node's **built-in test runner** (no extra package needed), which finds
  files named `*.test.js` and runs them. The frontend's tests are written in chapter 16; until then
  `npm test` simply finds nothing to run.
- `"dependencies"` are needed by the app in the browser (React itself). `"devDependencies"` are only
  needed while developing/building (Vite, the linter, type definitions).
- `^19.2.8` means "19.2.8 or any newer 19.x". The exact versions installed get recorded in
  `package-lock.json`, which you **commit** so everyone gets the same versions. (The Python
  equivalent is pinning with `==` in `requirements.txt`.)

> 💡 The project's `README.md` advertises "React 18"; `package.json` says React **19**. Again: trust
> the code over the docs.

Install:

```bash
npm install
```

This creates `node_modules/` (thousands of files, never committed) and `package-lock.json`.

---

## Step 15.3 — Vite configuration

📄 **File:** `frontend/vite.config.js` — *create this file*

```js
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
```

**How it works**

- `plugins: [react()]` teaches Vite to compile JSX.
- **The proxy:** during `npm run dev`, any request the page makes to `/api/...` **on the Vite server**
  (port 5173) is forwarded to Flask on port 5000. To the browser it looks like one origin, so **CORS isn't
  involved at all**.

> ⚠️ **Pitfall: configured but unused.** The app (chapter 16) calls the API with an **absolute** URL,
> `http://127.0.0.1:5000/api/solve`, so requests go straight to Flask and the proxy is never used (CORS
> handles it instead). There are two mechanisms for one job, and only one is active. To use the proxy,
> the app would call relative URLs (`fetch("/api/solve")`), so set the base URL to `""` in development.

---

## Step 15.4 — Linter configuration

📄 **File:** `frontend/.oxlintrc.json` — *create this file*

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "oxc"],
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

- `react/rules-of-hooks` enforces React's rule: call hooks (`useState`, `useEffect`) only at the **top
  level** of a component, never inside `if`s or loops. Otherwise React mixes up which state is which.
- `only-export-components` keeps hot-reload working reliably.
- `$schema` gives your editor autocomplete for this file.

Run it any time with `npm run lint`.

---

## Step 15.5 — The HTML page and the entry point

📄 **File:** `frontend/index.html` — *create this file*

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LIÊNG SCOPE // Tactical GTO Solver</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

**How it works**

- This is the only real HTML file. The page is **empty** except for `<div id="root"></div>`. React
  fills that div with everything you see.
- `<meta name="viewport" …>` makes the page scale properly on phones.
- The Google Fonts links load **JetBrains Mono** (the monospace "terminal" font from `DESIGN.md`) and
  **Inter**. `preconnect` starts the network connection early to speed up loading.
- `<script type="module" src="/src/main.jsx">`: Vite intercepts this and serves the compiled JSX.

📄 **File:** `frontend/src/main.jsx` — *create this file*

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

**How it works**

- `createRoot(element).render(<App />)` tells React: "manage the inside of `#root`, and draw `<App />`
  there".
- `import './index.css'`: with Vite, importing a CSS file applies it to the page.
- **`<StrictMode>`** is a development helper that warns about unsafe patterns. One visible side effect:
  in development, React deliberately **mounts components twice**, so `useEffect(..., [])` runs **twice**.
  You'll see two `/api/solve` requests when the dashboard loads. In a production build it runs once.

---

## Step 15.6 — The frontend `.gitignore`

📄 **File:** `frontend/.gitignore` — *create this file*

```gitignore
# Logs
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

node_modules
dist
dist-ssr
*.local

# Editor directories and files
.vscode/*
!.vscode/extensions.json
.idea
.DS_Store
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
```

This is Vite's standard file (probably identical to what was generated). `dist` is the production build
output (chapter 17), and `*.local` covers files like `.env.local`, where you'd keep private settings.

---

## Step 15.7 — A first page that talks to the API (temporary)

Before building the real dashboard, prove the whole chain works: browser → React → fetch → Flask →
JSON → screen. Replace the generated `src/App.jsx` with this **temporary** version (no 📄 label;
chapter 16 replaces it):

```jsx
// frontend/src/App.jsx  (temporary — replaced in chapter 16)
import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message));
  }, []);

  if (error) return <p>Backend unreachable: {error}</p>;
  if (!health) return <p>Loading...</p>;
  return <h1>{health.classes_loaded} classes loaded, status: {health.status}</h1>;
}
```

**How it works**

- **`import.meta.env.VITE_API_URL`**: Vite exposes environment variables whose names start with
  `VITE_` to the browser code. If it isn't set, we fall back to the local Flask address. In production
  (chapter 17) you set it to the deployed API's URL.
- `.then(...)` is the older way of writing `await`: "when the Promise resolves, do this".
- The component has three states: error, loading (`health` still `null`), and loaded.

If your starter `src/index.css` or `src/App.css` contains demo styles, you can empty them for now.
Chapter 16 rewrites both.

---

## ✅ Checkpoint

You need **two terminals**.

Terminal 1, the backend:

```bash
cd backend
source .venv/bin/activate
python app.py
```

Terminal 2, the frontend:

```bash
cd frontend
npm run dev
```

Expected output in terminal 2 (the version and timing will vary):

```
  VITE v8.2.2  ready in 300 ms

  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173** in your browser. You should see:

```
455 classes loaded, status: healthy
```

Now stop Flask (Ctrl-C in terminal 1) and reload the page: you should see "Backend unreachable: Failed
to fetch". Your page really is talking to your API. Start Flask again.

Open the browser's **developer tools** (F12) → **Network** tab and reload: you'll see the `health`
request **twice** in development (that's StrictMode), each answered with status 200.

Commit (from the project root):

```bash
git add frontend && git commit -m "feat: React + Vite frontend skeleton"
```

Check that `git status` doesn't list `frontend/node_modules`.

## Recap

- **Node/npm** install the tools; **Vite** serves the page with instant reload; **React** builds the UI.
- A component is a function returning **JSX**; **state** (`useState`) re-renders when changed;
  **effects** (`useEffect(fn, [])`) run after mounting; **controlled inputs** mirror state.
- `fetch` + `async`/`await` call the API; `import.meta.env.VITE_API_URL` configures where it lives.
- `StrictMode` runs effects twice in development; the Vite proxy is configured but unused by the app.

**Next:** [16 — Building the UI](16-building-the-ui.md)