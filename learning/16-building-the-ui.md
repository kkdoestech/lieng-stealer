# 15 — Building the UI ("LIÊNG SCOPE")

> **Goal:** build the full dashboard: inputs on the left; verdict, metrics and tables on the right;
> styled as a dark "tactical radar terminal".
> **You will build:** `frontend/src/index.css`, `frontend/src/App.jsx`, `frontend/src/App.css`.
> **Time:** ~3 hours.
> **Prerequisites:** [14](15-frontend-foundations.md). Flask running (`python app.py` in `backend/`).

---

## The big picture

The whole UI is **one component**, `App`, plus two stylesheets. The data flow is a loop:

```
   ┌───────────── state (useState) ──────────────┐
   │ pot, betSize, foldEquity, hand   ◄── inputs  │◄──── user types / clicks a preset
   │ solveData, aiAdvice, isLoading, error, …     │
   └──────────────┬───────────────────────────────┘
                  │ "EXECUTE SOLVER" → handleSolve()
                  ▼
     POST /api/solve  ──►  setSolveData(json)  ──►  POST /api/analyze  ──►  setAiAdvice(text)
                  │
                  ▼ every state change re-renders App
     verdict banner · 4 HUD cards · category matrix · top-10 table · notes drawer
```

The page layout:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ LIÊNG SCOPE                                          ● LIVE SOLVER / 455 CLASSES│  header
├──────────────────────────┬──────────────────────────────────────────────────────┤
│ // TELEMETRY CONTROLS    │ ACTION: RAISE / ALL-IN                  +132,097 VND │  verdict
│ CURRENT POT  [100000]    ├─────────────┬─────────────┬────────────┬─────────────┤
│  50k 100k 200k 500k      │ RANGE COV.  │ SHOWDOWN EQ │ EXP. VALUE │ BLUFF THRESH│  HUD
│ BET / RAISE  [50000]     ├─────────────┴─────────────┴────────────┴─────────────┤
│  0.5x 1.0x 2.0x Pot      │ // CATEGORY COVERAGE MATRIX  (SÁP, LIÊNG, ĐĨ, ĐIỂM)  │  table
│ FOLD FREQUENCY ──●── 35% ├──────────────────────────────────────────────────────┤
│ HAND [As Kh Qd]          │ // TOP PROFITABLE HOLDINGS   (top 10 canonical hands)│  table
│ [ EXECUTE SOLVER ]       ├──────────────────────────────────────────────────────┤
│ specs                    │ [ + MATHEMATICAL TELEMETRY NOTES ]  ▼                │  drawer
└──────────────────────────┴──────────────────────────────────────────────────────┘
```

We build it in three parts:

- **Part A:** `index.css`, global design tokens (colours, font, background grid).
- **Part B:** `App.jsx`, the logic and the markup.
- **Part C:** `App.css`, the styles, section by section, watching the page change after each one.

> 📝 **Which version?** This chapter rebuilds the version **committed** in the repository. If your
> copy of the original has newer, uncommitted changes (for example a language switcher with an
> `i18n.js` file), they're not covered here.

---

## Concepts you need: CSS in brief

CSS is a list of **rules**: a **selector** (which elements) and **declarations** (what style):

```css
.panel-tag {                 /* selector: every element with class="panel-tag" */
  font-size: 0.75rem;        /* declaration: property: value; */
  color: var(--accent-green);
}
```

| Concept | Example | Meaning |
|---|---|---|
| class selector | `.hud-card` | elements with `className="hud-card"` |
| combined | `.verdict-raise .verdict-title` | a `.verdict-title` **inside** a `.verdict-raise` |
| both classes | `.preset-chip.active` | an element that has **both** classes |
| pseudo-class | `:hover`, `:focus`, `:disabled`, `:not(...)` | element **state** |
| pseudo-element | `::selection`, `::-webkit-slider-thumb` | a **part** of an element |
| CSS variable | `--accent-green: #22C55E;` then `var(--accent-green)` | reusable named value |
| `rem` | `1.5rem` | relative to the root font size (usually 16px), so it scales with user settings |
| flexbox | `display: flex; justify-content: space-between;` | lay children out in a **row** (or column) |
| grid | `display: grid; grid-template-columns: 380px 1fr;` | lay children out in a **2-D grid**; `1fr` = "the remaining space" |
| media query | `@media (max-width: 1024px) { … }` | rules that apply only on smaller screens (responsive design) |
| transition | `transition: all 0.15s ease;` | animate changes smoothly (e.g. on hover) |
| keyframes | `@keyframes pulse { 0% {…} 50% {…} }` | a named animation |

The **design spec** for this look is in [`DESIGN.md`](../DESIGN.md): near-black background, radar green
`#22C55E`, monospace font everywhere, sharp 2px corners, no emoji, no purple gradients.

---

# Part A — Global design tokens

## Step 15.1 — `index.css`

📄 **File:** `frontend/src/index.css` — *create this file*

```css
:root {
  /* Canvas & Surfaces */
  --bg-canvas: #050705;
  --bg-grid: rgba(34, 197, 94, 0.03);
  --bg-surface: #101511;
  --bg-surface-hover: #151C17;
  --bg-surface-input: #0A0E0B;

  /* Tactical Borders */
  --border-base: #1C261F;
  --border-highlight: #22C55E;
  --border-subtle: #141C16;

  /* Accents & Status */
  --accent-green: #22C55E;
  --accent-green-muted: #153820;
  --accent-green-glow: rgba(34, 197, 94, 0.15);
  --accent-red: #EF4444;
  --accent-red-muted: #2A1215;
  --accent-red-glow: rgba(239, 68, 68, 0.15);
  --accent-amber: #F59E0B;

  /* Typography */
  --text-white: #FFFFFF;
  --text-green: #22C55E;
  --text-muted: #85998B;
  --text-dim: #4B5E51;

  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: dark;
}
```

**How it works**

- `:root` is the `<html>` element. Variables defined here are available **everywhere**. These are the
  **design tokens** from `DESIGN.md` §2: change `--accent-green` once and the whole app changes colour.
- Colours: `#RRGGBB` hex, or `rgba(r, g, b, alpha)` where alpha 0.03 = 3% opaque (a faint tint).
- `font-family` is a **fallback list**: use JetBrains Mono if it loaded, otherwise the next one available.
- `color-scheme: dark` tells the browser to draw built-in widgets (scrollbars, inputs) in dark style.

📄 **File:** `frontend/src/index.css` — *add to the end*

```css

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  background-color: var(--bg-canvas);
  color: var(--text-white);
  min-height: 100vh;
  background-image:
    linear-gradient(to right, var(--bg-grid) 1px, transparent 1px),
    linear-gradient(to bottom, var(--bg-grid) 1px, transparent 1px);
  background-size: 24px 24px;
  background-attachment: fixed;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

code, pre, .mono {
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
```

**How it works**

- `*` selects **every** element. `box-sizing: border-box` makes `width` include padding and border
  (much easier to reason about); zeroing `margin`/`padding` removes browser defaults (a "CSS reset").
