# 16 — Building the UI ("LIÊNG SCOPE")

> **Goal:** build the full dashboard: inputs on the left; verdict, metrics and tables on the right; an
> English/Vietnamese language switch; an opponent-model toggle with a "profit map"; styled as a dark
> "tactical radar terminal".
> **You will build:** `frontend/src/index.css`, `frontend/src/i18n.js`, `frontend/src/App.jsx`,
> `frontend/src/App.css`.
> **Time:** ~4 hours.
> **Prerequisites:** [15](15-frontend-foundations.md). Flask running (`python app.py` in `backend/`).

---

## The big picture

The whole UI is **one component**, `App`, plus a dictionary of UI texts (`i18n.js`) and two stylesheets.
The data flow is a loop:

```
   ┌──────────────────── state (useState) ─────────────────────┐
   │ pot, betSize, foldEquity, hand, opponentModel  ◄── inputs  │◄──── user types / clicks a preset
   │ lang ("en"/"vi")  ◄── language toggle (saved in localStorage)
   │ solveData, aiAdvice, isLoading, solveError, …              │
   └──────────────┬─────────────────────────────────────────────┘
                  │ "EXECUTE SOLVER" → handleSolve()
                  ▼
     POST /api/solve  ──►  setSolveData(json)  ──►  POST /api/analyze  ──►  setAiAdvice(text)
                  │
                  ▼ every state change re-renders App, with every label looked up in STRINGS[lang]
     verdict banner · profit map · 4 HUD cards · category matrix · top-10 table · notes drawer
```

The page layout:

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ LIÊNG SCOPE                                 ● LIVE SOLVER / 455 CLASSES   [EN|VI]   │  header
├──────────────────────────┬───────────────────────────────────────────────────────────┤
│ // TELEMETRY CONTROLS    │ ACTION: RAISE / ALL-IN                     +131.876 VND   │  verdict
│ CURRENT POT  [100000]    │ … • [Q-K-A] • …            RAISE +EV WHEN OPP. FOLDS: 0%–100%
│  50k 100k 200k 500k      ├──────────────┬──────────────┬─────────────┬──────────────┤
│ BET / RAISE  [50000]     │ RANGE COV.   │ SHOWDOWN EQ  │ EXP. VALUE  │ BLUFF THRESH │  HUD
│  0.5x 1.0x 2.0x Pot      ├──────────────┴──────────────┴─────────────┴──────────────┤
│ FOLD FREQUENCY ──●── 35% │ // CATEGORY COVERAGE MATRIX   (SÁP, LIÊNG, ĐĨ, ĐIỂM)      │  table
│ OPPONENT FOLDS [WEAKEST HANDS][AT RANDOM]                                            │
│ RAISE PROFIT MAP ▓▓▓░░░▓▓▓│ (green = +EV zones, white line = current fold %)        │
│ HAND [As Kh Qd]          ├───────────────────────────────────────────────────────────┤
│ [ EXECUTE SOLVER ]       │ // TOP PROFITABLE HOLDINGS    (top 10 canonical hands)    │  table
│ specs                    │ [ + MATHEMATICAL TELEMETRY NOTES ]  ▼                     │  drawer
└──────────────────────────┴───────────────────────────────────────────────────────────┘
```

We build it in three parts:

- **Part A:** `index.css`, global design tokens (colours, font, background grid).
- **Part B:** `i18n.js` (all UI texts in two languages) and `App.jsx` (the logic and the markup).
- **Part C:** `App.css`, the styles, section by section, watching the page change after each one.

---

## Concepts you need

### CSS in brief

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
| child selector | `.terminal-grid > *` | every **direct child** of `.terminal-grid` |
| pseudo-class | `:hover`, `:focus`, `:focus-visible`, `:disabled`, `:not(...)` | element **state** |
| pseudo-element | `::selection`, `::-webkit-slider-thumb` | a **part** of an element |
| CSS variable | `--accent-green: #22C55E;` then `var(--accent-green)` | reusable named value |
| `rem` | `1.5rem` | relative to the root font size (usually 16px), so it scales with user settings |
| flexbox | `display: flex; justify-content: space-between;` | lay children out in a **row** (or column) |
| grid | `display: grid; grid-template-columns: 380px 1fr;` | lay children out in a **2-D grid**; `1fr` = "the remaining space" |
| positioning | `position: relative` on a parent, `position: absolute; left: 40%` on a child | place a child at exact coordinates inside its parent (used by the profit map) |
| media query | `@media (max-width: 1024px) { … }` | rules that apply only on smaller screens (responsive design) |
| transition | `transition: all 0.15s ease;` | animate changes smoothly (e.g. on hover) |
| keyframes | `@keyframes pulse { 0% {…} 50% {…} }` | a named animation |

The **design spec** for this look is in [`DESIGN.md`](../DESIGN.md): near-black background, radar green
`#22C55E`, monospace font everywhere, sharp 2px corners, no emoji, no purple gradients.

### Internationalisation (i18n)

**i18n** (an "i", 18 letters, an "n") means making an app work in several languages. The simplest
correct approach, used here:

1. Put **every** UI text in a dictionary per language, with the **same keys**:

   ```js
   const STRINGS = {
     en: { solveIdle: "[ EXECUTE SOLVER ]", invalidInput: (detail) => `INVALID INPUT: ${detail}` },
     vi: { solveIdle: "[ CHẠY BỘ GIẢI ]",   invalidInput: (detail) => `DỮ LIỆU KHÔNG HỢP LỆ: ${detail}` },
   };
   const t = STRINGS[lang];          // pick the current language's dictionary
   <button>{t.solveIdle}</button>     // components only ever use keys
   ```

2. Texts with a **variable part** are **functions** (`invalidInput(detail)`), because word order differs
   between languages; you can't just glue strings together.
3. Store **keys**, not finished sentences, in state. If an error is stored as
   `{ key: "invalidInput", detail: "…" }`, switching the language re-translates it on the next render.
   A stored English sentence would stay English.

### `localStorage` and lazy initial state

`localStorage` is a small key/value store in the browser that **survives page reloads**:
`localStorage.setItem("lieng-scope-lang", "vi")` / `localStorage.getItem("lieng-scope-lang")`. It can
throw (e.g. in some private-browsing modes), so the code wraps it in `try/catch`.

`useState(loadSavedLang)` (a function, **without** calling it) is a **lazy initial state**: React calls
the function only on the first render to compute the starting value, instead of on every render.

### Accessibility attributes

Screen readers (software that reads the page aloud for blind users) need extra hints for custom
controls:

- `aria-label="…"` names a button whose visible text isn't self-explanatory ("EN VI");
- `aria-pressed={true/false}` tells that a toggle button is on or off;
- `role="group"` + `aria-label` groups related buttons ("OPPONENT FOLDS: WEAKEST HANDS / AT RANDOM").

---

# Part A — Global design tokens

## Step 16.1 — `index.css`

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

# Part B — `i18n.js` and `App.jsx`

## Step 16.2 — `i18n.js`, part 1: the English texts

Every text the user sees (apart from game terms and the hand names the backend sends) lives in one
file. We write the English dictionary first.

📄 **File:** `frontend/src/i18n.js` — *create this file*

