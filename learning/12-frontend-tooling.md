# Lesson 12 — Frontend tooling

> **Goal:** know what each frontend tool does, what happens between `npm run dev` and a page in
> your browser, and how that page finds the API in development and in production.
> **Files:** [`frontend/package.json`](../frontend/package.json), [`frontend/vite.config.js`](../frontend/vite.config.js),
> [`frontend/index.html`](../frontend/index.html), [`frontend/src/main.jsx`](../frontend/src/main.jsx),
> [`frontend/.oxlintrc.json`](../frontend/.oxlintrc.json), and one line of [`App.jsx`](../frontend/src/App.jsx#L6).
> **Time:** ~40 min. **Before this:** [11 — Tracing one request end to end](11-request-trace.md).

---

## Where this fits

```
 frontend/                                                       backend/
 ┌────────────────────────────────────────────────┐
 │ ┌──────────────── this lesson ───────────────┐ │
 │ │ package.json    scripts and dependencies   │ │
 │ │ vite.config.js  dev server, /api proxy     │ │
 │ │ index.html ──► src/main.jsx ──► <App />    │ │
 │ │ .oxlintrc.json  lint rules; node --test    │ │
 │ └────────────────────────────────────────────┘ │
 │   App.jsx, i18n.js, format.js     (lesson 13)  │    fetch      ┌───────────────────┐
 │   index.css, App.css              (lesson 14)  │ ────────────► │ app.py on :5000   │
 └────────────────────────────────────────────────┘  JSON + CORS  │ (lessons 10, 11)  │
                                                                  └───────────────────┘
```

Lesson 11 followed one click from `App.jsx` down to the evaluator and back. This lesson covers the
machinery around that code: the files that install the tools, start the dev server, compile JSX,
decide which URL the page calls, and check the code. None of it is game logic, but every frontend
bug you chase passes through it. Two of its behaviours surprise people: the page calls the API
twice on load in development, and the dev proxy you can see in `vite.config.js` is never used.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [package.json:6-12](../frontend/package.json#L6-L12) | The five scripts. Each one is a single tool. |
| 2 | [package.json:13-23](../frontend/package.json#L13-L23) | Two runtime dependencies, five development ones. |
| 3 | [index.html:9-10](../frontend/index.html#L9-L10) | An empty `<div id="root">` and one `<script type="module">`. |
| 4 | [main.jsx:6-10](../frontend/src/main.jsx#L6-L10) | `createRoot(...).render(<StrictMode><App /></StrictMode>)`. |
| 5 | [App.jsx:6](../frontend/src/App.jsx#L6) | `API_BASE`: where every request goes. |
| 6 | [vite.config.js:7-12](../frontend/vite.config.js#L7-L12) | The `/api` proxy, and why line 5 above bypasses it. |
| 7 | [App.jsx:116-119](../frontend/src/App.jsx#L116-L119) | The mount effect that StrictMode runs twice, and that lint warns about. |
| 8 | [.oxlintrc.json](../frontend/.oxlintrc.json) | Two rules set by hand, on top of oxlint's defaults. |

---

## Walkthrough

### 1. Six tools and their Python equivalents

| Tool | Installed here | What it does | Closest Python equivalent |
|------|----------------|--------------|---------------------------|
| **Node.js** | v22.23.2 | Runs JavaScript outside the browser. Vite, oxlint and the tests all run on it. | the `python` program |
| **npm** | 10.9.8 | Installs packages listed in `package.json` and runs its scripts. | `pip` + `requirements.txt`, plus a Makefile |
| **Vite** | 8.2.2 | A dev server that compiles files on request and reloads the page, and a bundler for production. | `flask run --debug` plus a packager |
| **React** | 19.2.8 | Builds the page from components and state. | no direct equivalent (think Jinja templates that re-render themselves) |
| **oxlint** | 1.81.0 | Static checks for likely bugs. | `ruff` / `flake8` |
| **node --test** | built into Node | Finds `*.test.js` files and runs them. | `pytest` |

`@vitejs/plugin-react` (6.1.1) is the Vite plugin that compiles JSX and keeps component state across
edits (Fast Refresh). `@types/react` and `@types/react-dom` only give your editor type hints. The
project has no TypeScript.

### 2. `package.json`: the manifest

📍 [`frontend/package.json:1-24`](../frontend/package.json#L1-L24)
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

- **`"type": "module"`** makes every `.js` file an ES module (see the concept box). That is why the
  tests can `import` from `./i18n.js` with no build step.
- **Scripts** are named shortcuts: `npm run dev` runs `vite`, `npm run build` runs `vite build`, and
  so on. `test` is special: `npm test` works without `run`.
- **`dependencies`** end up in the browser bundle: only React. **`devDependencies`** are tools you
  need while developing and building.
- **`^19.2.8`** means "19.2.8 or any later 19.x". The exact versions are pinned in
  `package-lock.json`, which is committed, like a `pip freeze` file. That is how `oxlint` can be
  1.81.0 on disk while `package.json` says `^1.79.0`.

| Command | What runs | What you get |
|---------|-----------|--------------|
| `npm install` | npm | `node_modules/` (gitignored), matching `package-lock.json` |
| `npm run dev` | `vite` | a dev server on http://localhost:5173 |
| `npm run build` | `vite build` | `dist/`: one HTML, one CSS and one JS file |
| `npm run preview` | `vite preview` | serves `dist/` on http://localhost:4173, to test the build |
| `npm run lint` | `oxlint` | warnings and errors for `src/` |
| `npm test` | `node --test` | the 6 tests in `src/*.test.js` |

### 3. From `index.html` to `<App />`

📍 [`frontend/index.html:1-12`](../frontend/index.html#L1-L12)
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Liêng Scope – GTO solver</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

This is the only HTML file. The body is one empty `<div>` and one script. Everything you see on the
page is drawn into that `<div>` by React. There are no font links, because the app uses the system
font (lesson 14).

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

### 4. Where the requests go: `API_BASE`, the proxy and CORS

Every `fetch` in the app starts with this constant:

📍 [`frontend/src/App.jsx:6`](../frontend/src/App.jsx#L6)
```jsx
const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";
```

`import.meta.env.VITE_API_URL` is an environment variable that Vite exposes to browser code (only
names that start with `VITE_` are exposed). Vite **replaces it with its value when it compiles**, so
for a production build the URL is fixed at build time. If it is not set, the page calls Flask
directly on port 5000.

Now look at the dev server config:

📍 [`frontend/vite.config.js:1-15`](../frontend/vite.config.js#L1-L15)
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

The proxy says: when the browser asks **the Vite server** for anything under `/api`, Vite forwards
it to Flask and passes the answer back. It works. With both servers running:

```bash
curl -s -X POST http://localhost:5173/api/solve -H 'Content-Type: application/json' \
     -d '{"hand":"As Kh Qd","opponent_model":"range"}'      # → Flask's JSON: RAISE, ev 131876.0
curl -s http://localhost:5173/health                           # → Vite's index.html, not Flask
```

`/health` is not under `/api`, so Vite answers it with the page itself.

**But the app never uses the proxy.** `API_BASE` is an absolute URL, so the browser sends
`POST http://127.0.0.1:5000/api/solve` straight to Flask. The page lives on `localhost:5173` and
the API on `127.0.0.1:5000`: two different origins. The browser only lets the page read the answer
because Flask sends CORS headers ([app.py:28](../backend/app.py#L28), lesson 10). You can see them:

```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:5173
```

flask-cors is configured with `"*"`, and it answers by echoing the origin that asked.

| | Today: absolute URL + CORS | Alternative: relative URL + proxy |
|---|---|---|
| `API_BASE` in dev | `http://127.0.0.1:5000` | `""`, so requests go to `/api/solve` on 5173 |
| Who answers in dev | Flask directly | Vite, which forwards to Flask |
| CORS needed | yes, in dev and production | not in dev |
| Production | `VITE_API_URL` set at build time, or the localhost fallback | the host must serve the API on the same origin, or you still set `VITE_API_URL` |
| What the Network tab shows | requests to port 5000 | requests to port 5173 |

Both work. The cost of having both is confusion: the proxy suggests one design, and the code uses the
other (weak spot 1). Exercise 4 switches to the proxy.

### 5. StrictMode: two requests on every page load in development

With the Vite dev server running, a headless browser recorded these requests on one page load:

```
POST http://127.0.0.1:5000/api/solve
POST http://127.0.0.1:5000/api/solve
POST http://127.0.0.1:5000/api/analyze
POST http://127.0.0.1:5000/api/analyze
```

The production build, served as static files, made one of each. The cause is this effect, plus
StrictMode:

📍 [`frontend/src/App.jsx:116-119`](../frontend/src/App.jsx#L116-L119)
```jsx
  // Run initial solve on mount
  useEffect(() => {
    handleSolve();
  }, []);
```

`useEffect(fn, [])` means "run `fn` after the component first appears" (lesson 13). In development,
StrictMode deliberately mounts the component, unmounts it and mounts it again, to expose effects
that do not clean up after themselves. This effect has no cleanup, so it runs twice, and each run
starts the two-step fetch from lesson 11. Both answers are identical, so the page looks right, but
the backend does the work twice, and the analysis request (an LLM call when a key is configured) is
also sent twice. The language effect at [App.jsx:41-48](../frontend/src/App.jsx#L41-L48) also runs
twice, which is harmless because writing the same value twice changes nothing.

### 6. Linting: 104 rules, two warnings

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

`npm run lint` prints two warnings, both about the mount effect above:

```
src/App.jsx:118:5: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders help: Effects should synchronize React with external systems. Calling setState synchronously inside an effect starts another render and is usually unnecessary. Derive the value during render, initialize state directly, or update it from the event that caused the change. Use an effect only when synchronizing with an external system.
src/App.jsx:118:5: warning react-hooks(exhaustive-deps): React Hook useEffect has a missing dependency: 'handleSolve' help: Either include it or remove the dependency array.
```

The exit code is still 0, so nothing forces anyone to fix them. Lesson 13 explains both and the
fix (exercise 8 there).

### 7. Tests with `node --test`

`npm test` runs `node --test` with no arguments. Node then searches the folder for test files
(names like `*.test.js`, skipping `node_modules`) and finds two: `src/format.test.js` and
`src/i18n.test.js`, with 6 tests between them. There is no Jest, no Vitest and no config file.

This works only because `format.js` and `i18n.js` are plain JavaScript modules with no JSX and no
`import.meta.env`. Node cannot load the component itself:

```
TypeError [ERR_UNKNOWN_FILE_EXTENSION]: Unknown file extension ".jsx" for /home/kietto/Desktop/lieng-stealer/frontend/src/App.jsx
```

So the rule in this project is: **logic that needs a test goes into a `.js` file outside the
component.** That is why `format.js` exists ([format.js:1](../frontend/src/format.js#L1) says so).
Lesson 13 reads the tests themselves.

### 8. The production build

`npm run build` writes `dist/`:

| File | Size | gzip |
|------|------|------|
| `dist/index.html` | 0.41 kB | 0.29 kB |
| `dist/assets/index-D2Sg5JNI.css` | 7.68 kB | 2.15 kB |
| `dist/assets/index-D-7Ktmhb.js` | 210.48 kB | 65.75 kB |

Vite transformed 19 modules into one JS file, which is mostly React. The hash in each name changes
when the content changes, so browsers never use a stale cached copy. The built `index.html` no longer
points at `/src/main.jsx`. It loads `/assets/index-D-7Ktmhb.js` and the CSS file instead. The two
files in `public/` (`favicon.svg`, `icons.svg`) are copied into `dist/` unchanged, even though
nothing uses them.

The API URL is baked in. A build with `VITE_API_URL=https://api.example.invalid` contains only
`https://api.example.invalid`, and the fallback disappears from the bundle. A build without it
contains `http://127.0.0.1:5000`. Lesson 16 uses this for deployment.

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
cleanup function that undoes it), the double run is invisible. A fetch with no cleanup shows up as
two requests. The usual cleanup for a fetch is an `AbortController` that cancels the first request.

---

## Design decisions

- **Vite instead of Create React App or Webpack.** It starts in a fraction of a second and
  compiles on demand. The project was scaffolded with `npm create vite`, and the leftovers show it
  (weak spot 5).
- **oxlint instead of ESLint.** It is a single fast binary with React rules built in, and there is
  no plugin list to maintain. The cost: fewer ecosystem plugins, and only two rules are set on
  purpose.
- **`node --test` instead of Jest or Vitest.** There is nothing to install or configure. The cost
  is that it cannot render components, so only pure modules are tested.
- **An absolute URL plus CORS rather than the proxy.** Development and production work the same
  way (the browser talks to Flask directly), and Flask already needs CORS for a separately hosted
  frontend. The cost: the proxy in `vite.config.js` is dead configuration.
- **StrictMode left on.** It catches unsafe effects early. The price is the doubled requests in
  development.

---

## ⚠️ Weak spots

1. **A proxy nobody uses.** [vite.config.js:7-12](../frontend/vite.config.js#L7-L12) forwards `/api`,
   but [App.jsx:6](../frontend/src/App.jsx#L6) calls an absolute URL. Readers assume one design
   and debug the other. *Fix:* pick one: delete the proxy, or make `API_BASE` default to `""`
   (exercise 4).
2. **A silent localhost fallback in production.** If you forget `VITE_API_URL` when building, the
   bundle calls `http://127.0.0.1:5000`, which is each visitor's own computer. The page then shows
   "Can't reach the solver" ([i18n.js:26](../frontend/src/i18n.js#L26)) with no hint about the cause.
   *Fix:* use the fallback only when `import.meta.env.DEV` is true, or fail the build when the
   variable is missing.
3. **Lint warnings never fail.** [package.json:9](../frontend/package.json#L9) runs plain `oxlint`,
   which exits 0 with warnings, so the two warnings in section 6 have survived. *Fix:*
   `oxlint --deny-warnings` (exercise 5), once they are fixed.
4. **No `engines` field.** Vite 8 needs Node 20.19+ or 22.12+ ([COURSE.md](COURSE.md#setup) says so),
   but [package.json](../frontend/package.json) does not, so npm will not warn on an older Node.
   *Fix:* add `"engines": { "node": "^20.19.0 || >=22.12.0" }`.
5. **Template leftovers.** `src/assets/` (`hero.png`, `react.svg`, `vite.svg`), `public/`
   (`favicon.svg`, `icons.svg`) and the template [frontend/README.md](../frontend/README.md) are never
   used. The `public/` files are even copied into every build. *Fix:* delete them, or link the
   favicon from `index.html`.
6. **The component has no tests.** Only `format.js` and `i18n.js` are tested. Node cannot load
   `.jsx`, so `handleSolve`, the error paths and the rendering in
   [App.jsx](../frontend/src/App.jsx) are untested (lesson 15). *Fix:* move more logic into `.js`
   modules, or add Vitest with a DOM library.
7. **A title that oversells.** [index.html:6](../frontend/index.html#L6) says "GTO solver", while the
   README says the tool computes EV, not an equilibrium (lessons 00 and 17).

---

## 🧪 Try it

Run from `frontend/` (see [COURSE.md](COURSE.md#setup)).

```bash
npm test
```

The end of the output (timings vary):

```
1..6
# tests 6
# suites 0
# pass 6
# fail 0
# cancelled 0
# skipped 0
# todo 0
```

```bash
npm run lint; echo "exit code $?"
```

Expected: the two `src/App.jsx:118:5` warnings from section 6, then `exit code 0`.

See which lines the tests cover:

```bash
node --test --experimental-test-coverage 2>&1 | grep -A 12 'start of coverage'
```

```
# start of coverage report
# ----------------------------------------------------------------
# file            | line % | branch % | funcs % | uncovered lines
# ----------------------------------------------------------------
# src             |        |          |         |
#  format.js      | 100.00 |   100.00 |  100.00 |
#  format.test.js | 100.00 |   100.00 |  100.00 |
#  i18n.js        | 100.00 |   100.00 |   57.14 |
#  i18n.test.js   | 100.00 |   100.00 |  100.00 |
# ----------------------------------------------------------------
# all files       | 100.00 |   100.00 |   76.92 |
# ----------------------------------------------------------------
# end of coverage report
```

Prove the URL is baked in at build time. This writes `frontend/dist/`, which is gitignored:

```bash
VITE_API_URL=https://api.example.invalid npm run build > /dev/null
grep -o -E 'https://api.example.invalid|http://127.0.0.1:5000' dist/assets/*.js
npm run build > /dev/null
grep -o -E 'https://api.example.invalid|http://127.0.0.1:5000' dist/assets/*.js
```

```
https://api.example.invalid
http://127.0.0.1:5000
```

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
How many `POST /api/solve` requests does each make on load? Check in the browser's DevTools,
Network tab, filtered on `api`.

<details><summary>Solution</summary>

Two in development, one in the preview. StrictMode mounts the component twice in development only,
and the mount effect at [App.jsx:117-119](../frontend/src/App.jsx#L117-L119) has no cleanup.
`/api/analyze` follows the same pattern: two, then one.
</details>

**🟢 2. Predict.** With both servers running, what does `curl -s http://localhost:5173/api/health`
return, and why is it different from `curl -s http://localhost:5173/health`?

<details><summary>Solution</summary>

`/api/health` goes through the proxy to Flask, which has no such route, so you get Flask's HTML
"404 Not Found" page (lesson 10 lists the HTML error pages as a weak spot). `/health` is not under
`/api`, so Vite answers it with `index.html`. Neither URL reaches Flask's real `/health` route.
</details>

**🟢 3. Predict.** You build with `VITE_API_URL=https://api.example.invalid`, deploy the build, and
later change the variable on your hosting dashboard without rebuilding. Which URL does the live page
call?

<details><summary>Solution</summary>

Still `https://api.example.invalid`. Vite replaced `import.meta.env.VITE_API_URL` with the string
when it built the bundle. The browser never sees environment variables, so only a rebuild changes
the URL.
</details>

**🟡 4. Use the proxy.** Change [App.jsx:6](../frontend/src/App.jsx#L6) to
`const API_BASE = import.meta.env.VITE_API_URL ?? "";` and reload `npm run dev`. Where do the
requests go now? Does `npm test` still pass? What would happen in a production build without
`VITE_API_URL`?

<details><summary>Solution</summary>

The Network tab now shows `POST http://localhost:5173/api/solve` (twice, StrictMode) and the
same for `/api/analyze`. Vite forwards them to Flask, so the page works and CORS is no longer
involved in development. `npm test` still passes 6 of 6, because no test imports `App.jsx`. In a
production build without the variable, the page would call `/api/solve` on whatever host serves the
static files. That works only if that host also routes `/api` to Flask. `??` rather than `||`
matters here: `VITE_API_URL=""` would then mean "same origin" on purpose.
Undo with `git checkout -- frontend/src/App.jsx`.
</details>

**🟡 5. Make warnings fail.** Change the `lint` script in
[package.json:9](../frontend/package.json#L9) to `oxlint --deny-warnings`. Run
`npm run lint; echo $?`.

<details><summary>Solution</summary>

The same two warnings are printed, and the exit code is now 1, so a CI job would fail. Keep this
change only after fixing the warnings (lesson 13, exercise 8). Undo with
`git checkout -- frontend/package.json`.
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

One `/api/solve` and one `/api/analyze`, as in production. That proves the doubling came from
StrictMode and not from the code. It is still better to keep StrictMode and make the effect safe
(lesson 13). Undo with `git checkout -- frontend/src/main.jsx`.
</details>

**🔴 7. Close the coverage gap.** The coverage report says `i18n.js` has 57.14% function coverage.
Find out which functions the tests never call, and add a test to
[i18n.test.js](../frontend/src/i18n.test.js) that brings it to 100%. Check with
`node --test --experimental-test-coverage`.

<details><summary>Solution</summary>

The second test calls only functions with a parameter (`value.length > 0`). The three
parameterless messages, `solverOffline`, `aiNoAdvice` and `aiUnreachable`, are never called in
either language: 8 of 14 functions, 57.14%. Add:

```js
test("every message function returns a non-empty string in every language", () => {
  for (const lang of LANGUAGES) {
    for (const [key, value] of Object.entries(STRINGS[lang])) {
      if (typeof value === "function") {
        const text = value("x");
        assert.equal(typeof text, "string", `${lang}.${key}`);
        assert.ok(text.length > 0, `${lang}.${key}`);
      }
    }
  }
});
```

Now 7 tests pass and `i18n.js` shows `100.00 | 100.00 | 100.00`.
Undo with `git checkout -- frontend/src/i18n.test.js`.
</details>

---

## ❓ Quiz

1. Which `package.json` entries end up in the browser bundle, and which never leave your machine?
2. Why can `node --test` import `i18n.js` but not `App.jsx`?
3. The proxy in `vite.config.js` works. Why does the app still need CORS?
4. Why do two `/api/solve` requests appear in development and only one in production?
5. Where does a production build get its API URL from, and when is that decided?

<details><summary>Answers</summary>

1. `dependencies` (React and React DOM) are bundled into `dist/assets/index-*.js`.
   `devDependencies` (Vite, the React plugin, oxlint, the type definitions) are only used to
   develop, lint and build.
2. `"type": "module"` makes `.js` files ES modules that Node can import directly. `App.jsx`
   contains JSX, which only Vite's React plugin can compile, so Node rejects the `.jsx` extension.
3. Because the app does not go through it. `API_BASE` is `http://127.0.0.1:5000`, a different
   origin from `localhost:5173`, so the browser calls Flask directly and needs Flask's
   `Access-Control-Allow-Origin` header to read the answer.
4. StrictMode mounts the component, unmounts it and mounts it again in development, so the mount
   effect runs twice. StrictMode does nothing in a production build.
5. From `VITE_API_URL`, replaced into the code by Vite at build time. Without it the bundle contains
   the fallback `http://127.0.0.1:5000`. Changing the variable later has no effect until you
   rebuild.
</details>

---

## Recap

- Node runs the tools, npm installs them and runs the five scripts, Vite serves and builds the page,
  React draws it, oxlint checks it and `node --test` tests the pure modules.
- `index.html` is an empty shell. `main.jsx` mounts `<App />` into `#root` inside `<StrictMode>`.
- Every request goes to `API_BASE`: `VITE_API_URL`, fixed at build time, or `http://127.0.0.1:5000`.
  The Vite proxy is configured but bypassed, so CORS does the work.
- StrictMode runs the mount effect twice in development, which means two `/api/solve` and two
  `/api/analyze` calls. Production makes one of each.
- `npm run lint` has 104 rules active and reports two warnings on the mount effect, but exits 0.
- Only `.js` modules can be tested with `node --test`. Put logic you want to test outside the
  component.

**Next:** [13 — The React app](13-frontend-app.md)