- `100vh` = 100% of the viewport (window) height.
- **The radar grid background:** two gradients, each a 1px faint-green line followed by transparency,
  one horizontal and one vertical, repeated every 24px (`background-size`). Result: graph paper.
  `background-attachment: fixed` keeps the grid still while content scrolls.

📄 **File:** `frontend/src/index.css` — *add to the end*

```css

/* Tactical terminal selection */
::selection {
  background: var(--accent-green-muted);
  color: var(--accent-green);
}

/* Precision scrollbars */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-canvas);
}

::-webkit-scrollbar-thumb {
  background: var(--border-base);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--accent-green-muted);
}
```

`::selection` styles highlighted text. The `::-webkit-scrollbar` pseudo-elements style scrollbars in
Chrome, Edge and Safari (Firefox ignores them and keeps its own).

Create an empty stylesheet now, so the `import './App.css'` in the next part doesn't fail:

```bash
: > src/App.css          # Windows PowerShell: Set-Content src/App.css ""
```

---

# Part B — `App.jsx`

We write `App.jsx` in **slices**, from top to bottom. The file only becomes valid when all slices are in
(a JSX tag opened in one slice may be closed several slices later), so **don't run the page until
Step 15.15**. Each slice is explained as you add it.

## Step 15.2 — Imports, helpers and state

📄 **File:** `frontend/src/App.jsx` — *create this file*

```jsx
import { useState, useEffect } from 'react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";

function formatMoney(num) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat("vi-VN").format(Math.round(num));
}

export default function App() {
  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);

  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [solveData, setSolveData] = useState(null);
  const [aiAdvice, setAiAdvice] = useState("");
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  const [error, setError] = useState("");
```

**How it works**

- `formatMoney` uses the browser's built-in **`Intl.NumberFormat`** with the Vietnamese locale, which
  uses **dots** as thousands separators: `132097` → `"132.097"`.
- **Ten pieces of state**, in two groups:
  - **inputs** the user controls: `pot`, `betSize`, `hand`, `foldEquity` (defaults: the chapter 1
    example);
  - **UI/results state**: two loading flags, the API results, whether the notes drawer is open, and an
    error message.
- `export default function App()` makes `App` the module's main export (what `main.jsx` imports).

---

## Step 15.3 — `handleSolve`, part 1: call `/api/solve`

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setError("");

    try {
      // 1. Call solve endpoint
      const solveRes = await fetch(`${API_BASE}/api/solve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pot: Number(pot),
          bet_size: Number(betSize),
          fold_equity: Number(foldEquity),
          hand: hand.trim(),
        }),
      });

      if (!solveRes.ok) {
        const errJson = await solveRes.json();
        throw new Error(errJson.error || `Server responded with ${solveRes.status}`);
      }

      const solveJson = await solveRes.json();
      setSolveData(solveJson);
      setIsLoading(false);
```

**How it works**

- `handleSolve` is an `async` arrow function stored in a constant. React calls it when the button is
  clicked.
- Turn on both loading flags and clear any old error **before** the request, so the button immediately
  shows "COMPUTING…".
- The JSON body uses the API's field names (`bet_size`, `fold_equity`: snake_case, Python style) while
  the JS variables are camelCase. `Number(...)` makes sure we send numbers, not strings.
- If the server answers with an error status (e.g. 400 for a bad hand), we read its `{"error": ...}`
  message and `throw`, jumping to the `catch` at the end (Step 15.4).
- On success, store the whole JSON in `solveData` → React re-renders with the results.

---

## Step 15.4 — `handleSolve`, part 2: call `/api/analyze`, handle errors

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

      // 2. Call analyze endpoint for strategic AI telemetry
      try {
        const analyzeRes = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pot: Number(pot),
            bet_size: Number(betSize),
            fold_equity: Number(foldEquity),
            hand: hand.trim(),
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });

        if (analyzeRes.ok) {
          const analyzeJson = await analyzeRes.json();
          setAiAdvice(analyzeJson.advice || "No telemetry analysis generated.");
        } else {
          setAiAdvice("AI telemetry gateway unreachable.");
        }
      } catch (aiErr) {
        setAiAdvice(`Telemetry transmission fault: ${aiErr.message}`);
      } finally {
        setIsAiLoading(false);
      }
    } catch (err) {
      setError("LOCAL SOLVER DAEMON OFFLINE. VERIFY BACKEND RUNNING ON PORT 5000.");
      setIsLoading(false);
      setIsAiLoading(false);
    }
  };
```

**How it works**

- **Two requests in sequence:** the analysis needs the solve results (`hand_evaluation`, coverage), so it
  runs only after `/api/solve` succeeded. The main results are already on screen while the (possibly
  slow, up to 20 s) LLM call runs. That's good UX.
- The analyze call has its **own** `try/catch/finally`: if the AI fails, the solver results stay visible
  and only the notes drawer shows an error. `finally` runs whether it succeeded or failed, so the
  spinner always stops.
- The outer `catch (err)` handles any failure of the solve call.

> ⚠️ **Pitfall: every error looks like "server offline".** The outer `catch` ignores `err` and always
> shows "LOCAL SOLVER DAEMON OFFLINE…". But Step 15.3 *throws* for a **400 Bad Request** too. Type
> `Xx Kh Qd` as the hand: the backend answers "Invalid hand: Invalid rank 'X'…", yet the page claims
> the server is offline. A useful fix: `setError(err.message)` (the server's own message), keeping the
> "offline" text only for network failures (when `fetch` itself throws a `TypeError`).

---

## Step 15.5 — Solve on page load, and derived values

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  // Run initial solve on mount
  useEffect(() => {
    handleSolve();
  }, []);

  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const isRaise = handEval?.decision === "RAISE";

  // Category Matrix Statistics
  const totalProfitableCombos = summary?.profitable_combinations || 0;
  const sapProfitable = Math.min(52, Math.max(0, totalProfitableCombos));
  const liengProfitable = Math.min(768, Math.max(0, totalProfitableCombos - 52));
  const diProfitable = Math.min(288, Math.max(0, totalProfitableCombos - 820));
  const diemProfitable = Math.min(20992, Math.max(0, totalProfitableCombos - 1108));
```

**How it works**

- `useEffect(() => { handleSolve(); }, [])` runs the solver once when the page opens, so the dashboard is
  never empty. (Under `StrictMode` in development it runs twice, see chapter 14.)
- **Derived values** are computed from state on every render, not stored in state. `handEval`,
  `summary` and `isRaise` are always consistent with `solveData`. The `?.` operator returns `undefined`
  instead of crashing while `solveData` is still `null`.
- **The category maths:** the API only returns the *total* number of profitable combos. The code then
  **guesses** the per-category numbers by "filling" the categories in strength order (Sáp first, then
  Liêng, …), each capped by `Math.min(categoryTotal, …)`. Chapter 10 showed why filling in order is
  roughly right: the profitable range is always "the strongest hands". But…