```js
// UI copy for each supported language. Game terms (Sáp, Liêng, Đĩ, Điểm) and
// backend-provided hand names are Vietnamese in both languages.
export const STRINGS = {
  en: {
    locale: "en-US",
    langToggleLabel: "Switch language to Vietnamese",

    subtitle: "GTO SOLVER & COMBINATORIAL ENGINE",
    liveSolver: "LIVE SOLVER",
    classesLoaded: "455 CLASSES LOADED",

    controlsTag: "// TELEMETRY CONTROLS",
    potLabel: "CURRENT POT (VND)",
    betLabel: "BET / RAISE SIZING",
    foldLabel: "OPPONENT FOLD FREQUENCY",
    foldMin: "0% (CALLING STATION)",
    foldMax: "100% (EXTREME FOLD)",
    opponentFolds: "OPPONENT FOLDS",
    modelRange: "WEAKEST HANDS",
    modelRandom: "AT RANDOM",
    profitMap: "RAISE PROFIT MAP (THIS HAND)",
    handLabel: "PLAYER HAND (3 CARDS)",
    handPlaceholder: "e.g. As Kh Qd",
    solveBusy: "[ COMPUTING RANGE... ]",
    solveIdle: "[ EXECUTE SOLVER ]",
    solverOffline: () => "LOCAL SOLVER DAEMON OFFLINE. VERIFY BACKEND RUNNING ON PORT 5000.",
    invalidInput: (detail) => `INVALID INPUT: ${detail}`,

    specArchitecture: "SOLVER ARCHITECTURE",
    specArchitectureVal: "MONTE CARLO / CANONICAL",
    specSpace: "COMBINATORIAL SPACE",
    specSpaceVal: "22,100 COMBOS (455 CLS)",
    specQuery: "ONLINE QUERY COMPLEXITY",
    specQueryVal: "O(1) CACHED LOOKUP",

    recommendedAction: "// RECOMMENDED ACTION",
    actionRaise: "ACTION: RAISE / ALL-IN",
    actionFold: "ACTION: CHECK / FOLD",
    expectedValueTag: "// EXPECTED VALUE",
    profitableWhen: "RAISE +EV WHEN OPP. FOLDS:",
```

📄 **File:** `frontend/src/i18n.js` — *add to the end*

```js

    rangeCoverage: "RANGE COVERAGE",
    combosOfTotal: "/ 22,100 COMBOS",
    showdownEquity: "SHOWDOWN EQUITY",
    showdownEquitySub: "VS UNKNOWN 49-CARD SPECTRUM",
    vsCallingRange: (pct) => `VS TOP ${pct}% CALLING RANGE`,
    vsRandomShort: (equity) => `RANDOM ${equity}`,
    expectedValue: "EXPECTED VALUE",
    expectedValueSub: "NET VND GAIN PER DECISION",
    bluffThreshold: "PURE BLUFF THRESHOLD",
    bluffThresholdSub: "MIN FOLD EQ FOR 0-PT AIR",
    notAvailable: "N/A",

    matrixTag: "// CATEGORY COVERAGE MATRIX",
    matrixId: "4 CORE HIERARCHIES",
    colCategory: "CATEGORY",
    colDescription: "DESCRIPTION",
    colClasses: "CLASSES",
    colCombos: "COMBOS",
    colProfitable: "PROFITABLE",
    colCoverage: "COVERAGE",
    colStatus: "RADAR STATUS",
    descSap: "Three of a Kind",
    descLieng: "Straight Sequence",
    descDi: "Three Face Cards",
    descDiem: "Points Modulo 10",
    statusFull: "100% PUSH",
    statusPartial: "PARTIAL",
    statusZero: "FOLD",

    topHandsTag: "// TOP PROFITABLE HOLDINGS",
    topHandsId: "SAMPLE EQUIVALENCE CLASSES",
    colCanonicalId: "CANONICAL ID",
    colEquity: "SHOWDOWN EQUITY",
    colEv: "EXPECTED VALUE (EV)",
    colMultiplicity: "MULTIPLICITY",
    colAction: "ACTION",
    combosSuffix: "combos",
    raise: "RAISE",
    fold: "FOLD",

    notesCollapse: "[ − COLLAPSE TELEMETRY NOTES ]",
    notesExpand: "[ + MATHEMATICAL TELEMETRY NOTES ]",
    notesTitle: "// GAME-THEORETIC TELEMETRY ADVISORY",
    notesLoading: "> TRANSMITTING GAME-THEORETIC TELEMETRY QUERY...",
    notesEmpty: "No active telemetry payload recorded for this game state.",
    aiNoAdvice: () => "No telemetry analysis generated.",
    aiUnreachable: () => "AI telemetry gateway unreachable.",
    aiTransportFault: (detail) => `Telemetry transmission fault: ${detail}`,
  },
```

**How it works**

- `export const STRINGS = { en: { … }, vi: { … } }`: one object per language, **same keys** in both.
  `export` makes it importable from `App.jsx`.
- Plain texts are strings (`potLabel: "CURRENT POT (VND)"`). Texts with a **variable part** are arrow
  functions: `vsCallingRange: (pct) => \`VS TOP ${pct}% CALLING RANGE\``. The component calls
  `t.vsCallingRange(65)` → `"VS TOP 65% CALLING RANGE"`.
- Messages that are stored in **state** (errors and AI notices) are *all* functions, even those without
  a parameter (`solverOffline: () => "…"`). That way the component can always call
  `t[key](detail)` without checking which kind it is. A uniform shape keeps the calling code simple.
- `locale: "en-US"` is used for number formatting (`22,100` in English, `22.100` in Vietnamese).
- The comment at the top states a design decision: **game terms** (Sáp, Liêng, Đĩ, Điểm) stay
  Vietnamese in both languages, like "Texas Hold'em" stays English in every language.

## Step 16.3 — `i18n.js`, part 2: the Vietnamese texts and the language list

📄 **File:** `frontend/src/i18n.js` — *add to the end*

```js

  vi: {
    locale: "vi-VN",
    langToggleLabel: "Chuyển ngôn ngữ sang tiếng Anh",

    subtitle: "BỘ GIẢI GTO & ĐỘNG CƠ TỔ HỢP",
    liveSolver: "ĐANG CHẠY",
    classesLoaded: "ĐÃ NẠP 455 LỚP BÀI",

    controlsTag: "// BẢNG ĐIỀU KHIỂN",
    potLabel: "POT HIỆN TẠI (VND)",
    betLabel: "MỨC CƯỢC / TỐ",
    foldLabel: "TẦN SUẤT ĐỐI THỦ BỎ BÀI",
    foldMin: "0% (LUÔN THEO)",
    foldMax: "100% (LUÔN BỎ)",
    opponentFolds: "ĐỐI THỦ BỎ",
    modelRange: "BÀI YẾU NHẤT",
    modelRandom: "NGẪU NHIÊN",
    profitMap: "BẢN ĐỒ LÃI KHI TỐ (BÀI NÀY)",
    handLabel: "BÀI CỦA BẠN (3 LÁ)",
    handPlaceholder: "VD: As Kh Qd",
    solveBusy: "[ ĐANG TÍNH TOÁN... ]",
    solveIdle: "[ CHẠY BỘ GIẢI ]",
    solverOffline: () => "BỘ GIẢI CỤC BỘ KHÔNG PHẢN HỒI. KIỂM TRA BACKEND ĐANG CHẠY Ở CỔNG 5000.",
    invalidInput: (detail) => `DỮ LIỆU KHÔNG HỢP LỆ: ${detail}`,

    specArchitecture: "KIẾN TRÚC BỘ GIẢI",
    specArchitectureVal: "MONTE CARLO / CHUẨN HÓA",
    specSpace: "KHÔNG GIAN TỔ HỢP",
    specSpaceVal: "22.100 TỔ HỢP (455 LỚP)",
    specQuery: "ĐỘ PHỨC TẠP TRUY VẤN",
    specQueryVal: "O(1) TRA CỨU BỘ ĐỆM",

    recommendedAction: "// HÀNH ĐỘNG KHUYẾN NGHỊ",
    actionRaise: "HÀNH ĐỘNG: TỐ / TẤT TAY",
    actionFold: "HÀNH ĐỘNG: KHÔNG TỐ / BỎ BÀI",
    expectedValueTag: "// GIÁ TRỊ KỲ VỌNG",
    profitableWhen: "TỐ CÓ LÃI KHI ĐỐI THỦ BỎ:",
```

