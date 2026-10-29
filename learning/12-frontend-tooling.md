# Lesson 12 — Frontend tooling

> **Goal:** know what each frontend tool does, what happens between `npm run dev` and a page in
> your browser, and how that page finds the API in development and in production.
> **Files:** [`frontend/package.json`](../frontend/package.json), [`frontend/vite.config.js`](../frontend/vite.config.js),
> [`frontend/index.html`](../frontend/index.html), [`frontend/src/main.jsx`](../frontend/src/main.jsx),
> [`frontend/src/test-setup.js`](../frontend/src/test-setup.js), [`frontend/.oxlintrc.json`](../frontend/.oxlintrc.json),
> and three lines of [`App.jsx`](../frontend/src/App.jsx#L6-L8).
> **Time:** ~40 min. **Before this:** [11 — Tracing one request end to end](11-request-trace.md).

---

## Where this fits

```
 frontend/                                                        backend/
 ┌─────────────────────────────────────────────────┐
 │ ┌──────────────── this lesson ────────────────┐ │
 │ │ package.json    scripts, dependencies, Node │ │
 │ │ vite.config.js  dev server, /api proxy,     │ │
 │ │                 test settings               │ │
 │ │ index.html ──► src/main.jsx ──► <App />     │ │
 │ │ .oxlintrc.json  lint rules; Vitest + jsdom  │ │
 │ └─────────────────────────────────────────────┘ │
 │   App.jsx, i18n.js, format.js     (lesson 13)   │  /api/... on   ┌───────────────────┐
 │   index.css, App.css              (lesson 14)   │  :5173, proxied│ app.py on :5000   │
 └─────────────────────────────────────────────────┘ ─────────────► │ (lessons 10, 11)  │
                                                                    └───────────────────┘
```

Lesson 11 followed one click from `App.jsx` down to the evaluator and back. This lesson covers the
machinery around that code: the files that install the tools, start the dev server, compile JSX,
decide which URL the page calls, and check and test the code. None of it is game logic, but every
frontend bug you chase passes through it. Two behaviours are worth knowing before you open the
browser's Network tab: in development every request goes to the Vite server, which forwards it to
Flask, and the first request on page load is sent twice, with the first copy cancelled.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [package.json:6-12](../frontend/package.json#L6-L12) | The five scripts. Each one is a single tool. |
| 2 | [package.json:13-32](../frontend/package.json#L13-L32) | Two runtime dependencies, eleven development ones, and the Node version. |
| 3 | [index.html:9-10](../frontend/index.html#L9-L10) | An empty `<div id="root">` and one `<script type="module">`. |
| 4 | [main.jsx:6-10](../frontend/src/main.jsx#L6-L10) | `createRoot(...).render(<StrictMode><App /></StrictMode>)`. |
| 5 | [App.jsx:6-8](../frontend/src/App.jsx#L6-L8) | `API_BASE`: empty by default, so requests stay on the page's own origin. |
| 6 | [vite.config.js:7-14](../frontend/vite.config.js#L7-L14) | The `/api` proxy that turns those requests into calls to Flask. |
| 7 | [App.jsx:198-209](../frontend/src/App.jsx#L198-L209) | The mount effect that StrictMode runs twice, and the cleanup that cancels the extra run. |
| 8 | [vite.config.js:15-18](../frontend/vite.config.js#L15-L18) and [test-setup.js](../frontend/src/test-setup.js) | How Vitest gets a browser-like DOM. |
| 9 | [.oxlintrc.json](../frontend/.oxlintrc.json) | Two rules set by hand, on top of oxlint's defaults. |

---

## Walkthrough

### 1. The tools and their Python equivalents

| Tool | Installed here | What it does | Closest Python equivalent |
|------|----------------|--------------|---------------------------|
| **Node.js** | v22.23.2 | Runs JavaScript outside the browser. Vite, oxlint and the tests all run on it. | the `python` program |
| **npm** | 10.9.8 | Installs packages listed in `package.json` and runs its scripts. | `pip` + `requirements.txt`, plus a Makefile |
| **Vite** | 8.3.5 | A dev server that compiles files on request and reloads the page, and a bundler for production. | `flask run --debug` plus a packager |
| **React** | 19.2.8 | Builds the page from components and state. | no direct equivalent (think Jinja templates that re-render themselves) |
| **oxlint** | 1.81.0 | Static checks for likely bugs. | `ruff` / `flake8` |
| **Vitest** | 5.0.5 | Finds `*.test.js` / `*.test.jsx` files and runs them, using Vite to compile them. | `pytest` |
| **jsdom** | 30.1.3 | A browser DOM written in JavaScript, so tests can render components without a browser. | no direct equivalent (a fake browser) |
| **Testing Library** | react 16.3.3, user-event 14.6.8, jest-dom 7.0.1 | Render a component, find elements the way a user would, click and type, and assert with `toBeInTheDocument()`. | Flask's `test_client()`, but for a page |

`@vitejs/plugin-react` (6.1.1) is the Vite plugin that compiles JSX and keeps component state across
edits (Fast Refresh). `@types/react` and `@types/react-dom` only give your editor type hints. The
project has no TypeScript.

### 2. `package.json`: the manifest

📍 [`frontend/package.json:1-33`](../frontend/package.json#L1-L33)
```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint --deny-warnings",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^19.2.8",
    "react-dom": "^19.2.8"
  },
  "devDependencies": {
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.8",
    "@types/react": "^19.2.18",
    "@types/react-dom": "^19.2.4",
    "@vitejs/plugin-react": "^6.1.0",
    "jsdom": "^30.1.3",
    "oxlint": "^1.79.0",
    "vite": "^8.2.2",
    "vitest": "^5.0.5"
  },
  "engines": {
    "node": ">=22.22.2"
  }
}
```

- **`"type": "module"`** makes every `.js` file an ES module (see the concept box).
- **Scripts** are named shortcuts: `npm run dev` runs `vite`, `npm run build` runs `vite build`, and
  so on. `test` is special: `npm test` works without `run`. `vitest run` runs the tests once and
  exits; plain `vitest` would keep watching the files.
- **`--deny-warnings`** makes oxlint exit with code 1 on any warning, not only on errors, so a CI job
  fails ([ci.yml:41](../.github/workflows/ci.yml#L41)).
- **`dependencies`** end up in the browser bundle: only React. **`devDependencies`** are tools you
  need while developing, testing and building. Six of the eleven are for tests.
- **`^19.2.8`** means "19.2.8 or any later 19.x". The exact versions are pinned in
  `package-lock.json`, which is committed, like a `pip freeze` file. That is how Vite can be 8.3.5 on
  disk while `package.json` says `^8.2.2`: `npm audit fix` moved the lock file to 8.3.5 to clear two
  high-severity dev-server advisories, and 8.3.5 still satisfies `^8.2.2`.
- **`engines`** records the Node version the project needs. The strictest dependency sets it: jsdom
  30 declares `^22.22.2 || ^24.15.0 || >=26.0.0`. The field is advisory: npm's `engine-strict`
  setting is off by default (`npm config get engine-strict` prints `false`).

| Command | What runs | What you get |
|---------|-----------|--------------|
| `npm install` | npm | `node_modules/` (gitignored), matching `package-lock.json` |
| `npm run dev` | `vite` | a dev server on http://localhost:5173 |
| `npm run build` | `vite build` | `dist/`: one HTML, one CSS and one JS file |
| `npm run preview` | `vite preview` | serves `dist/` on http://localhost:4173, to test the build |
| `npm run lint` | `oxlint --deny-warnings` | nothing at all when the code is clean; exit code 1 on any warning |
| `npm test` | `vitest run` | the 20 tests in `src/*.test.js` and `src/App.test.jsx` |

### 3. From `index.html` to `<App />`

📍 [`frontend/index.html:1-12`](../frontend/index.html#L1-L12)
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Liêng Scope – EV solver</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

This is the only HTML file. The body is one empty `<div>` and one script. Everything you see on the
page is drawn into that `<div>` by React. There are no font links, because the app uses the system
font (lesson 14), and no favicon link: the project has no `public/` folder any more.

The browser cannot run JSX, so Vite steps in. When you fetch `http://localhost:5173/` from the
running dev server, the HTML comes back with two scripts added at the top: `/@react-refresh` (Fast
Refresh) and `/@vite/client` (the hot-reload connection). When the browser then asks for
`/src/main.jsx`, Vite compiles it on the spot and sends plain JavaScript: `<App />` has become a call
like `_jsxDEV(App, {}, …)`, and `import App from './App.jsx'` has become
`import App from "/src/App.jsx"`. Each file is compiled only when it is requested.

📍 [`frontend/src/main.jsx:1-10`](../frontend/src/main.jsx#L1-L10)
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

- `createRoot(element).render(…)` hands the inside of `#root` to React.
- `import './index.css'` imports a stylesheet for its side effect: Vite puts the CSS on the page.
  `App.jsx` does the same with `App.css` ([App.jsx:2](../frontend/src/App.jsx#L2)).
- `<StrictMode>` is a development-only checker. It has a visible cost, covered in section 5.

### 4. Where the requests go: `API_BASE` and the proxy

Every `fetch` in the app starts with this constant:

📍 [`frontend/src/App.jsx:6-8`](../frontend/src/App.jsx#L6-L8)
```jsx
// Empty by default: requests go to /api on the page's own origin, which the Vite dev server
// proxies to Flask (vite.config.js). Set VITE_API_URL at build time when the API lives elsewhere.
const API_BASE = import.meta.env.VITE_API_URL ?? "";
```

`import.meta.env.VITE_API_URL` is an environment variable that Vite exposes to browser code (only
names that start with `VITE_` are exposed). Vite **replaces it with its value when it compiles**, so
for a production build the URL is fixed at build time. If it is not set, `API_BASE` is `""` and the
page calls `fetch("/api/solve")`: a relative URL, which the browser sends to the server the page came
from. `??` (not `||`) means only a missing variable falls back; `VITE_API_URL=""` is also "same
origin".

In development the page comes from the Vite server on port 5173, so that is where `/api/solve` goes.
The dev server config decides what happens next:

📍 [`frontend/vite.config.js:1-19`](../frontend/vite.config.js#L1-L19)
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
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
  },
})
```

The proxy says: when the browser asks **the Vite server** for anything under `/api`, Vite forwards
it to Flask and passes the answer back. `changeOrigin` rewrites the `Host` header to
`127.0.0.1:5000`, as if the request had been sent there directly. (The `test` block is for Vitest,
section 7.) With both servers running:

```bash
curl -s -X POST http://localhost:5173/api/solve -H 'Content-Type: application/json' \
     -d '{"hand":"As Kh Qd","opponent_model":"range"}'      # → Flask's JSON: RAISE, ev 131876.0
curl -s http://localhost:5173/health                           # → Vite's index.html, not Flask
```

`/health` is not under `/api`, so Vite answers it with the page itself.

Because the browser only ever talks to port 5173, page and API share one origin in development and
**CORS plays no part**. Flask still sends CORS headers, but only to the origins listed in
`CORS_ORIGINS` (by default `http://localhost:5173` and `http://127.0.0.1:5173`,
[app.py:141-142](../backend/app.py#L141-L142), lesson 16). They matter only when the page and the API
are on different origins, which is what `VITE_API_URL` is for.

When Flask is not running, the proxy cannot connect and answers by itself:

```
HTTP/1.1 502 Bad Gateway
Content-Type: text/plain
```

with an empty body. Every error from Flask has a JSON body with a `code`, so `solveErrorFor`
([App.jsx:41-46](../frontend/src/App.jsx#L41-L46), lesson 13) reads "no `code`", whatever the status,
as "the solver is not reachable" and shows "Can't reach the solver". Two tests pin it: this 502 and
a bare 404 from some other server ([App.test.jsx:99-100](../frontend/src/App.test.jsx#L99-L100)).

The app used to do this differently, and the comparison explains the current design:

| | Before (absolute URL + CORS) | Now (relative URL + proxy) |
|---|---|---|
| `API_BASE` in dev | `http://127.0.0.1:5000` | `""`, so requests go to `/api/solve` on 5173 |
| Who answers in dev | Flask directly | Vite, which forwards to Flask |
| CORS needed in dev | yes | no |
| A production build without `VITE_API_URL` | calls `127.0.0.1:5000`: each visitor's own computer | calls `/api` on the host that served the page |
| What the Network tab shows | requests to port 5000 | requests to port 5173 |

### 5. StrictMode: one extra, cancelled request on page load in development

With the Vite dev server running, headless Chromium recorded these requests on one page load (from a
network log):

```
POST http://localhost:5173/api/solve      sent, cancelled before the answer arrived
POST http://localhost:5173/api/solve      answered
POST http://localhost:5173/api/analyze    answered
```

The production build, served by `vite preview`, made one `/api/solve` and one `/api/analyze`. The
difference comes from StrictMode and this effect:

📍 [`frontend/src/App.jsx:199-210`](../frontend/src/App.jsx#L199-L210)
```jsx
  // The first run on mount. It reads the current inputs without making them effect dependencies.
  const startFirstRun = useEffectEvent((controller) => {
    currentRun.current = controller;
    runSolve(controller);
  });

  useEffect(() => {
    const controller = new AbortController();
    startFirstRun(controller);
    // In development StrictMode mounts twice; aborting here cancels the first, duplicate request.
    return () => controller.abort();
  }, []);
```

`useEffect(fn, [])` means "run `fn` after the component first appears", and the function `fn` returns
is its **cleanup**, run when the component goes away (lesson 13). In development, StrictMode
deliberately mounts the component, unmounts it and mounts it again, to expose effects that do not
clean up after themselves. Here the cleanup aborts the first run's `AbortController`, so the first
`/api/solve` is cancelled, its answer is thrown away, and its `/api/analyze` is never sent. The
request had already left the browser, so Flask may still compute it once; the page just ignores the
result. A test renders `<StrictMode><App /></StrictMode>` and checks exactly that: two solve requests,
the first one aborted ([App.test.jsx:174-182](../frontend/src/App.test.jsx#L174-L182)).

The language effect at [App.jsx:147-154](../frontend/src/App.jsx#L147-L154) also runs twice, which
is harmless because writing the same value twice changes nothing.

### 6. Linting: 104 rules, zero warnings

📍 [`frontend/.oxlintrc.json:1-8`](../frontend/.oxlintrc.json#L1-L8)
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

The file sets only two rules, but `npx oxlint --print-config` shows **104 active rules**: oxlint
turns on its whole "correctness" category by default, as warnings. The two rules set here:

- **`rules-of-hooks`** (an error): call `useState` and `useEffect` only at the top level of a
  component, never inside an `if` or a loop. React matches state to hooks by call order, so a
  conditional hook mixes them up.
- **`only-export-components`**: a component file should export only components, so Fast Refresh
  can swap it in place.

`npm run lint` prints nothing and exits 0. That is what a clean run of oxlint 1.81 looks like. Until
recently it printed two warnings about the mount effect, which then looked like this:

```jsx
  useEffect(() => {
    handleSolve();
  }, []);
```

- `react(set-state-in-effect)`: `handleSolve` called `setIsLoading(true)` synchronously inside the
  effect, which starts a second render straight away.
- `react-hooks(exhaustive-deps)`: the effect used `handleSolve` without listing it as a dependency.

The plain `oxlint` script exited 0 anyway, so nothing forced a fix. The new effect sets no state
itself (the first render already starts in the loading state), and `useEffectEvent` lets it read the
current inputs without listing them (lesson 13). Now that the code is clean, `--deny-warnings` keeps
it that way: exercise 5 brings a warning back and watches the exit code.

### 7. Tests with Vitest and jsdom

`npm test` runs `vitest run`. Vitest reads the same `vite.config.js` as the dev server, so tests are
compiled with the same React plugin, and JSX works in tests. Its `test` block (lines 15-18 above)
adds two settings:

- **`environment: 'jsdom'`** gives every test file a fake browser: `document`, `window`,
  `localStorage`, events. React can render into it.
- **`setupFiles`** runs one file before every test file:

📍 [`frontend/src/test-setup.js:1-8`](../frontend/src/test-setup.js#L1-L8)
```js
// Runs before every Vitest file: DOM matchers (toBeInTheDocument, …) and a clean DOM per test.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
```

The first import adds matchers such as `toBeInTheDocument()` and `toHaveTextContent()` to
`expect`. `cleanup()` removes whatever the previous test rendered, so tests can't see each other's
DOM.

Vitest finds three files: `src/App.test.jsx` (14 tests), `src/format.test.js` (4) and
`src/i18n.test.js` (2), 20 tests in all. The App tests replace `fetch` with a fake
([App.test.jsx:43-55](../frontend/src/App.test.jsx#L43-L55)), so no server is needed. Lesson 13
reads them, and lesson 15 puts them next to the backend suite.

The two older files predate Vitest: they still use Node's own `assert` module and only import `test`
from `vitest`. `format.js` exists because, under the previous test runner (`node --test`, which
cannot load JSX), logic had to live outside the component to be testable
([format.js:1](../frontend/src/format.js#L1) still says so). With jsdom that restriction is gone, but
a pure function is still the cheapest thing to test.

### 8. The production build

`npm run build` writes `dist/`:

| File | Size | gzip |
|------|------|------|
| `dist/index.html` | 0.41 kB | 0.29 kB |
| `dist/assets/index-C6PIeJn2.css` | 7.87 kB | 2.19 kB |
| `dist/assets/index-FK4GEu6c.js` | 210.10 kB | 66.11 kB |

Vite transformed 19 modules into one JS file, which is mostly React. The test files and the testing
libraries are not in it: nothing that `main.jsx` imports reaches them. The hash in each name changes
when the content changes, so browsers never use a stale cached copy. The built `index.html` no longer
points at `/src/main.jsx`. It loads `/assets/index-FK4GEu6c.js` and the CSS file instead.

The API URL is baked in. A build with `VITE_API_URL=https://api.example.invalid` contains the string
`https://api.example.invalid`. A build without it contains an empty string in its place, so the
bundle calls `/api/solve` on whatever host serves it. Lesson 16 uses this for deployment.

---

## 💡 Concept: ES modules (`import` / `export`)

A JavaScript file with `"type": "module"` is a module, much like a Python file:

```js
// format.js                          // App.jsx
export function formatMoney() {}      import { formatMoney } from './format.js';   // like: from format import formatMoney
export default function App() {}      import App from './App.jsx';                 // the one "default" export
                                      import './App.css';                          // side effect only (Vite: add CSS)
```

Differences from Python: the path is explicit (`./format.js`, with the extension), names are
imported only if they were `export`ed, and a module has at most one `default` export. Imports
without `./` (`'react'`) come from `node_modules`.

## 💡 Concept: StrictMode

`<StrictMode>` changes nothing in production. In development it runs extra checks:

- it calls each component function **twice** per render, to catch code that is not pure;
- it mounts, unmounts and remounts each component once, so every effect runs, cleans up and runs
  again.

If an effect is written correctly (it either does something harmless to repeat, or returns a
cleanup function that undoes it), the double run is invisible to the user. A fetch with no cleanup
shows up as two complete requests whose answers both land. The usual cleanup for a fetch is an
`AbortController` that cancels the first request, which is exactly what section 5 shows.

---

## Design decisions

- **Vite instead of Create React App or Webpack.** It starts in a fraction of a second and
  compiles on demand. The project was scaffolded with `npm create vite`; the unused starter files
  (`src/assets/`, `public/`, the template README) have since been deleted.
- **oxlint instead of ESLint.** It is a single fast binary with React rules built in, and there is
  no plugin list to maintain. The cost: fewer ecosystem plugins, and only two rules are set on
  purpose.
- **Vitest + jsdom + Testing Library instead of `node --test`.** It can render the real component
  and click through it, and it reuses the Vite config, so there is nothing separate to keep in sync.
  The cost: six more devDependencies and a higher Node floor (jsdom 30 needs 22.22.2+).
- **A relative URL plus the proxy rather than an absolute URL plus CORS.** Development behaves like a
  same-origin production deployment, and forgetting `VITE_API_URL` no longer points visitors at their
  own machine. The cost: in production, something must route `/api` to Flask, or you set
  `VITE_API_URL` and list the page's origin in `CORS_ORIGINS` (lesson 16).
- **StrictMode left on.** It catches unsafe effects early. The price is one cancelled request on each
  page load in development.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: a proxy nobody used.** The proxy forwarded `/api`, but the app called
  `http://127.0.0.1:5000` directly. Now `API_BASE` defaults to `""` ([App.jsx:6-8](../frontend/src/App.jsx#L6-L8)),
  so every dev request goes through the proxy ([vite.config.js:7-14](../frontend/vite.config.js#L7-L14)).
  No test pins the URL itself (see the first open item below).
- ✅ **Fixed: a silent localhost fallback in production.** A build without `VITE_API_URL` used to call
  `127.0.0.1:5000`, each visitor's own computer. It now calls `/api` on its own origin.
- ✅ **Fixed: lint warnings never failed.** [package.json:9](../frontend/package.json#L9) runs
  `oxlint --deny-warnings`, the two mount-effect warnings are gone (section 6), and CI runs the lint
  on every push ([ci.yml:40-43](../.github/workflows/ci.yml#L40-L43)).
- ✅ **Fixed: no `engines` field.** [package.json:30-32](../frontend/package.json#L30-L32) asks for
  Node 22.22.2 or newer, the floor jsdom sets.
- ✅ **Fixed: template leftovers.** `src/assets/`, `public/` and the template README were deleted;
  [frontend/README.md](../frontend/README.md) now describes this project.
- ✅ **Fixed: the component had no tests.** 14 Vitest tests now render `App` with `fetch` mocked
  ([App.test.jsx](../frontend/src/App.test.jsx)); 8 of the first 12 fail on the `App.jsx` that came
  before them.
- ✅ **Fixed: a title that oversold.** [index.html:6](../frontend/index.html#L6) now says "EV solver",
  matching the README (the tool computes EV, not an equilibrium).
- ✅ **Fixed: a 4xx without a `code` was called an input problem.** If a production host didn't route
  `/api` and answered with its own HTML 404, the page used to say "Check your inputs: HTTP 404".
  `solveErrorFor` now looks only at the body: no `code` means "not the solver"
  ([App.jsx:42](../frontend/src/App.jsx#L42)), whatever the status; `invalid_hand` and
  `invalid_params` are input problems; any other API code is a server error
  ([App.jsx:43-45](../frontend/src/App.jsx#L43-L45)). Two new table cases pin it: a bare 404 shows
  "Can't reach the solver", and a 404 with the API's `not_found` code shows the internal-error
  message ([App.test.jsx:100-101](../frontend/src/App.test.jsx#L100-L101)).

Still open:

1. **The tests can't tell a relative URL from an absolute one.** The fake `fetch` keeps only the
   path ([App.test.jsx:46](../frontend/src/App.test.jsx#L46)), so all 14 App tests still pass when
   `API_BASE` is `http://127.0.0.1:5000` (try it: `VITE_API_URL=http://127.0.0.1:5000 npm test`).
   The old fallback could come back unnoticed. *Fix:* one test that checks the exact URL (exercise 7).

---

## 🧪 Try it

Run from `frontend/` (see [COURSE.md](COURSE.md#setup)).

```bash
npm test
```

The end of the output (timings vary):

```
 Test Files  3 passed (3)
      Tests  20 passed (20)
```

List every test by name:

```bash
npx vitest run --reporter=verbose | grep '✓'
```

```
 ✓ src/format.test.js > formatMoney uses the requested locale's thousands separator 16ms
 ✓ src/format.test.js > formatMoney rounds to whole VND and keeps the minus sign 0ms
 ✓ src/format.test.js > formatMoney shows 0 before any value has arrived 0ms
 ✓ src/format.test.js > formatZones lists every profitable fold-frequency interval 1ms
 ✓ src/i18n.test.js > every language defines exactly the English keys, with the same kinds of values 3ms
 ✓ src/i18n.test.js > messages with a parameter include it in every language 1ms
 ✓ src/App.test.jsx > App > renders the verdict and figures from /api/solve 259ms
 ✓ src/App.test.jsx > App > the top-hands table reads showdown_equity 43ms
 ✓ src/App.test.jsx > App > an invalid hand shows its message and clears the old verdict 114ms
 ✓ src/App.test.jsx > App > a network failure shows the matching message 30ms
 ✓ src/App.test.jsx > App > a server error shows the matching message 30ms
 ✓ src/App.test.jsx > App > a 5xx that did not come from the API shows the matching message 39ms
 ✓ src/App.test.jsx > App > a 404 that did not come from the API shows the matching message 28ms
 ✓ src/App.test.jsx > App > an API error that isn't about the input shows the matching message 29ms
 ✓ src/App.test.jsx > App > the language toggle switches the text and is remembered 96ms
 ✓ src/App.test.jsx > App > the pot stepper moves by 10k and stops at 1,000 199ms
 ✓ src/App.test.jsx > App > the notes show the model the API reports 70ms
 ✓ src/App.test.jsx > App > analysis requests send only the inputs, never client-side results 26ms
 ✓ src/App.test.jsx > App > a click while the analysis is still loading cancels the old run 118ms
 ✓ src/App.test.jsx > App > StrictMode's double mount aborts the duplicate first request 46ms
```

```bash
npm run lint; echo "exit code $?"
```

```
> frontend@0.0.0 lint
> oxlint --deny-warnings

exit code 0
```

Prove the URL is baked in at build time. This writes `frontend/dist/`, which is gitignored. The
pattern matches the minified `API_BASE` constant, which sits right before the storage key:

```bash
VITE_API_URL=https://api.example.invalid npm run build > /dev/null
grep -o -E '[a-zA-Z_$]+=`[^`]*`,[a-zA-Z_$]+=`lieng-scope-lang`' dist/assets/*.js
npm run build > /dev/null
grep -o -E '[a-zA-Z_$]+=`[^`]*`,[a-zA-Z_$]+=`lieng-scope-lang`' dist/assets/*.js
```

```
_=`https://api.example.invalid`,v=`lieng-scope-lang`
_=``,v=`lieng-scope-lang`
```

(The one-letter names come from the minifier and can differ on your machine.)

With `python app.py` and `npm run dev` both running, try the proxy:

```bash
curl -s -X POST http://localhost:5173/api/solve -H 'Content-Type: application/json' \
     -d '{"hand":"As Kh Qd","opponent_model":"range"}' \
  | python3 -c 'import sys, json; e = json.load(sys.stdin)["hand_evaluation"]; print(e["decision"], e["ev"])'
```

```
RAISE 131876.0
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You open the page with `npm run dev`, then with `npm run build && npm run preview`.
How many `POST /api/solve` requests does each make on load, and how many `/api/analyze`? Check in
the browser's DevTools, Network tab, filtered on `api`.

<details><summary>Solution</summary>

In development: two `/api/solve`, the first shown as cancelled, and one `/api/analyze`. StrictMode
mounts the component twice in development only, and the cleanup of the mount effect
([App.jsx:204-209](../frontend/src/App.jsx#L204-L209)) aborts the first run before it gets as far as
the analysis. In the preview: one of each. `vite preview` uses the same proxy settings as the dev
server (its `preview.proxy` defaults to `server.proxy`), so the built page reaches Flask too.
</details>

**🟢 2. Predict.** With both servers running, what does `curl -s http://localhost:5173/api/health`
return, and why is it different from `curl -s http://localhost:5173/health`?

<details><summary>Solution</summary>

`/api/health` goes through the proxy to Flask, which has no such route, so you get Flask's JSON 404:
`{"code":"not_found","error":"The requested URL was not found on the server. …"}`. `/health` is not
under `/api`, so Vite answers it with `index.html`. Neither URL reaches Flask's real `/health`
route.
</details>

**🟢 3. Predict.** You build with `VITE_API_URL=https://api.example.invalid`, deploy the build, and
later change the variable on your hosting dashboard without rebuilding. Which URL does the live page
call?

<details><summary>Solution</summary>

Still `https://api.example.invalid`. Vite replaced `import.meta.env.VITE_API_URL` with the string
when it built the bundle. The browser never sees environment variables, so only a rebuild changes
the URL.
</details>

**🟡 4. Stop the backend.** With `npm run dev` running, stop `python app.py` and click "Run solver".
Predict what the Network tab shows for `/api/solve` and which message appears under the button. Then
find the line of `App.jsx` that chose the message, and the test that pins it.

<details><summary>Solution</summary>

`/api/solve` gets `502 Bad Gateway` with an empty `text/plain` body: the proxy itself answers, and
the dev-server terminal prints `http proxy error: /api/solve … ECONNREFUSED 127.0.0.1:5000`. The
body isn't JSON, so `.json().catch(() => ({}))` gives `{}`, and `solveErrorFor`
([App.jsx:42](../frontend/src/App.jsx#L42)) sees no `code`, so the message is "Can't reach the
solver. Start the backend on port 5000 and try again." The test is the third case of the table at
[App.test.jsx:96-106](../frontend/src/App.test.jsx#L96-L106), which answers with `reply(502, {})`.
Nothing to undo; start Flask again.
</details>

**🟡 5. Bring a warning back.** Replace the mount effect at
[App.jsx:204-209](../frontend/src/App.jsx#L204-L209) with the old version,
`useEffect(() => { startSolve(); }, []);`, and run `npm run lint; echo $?`. How many warnings, and
what is the exit code?

<details><summary>Solution</summary>

Three warnings and exit code 1. Two are the old ones on the effect line
(`react(set-state-in-effect)`, because `startSolve` calls `setIsLoading(true)`, and
`react-hooks(exhaustive-deps)`, because `startSolve` is not a dependency). The third is new:
`eslint(no-unused-vars)` for `startFirstRun`, which nothing calls any more. With the old plain
`oxlint` script the exit code would have been 0. `npm test` still passes all 20, by the way:
`startSolve` aborts whatever run is in `currentRun` before it starts a new one, so the StrictMode
test still sees the first request aborted. Here the linter is the only guard. Undo with
`git checkout -- frontend/src/App.jsx`.
</details>

**🟡 6. Turn StrictMode off.** In [main.jsx](../frontend/src/main.jsx), render `<App />` without
`<StrictMode>` (and drop the import). Reload the dev page and count the requests again.

<details><summary>Solution</summary>

```jsx
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(<App />)
```

One `/api/solve` and one `/api/analyze`, as in production, and no cancelled request. That proves the
extra request came from StrictMode and not from the code. It is still better to keep StrictMode: it
is what showed that the effect needed a cleanup. Undo with `git checkout -- frontend/src/main.jsx`.
</details>

**🔴 7. Pin the relative URL.** Run `VITE_API_URL=http://127.0.0.1:5000 npm test`. All 20 tests pass,
although the page now calls Flask directly, as it did before the fix. Explain why, then add a test to
[App.test.jsx](../frontend/src/App.test.jsx) that fails in exactly this situation and passes with a
plain `npm test`.

<details><summary>Solution</summary>

`mockFetch` turns every URL into `new URL(url, "http://localhost").pathname`
([App.test.jsx:46](../frontend/src/App.test.jsx#L46)), which throws the scheme, host and port away,
so `/api/solve` and `http://127.0.0.1:5000/api/solve` look the same. Look at the raw first argument
instead:

```jsx
test("requests go to /api on the page's own origin", async () => {
  const fetchMock = vi.fn(() => new Promise(() => {}));  // never answers; we only look at the URL
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/solve");
});
```

With `npm test` it passes. With `VITE_API_URL=http://127.0.0.1:5000 npm test` it fails:

```
AssertionError: expected 'http://127.0.0.1:5000/api/solve' to be '/api/solve' // Object.is equality
```

Keep the test if you like; undo with `git checkout -- frontend/src/App.test.jsx`.
</details>

---

## ❓ Quiz

1. Which `package.json` entries end up in the browser bundle, and which never leave your machine?
2. Why can Vitest render `App.jsx` when `node --test` could not even load it?
3. In development, why does the browser not need CORS headers to read Flask's answers?
4. Why do two `/api/solve` requests appear in development, and why does only one of them count?
5. Where does a production build get its API URL from, and when is that decided?

<details><summary>Answers</summary>

1. `dependencies` (React and React DOM) are bundled into `dist/assets/index-*.js`.
   `devDependencies` (Vite, the React plugin, oxlint, Vitest, jsdom, Testing Library, the type
   definitions) are only used to develop, lint, test and build.
2. Vitest compiles test files and everything they import with Vite and the React plugin, so JSX
   works, and `environment: 'jsdom'` gives React a DOM to render into. Node alone has neither a JSX
   compiler nor a `document`.
3. Because the page and the API share one origin: the page calls `/api/solve` on
   `localhost:5173`, and the Vite proxy forwards it to Flask server-side. CORS only applies when a page
   reads a response from a different origin.
4. StrictMode mounts the component, unmounts it and mounts it again in development, so the mount
   effect runs twice. The cleanup aborts the first run's `AbortController`, so its answer is ignored
   and its analysis never starts. StrictMode does nothing in a production build.
5. From `VITE_API_URL`, replaced into the code by Vite at build time. Without it the bundle contains
   an empty string, so requests go to `/api` on the host that served the page. Changing the variable
   later has no effect until you rebuild.
</details>

---

## Recap

- Node runs the tools, npm installs them and runs the five scripts, Vite serves and builds the page,
  React draws it, oxlint checks it, and Vitest with jsdom and Testing Library tests it.
- `index.html` is an empty shell. `main.jsx` mounts `<App />` into `#root` inside `<StrictMode>`.
- Every request goes to `API_BASE`: `VITE_API_URL`, fixed at build time, or `""`, meaning the
  page's own origin. In development the Vite proxy forwards `/api` to Flask, so no CORS is involved;
  when Flask is down, the proxy answers 502 with an empty body.
- StrictMode runs the mount effect twice in development; the effect's cleanup aborts the first run,
  so only one solve and one analysis count. Production makes one of each.
- `npm run lint` has 104 rules active, prints nothing and exits 0; with `--deny-warnings`, any warning
  fails it. `npm test` runs 20 tests, 14 of them on the component.

**Next:** [13 — The React app](13-frontend-app.md)