> ⚠️ **Pitfall: wrong totals.** The caps and offsets use **288** combos for Đĩ and **20,992** for Điểm.
> Chapter 6 proved the real numbers are **144** and **21,136** (6 types × 24, and 22,100 − 52 − 768 −
> 144). The offset `1108` should be `964` (= 52 + 768 + 144). Because 52 + 768 + 288 + 20,992 also adds
> up to 22,100, the total looks right and the mistake hides. The same wrong numbers are in `DESIGN.md`.
> Effect at fold equity 0 (pot 100k, bet 50k):
>
> | Category | UI shows | True |
> |---|---|---|
> | Đĩ | 288 / 288 | 144 / 144 |
> | Điểm | 15,504 / 20,992 (73.9%) | 15,648 / 21,136 (74.0%) |
>
> **The real fix** is not to correct the constants but to stop guessing: have `/api/solve` return the
> per-category counts (computed like the CLI's table in chapter 11), e.g.
>
> ```python
> # backend/app.py, inside solve_api, before the return
> categories = {
>     cat.name: {
>         "profitable": sum(r.multiplicity for r in profitable_records if r.category == cat),
>         "total": sum(r.multiplicity for r in records if r.category == cat),
>     }
>     for cat in HandCategory
> }
> # ...and add  "categories": categories  to the JSON response
> ```
>
> and read `summary.categories.DI.profitable` etc. in the UI. **Lesson:** don't re-derive in the
> frontend what the backend can compute exactly; duplicated "facts" drift.

---

## Step 15.6 — The category table's data

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  const categoryMatrix = [
    {
      name: "SÁP",
      desc: "Three of a Kind",
      classes: 13,
      combos: 52,
      profitable: sapProfitable,
      pct: ((sapProfitable / 52) * 100).toFixed(1),
      tier: "TIER 1 (NUTS)",
    },
    {
      name: "LIÊNG",
      desc: "Straight Sequence",
      classes: 12,
      combos: 768,
      profitable: liengProfitable,
      pct: ((liengProfitable / 768) * 100).toFixed(1),
      tier: "TIER 2 (STRONG)",
    },
    {
      name: "ĐĨ",
      desc: "Three Face Cards",
      classes: 6,
      combos: 288,
      profitable: diProfitable,
      pct: ((diProfitable / 288) * 100).toFixed(1),
      tier: "TIER 3 (MEDIUM)",
    },
    {
      name: "ĐIỂM",
      desc: "Points Modulo 10",
      classes: 424,
      combos: 20992,
      profitable: diemProfitable,
      pct: ((diemProfitable / 20992) * 100).toFixed(1),
      tier: "TIER 4 (MARGINAL)",
    },
  ];
```

**How it works**

- An **array of plain objects**, one per table row. Later the JSX does `categoryMatrix.map(cat => <tr>…)`.
  Separating *data* from *markup* keeps the JSX short.
- `.toFixed(1)` formats a number with 1 decimal and returns a **string** (`"73.9"`). That's why the JSX
  later converts it back with `Number(cat.pct)` to compare.
- `tier` is defined but never displayed (dead data).

---

## Step 15.7 — Start rendering: container and header

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  return (
    <div className="terminal-container">
      {/* Tactical Header & Telemetry Status */}
      <header className="terminal-header">
        <div className="brand-group">
          <h1 className="terminal-title">
            <span className="brand-white">LIÊNG</span> <span className="brand-green">SCOPE</span>
          </h1>
          <p className="terminal-subtitle">GTO SOLVER & COMBINATORIAL ENGINE</p>
        </div>

        <div className="telemetry-status-tag">
          <span className="radar-beacon"></span>
          <span className="telemetry-status-text">LIVE SOLVER</span>
          <span className="telemetry-separator">/</span>
          <span className="telemetry-classes">455 CLASSES LOADED</span>
        </div>
      </header>
```

**How it works**

- `return ( … )`: everything returned is JSX. A component must return **one** root element (here the
  `terminal-container` div).
- `{/* … */}` is how you write a comment inside JSX.
- The title is two `<span>`s with different classes, white "LIÊNG" and green "SCOPE", exactly as
  `DESIGN.md` §4.1 asks. The empty `radar-beacon` span becomes the pulsing green dot (via CSS).

> 💡 "LIVE SOLVER / 455 CLASSES LOADED" is static text, shown even if the backend is down. The
> `/health` endpoint (chapter 12) returns the real `classes_loaded`; using it would make the badge honest.

---

## Step 15.8 — The control panel: pot

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

      {/* Main Tactical Grid */}
      <main className="terminal-grid">
        {/* Left Column: Control Telemetry */}
        <section className="terminal-card control-panel">
          <div className="panel-header">
            <span className="panel-tag">// TELEMETRY CONTROLS</span>
            <span className="panel-id">SEC-01</span>
          </div>

          <div className="form-group">
            <label className="form-label">CURRENT POT (VND)</label>
            <div className="input-wrapper">
              <input
                type="number"
                className="input-field"
                value={pot}
                onChange={(e) => setPot(Number(e.target.value))}
                step="10000"
                min="1000"
              />
            </div>
            <div className="preset-chips">
              {[50000, 100000, 200000, 500000].map((v) => (
                <button
                  key={v}
                  type="button"
                  className={`preset-chip ${pot === v ? "active" : ""}`}
                  onClick={() => setPot(v)}
                >
                  {v / 1000}k
                </button>
              ))}
            </div>
          </div>
```

**How it works**

- `<main className="terminal-grid">` opens the two-column grid; the left `<section>` is the control panel.
- **Controlled number input:** `value={pot}` shows the state; `onChange` converts the typed text to a
  number and stores it. `step` and `min` control the arrow buttons.
- **Preset chips** are generated from an array with `.map`. Each needs a unique `key` (React uses it to
  track list items). The class is built with a template literal: a chip gets the extra class `active`
  when it equals the current pot, which CSS highlights. `{v / 1000}k` displays `100k`.
- `type="button"` stops the button from acting as a form "submit" button.

---

## Step 15.9 — Bet sizing

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <label className="form-label">BET / RAISE SIZING</label>
            <div className="input-wrapper">
              <input
                type="number"
                className="input-field"
                value={betSize}
                onChange={(e) => setBetSize(Number(e.target.value))}
                step="10000"
                min="1000"
              />
            </div>
            <div className="preset-chips">
              <button
                type="button"
                className={`preset-chip ${betSize === Math.round(pot * 0.5) ? "active" : ""}`}
                onClick={() => setBetSize(Math.round(pot * 0.5))}
              >
                0.5x Pot
              </button>
              <button
                type="button"
                className={`preset-chip ${betSize === pot ? "active" : ""}`}
                onClick={() => setBetSize(pot)}
              >
                1.0x Pot
              </button>
              <button
                type="button"
                className={`preset-chip ${betSize === pot * 2 ? "active" : ""}`}
                onClick={() => setBetSize(pot * 2)}
              >
                2.0x Pot
              </button>
            </div>
          </div>
```

Same pattern, but the presets are **relative to the pot** (½×, 1×, 2×). Bet sizes relative to the pot
are how poker players think, and chapter 9's table showed why: the break-even numbers depend only on the
ratio `B / P`.

---

## Step 15.10 — The fold-frequency slider

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <div className="slider-label-row">
              <label className="form-label">OPPONENT FOLD FREQUENCY</label>
              <span className="slider-value-badge">{Math.round(foldEquity * 100)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={foldEquity}
              onChange={(e) => setFoldEquity(parseFloat(e.target.value))}
              className="radar-slider"
            />
            <div className="slider-calibrations">
              <span>0% (CALLING STATION)</span>
              <span>50%</span>
              <span>100% (EXTREME FOLD)</span>
            </div>
          </div>
```

`<input type="range">` is a slider. It works in the 0–1 range with 0.01 steps (the probability the API
expects), and the badge shows it as a percentage. Input values are always strings, hence `parseFloat`.

---

## Step 15.11 — The hand input and presets

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <label className="form-label">PLAYER HAND (3 CARDS)</label>
            <div className="input-wrapper">
              <input
                type="text"
                className="input-field mono-bold"
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                placeholder="e.g. As Kh Qd"
              />
            </div>
            <div className="preset-chips">
              <button
                type="button"
                className={`preset-chip ${hand === "As Kh Qd" ? "active" : ""}`}
                onClick={() => setHand("As Kh Qd")}
              >
                Liêng Q-K-A
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "7s 7h 7d" ? "active" : ""}`}
                onClick={() => setHand("7s 7h 7d")}
              >
                Sáp 7
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "Js Qh Kd" ? "active" : ""}`}
                onClick={() => setHand("Js Qh Kd")}
              >
                Liêng J-Q-K
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "9s 10h Kd" ? "active" : ""}`}
                onClick={() => setHand("9s 10h Kd")}
              >
                9 Điểm
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "2s 3h 5d" ? "active" : ""}`}
                onClick={() => setHand("2s 3h 5d")}
              >
                0 Điểm (Bù)
              </button>
            </div>
          </div>
```