📄 **File:** `frontend/src/i18n.js` — *add to the end*

```js

    rangeCoverage: "ĐỘ PHỦ DẢI BÀI",
    combosOfTotal: "/ 22.100 TỔ HỢP",
    showdownEquity: "TỶ LỆ THẮNG KHI LẬT BÀI",
    showdownEquitySub: "TRƯỚC 49 LÁ CHƯA BIẾT",
    vsCallingRange: (pct) => `TRƯỚC TOP ${pct}% BÀI THEO`,
    vsRandomShort: (equity) => `NGẪU NHIÊN ${equity}`,
    expectedValue: "GIÁ TRỊ KỲ VỌNG",
    expectedValueSub: "LÃI RÒNG (VND) MỖI QUYẾT ĐỊNH",
    bluffThreshold: "NGƯỠNG TỐ HÙ (BLUFF)",
    bluffThresholdSub: "TỶ LỆ BỎ BÀI TỐI THIỂU CHO BÀI 0 ĐIỂM",
    notAvailable: "N/A",

    matrixTag: "// MA TRẬN ĐỘ PHỦ THEO NHÓM BÀI",
    matrixId: "4 CẤP BẬC CHÍNH",
    colCategory: "NHÓM BÀI",
    colDescription: "MÔ TẢ",
    colClasses: "LỚP",
    colCombos: "TỔ HỢP",
    colProfitable: "CÓ LÃI",
    colCoverage: "ĐỘ PHỦ",
    colStatus: "TRẠNG THÁI",
    descSap: "Ba lá cùng hạng",
    descLieng: "Ba lá liên tiếp",
    descDi: "Ba lá hình (J, Q, K)",
    descDiem: "Tính điểm (mod 10)",
    statusFull: "100% TỐ",
    statusPartial: "MỘT PHẦN",
    statusZero: "BỎ BÀI",

    topHandsTag: "// CÁC THẾ BÀI CÓ LÃI NHẤT",
    topHandsId: "MẪU LỚP TƯƠNG ĐƯƠNG",
    colCanonicalId: "MÃ CHUẨN",
    colEquity: "TỶ LỆ THẮNG",
    colEv: "GIÁ TRỊ KỲ VỌNG (EV)",
    colMultiplicity: "SỐ TỔ HỢP",
    colAction: "HÀNH ĐỘNG",
    combosSuffix: "tổ hợp",
    raise: "TỐ",
    fold: "BỎ",

    notesCollapse: "[ − THU GỌN GHI CHÚ PHÂN TÍCH ]",
    notesExpand: "[ + GHI CHÚ PHÂN TÍCH TOÁN HỌC ]",
    notesTitle: "// TƯ VẤN LÝ THUYẾT TRÒ CHƠI",
    notesLoading: "> ĐANG GỬI TRUY VẤN PHÂN TÍCH...",
    notesEmpty: "Chưa có dữ liệu phân tích cho tình huống này.",
    aiNoAdvice: () => "Không có phân tích nào được tạo.",
    aiUnreachable: () => "Không kết nối được cổng phân tích AI.",
    aiTransportFault: (detail) => `Lỗi truyền dữ liệu phân tích: ${detail}`,
  },
};

export const LANGUAGES = Object.keys(STRINGS);
```

**How it works**

- The `vi` block mirrors `en` key by key. Note the Vietnamese poker vocabulary from chapter 1: *TỐ*
  (raise), *TẤT TAY* (all-in), *BỎ BÀI* (fold).
- `locale: "vi-VN"` and `specSpaceVal: "22.100 TỔ HỢP"`: Vietnamese uses a **dot** as the thousands
  separator.
- `export const LANGUAGES = Object.keys(STRINGS);` → `["en", "vi"]`. The list of languages is
  **derived** from the dictionary, so adding a third language is just adding a third block.

> 💡 **Keeping two dictionaries in sync.** Nothing checks that `vi` has every key `en` has. A missing key
> shows up as `undefined` on screen, or as a crash for function-valued keys (`t[key] is not a function`).
> A tiny test would guard it:
> `expect(Object.keys(STRINGS.vi).sort()).toEqual(Object.keys(STRINGS.en).sort())` (with a JS test
> runner such as Vitest), or a TypeScript type for the dictionary.

---

From here we write `App.jsx` in **slices**, from top to bottom. The file only becomes valid when all
slices are in (a JSX tag opened in one slice may be closed several slices later), so **don't run the page
until Step 16.20**. Each slice is explained as you add it.

## Step 16.4 — Imports, constants and helper functions

📄 **File:** `frontend/src/App.jsx` — *create this file*

```jsx
import { useState, useEffect } from 'react';
import './App.css';
import { STRINGS, LANGUAGES } from './i18n.js';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";
const LANG_STORAGE_KEY = "lieng-scope-lang";

// Backend category enum -> display label and i18n description key
const CATEGORY_LABELS = { SAP: "SÁP", LIENG: "LIÊNG", DI: "ĐĨ", DIEM: "ĐIỂM" };
const CATEGORY_DESC_KEYS = { SAP: "descSap", LIENG: "descLieng", DI: "descDi", DIEM: "descDiem" };

function formatMoney(num) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat("vi-VN").format(Math.round(num));
}

function formatZones(zones) {
  const pct = (f) => `${Math.round(f * 100)}%`;
  return zones.map(([start, end]) => (start === end ? pct(start) : `${pct(start)}–${pct(end)}`)).join(" · ");
}

function loadSavedLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return LANGUAGES.includes(saved) ? saved : "en";
  } catch {
    return "en";
  }
}
```

**How it works**

- `import { STRINGS, LANGUAGES } from './i18n.js'` brings in the dictionary from Steps 16.2–16.3.
- **Two lookup tables** translate the backend's ASCII category names (chapter 13) for display:
  `CATEGORY_LABELS.DI` → `"ĐĨ"`, and `CATEGORY_DESC_KEYS.DI` → `"descDi"`, a key into `STRINGS`.
- `formatMoney` uses the browser's built-in **`Intl.NumberFormat`** with the Vietnamese locale (dots as
  thousands separators): `131876` → `"131.876"`.
- `formatZones` turns the API's `profitable_fold_zones` (chapter 13) into text:
  `[[0, 0.08], [0.51, 1]]` → `"0%–8% · 51%–100%"`. A zone with `start === end` (a single grid point)
  prints once. `zones.map(...).join(" · ")` is the JS version of `" · ".join(...)` in Python.
- `loadSavedLang` reads the saved language, **accepts it only if it's a known language** (never trust
  stored data either), and defaults to English. `catch { … }` without a variable (optional catch
  binding) is used because the error itself isn't needed.