Five example hands, one per interesting case from chapter 1. Click "Liêng J-Q-K" later and look at the
verdict: the canonical class shows `[K-Q-J]`, the naming inconsistency from chapter 6.

> 💡 **Repetition.** Five nearly identical `<button>` blocks differ only in the hand and the label. An
> array like `const HAND_PRESETS = [["As Kh Qd", "Liêng Q-K-A"], …]` plus one `.map` (as the pot chips
> do) would be shorter and harder to get wrong.

---

## Step 15.12 — The solve button, error box and specs card

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <button
            type="button"
            className="tactical-btn"
            onClick={handleSolve}
            disabled={isLoading}
          >
            {isLoading ? "[ COMPUTING RANGE... ]" : "[ EXECUTE SOLVER ]"}
          </button>

          {error && (
            <div className="terminal-alert">
              <span className="alert-marker">!</span>
              <span>{error}</span>
            </div>
          )}

          {/* Engine Specs Sub-Card */}
          <div className="specs-subcard">
            <div className="spec-row">
              <span className="spec-label">SOLVER ARCHITECTURE</span>
              <span className="spec-val">MONTE CARLO / CANONICAL</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">COMBINATORIAL SPACE</span>
              <span className="spec-val">22,100 COMBOS (455 CLS)</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">ONLINE QUERY COMPLEXITY</span>
              <span className="spec-val">O(1) CACHED LOOKUP</span>
            </div>
          </div>
        </section>
```

**How it works**

- `onClick={handleSolve}` passes the function itself (no parentheses: we don't call it now, React calls it
  on click).
- `disabled={isLoading}` prevents double-submits while a request is running, and the label changes.
- `{error && (…)}` renders the alert **only** when `error` is a non-empty string.
- `</section>` closes the left column opened in Step 15.8.

(The specs card says "MONTE CARLO"; the shipped data was actually computed by **exact enumeration**,
chapter 7.)

---

## Step 15.13 — Right column: the verdict banner

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

        {/* Right Column: Strategic HUD & Matrix */}
        <section className="results-container">
          {/* Verdict Banner */}
          {handEval && (
            <div className={`verdict-banner ${isRaise ? "verdict-raise" : "verdict-fold"}`}>
              <div className="verdict-col-left">
                <span className="verdict-label">// RECOMMENDED ACTION</span>
                <h2 className="verdict-title">
                  {isRaise ? "ACTION: RAISE / ALL-IN" : "ACTION: CHECK / FOLD"}
                </h2>
                <div className="verdict-meta">
                  <span className="holding-tag">{handEval.hand}</span>
                  <span className="holding-sep">•</span>
                  <span className="holding-class">[{handEval.canonical_id}]</span>
                  <span className="holding-sep">•</span>
                  <span className="holding-score">{handEval.score_name.toUpperCase()}</span>
                </div>
              </div>

              <div className="verdict-col-right">
                <span className="verdict-label">// EXPECTED VALUE</span>
                <div className="verdict-ev">
                  {handEval.ev > 0 ? "+" : ""}{formatMoney(handEval.ev)} <span className="ev-currency">VND</span>
                </div>
                <div className="verdict-breakeven">
                  BREAK-EVEN FOLD EQ: <span className="mono-green">{Math.round(handEval.break_even_fold_equity * 100)}%</span>
                </div>
              </div>
            </div>
          )}
```

**How it works**

- Only shown when a hand was evaluated (`handEval && …`).
- **One class switches the whole look:** `verdict-raise` (green border and title) or `verdict-fold`
  (red). The CSS (Part C) uses combined selectors like `.verdict-raise .verdict-title`.
- Every value comes straight from the API's `hand_evaluation` object (chapter 12, Step 12.5).
- The `+` sign is added only for positive EV; `formatMoney` already includes the minus sign for negative
  numbers.

---