> ⚠️ **Pitfall: two number formats on one page.** `formatMoney` always uses `"vi-VN"` (dots), while
> other numbers use `toLocaleString(t.locale)` (commas in English). In English mode the EV shows
> `+131.876` but the combo count shows `22,100`. To an English reader, `131.876` looks like a hundred and
> thirty-one point eight. The fix: pass the locale in, `formatMoney(num, t.locale)`.

## Step 16.5 — The component, its state, and the language effect

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

export default function App() {
  const [lang, setLang] = useState(loadSavedLang);
  const t = STRINGS[lang];

  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);
  const [opponentModel, setOpponentModel] = useState("range");

  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [solveData, setSolveData] = useState(null);
  // { text } from the server, or { key, detail } for a client-side notice translated at render
  const [aiAdvice, setAiAdvice] = useState(null);
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  // { key, detail } translated at render, or null
  const [solveError, setSolveError] = useState(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      // Storage unavailable (e.g. private mode): the choice just won't persist.
    }
  }, [lang]);
```

**How it works**

- `useState(loadSavedLang)`: **lazy initial state** (see Concepts). `t = STRINGS[lang]` is recomputed on
  every render: when `lang` changes, every `t.something` in the JSX switches language.
- **Inputs:** `pot`, `betSize`, `hand`, `foldEquity` (defaults: the chapter 1 example) and
  `opponentModel`, which defaults to **`"range"`**, the more realistic model (chapter 9).
- **UI/result state:** two loading flags, the solve results, the AI advice, the drawer toggle, and
  `solveError`. The comments describe their **shape**: `aiAdvice` is `{ text }` (from the server) or
  `{ key, detail }` (a client-side notice), and `solveError` is `{ key, detail }`. Keys, not sentences, so
  they re-translate when the language changes (Concepts, i18n rule 3).
- **The language effect:** `useEffect(…, [lang])` runs after every render in which `lang` changed:
  - `document.documentElement.lang = lang` sets `<html lang="vi">`, so screen readers pronounce the text
    correctly and browsers offer the right translation/spell-check;
  - it saves the choice in `localStorage` inside `try/catch`, with a comment explaining why ignoring
    the error is safe. That's the right way to "swallow" an exception: deliberately, narrowly, documented.

> 💡 **Different defaults by design.** The API's default is `"random"` (backward compatibility for old
> clients, chapter 13), but the UI's default is `"range"` (better advice for humans). Both choices are
> reasonable, but remember it: the same hand without `opponent_model` gives the API's random-model answer,
> which can differ from what the web page shows.

## Step 16.6 — `handleSolve`, part 1: call `/api/solve`

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setSolveError(null);

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
          opponent_model: opponentModel,
        }),
      });

      if (!solveRes.ok) {
        // The solver is up but rejected the input (e.g. duplicate cards)
        const errJson = await solveRes.json().catch(() => ({}));
        setSolveError({ key: "invalidInput", detail: errJson.error || `HTTP ${solveRes.status}` });
        setIsLoading(false);
        setIsAiLoading(false);
        return;
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
- The JSON body uses the API's field names (`bet_size`, `fold_equity`, `opponent_model`: snake_case,
  Python style), while the JS variables are camelCase. `Number(...)` makes sure we send numbers.
- **Two kinds of failure are told apart:**
  - the server answered but said **no** (`!solveRes.ok`, e.g. 400 for `"Xx Kh Qd"`): show
    `invalidInput` with the server's own message, turn the loading flags off, and `return` early;
  - the server **didn't answer at all**: `fetch` itself throws, handled in Step 16.7.
- `solveRes.json().catch(() => ({}))`: if the error body isn't valid JSON, use an empty object instead of
  crashing. `({})` needs parentheses so JS reads it as an object, not an empty function body.

> ✅ **How the code fixed this (before → after).** The first version *threw* on a 400 and let the outer
> `catch` show "LOCAL SOLVER DAEMON OFFLINE" for **every** error, so a typo in the hand claimed the
> server was down. Now a rejected input shows `INVALID INPUT: Invalid hand: Invalid rank 'X'…`, and
> "offline" is kept for real network failures. **Lesson:** an error message must describe the error that
> actually happened.

## Step 16.7 — `handleSolve`, part 2: call `/api/analyze`, handle network errors

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
            opponent_model: opponentModel,
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });

        if (analyzeRes.ok) {
          const analyzeJson = await analyzeRes.json();
          setAiAdvice(analyzeJson.advice ? { text: analyzeJson.advice } : { key: "aiNoAdvice" });
        } else {
          setAiAdvice({ key: "aiUnreachable" });
        }
      } catch (aiErr) {
        setAiAdvice({ key: "aiTransportFault", detail: aiErr.message });
      } finally {
        setIsAiLoading(false);
      }
    } catch {
      setSolveError({ key: "solverOffline" });
      setIsLoading(false);
      setIsAiLoading(false);
    }
  };
```

**How it works**

- **Two requests in sequence:** the analysis needs the solve results (`hand_evaluation`, coverage) and
  the `opponent_model` (so the AI text explains which model the numbers assume, chapter 13). It runs only
  after `/api/solve` succeeded: the main results are already on screen while the (possibly slow, up to
  20 s) LLM call runs. That's good UX.
- The analyze call has its **own** `try/catch/finally`, so if the AI fails the solver results stay
  visible. `finally` runs whether it succeeded or failed, so the spinner always stops.
- Advice is stored as `{ text }` (server text, shown as-is) or `{ key, detail }` (our own notice, translated
  at render time).
- The outer `catch { … }` has no variable: it doesn't need the error object, because it always means
  "couldn't reach the solver".

> ✅ **Fixed: a linter warning.** The first version wrote `catch (err)` and never used `err`; the linter
> (chapter 15) flagged it. Optional catch binding (`catch {`) states the intent: "any failure here means
> offline".

## Step 16.8 — Solve on page load, and derived values

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

  // Run initial solve on mount
  useEffect(() => {
    handleSolve();
  }, []);

  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const isRaise = handEval?.decision === "RAISE";

  const zones = handEval?.profitable_fold_zones;

  // Category Matrix Statistics (computed by the solver per category)
  const categoryMatrix = (summary?.category_breakdown || []).map((row) => ({
    ...row,
    pct: ((row.profitable_combos / row.combos) * 100).toFixed(1),
  }));
```

**How it works**

- `useEffect(() => { handleSolve(); }, [])` runs the solver once when the page opens, so the dashboard is
  never empty. (Under `StrictMode` in development it runs twice, see chapter 15.)
- **Derived values** are computed from state on every render, not stored in state: `handEval`,
  `summary`, `isRaise`, `zones`. The `?.` operator returns `undefined` instead of crashing while
  `solveData` is still `null`.
- **The category matrix comes straight from the backend** (`summary.category_breakdown`, chapter 13).
  Each row is copied with the **spread** syntax (`{ ...row, pct: … }` = all of `row`'s fields plus a new
  `pct` field), adding the coverage percentage as a string with one decimal (`.toFixed(1)`).
  `|| []` gives an empty table before the first response.

> ✅ **How the code fixed this (before → after).** The first version received only the *total* of
> profitable combos and **guessed** the split with hard-coded caps: `Math.min(288, …)` for Đĩ and
> `Math.min(20992, …)` for Điểm. Those numbers were wrong: chapter 6 proves 144 and 21,136, and the old
> table showed "288 / 288" Đĩ combos when only 144 exist. Now the backend computes exact per-category
> counts from the data, and this code just displays them: **20 lines of guessing became 4 lines of
> mapping**. **Lesson:** don't re-derive in the frontend what the backend can compute exactly.

## Step 16.9 — Start rendering: container and header with the language toggle

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
          <p className="terminal-subtitle">{t.subtitle}</p>
        </div>

        <div className="header-actions">
          <div className="telemetry-status-tag">
            <span className="radar-beacon"></span>
            <span className="telemetry-status-text">{t.liveSolver}</span>
            <span className="telemetry-separator">/</span>
            <span className="telemetry-classes">{t.classesLoaded}</span>
          </div>

          <button
            type="button"
            className="lang-toggle"
            onClick={() => setLang((cur) => (cur === "en" ? "vi" : "en"))}
            aria-label={t.langToggleLabel}
            title={t.langToggleLabel}
          >
            {LANGUAGES.map((code) => (
              <span key={code} className={`lang-option ${lang === code ? "active" : ""}`}>
                {code.toUpperCase()}
              </span>
            ))}
          </button>
        </div>
      </header>
```

**How it works**

- `return ( … )`: everything returned is JSX. A component must return **one** root element (here the
  `terminal-container` div). `{/* … */}` is how you write a comment inside JSX.
- The title is two `<span>`s, white "LIÊNG" and green "SCOPE" (`DESIGN.md` §4.1); the subtitle comes from
  the dictionary (`{t.subtitle}`).
- `header-actions` groups the status tag and the new **language toggle** on the right.
- **The toggle** is one button showing both codes (`EN` `VI`), the active one highlighted via the
  `active` class. Clicking flips the language:
  `setLang((cur) => (cur === "en" ? "vi" : "en"))`. Passing a **function** to a state setter
  ("given the current value, compute the next one") is the safe way to update state based on its
  previous value.
- `aria-label` and `title` describe what the button does (in the *current* language): "Switch language
  to Vietnamese". `title` also shows as a tooltip on hover.

> 💡 "LIVE SOLVER / 455 CLASSES LOADED" is static text, shown even if the backend is down. The
> `/health` endpoint (chapter 13) returns the real `classes_loaded`; using it would make the badge honest.

## Step 16.10 — The control panel: pot

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

      {/* Main Tactical Grid */}
      <main className="terminal-grid">
        {/* Left Column: Control Telemetry */}
        <section className="terminal-card control-panel">
          <div className="panel-header">
            <span className="panel-tag">{t.controlsTag}</span>
            <span className="panel-id">SEC-01</span>
          </div>

          <div className="form-group">
            <label className="form-label">{t.potLabel}</label>
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

## Step 16.11 — Bet sizing

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <label className="form-label">{t.betLabel}</label>
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
are how poker players think, and chapter 10's table showed why: the break-even numbers depend only on the
ratio `B / P`. (`0.5x Pot` etc. aren't translated: they're universal poker shorthand.)

## Step 16.12 — The fold-frequency slider

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <div className="slider-label-row">
              <label className="form-label">{t.foldLabel}</label>
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
              <span>{t.foldMin}</span>
              <span>50%</span>
              <span>{t.foldMax}</span>
            </div>
```

`<input type="range">` is a slider. It works in the 0–1 range with 0.01 steps (the probability the API
expects), and the badge shows it as a percentage. Input values are always strings, hence `parseFloat`.
Note that this `form-group` div is **not closed yet**: the next slice adds two more controls inside it.

## Step 16.13 — The opponent-model toggle and the profit map

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

            <div className="model-row">
              <span className="form-label model-label">{t.opponentFolds}</span>
              <div className="preset-chips model-chips" role="group" aria-label={t.opponentFolds}>
                {["range", "random"].map((model) => (
                  <button
                    key={model}
                    type="button"
                    className={`preset-chip ${opponentModel === model ? "active" : ""}`}
                    aria-pressed={opponentModel === model}
                    onClick={() => setOpponentModel(model)}
                  >
                    {model === "range" ? t.modelRange : t.modelRandom}
                  </button>
                ))}
              </div>
            </div>

            {zones && (
              <div className="profit-map">
                <span className="profit-map-label">{t.profitMap}</span>
                <div className="profit-map-bar">
                  {zones.map(([start, end]) => (
                    <span
                      key={start}
                      className="profit-zone"
                      style={{ left: `${Math.min(start, 0.99) * 100}%`, width: `${Math.max(end - start, 0.01) * 100}%` }}
                    />
                  ))}
                  <span className="profit-marker" style={{ left: `${foldEquity * 100}%` }} />
                </div>
              </div>
            )}
          </div>
```

**How it works**

- **The opponent-model toggle**: two chips generated from `["range", "random"]`, labelled
  "WEAKEST HANDS" / "AT RANDOM" (chapters 1 and 9). `aria-pressed` tells screen readers which one is on;
  `role="group"` + `aria-label` names the pair.
- **The profit map** is a small chart built from plain `<span>`s, shown once a hand was evaluated
  (`zones && …`):
  - the bar itself is red (= raising loses money);
  - each profitable zone `[start, end]` is a green `<span>` placed with **inline styles**:
    `left: 51%` and `width: 49%` for the zone `[0.51, 1.0]`. `style={{ … }}` is an object of CSS properties
    (camelCase names; the outer braces are JSX, the inner braces the object);
  - `Math.min(start, 0.99)` and `Math.max(end - start, 0.01)` keep even a single-point zone (e.g.
    `[1.0, 1.0]`) visible as a 1%-wide sliver inside the bar;
  - a white **marker** at `left: foldEquity × 100%` shows where the current slider value falls.
- So for `K-Q-3` with a pot-sized bet under the range model you see: green 0–8%, red 9–50%, green
  51–100%, and the marker at 35% in the red. **Chapter 10's non-monotonic EV, drawn as a picture.**
- The final `</div>` closes the `form-group` opened in Step 16.12.

> 💡 The green zones come from the last solve and **don't depend on the slider**: the API scans the whole
> 0–100% grid (chapter 13). Only the white marker follows the slider live, because it reads the
> `foldEquity` state, not the response. So you can drag the slider to see where your fold estimate falls
> without re-solving; changing the pot, bet, hand or model needs a new solve.

## Step 16.14 — The hand input and presets

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <div className="form-group">
            <label className="form-label">{t.handLabel}</label>
            <div className="input-wrapper">
              <input
                type="text"
                className="input-field mono-bold"
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                placeholder={t.handPlaceholder}
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
verdict: the canonical class shows `[K-Q-J]`, the naming inconsistency from chapter 6. The preset
labels aren't translated: they're game terms.

> 💡 **Repetition.** Five nearly identical `<button>` blocks differ only in the hand and the label. An
> array like `const HAND_PRESETS = [["As Kh Qd", "Liêng Q-K-A"], …]` plus one `.map` (as the pot chips
> and the model chips do) would be shorter and harder to get wrong.

## Step 16.15 — The solve button, error box and specs card

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          <button
            type="button"
            className="tactical-btn"
            onClick={handleSolve}
            disabled={isLoading}
          >
            {isLoading ? t.solveBusy : t.solveIdle}
          </button>

          {solveError && (
            <div className="terminal-alert">
              <span className="alert-marker">!</span>
              <span>{t[solveError.key](solveError.detail)}</span>
            </div>
          )}

          {/* Engine Specs Sub-Card */}
          <div className="specs-subcard">
            <div className="spec-row">
              <span className="spec-label">{t.specArchitecture}</span>
              <span className="spec-val">{t.specArchitectureVal}</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">{t.specSpace}</span>
              <span className="spec-val">{t.specSpaceVal}</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">{t.specQuery}</span>
              <span className="spec-val">{t.specQueryVal}</span>
            </div>
          </div>
        </section>