## Step 15.14 — The four HUD metric cards

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* 4-Card Metrics HUD */}
          <div className="hud-metrics-grid">
            <div className="hud-card">
              <div className="hud-label">RANGE COVERAGE</div>
              <div className="hud-value green-glow">
                {summary?.range_coverage_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="hud-subtext">
                {summary?.profitable_combinations?.toLocaleString() || "0"} / 22,100 COMBOS
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">SHOWDOWN EQUITY</div>
              <div className="hud-value white-metric">
                {handEval ? `${(handEval.showdown_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="hud-subtext">VS UNKNOWN 49-CARD SPECTRUM</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">EXPECTED VALUE</div>
              <div className={`hud-value ${handEval?.ev > 0 ? "green-metric" : "dim-metric"}`}>
                {handEval ? `${handEval.ev > 0 ? "+" : ""}${formatMoney(handEval.ev)}` : "0"}
              </div>
              <div className="hud-subtext">NET VND GAIN PER DECISION</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">PURE BLUFF THRESHOLD</div>
              <div className="hud-value amber-metric">
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="hud-subtext">MIN FOLD EQ FOR 0-PT AIR</div>
            </div>
          </div>
```

Four cards, each a label, a big value and a sub-text (`DESIGN.md` §4.3): coverage (chapter 10), equity
(chapter 7), EV (chapter 9) and the pure-bluff threshold `B/(P+B)` (chapter 9). Each value has a
fallback (`"N/A"`, `"0"`) for when data hasn't arrived yet. `toLocaleString()` adds thousands separators
using the browser's language.

---

## Step 15.15 — The category coverage matrix

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Range Breakdown Matrix Table */}
          <div className="terminal-card table-panel">
            <div className="panel-header">
              <span className="panel-tag">// CATEGORY COVERAGE MATRIX</span>
              <span className="panel-id">4 CORE HIERARCHIES</span>
            </div>

            <div className="table-wrapper">
              <table className="tactical-table">
                <thead>
                  <tr>
                    <th>CATEGORY</th>
                    <th>DESCRIPTION</th>
                    <th>CLASSES</th>
                    <th>COMBOS</th>
                    <th>PROFITABLE</th>
                    <th>COVERAGE</th>
                    <th>RADAR STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryMatrix.map((cat) => (
                    <tr key={cat.name}>
                      <td>
                        <span className={`cat-pill cat-${cat.name}`}>{cat.name}</span>
                      </td>
                      <td className="desc-cell">{cat.desc}</td>
                      <td className="mono-num">{cat.classes}</td>
                      <td className="mono-num">{cat.combos.toLocaleString()}</td>
                      <td className="mono-num">{cat.profitable.toLocaleString()}</td>
                      <td className="mono-num highlight-val">{cat.pct}%</td>
                      <td>
                        <span
                          className={`status-chip ${
                            Number(cat.pct) === 100
                              ? "chip-full"
                              : Number(cat.pct) > 0
                              ? "chip-partial"
                              : "chip-zero"
                          }`}
                        >
                          {Number(cat.pct) === 100
                            ? "100% PUSH"
                            : Number(cat.pct) > 0
                            ? "PARTIAL"
                            : "FOLD"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
```

**How it works**

- A standard HTML table: `<thead>` with column titles, `<tbody>` with one `<tr>` per category from the
  `categoryMatrix` array.
- `cat-${cat.name}` produces class names like `cat-SÁP` or `cat-ĐĨ` (CSS class names may contain
  Unicode letters); the stylesheet colours each category's "pill" differently.
- The status chip uses a **chained ternary** (`a ? x : b ? y : z`): 100% → "100% PUSH", more than 0 →
  "PARTIAL", else "FOLD".

---

## Step 15.16 — Top holdings table

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Top Canonical Holdings Table */}
          {solveData?.top_hands && (
            <div className="terminal-card table-panel">
              <div className="panel-header">
                <span className="panel-tag">// TOP PROFITABLE HOLDINGS</span>
                <span className="panel-id">SAMPLE EQUIVALENCE CLASSES</span>
              </div>

              <div className="table-wrapper">
                <table className="tactical-table">
                  <thead>
                    <tr>
                      <th>CANONICAL ID</th>
                      <th>CATEGORY</th>
                      <th>SHOWDOWN EQUITY</th>
                      <th>EXPECTED VALUE (EV)</th>
                      <th>MULTIPLICITY</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solveData.top_hands.slice(0, 10).map((item) => (
                      <tr key={item.canonical_id}>
                        <td className="mono-canonical">{item.canonical_id}</td>
                        <td>
                          <span className={`cat-pill cat-${item.category}`}>{item.category}</span>
                        </td>
                        <td className="mono-num">{(item.equity * 100).toFixed(1)}%</td>
                        <td className={`mono-num bold-num ${item.ev > 0 ? "positive-ev" : "negative-ev"}`}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev)} VND
                        </td>
                        <td className="dim-cell">{item.multiplicity} combos</td>
                        <td>
                          <span className={`action-badge ${item.is_profitable ? "act-raise" : "act-fold"}`}>
                            {item.is_profitable ? "RAISE" : "FOLD"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
```

The API sends the top 30 records; `.slice(0, 10)` shows the first 10. `canonical_id` is unique, so it's
a good `key`. Here `item.category` is the API's ASCII name (`SAP`, `DI`…), which is why the CSS defines
both `.cat-SÁP` and `.cat-SAP`.

> 💡 Because the list is sorted by EV and the strongest hands always have the highest EV, this table is
> almost always the same ten Sáp hands (A-A-A, K-K-K, …). Showing the **threshold** region (the
> weakest hands that are still profitable, where decisions are actually hard) would be more informative.

---

## Step 15.17 — The notes drawer, and closing everything

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Collapsible Mathematical Telemetry Notes Drawer */}
          <div className="notes-drawer-container">
            <button
              type="button"
              className="drawer-toggle-btn"
              onClick={() => setIsNotesOpen(!isNotesOpen)}
            >
              <span>{isNotesOpen ? "[ − COLLAPSE TELEMETRY NOTES ]" : "[ + MATHEMATICAL TELEMETRY NOTES ]"}</span>
              <span className="drawer-indicator">{isNotesOpen ? "▲" : "▼"}</span>
            </button>

            {isNotesOpen && (
              <div className="drawer-content">
                <div className="drawer-header">
                  <span className="drawer-title">// GAME-THEORETIC TELEMETRY ADVISORY</span>
                  <span className="drawer-sub">OPENROUTER / LLAMA 3.1 8B INSTRUCT</span>
                </div>

                {isAiLoading ? (
                  <div className="telemetry-loading">
                    <span className="radar-spinner"></span>
                    <span>&gt; TRANSMITTING GAME-THEORETIC TELEMETRY QUERY...</span>
                  </div>
                ) : (
                  <div className="telemetry-body">
                    {aiAdvice || "No active telemetry payload recorded for this game state."}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
```

**How it works**

- A **toggle**: `setIsNotesOpen(!isNotesOpen)` flips a boolean; the content renders only when open.
- While the analysis is loading, show a spinner; then show the advice text. `&gt;` is the HTML escape for
  `>` (a bare `>` would confuse the JSX parser).
- The advice is Markdown (`**bold**`) but is shown as **plain text**, so you'll see the asterisks. A
  Markdown renderer library would display it properly. Never insert server-provided HTML directly
  (`dangerouslySetInnerHTML`): that opens the door to script-injection attacks (XSS).
- The last lines close `section`, `main`, the container `div`, the `return (`, and the `App` function.

🧪 **Mini-check.** With Flask running, start Vite (`npm run dev`) and open http://localhost:5173. The page
should work **completely**: the verdict "ACTION: RAISE / ALL-IN" with `+132.097 VND`, the HUD (100.0%
coverage, 99.7% equity, 33.3% bluff threshold) and both tables. It just looks plain and white-on-black,
because `App.css` is still empty. Let's fix that.

---

# Part C — `App.css`

From here on, **every step leaves the page working**. Keep the browser open next to your editor: Vite
reloads styles instantly when you save.

## Step 15.18 — Container, header and branding

📄 **File:** `frontend/src/App.css` — *create this file*

```css
/* ==========================================================================
   LIÊNG SCOPE - TACTICAL RADAR ANALYTICS TERMINAL (EPL SCOPE AESTHETIC)
   ========================================================================== */

.terminal-container {
  max-width: 1360px;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 4rem;
}

/* --------------------------------------------------------------------------
   TACTICAL HEADER & BRANDING
   -------------------------------------------------------------------------- */
.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-base);
}

.brand-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.terminal-title {
  font-size: 2.2rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  margin: 0;
}

.brand-white {
  color: var(--text-white);
}

.brand-green {
  color: var(--accent-green);
  text-shadow: 0 0 12px var(--accent-green-glow);
}

.terminal-subtitle {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin: 0;
}
```

**How it works**

- `max-width: 1360px; margin: 0 auto;` centres the page and stops it from getting too wide on big screens.
- `padding: 1.5rem 1.5rem 4rem;` is top, left/right, bottom.
- The header is a **flex row**: `justify-content: space-between` pushes the title to the left and the
  status tag to the right; `align-items: center` centres them vertically.
- `.brand-group` is a flex **column** with a small `gap` between title and subtitle.
- `text-shadow: 0 0 12px …` with no offset and a blur creates the green **glow**.
- `letter-spacing` in `em` (relative to font size) gives the wide "terminal" lettering.

**Save → look:** the title is now big with a glowing green "SCOPE", and a line separates the header.

---

## Step 15.19 — The live-status tag and its pulsing beacon

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Right-side status tag: ● LIVE SOLVER / 455 CLASSES LOADED */
.telemetry-status-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.65rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 0.45rem 0.9rem;
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.radar-beacon {
  width: 8px;
  height: 8px;
  background: var(--accent-green);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-green);
  animation: pulse-beacon 2s infinite ease-in-out;
}

@keyframes pulse-beacon {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
    box-shadow: 0 0 8px var(--accent-green);
  }
  50% {
    opacity: 0.4;
    transform: scale(0.85);
    box-shadow: 0 0 2px var(--accent-green);
  }
}

.telemetry-status-text {
  color: var(--accent-green);
  font-weight: 700;
}

.telemetry-separator {
  color: var(--text-dim);
}

.telemetry-classes {
  color: var(--text-muted);
}
```

**How it works**

- `border-radius: 50%` turns the 8×8 square into a **circle**.
- **Animation:** `@keyframes pulse-beacon` describes the states at 0%, 50% and 100% of the cycle (fade
  and shrink, then back). `animation: pulse-beacon 2s infinite ease-in-out` plays it every 2 seconds,
  forever, with smooth acceleration.
- `border-radius: 2px`: sharp corners everywhere, per `DESIGN.md` ("NO rounded bubble cards").

---

## Step 15.20 — The two-column grid and panels

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   MAIN DASHBOARD GRID LAYOUT
   -------------------------------------------------------------------------- */
.terminal-grid {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .terminal-grid {
    grid-template-columns: 1fr;
  }
}

/* --------------------------------------------------------------------------
   TACTICAL CARDS & PANELS
   -------------------------------------------------------------------------- */
.terminal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 1.25rem;
  position: relative;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 0.65rem;
  margin-bottom: 1.25rem;
}

.panel-tag {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--accent-green);
}

.panel-id {
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--text-dim);
  letter-spacing: 0.05em;
}
```

**How it works**

- **CSS Grid:** two columns, a fixed **380px** control panel and `1fr` (all remaining space) for results.
  `align-items: start` keeps each column only as tall as its content.
- **Responsive design:** on screens **1024px or narrower** (tablets, phones), the media query switches to
  a single column, so the results drop below the controls. Try it by narrowing your browser window.
- `.terminal-card` is the reusable "dark panel" look, used by the control panel and both tables.

**Save → look:** the page now has its two-column layout.

---

## Step 15.21 — Form controls: labels, inputs and preset chips

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   FORM CONTROLS & TELEMETRY INPUTS
   -------------------------------------------------------------------------- */
.form-group {
  margin-bottom: 1.25rem;
}

.form-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.4rem;
}

.input-wrapper {
  position: relative;
}

.input-field {
  width: 100%;
  background: var(--bg-surface-input);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 0.65rem 0.85rem;
  color: var(--text-white);
  font-size: 0.95rem;
  font-family: inherit;
  transition: all 0.15s ease;
}

.input-field.mono-bold {
  font-weight: 700;
  letter-spacing: 0.05em;
}

.input-field:focus {
  outline: none;
  border-color: var(--border-highlight);
  box-shadow: 0 0 0 1px var(--border-highlight), 0 0 10px var(--accent-green-glow);
}

.preset-chips {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.45rem;
  flex-wrap: wrap;
}

.preset-chip {
  background: transparent;
  border: 1px solid var(--border-base);
  color: var(--text-muted);
  border-radius: 2px;
  padding: 0.25rem 0.55rem;
  font-size: 0.72rem;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.preset-chip:hover {
  background: var(--bg-surface-hover);
  border-color: var(--accent-green);
  color: var(--text-white);
}

.preset-chip.active {
  background: var(--accent-green-muted);
  border-color: var(--accent-green);
  color: var(--accent-green);
  font-weight: 600;
}
```

**How it works**

- `font-family: inherit`: form controls don't inherit the page font by default; this makes them use
  JetBrains Mono too.
- **`:focus`** styles the input being typed in. `outline: none` removes the browser's default ring and
  replaces it with a green border plus two shadows: a 1px "ring" and a soft glow (`DESIGN.md` §3).
  (When you remove the default focus outline, always provide a visible replacement, or keyboard users
  can't see where they are.)
- **`.preset-chip.active`**: the class added in JSX (Step 15.8) when a chip matches the current value.
- `flex-wrap: wrap` lets chips flow onto a second line when there isn't room.
- `transition: all 0.15s` animates colour changes on hover.

---

## Step 15.22 — The slider

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Slider Controls */
.slider-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.slider-value-badge {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--accent-green);
  letter-spacing: 0.05em;
}

.radar-slider {
  width: 100%;
  height: 4px;
  background: var(--border-base);
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
  appearance: none;
  border-radius: 0;
}

.radar-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  background: var(--accent-green);
  border: 2px solid var(--bg-canvas);
  border-radius: 0;
  cursor: pointer;
  box-shadow: 0 0 6px var(--accent-green);
}

.radar-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  background: var(--accent-green);
  border: 2px solid var(--bg-canvas);
  border-radius: 0;
  cursor: pointer;
  box-shadow: 0 0 6px var(--accent-green);
}

.slider-calibrations {
  display: flex;
  justify-content: space-between;
  font-size: 0.65rem;
  color: var(--text-dim);
  letter-spacing: 0.04em;
  margin-top: 0.35rem;
}
```

**How it works**

- `appearance: none` removes the browser's native slider look so we can draw our own: a thin 4px track
  and a square green **thumb**.
- Browsers name the thumb differently: `::-webkit-slider-thumb` (Chrome, Edge, Safari) and
  `::-moz-range-thumb` (Firefox). The same styles are written twice, once per engine.
- `.slider-calibrations` spreads the three labels (0%, 50%, 100%) across the width with
  `space-between`.

---

## Step 15.23 — The action button, alert and specs card

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Solid Rectangular Green Action Button */
.tactical-btn {
  width: 100%;
  padding: 0.85rem;
  background: var(--accent-green);
  color: #050705;
  border: none;
  border-radius: 2px;
  font-size: 0.95rem;
  font-weight: 800;
  font-family: inherit;
  letter-spacing: 0.08em;
  cursor: pointer;
  transition: all 0.15s ease;
  margin-top: 0.5rem;
  box-shadow: 0 0 15px var(--accent-green-glow);
}

.tactical-btn:hover:not(:disabled) {
  background: #1ea850;
  box-shadow: 0 0 25px rgba(34, 197, 94, 0.3);
}

.tactical-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

.terminal-alert {
  margin-top: 0.85rem;
  padding: 0.6rem 0.85rem;
  background: var(--accent-red-muted);
  border: 1px solid var(--accent-red);
  color: var(--accent-red);
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: 2px;
}

.alert-marker {
  font-weight: 900;
  padding: 0 0.3rem;
  background: var(--accent-red);
  color: #fff;
  border-radius: 1px;
}
```

**How it works**

- `:hover:not(:disabled)`: hover effect **only** when the button is enabled. Chaining pseudo-classes
  narrows the selector.
- `:disabled` (while loading) fades the button and shows a "not allowed" cursor.
- The alert uses the red tokens. Stop Flask and click the button to see it.

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Specs Subcard */
.specs-subcard {
  background: var(--bg-surface-input);
  border: 1px solid var(--border-subtle);
  border-radius: 2px;
  padding: 0.75rem 0.85rem;
  margin-top: 1.25rem;
}

.spec-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.68rem;
  padding: 0.25rem 0;
}

.spec-label {
  color: var(--text-dim);
  letter-spacing: 0.04em;
}

.spec-val {
  color: var(--text-muted);
  font-weight: 600;
}
```

**Save → look:** the left column is now complete.

---

## Step 15.24 — Right column and the verdict banner

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   RIGHT COLUMN: STRATEGIC HUD & VERDICT
   -------------------------------------------------------------------------- */
.results-container {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* Verdict Banner */
.verdict-banner {
  padding: 1.25rem 1.5rem;
  border-radius: 2px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.2s ease;
}

.verdict-raise {
  background: rgba(34, 197, 94, 0.06);
  border: 1px solid var(--accent-green);
  box-shadow: 0 0 25px var(--accent-green-glow);
}

.verdict-fold {
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid var(--accent-red);
  box-shadow: 0 0 25px var(--accent-red-glow);
}

.verdict-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  display: block;
}

.verdict-title {
  font-size: 1.75rem;
  font-weight: 900;
  letter-spacing: -0.02em;
  margin: 0.25rem 0 0.4rem;
}

.verdict-raise .verdict-title {
  color: var(--accent-green);
  text-shadow: 0 0 10px var(--accent-green-glow);
}

.verdict-fold .verdict-title {
  color: var(--accent-red);
  text-shadow: 0 0 10px var(--accent-red-glow);
}
```