```

**How it works**

- `onClick={handleSolve}` passes the function itself (no parentheses: we don't call it now, React calls it
  on click). `disabled={isLoading}` prevents double-submits while a request is running.
- **Translating a stored error:** `t[solveError.key](solveError.detail)`. `t["invalidInput"]` is a
  function (Step 16.2); calling it with the detail produces the sentence in the **current** language.
  Switch the language while an error is shown and it re-translates instantly.
- `</section>` closes the left column opened in Step 16.10.

(The specs card still says "MONTE CARLO"; the shipped data was actually computed by **exact
enumeration**, chapter 7.)

## Step 16.16 — Right column: the verdict banner

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

        {/* Right Column: Strategic HUD & Matrix */}
        <section className="results-container">
          {/* Verdict Banner */}
          {handEval && (
            <div className={`verdict-banner ${isRaise ? "verdict-raise" : "verdict-fold"}`}>
              <div className="verdict-col-left">
                <span className="verdict-label">{t.recommendedAction}</span>
                <h2 className="verdict-title">
                  {isRaise ? t.actionRaise : t.actionFold}
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
                <span className="verdict-label">{t.expectedValueTag}</span>
                <div className="verdict-ev">
                  {handEval.ev > 0 ? "+" : ""}{formatMoney(handEval.ev)} <span className="ev-currency">VND</span>
                </div>
                <div className="verdict-breakeven">
                  {t.profitableWhen} <span className="mono-green">{formatZones(zones)}</span>
                </div>
              </div>
            </div>
          )}
```

**How it works**

- Only shown when a hand was evaluated (`handEval && …`).
- **One class switches the whole look:** `verdict-raise` (green border and title) or `verdict-fold`
  (red). The CSS (Part C) uses combined selectors like `.verdict-raise .verdict-title`.
- Every value comes straight from the API's `hand_evaluation` object (chapter 13, Step 13.8). The hand
  name (`score_name`, e.g. "LIÊNG Q-K-A", "3 ĐIỂM") is produced by the backend in Vietnamese and isn't
  translated, by design.
- The bottom line used to show a single "break-even fold equity". It now shows **all** profitable zones:
  "RAISE +EV WHEN OPP. FOLDS: 0%–8% · 51%–100%", because under the range model a single number can't
  describe the answer (chapter 10).

> ⚠️ **Pitfall: an empty answer.** If raising is never profitable, `zones` is `[]`, `formatZones` returns
> `""`, and the banner reads "RAISE +EV WHEN OPP. FOLDS:" followed by nothing. A short "NEVER" text (a
> new i18n key) would be clearer.

## Step 16.17 — The four HUD metric cards

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* 4-Card Metrics HUD */}
          <div className="hud-metrics-grid">
            <div className="hud-card">
              <div className="hud-label">{t.rangeCoverage}</div>
              <div className="hud-value green-glow">
                {summary?.range_coverage_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="hud-subtext">
                {summary?.profitable_combinations?.toLocaleString(t.locale) || "0"} {t.combosOfTotal}
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.showdownEquity}</div>
              <div className="hud-value white-metric">
                {handEval ? `${(handEval.showdown_equity * 100).toFixed(1)}%` : t.notAvailable}
              </div>
              <div className="hud-subtext">
                {handEval && summary.opponent_model === "range"
                  ? `${t.vsCallingRange(Math.round((1 - summary.fold_equity) * 100))} · ${t.vsRandomShort(
                      `${(handEval.equity_vs_random * 100).toFixed(1)}%`
                    )}`
                  : t.showdownEquitySub}
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.expectedValue}</div>
              <div className={`hud-value ${handEval?.ev > 0 ? "green-metric" : "dim-metric"}`}>
                {handEval ? `${handEval.ev > 0 ? "+" : ""}${formatMoney(handEval.ev)}` : "0"}
              </div>
              <div className="hud-subtext">{t.expectedValueSub}</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.bluffThreshold}</div>
              <div className="hud-value amber-metric">
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : t.notAvailable}
              </div>
              <div className="hud-subtext">{t.bluffThresholdSub}</div>
            </div>
          </div>