**How it works**

- `.results-container` stacks the right-hand blocks vertically with equal gaps (flex column + `gap`).
- **One switch, many effects:** `.verdict-raise .verdict-title` means "a title *inside* a raise banner".
  Changing the single class on the banner (Step 15.13) recolours the border, glow and title together.

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

.verdict-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.holding-tag {
  font-weight: 800;
  color: var(--text-white);
}

.holding-sep {
  color: var(--text-dim);
}

.holding-class {
  color: var(--accent-green);
  font-weight: 700;
}

.holding-score {
  color: var(--text-muted);
}

.verdict-col-right {
  text-align: right;
}

.verdict-ev {
  font-size: 1.75rem;
  font-weight: 900;
  color: var(--text-white);
  letter-spacing: -0.02em;
  margin: 0.25rem 0 0.2rem;
}

.verdict-raise .verdict-ev {
  color: var(--accent-green);
}

.ev-currency {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-muted);
}

.verdict-breakeven {
  font-size: 0.72rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.mono-green {
  color: var(--accent-green);
  font-weight: 700;
}
```

**Save → look:** click the "0 Điểm (Bù)" preset, set the slider to 5% and execute: the banner turns red
("ACTION: CHECK / FOLD", −42.044 VND). Move the slider to 50% and execute again: green, +25.240.
That's chapter 13's scenarios 2 and 3, live.

---

## Step 15.25 — The HUD metric cards

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   4-CARD METRICS HUD
   -------------------------------------------------------------------------- */
.hud-metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}

@media (max-width: 840px) {
  .hud-metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .hud-metrics-grid {
    grid-template-columns: 1fr;
  }
}

.hud-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 1rem;
}

.hud-label {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.hud-value {
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hud-value.green-glow {
  color: var(--accent-green);
  text-shadow: 0 0 10px var(--accent-green-glow);
}

.hud-value.white-metric {
  color: var(--text-white);
}

.hud-value.green-metric {
  color: var(--accent-green);
}

.hud-value.amber-metric {
  color: var(--accent-amber);
}

.hud-value.dim-metric {
  color: var(--text-muted);
}

.hud-subtext {
  font-size: 0.68rem;
  color: var(--text-dim);
  letter-spacing: 0.03em;
  margin-top: 0.25rem;
}
```

`repeat(4, 1fr)` = four equal columns. Two media queries make it **4 → 2 → 1** columns as the screen
narrows. The colour modifier classes (`green-glow`, `amber-metric`, …) give each metric its own colour
while sharing the base `.hud-value` size.

---

## Step 15.26 — Tables

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   TACTICAL DATA TABLES (CATEGORY MATRIX & TOP HOLDINGS)
   -------------------------------------------------------------------------- */
.table-panel {
  padding: 1.25rem;
}

.table-wrapper {
  overflow-x: auto;
  border: 1px solid var(--border-subtle);
  border-radius: 2px;
}

.tactical-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
  text-align: left;
}

.tactical-table th {
  background: var(--bg-surface-input);
  padding: 0.65rem 0.85rem;
  font-weight: 700;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border-base);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.tactical-table td {
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-white);
}

.tactical-table tr:hover td {
  background: var(--bg-surface-hover);
}
```

**How it works**

- `.table-wrapper { overflow-x: auto; }` lets a wide table **scroll sideways** on small screens instead of
  breaking the layout.
- `border-collapse: collapse` merges neighbouring cell borders into single lines.
- `tr:hover td` highlights the whole row under the mouse.

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

.desc-cell {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.mono-num {
  font-family: inherit;
  font-variant-numeric: tabular-nums;
}

.mono-canonical {
  font-weight: 700;
  color: var(--text-white);
}

.bold-num {
  font-weight: 700;
}

.highlight-val {
  color: var(--accent-green);
  font-weight: 700;
}

.dim-cell {
  color: var(--text-dim);
  font-size: 0.75rem;
}

.positive-ev {
  color: var(--accent-green);
}

.negative-ev {
  color: var(--accent-red);
}
```

`font-variant-numeric: tabular-nums` makes every digit the same width, so numbers line up in columns
(already true for a monospace font, but a good habit for tables).

---

## Step 15.27 — Category pills, status chips, action badges

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Category Badges */
.cat-pill {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 800;
  padding: 0.15rem 0.45rem;
  border-radius: 2px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.cat-SÁP, .cat-SAP {
  background: rgba(245, 158, 11, 0.15);
  color: #FBBF24;
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.cat-LIÊNG, .cat-LIENG {
  background: rgba(34, 197, 94, 0.15);
  color: #22C55E;
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.cat-ĐĨ, .cat-DI {
  background: rgba(56, 189, 248, 0.15);
  color: #38BDF8;
  border: 1px solid rgba(56, 189, 248, 0.35);
}

.cat-ĐIỂM, .cat-DIEM {
  background: rgba(133, 153, 139, 0.15);
  color: #85998B;
  border: 1px solid rgba(133, 153, 139, 0.3);
}
```

A comma between selectors (`.cat-SÁP, .cat-SAP`) applies the rule to **both**. That's needed because the
category table uses the Vietnamese names and the top-hands table uses the API's ASCII names. Each
category gets its own colour (amber, green, blue, grey), all built the same way: a 15%-opacity
background, a solid text colour and a 35%-opacity border.

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Status Chips */
.status-chip {
  display: inline-block;
  font-size: 0.65rem;
  font-weight: 800;
  padding: 0.15rem 0.5rem;
  border-radius: 2px;
  letter-spacing: 0.05em;
}

.chip-full {
  background: var(--accent-green-muted);
  color: var(--accent-green);
  border: 1px solid var(--accent-green);
}

.chip-partial {
  background: rgba(245, 158, 11, 0.12);
  color: var(--accent-amber);
  border: 1px solid rgba(245, 158, 11, 0.35);
}

.chip-zero {
  background: var(--accent-red-muted);
  color: var(--accent-red);
  border: 1px solid rgba(239, 68, 68, 0.35);
}

/* Action Badges */
.action-badge {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.act-raise {
  color: var(--accent-green);
}

.act-fold {
  color: var(--text-dim);
}
```

---

## Step 15.28 — The notes drawer

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* --------------------------------------------------------------------------
   COLLAPSIBLE MATHEMATICAL TELEMETRY NOTES DRAWER
   -------------------------------------------------------------------------- */
.notes-drawer-container {
  margin-top: 0.25rem;
}

.drawer-toggle-btn {
  width: 100%;
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 0.75rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--accent-green);
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all 0.15s ease;
}

.drawer-toggle-btn:hover {
  background: var(--bg-surface-hover);
  border-color: var(--accent-green);
}

.drawer-indicator {
  font-size: 0.65rem;
  color: var(--text-muted);
}

.drawer-content {
  background: var(--bg-surface-input);
  border: 1px solid var(--border-base);
  border-top: none;
  border-radius: 0 0 2px 2px;
  padding: 1.25rem;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 0.65rem;
  margin-bottom: 0.85rem;
  border-bottom: 1px solid var(--border-subtle);
}

.drawer-title {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--accent-green);
}

.drawer-sub {
  font-size: 0.65rem;
  color: var(--text-dim);
  letter-spacing: 0.05em;
}
```

`border-top: none` plus `border-radius: 0 0 2px 2px` (top-left, top-right, bottom-right, bottom-left)
make the open drawer look attached to the button above it.

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

.telemetry-loading {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--text-muted);
  font-size: 0.8rem;
  letter-spacing: 0.05em;
}

.radar-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--border-base);
  border-top-color: var(--accent-green);
  border-radius: 50%;
  animation: spin-radar 0.75s linear infinite;
}

@keyframes spin-radar {
  to {
    transform: rotate(360deg);
  }
}

.telemetry-body {
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--text-muted);
  white-space: pre-wrap;
}
```

**How it works**

- **The classic CSS spinner:** a circle (`border-radius: 50%`) with a grey border and **one** green side
  (`border-top-color`), rotated forever. `to { transform: rotate(360deg); }` is shorthand for a 0%→100%
  animation.
- `white-space: pre-wrap` keeps the line breaks (`\n`) in the advice text, which HTML would otherwise
  collapse into spaces.

---

## ✅ Checkpoint

1. Flask running (`python app.py`), Vite running (`npm run dev`), open http://localhost:5173.
2. On load you should see, without clicking anything:
   - **ACTION: RAISE / ALL-IN**, `As Kh Qd • [Q-K-A] • LIÊNG Q-K-A`, **+132.097 VND**, break-even 0%;
   - HUD: **100.0%** (22,100 / 22,100 combos), **99.7%**, **+132.097**, **33.3%**;
   - the category matrix (all rows "100% PUSH") and the top-10 table starting with `A-A-A`.
3. Click "0 Điểm (Bù)", drag the slider to **5%**, click **[ EXECUTE SOLVER ]** → red **CHECK / FOLD**,
   **−42.044 VND**, coverage **77.8%**.
4. Open the notes drawer: the Vietnamese rule-based analysis appears (or an LLM answer if you set
   `OPENROUTER_API_KEY` before starting Flask).
5. Narrow the window below 1024px: the layout becomes one column.
6. `npm run lint`: **no errors, 3 warnings**. The linter found real issues on its own:

   ```
   src/App.jsx:77:14: warning eslint(no-unused-vars): Catch parameter 'err' is caught but never used.
   src/App.jsx:86:5: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders
   src/App.jsx:86:5: warning react-hooks(exhaustive-deps): React Hook useEffect has a missing dependency: 'handleSolve'
   ```

   - The first is exactly the "every error looks like server offline" pitfall from Step 15.4: the error
     is caught and then ignored.
   - The other two concern `useEffect(() => { handleSolve(); }, [])`. The effect calls a function
     that is re-created on every render and that sets state. It works here, but React's recommended
     pattern is to keep effects for syncing with external systems. **Linters are cheap code reviewers:
     read their warnings.**

Compare your three files with the originals (`diff -B`; see chapter 5), then commit:

```bash
git add frontend && git commit -m "feat: LIÊNG SCOPE dashboard"
```

## Recap

- `App` holds the inputs and results in **state**; `handleSolve` calls `/api/solve`, then `/api/analyze`, and every
  state change re-renders the page.
- Derived values (`handEval`, `isRaise`, `categoryMatrix`) are computed from state, not stored.
- The CSS is built from **design tokens** (CSS variables), **flexbox** for rows, **grid** for the page and
  HUD, **media queries** for small screens, and **keyframes** for the beacon and spinner.
- Pitfalls: the category matrix uses wrong totals (Đĩ 288/Điểm 20,992 instead of 144/21,136) and guesses
  what the backend should send; every error is shown as "server offline"; static "LIVE" status;
  Markdown shown as raw text.

**Next:** [16 — Deployment](17-deployment.md)