```

**How it works**

- Four cards, each a label, a big value and a sub-text (`DESIGN.md` §4.3): coverage (chapter 11), equity
  (chapters 7 and 9), EV (chapter 10) and the pure-bluff threshold `B/(P+B)` (chapter 10). Each value has
  a fallback (`t.notAvailable`, `"0"`) for when data hasn't arrived yet.
- `toLocaleString(t.locale)` formats the combo count for the current language (`22,100` / `22.100`).
- **The equity card adapts to the model.** Under the range model its sub-text explains what the equity
  is measured against *and* shows the random-hand equity for comparison:
  "VS TOP 65% CALLING RANGE · RANDOM 99.7%". `Math.round((1 - fold_equity) * 100)` turns a 35% fold
  frequency into "top 65%". Under the random model it shows the old generic text.

## Step 16.18 — The category coverage matrix

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Range Breakdown Matrix Table */}
          <div className="terminal-card table-panel">
            <div className="panel-header">
              <span className="panel-tag">{t.matrixTag}</span>
              <span className="panel-id">{t.matrixId}</span>
            </div>

            <div className="table-wrapper">
              <table className="tactical-table">
                <thead>
                  <tr>
                    <th>{t.colCategory}</th>
                    <th>{t.colDescription}</th>
                    <th>{t.colClasses}</th>
                    <th>{t.colCombos}</th>
                    <th>{t.colProfitable}</th>
                    <th>{t.colCoverage}</th>
                    <th>{t.colStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryMatrix.map((cat) => (
                    <tr key={cat.category}>
                      <td>
                        <span className={`cat-pill cat-${cat.category}`}>{CATEGORY_LABELS[cat.category]}</span>
                      </td>
                      <td className="desc-cell">{t[CATEGORY_DESC_KEYS[cat.category]]}</td>
                      <td className="mono-num">{cat.classes}</td>
                      <td className="mono-num">{cat.combos.toLocaleString(t.locale)}</td>
                      <td className="mono-num">{cat.profitable_combos.toLocaleString(t.locale)}</td>
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
                            ? t.statusFull
                            : Number(cat.pct) > 0
                            ? t.statusPartial
                            : t.statusZero}
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

- A standard HTML table: `<thead>` with column titles, `<tbody>` with one `<tr>` per row of
  `categoryMatrix` (Step 16.8), i.e. per row of the backend's `category_breakdown`.
- The backend's ASCII names (`SAP`, `DI`…) are the `key`s and the CSS class suffix (`cat-SAP`), while the
  visible label goes through `CATEGORY_LABELS` ("SÁP", "ĐĨ") and the description through the i18n key
  table: `t[CATEGORY_DESC_KEYS[cat.category]]`. That's two lookups: category → key → text.
- The status chip uses a **chained ternary** (`a ? x : b ? y : z`): 100% → "100% PUSH", more than 0 →
  "PARTIAL", else "FOLD" (translated).

## Step 16.19 — Top holdings table

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Top Canonical Holdings Table */}
          {solveData?.top_hands && (
            <div className="terminal-card table-panel">
              <div className="panel-header">
                <span className="panel-tag">{t.topHandsTag}</span>
                <span className="panel-id">{t.topHandsId}</span>
              </div>

              <div className="table-wrapper">
                <table className="tactical-table">
                  <thead>
                    <tr>
                      <th>{t.colCanonicalId}</th>
                      <th>{t.colCategory}</th>
                      <th>{t.colEquity}</th>
                      <th>{t.colEv}</th>
                      <th>{t.colMultiplicity}</th>
                      <th>{t.colAction}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solveData.top_hands.slice(0, 10).map((item) => (
                      <tr key={item.canonical_id}>
                        <td className="mono-canonical">{item.canonical_id}</td>
                        <td>
                          <span className={`cat-pill cat-${item.category}`}>{CATEGORY_LABELS[item.category]}</span>
                        </td>
                        <td className="mono-num">{(item.equity * 100).toFixed(1)}%</td>
                        <td className={`mono-num bold-num ${item.ev > 0 ? "positive-ev" : "negative-ev"}`}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev)} VND
                        </td>
                        <td className="dim-cell">{item.multiplicity} {t.combosSuffix}</td>
                        <td>
                          <span className={`action-badge ${item.is_profitable ? "act-raise" : "act-fold"}`}>
                            {item.is_profitable ? t.raise : t.fold}
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
a good `key`. The equity shown is the one the selected model used (chapter 11).

> 💡 Because the list is sorted by EV and the strongest hands always have the highest EV, this table is
> almost always the same ten Sáp hands (A-A-A, K-K-K, …). Showing the **threshold** region (the
> weakest hands that are still profitable, where decisions are actually hard) would be more informative,
> though under the range model that region contains many tied equity-0 hands (chapter 11's pitfall).

## Step 16.20 — The notes drawer, and closing everything

📄 **File:** `frontend/src/App.jsx` — *add to the end*

```jsx

          {/* Collapsible Mathematical Telemetry Notes Drawer */}
          <div className="notes-drawer-container">
            <button
              type="button"
              className="drawer-toggle-btn"
              onClick={() => setIsNotesOpen(!isNotesOpen)}
            >
              <span>{isNotesOpen ? t.notesCollapse : t.notesExpand}</span>
              <span className="drawer-indicator">{isNotesOpen ? "▲" : "▼"}</span>
            </button>

            {isNotesOpen && (
              <div className="drawer-content">
                <div className="drawer-header">
                  <span className="drawer-title">{t.notesTitle}</span>
                  <span className="drawer-sub">OPENROUTER / LLAMA 3.1 8B INSTRUCT</span>
                </div>

                {isAiLoading ? (
                  <div className="telemetry-loading">
                    <span className="radar-spinner"></span>
                    <span>{t.notesLoading}</span>
                  </div>
                ) : (
                  <div className="telemetry-body">
                    {!aiAdvice ? t.notesEmpty : aiAdvice.text ?? t[aiAdvice.key](aiAdvice.detail)}
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
- While the analysis is loading, show a spinner; then show the advice:
  `!aiAdvice ? t.notesEmpty : aiAdvice.text ?? t[aiAdvice.key](aiAdvice.detail)`. Read it as: no advice
  yet → "empty" text; otherwise the server's text if there is one (`??` is the **nullish coalescing**
  operator: use the right side only if the left is `null`/`undefined`), else translate our own notice.
- The advice is Markdown (`**bold**`) but is shown as **plain text**, so you'll see the asterisks. A
  Markdown renderer library would display it properly. Never insert server-provided HTML directly
  (`dangerouslySetInnerHTML`): that opens the door to script-injection attacks (XSS).
- The AI's text is in Vietnamese (the prompt asks for it, chapter 13) even when the UI is in English.
- The last lines close `section`, `main`, the container `div`, the `return (`, and the `App` function.

🧪 **Mini-check.** With Flask running, start Vite (`npm run dev`) and open http://localhost:5173. The page
should work **completely** (opponent model "WEAKEST HANDS" by default): the verdict "ACTION: RAISE /
ALL-IN" with `+131.876 VND` and "RAISE +EV WHEN OPP. FOLDS: 0%–100%", the HUD (100.0% coverage, 99.5%
equity "VS TOP 65% CALLING RANGE · RANDOM 99.7%", 33.3% bluff threshold) and both tables. Click **VI**:
every label switches to Vietnamese. It just looks plain, because `App.css` is still empty. Let's fix that.

---

# Part C — `App.css`

From here on, **every step leaves the page working**. Keep the browser open next to your editor: Vite
reloads styles instantly when you save.

## Step 16.21 — Container, header and branding

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
  flex-wrap: wrap;
  gap: 1rem;
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
  status tag to the right; `align-items: center` centres them vertically. `flex-wrap: wrap` plus `gap:
  1rem` let the right-hand group drop below the title on narrow screens instead of squeezing it.
- `.brand-group` is a flex **column** with a small `gap` between title and subtitle.
- `text-shadow: 0 0 12px …` with no offset and a blur creates the green **glow**.
- `letter-spacing` in `em` (relative to font size) gives the wide "terminal" lettering.

**Save → look:** the title is now big with a glowing green "SCOPE", and a line separates the header.

---

## Step 16.22 — The live-status tag and its pulsing beacon

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

## Step 16.23 — The language toggle

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Language Toggle (EN / VI) */
.header-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.lang-toggle {
  display: inline-flex;
  background: var(--bg-surface);
  border: 1px solid var(--border-base);
  border-radius: 2px;
  padding: 0.2rem;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 0.15s;
}

.lang-toggle:hover,
.lang-toggle:focus-visible {
  border-color: var(--accent-green);
  outline: none;
}

.lang-option {
  padding: 0.25rem 0.6rem;
  border-radius: 2px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-dim);
  transition: all 0.15s;
}

.lang-option.active {
  background: var(--accent-green-muted);
  color: var(--accent-green);
  font-weight: 700;
}
```

**How it works**

- `.header-actions` lays the status tag and the toggle side by side (flex row, `gap`), wrapping on
  narrow screens.
- `.lang-toggle` is one bordered button; inside it, each `.lang-option` is a small label. The **active**
  language gets the green "chip" look (`.lang-option.active`), the same visual language as the preset
  chips, so the UI stays consistent.
- `:focus-visible` (instead of `:focus`) shows the focus border only when the user navigates with the
  **keyboard**, not after a mouse click. It's accessible and doesn't add visual noise for mouse users.
  `outline: none` is safe here because the border change replaces the outline.

**Save → look:** a compact `EN | VI` switch appears next to the status tag. Click it: the labels
change language, and the choice survives a page reload (`localStorage`).

---

## Step 16.24 — The two-column grid and panels

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

/* Let grid items shrink below their tables' min-content width (tables scroll instead) */
.terminal-grid > * {
  min-width: 0;
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
- **`.terminal-grid > * { min-width: 0; }`** fixes a classic grid surprise: by default a grid item is never
  narrower than its content's minimum width, so a wide table would push the whole column (and page)
  sideways. With `min-width: 0` the column keeps its size and the table scrolls inside its
  `.table-wrapper` (Step 16.31). The comment in the CSS says exactly that: comment the *why*.
- **Responsive design:** on screens **1024px or narrower** (tablets, phones), the media query switches to
  a single column, so the results drop below the controls. Try it by narrowing your browser window.
- `.terminal-card` is the reusable "dark panel" look, used by the control panel and both tables.

**Save → look:** the page now has its two-column layout.

---

## Step 16.25 — Form controls: labels, inputs and preset chips

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
- **`.preset-chip.active`**: the class added in JSX (Step 16.10) when a chip matches the current value.
- `flex-wrap: wrap` lets chips flow onto a second line when there isn't room.
- `transition: all 0.15s` animates colour changes on hover.

---

## Step 16.26 — The slider

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

## Step 16.27 — The opponent-model row and the profit map

📄 **File:** `frontend/src/App.css` — *add to the end*

```css

/* Opponent Model Toggle */
.model-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  margin-top: 0.9rem;
}

.model-label {
  margin-bottom: 0;
}

.model-chips {
  margin-top: 0;
}

/* Raise Profit Map: red track = -EV, green zones = +EV, white marker = current fold frequency */
.profit-map {
  margin-top: 0.9rem;
}

.profit-map-label {
  display: block;
  font-size: 0.65rem;
  color: var(--text-dim);
  letter-spacing: 0.04em;
  margin-bottom: 0.35rem;
}

.profit-map-bar {
  position: relative;
  height: 10px;
  background: var(--accent-red-muted);
  border: 1px solid var(--border-base);
  border-radius: 2px;
}

.profit-zone {
  position: absolute;
  top: 0;
  bottom: 0;
  background: var(--accent-green-muted);
  border-left: 1px solid var(--accent-green);
  border-right: 1px solid var(--accent-green);
}

.profit-marker {
  position: absolute;
  top: -4px;
  bottom: -4px;
  width: 2px;
  background: var(--text-white);
  transform: translateX(-1px);
  box-shadow: 0 0 4px var(--text-white);
}
```

**How it works**

- `.model-row` is a wrapping flex row: the "OPPONENT FOLDS" label on the left, the two chips on the
  right. `.model-label` and `.model-chips` only cancel margins that `.form-label` and `.preset-chips`
  would otherwise add. **Reusing existing classes and overriding one property** keeps the look
  consistent without duplicating styles.
- **The profit map** is the classic "absolute inside relative" layout:
  - `.profit-map-bar` is `position: relative`, 10px tall, with a dark-red background (= −EV);
  - each `.profit-zone` is `position: absolute` with `top: 0; bottom: 0` (full height). Its `left` and
    `width` come from the **inline styles** set in JSX (Step 16.13), so the same CSS draws any zones;
  - `.profit-marker` is a 2px white line that sticks out 4px above and below the bar
    (`top: -4px; bottom: -4px`). `transform: translateX(-1px)` shifts it left by half its width, so it
    is **centred** on the exact fold percentage.
- The comment above the block documents the colour meaning (red = −EV, green = +EV, white = current
  fold frequency). A chart with no legend should at least have its meaning written down somewhere.

**Save → look:** set the hand to `Ks Qh 3d`, the bet to "1.0x Pot", keep "WEAKEST HANDS" and 35%, and
execute: the map shows **green 0–8%, red 9–50%, green 51–100%** with the marker in the red. The
verdict says CHECK / FOLD. Click "AT RANDOM" and execute again: the whole bar turns green.

---

## Step 16.28 — The action button, alert and specs card

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

## Step 16.29 — Right column and the verdict banner

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
  Changing the single class on the banner (Step 16.16) recolours the border, glow and title together.

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

**Save → look:** click the "0 Điểm (Bù)" preset, click **AT RANDOM**, set the slider to 5% and execute:
the banner turns red ("ACTION: CHECK / FOLD", −42.044 VND). Move the slider to 50% and execute again:
green, +25.240. That's chapter 14's scenarios 2 and 3, live. (With **WEAKEST HANDS** the numbers are
−42.500 and +25.000: `2-3-5` can't beat any hand that calls, so its equity is exactly 0.)

---

## Step 16.30 — The HUD metric cards

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

## Step 16.31 — Tables

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

## Step 16.32 — Category pills, status chips, action badges

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

## Step 16.33 — The notes drawer

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
2. On load you should see, without clicking anything (model "WEAKEST HANDS", fold 35%):
   - **ACTION: RAISE / ALL-IN**, `As Kh Qd • [Q-K-A] • LIÊNG Q-K-A`, **+131.876 VND**, and
     "RAISE +EV WHEN OPP. FOLDS: **0%–100%**";
   - a fully green profit map with the marker at 35%;
   - HUD: **100.0%** (22,100 / 22,100 combos), **99.5%** ("VS TOP 65% CALLING RANGE · RANDOM 99.7%"),
     **+131.876**, **33.3%**;
   - the category matrix with **52 / 768 / 144 / 21,136** combos (all "100% PUSH") and the top-10 table
     starting with `A-A-A`.
3. **The two models, side by side.** Hand `Ks Qh 3d`, bet "1.0x Pot", fold 35%:
   - WEAKEST HANDS → red **CHECK / FOLD**, **−27.894 VND**, zones "0%–8% · 51%–100%", equity 1.1%
     ("RANDOM 36.0%"), coverage 54.6%;
   - AT RANDOM → green **RAISE**, zones "0%–100%", equity 36.0%, coverage 84.7%.
4. Type an invalid hand (`Xx Kh Qd`) and execute → "INVALID INPUT: Invalid hand: Invalid rank 'X'…"
   (not "offline"). Stop Flask and execute → "LOCAL SOLVER DAEMON OFFLINE…". Start Flask again.
5. Click **VI** → everything switches to Vietnamese (the error box too, if shown); reload the page → still
   Vietnamese.
6. Open the notes drawer: the Vietnamese rule-based analysis appears, mentioning the opponent model (or
   an LLM answer if you set `OPENROUTER_API_KEY` before starting Flask).
7. Narrow the window below 1024px: the layout becomes one column, and the header wraps.
8. `npm run lint`: **no errors, 2 warnings**:

   ```
   src/App.jsx:127:5: warning react(set-state-in-effect): Calling setState synchronously within an effect can trigger cascading renders
   src/App.jsx:127:5: warning react-hooks(exhaustive-deps): React Hook useEffect has a missing dependency: 'handleSolve'
   ```

   Both concern `useEffect(() => { handleSolve(); }, [])`: the effect calls a function that is
   re-created on every render and that sets state. It works here, but React's recommended pattern is to
   keep effects for syncing with external systems (like the language effect, which writes to
   `document` and `localStorage`). The first version had a third warning (an unused `err`), fixed in
   Step 16.7. **Linters are cheap code reviewers: read their warnings.**

Compare your four files with the originals (`diff -B`; see chapter 5), then commit:

```bash
git add frontend && git commit -m "feat: LIÊNG SCOPE dashboard with i18n and opponent models"
```

## Recap

- `App` holds inputs (including `opponentModel` and `lang`) and results in **state**; `handleSolve` calls
  `/api/solve`, then `/api/analyze`; every state change re-renders the page.
- **i18n:** all texts live in `STRINGS[lang]`; texts with variables are functions; state stores **keys**
  (`{ key, detail }`), so switching language re-translates everything, errors included. The choice is
  saved in `localStorage` and mirrored to `<html lang>`.
- Derived values (`handEval`, `zones`, `categoryMatrix`) are computed from state, not stored. The category
  matrix and the profit zones come **from the backend**, never guessed.
- The **profit map** draws chapter 10's non-monotonic EV with absolutely-positioned spans on a
  relatively-positioned bar.
- The CSS is built from **design tokens**, **flexbox**, **grid** (with `min-width: 0` so tables scroll),
  **media queries**, **keyframes**, and `:focus-visible` for keyboard users.
- ✅ Fixed since the first version: guessed (and wrong) category totals, every error shown as
  "offline", an unused-variable lint warning.
- ⚠️ Still open: two number formats in English mode, empty zones show blank text, static "LIVE" status,
  Markdown shown as raw text, repeated preset buttons, "MONTE CARLO" spec label, UI default model ≠ API
  default.

**Next:** [17 — Deployment](17-deployment.md)
