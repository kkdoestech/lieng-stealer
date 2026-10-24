# Lesson 13 — The React app

> **Goal:** read `App.jsx` from top to bottom: its state, the two-step fetch and every error path,
> how a newer run cancels an older one, how each JSON key becomes something on screen, and how
> `i18n.js` and `format.js` keep text and number formatting out of the component.
> **Files:** [`frontend/src/App.jsx`](../frontend/src/App.jsx), [`i18n.js`](../frontend/src/i18n.js),
> [`format.js`](../frontend/src/format.js), [`App.test.jsx`](../frontend/src/App.test.jsx),
> [`i18n.test.js`](../frontend/src/i18n.test.js), [`format.test.js`](../frontend/src/format.test.js).
> **Time:** ~75 min. **Before this:** [12 — Frontend tooling](12-frontend-tooling.md).

---

## Where this fits

```
                       ┌──────────────── App.jsx (this lesson) ─────────────────┐
  click, type, drag ──►│ 12 useState values ──► derived values ──► JSX render   │──► what you see
                       │        ▲                                      │        │
                       │        └── callbacks ◄── runSolve ◄── startSolve       │
                       │                             │                          │
                       │      fetchSolveAndAnalysis (no state, outside App)     │
                       └─────────────────────────────┬──────────────────────────┘
       i18n.js: t = STRINGS[lang]                    │ POST /api/solve, then POST /api/analyze
       format.js: formatMoney, formatZones           ▼
                                               app.py (lessons 10–11)
```

The whole UI is one file, 591 lines: some data and four plain functions at the top, then the `App`
component. It keeps the inputs and the last answer in state, sends two requests per "Run solver",
and draws everything from the answer. The EV, zones and category counts all come from the backend.
Its own jobs are input, errors, translation and formatting.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [App.jsx:1-36](../frontend/src/App.jsx#L1-L36) | Imports, `API_BASE`, steppers' limits, presets as data, label maps, `loadSavedLang`. |
| 2 | [App.jsx:38-90](../frontend/src/App.jsx#L38-L90) | `solveErrorFor` and `fetchSolveAndAnalysis`: two fetches, every way to fail, and the abort checks. |
| 3 | [App.jsx:92-122](../frontend/src/App.jsx#L92-L122) | `Stepper`, the one component used twice. |
| 4 | [App.jsx:124-153](../frontend/src/App.jsx#L124-L153) | All state, the `currentRun` ref, and the effect that saves the language. |
| 5 | [App.jsx:155-220](../frontend/src/App.jsx#L155-L220) | `runSolve`, `startSolve`, the mount effect, and the derived values. |
| 6 | [App.jsx:222-402](../frontend/src/App.jsx#L222-L402) | The header and the left column: steppers, presets, slider, model toggle, profit map. |
| 7 | [App.jsx:404-587](../frontend/src/App.jsx#L404-L587) | The right column: verdict, summary rows, two tables, notes. |
| 8 | [i18n.js](../frontend/src/i18n.js) and [i18n.test.js](../frontend/src/i18n.test.js) | Two dictionaries with the same 84 keys, and the test that enforces it. |
| 9 | [format.js](../frontend/src/format.js), [format.test.js](../frontend/src/format.test.js) and [App.test.jsx](../frontend/src/App.test.jsx) | The two pure helpers, and the 18 tests. |

---

## Walkthrough

### 1. The state

Every `useState` call gives one value and its setter (see the concept box). There are twelve:

| State | Initial value | Changed by | Read by |
|-------|---------------|-----------|---------|
| `lang` | saved choice or `"en"` | language toggle [:234](../frontend/src/App.jsx#L234) | `t` [:126](../frontend/src/App.jsx#L126), the effect [:146-153](../frontend/src/App.jsx#L146-L153) |
| `pot` | `100000` | the pot `Stepper` [:256](../frontend/src/App.jsx#L256), presets [:263](../frontend/src/App.jsx#L263) | request body [:159](../frontend/src/App.jsx#L159), bet presets [:276](../frontend/src/App.jsx#L276) |
| `betSize` | `50000` | the bet `Stepper` [:273](../frontend/src/App.jsx#L273), presets [:282](../frontend/src/App.jsx#L282) | request body [:160](../frontend/src/App.jsx#L160), preset highlight [:281](../frontend/src/App.jsx#L281) |
| `hand` | `"As Kh Qd"` | typing [:354](../frontend/src/App.jsx#L354), presets [:364](../frontend/src/App.jsx#L364) | request body [:162](../frontend/src/App.jsx#L162), preset highlight [:363](../frontend/src/App.jsx#L363) |
| `foldEquity` | `0.35` | slider [:303](../frontend/src/App.jsx#L303) | request body, `35%` badge [:294](../frontend/src/App.jsx#L294), profit marker [:340](../frontend/src/App.jsx#L340) |
| `opponentModel` | `"range"` | model buttons [:321](../frontend/src/App.jsx#L321) | request body, `aria-pressed` [:320](../frontend/src/App.jsx#L320) |
| `isLoading` | `true` | `startSolve` [:191](../frontend/src/App.jsx#L191), callbacks [:169](../frontend/src/App.jsx#L169), [:176](../frontend/src/App.jsx#L176) | button label and `disabled` [:376-378](../frontend/src/App.jsx#L376-L378) |
| `isAiLoading` | `true` | `startSolve` [:192](../frontend/src/App.jsx#L192), callbacks [:177](../frontend/src/App.jsx#L177), [:181](../frontend/src/App.jsx#L181) | notes drawer [:577](../frontend/src/App.jsx#L577) |
| `solveData` | `null` | callbacks [:168](../frontend/src/App.jsx#L168), [:174](../frontend/src/App.jsx#L174) | derived values [:210-220](../frontend/src/App.jsx#L210-L220), top hands [:520](../frontend/src/App.jsx#L520) |
| `aiAdvice` | `null` | callbacks [:175](../frontend/src/App.jsx#L175), [:180](../frontend/src/App.jsx#L180) | notes drawer [:574](../frontend/src/App.jsx#L574), [:581](../frontend/src/App.jsx#L581) |
| `isNotesOpen` | `false` | drawer button [:564](../frontend/src/App.jsx#L564) | drawer [:566-570](../frontend/src/App.jsx#L566-L570) |
| `solveError` | `null` | `startSolve` [:193](../frontend/src/App.jsx#L193), callbacks [:167](../frontend/src/App.jsx#L167), [:173](../frontend/src/App.jsx#L173) | error box [:381-385](../frontend/src/App.jsx#L381-L385) |

The first six are **inputs**. The last six describe **what happened**. Results are never edited by
hand: they are replaced as a whole when an answer arrives. `isLoading` and `isAiLoading` start as
`true` because the first solve begins as soon as the page mounts (section 4).

One more value is not state: `currentRun = useRef(null)` ([:144](../frontend/src/App.jsx#L144))
holds the `AbortController` of the run in progress. Changing a ref does not re-render; it is a box
that survives between renders (see the concept box).

The language is loaded once and saved on every change:

📍 [`frontend/src/App.jsx:29-36`](../frontend/src/App.jsx#L29-L36)
```jsx
function loadSavedLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return LANGUAGES.includes(saved) ? saved : "en";
  } catch {
    return "en";
  }
}
```

`useState(loadSavedLang)` at [:125](../frontend/src/App.jsx#L125) passes the function itself, so React
calls it only on the first render. `localStorage` survives reloads but can throw (some private
modes), hence the `try/catch` here and in the effect at [:146-153](../frontend/src/App.jsx#L146-L153),
which also sets `<html lang>` for screen readers. An unknown saved value falls back to English.
`t = STRINGS[lang]` ([:126](../frontend/src/App.jsx#L126)) is the dictionary every label reads.

### 2. `fetchSolveAndAnalysis`, step 1: `/api/solve`

The round trip lives **outside** the component. It holds no state; it reports each step through
three callbacks and stops calling them as soon as its `signal` is aborted:

📍 [`frontend/src/App.jsx:47-73`](../frontend/src/App.jsx#L47-L73)
```jsx
// One solve + analysis round trip. It holds no state: it reports each step through the callbacks
// and stops calling them as soon as `signal` is aborted (a newer run started, or the page unmounted).
async function fetchSolveAndAnalysis(body, signal, { onSolved, onSolveFailed, onAnalysis }) {
  const post = (path) =>
    fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body, signal });

  let solveJson;
  try {
    const solveRes = await post("/api/solve");
    if (signal.aborted) return;
    if (!solveRes.ok) {
      const errorBody = await solveRes.json().catch(() => ({}));
      if (!signal.aborted) onSolveFailed(solveErrorFor(solveRes.status, errorBody));
      return;
    }
    try {
      solveJson = await solveRes.json();
    } catch {
      if (!signal.aborted) onSolveFailed({ key: "badResponse" });
      return;
    }
  } catch {
    if (!signal.aborted) onSolveFailed({ key: "solverOffline" });
    return;
  }
  if (signal.aborted) return;
  onSolved(solveJson);
```

- **One body for both requests.** `body` is the JSON string built by `runSolve` (section 4): the five
  inputs and nothing else. Passing `signal` to `fetch` lets an abort cancel a request in flight.
- **Three nested failure points.** The outer `catch` fires only when no HTTP answer arrives at all
  (`fetch` rejects). A 400 is a normal response with `ok === false`, so it needs the explicit check.
  The inner `try` separates "the server answered 200 but the body isn't JSON" from "no answer".
- **`signal.aborted` after every `await`.** An `await` can resume after a newer run has started. The
  check makes the old run go quiet instead of overwriting the newer run's results (section 4).
- **Errors are a key plus a detail**, not a sentence (section 7). `solveErrorFor` picks the key:

📍 [`frontend/src/App.jsx:38-45`](../frontend/src/App.jsx#L38-L45)
```jsx
// Map a failed /api/solve response to the message shown under the button ({ key, detail }).
// The API answers every error with { error, code }; a 5xx without a code did not come from Flask
// (e.g. the dev proxy could not reach it), so it means the solver is not running.
function solveErrorFor(status, body) {
  if (status >= 500) return body.code ? { key: "serverError" } : { key: "solverOffline" };
  if (body.code === "invalid_hand") return { key: "invalidHand", detail: body.error };
  return { key: "invalidParams", detail: body.error ?? `HTTP ${status}` };
}
```

Every API error is `{"error": "...", "code": "..."}` (lesson 10), so the UI decides on the `code`
and shows the server's `error` only as the detail. The UI always sends all five fields, so the
backend's defaults never apply. Note `opponent_model`: the UI starts on `"range"`, while the API
defaults to `"random"` ([app.py:254](../backend/app.py#L254)). That is why the same Q-K-A shows
**+131,876** in the UI but **+132,097** from a bare `curl` (lesson 07).

### 3. Step 2: `/api/analyze`, and every way to fail

📍 [`frontend/src/App.jsx:75-90`](../frontend/src/App.jsx#L75-L90)
```jsx
  // The server recomputes everything for the analysis from the same inputs.
  let advice;
  try {
    const analyzeRes = await post("/api/analyze");
    if (signal.aborted) return;
    if (analyzeRes.ok) {
      const analyzeJson = await analyzeRes.json();
      advice = analyzeJson.advice ? { text: analyzeJson.advice, model: analyzeJson.model } : { key: "aiNoAdvice" };
    } else {
      advice = { key: analyzeRes.status === 429 ? "aiRateLimited" : "aiUnreachable" };
    }
  } catch (aiErr) {
    advice = { key: "aiTransportFault", detail: aiErr.message };
  }
  if (!signal.aborted) onAnalysis(advice);
}
```

The analysis request sends the **same five inputs** and nothing from step 1: `/api/analyze`
recomputes the evaluation on the server and ignores any numbers a client sends (lesson 10). A test
checks the body has exactly those five keys ([App.test.jsx:140-147](../frontend/src/App.test.jsx#L140-L147)).
`onSolved` has already run, so whatever happens to the analysis, the numbers stay on screen.

Every path below is covered by a test or was reproduced with `fetch` mocked; the backend texts are
the real ones:

| What happened | Caught at | State | Text shown (English) |
|---------------|-----------|-------|----------------------|
| Bad hand `As Xh Qd` → 400 `invalid_hand` | [:57-60](../frontend/src/App.jsx#L57-L60), [:43](../frontend/src/App.jsx#L43) | `solveError = {invalidHand, detail}`, old results cleared | Check your hand: Invalid card 'Xh': Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A. |
| Pot field emptied → `Number("")` is 0 → 400 `invalid_params` | [:44](../frontend/src/App.jsx#L44) | `{invalidParams, detail}` | Check your inputs: Pot and bet_size must be strictly greater than zero. |
| Server crash → 500 `internal_error` | [:42](../frontend/src/App.jsx#L42) | `{serverError}` | The solver hit an internal error. Try again; if it keeps happening, check the backend log. |
| Flask down behind the dev proxy → 502, empty body | [:42](../frontend/src/App.jsx#L42) (no `code`) | `{solverOffline}` | Can't reach the solver. Start the backend on port 5000 and try again. |
| No HTTP answer at all, `fetch` throws | outer `catch` [:68-70](../frontend/src/App.jsx#L68-L70) | `{solverOffline}` | same |
| 200, but the body is not valid JSON | inner `catch` [:64-66](../frontend/src/App.jsx#L64-L66) | `{badResponse}` | The solver sent a response this page couldn't read. Try again. |
| Analyze answers 429 (rate limit) | [:84](../frontend/src/App.jsx#L84) | `aiAdvice = {aiRateLimited}` | Too many analysis requests. Wait a minute, then run the solver again. |
| Analyze answers another non-2xx (e.g. 502 `upstream_error`) | [:84](../frontend/src/App.jsx#L84) | `aiAdvice = {aiUnreachable}` | Couldn't reach the AI analysis service. The numbers above are unaffected. |
| Analyze answers 200 with empty `advice` | [:82](../frontend/src/App.jsx#L82) | `aiAdvice = {aiNoAdvice}` | The analysis came back empty. |
| Analyze request fails in transit | [:86-87](../frontend/src/App.jsx#L86-L87) | `aiAdvice = {aiTransportFault, detail}` | Analysis request failed: Failed to fetch |
| A newer run started, or the page unmounted | the `signal.aborted` checks | nothing changes | (the newer run's results) |

A failed solve also clears the old verdict, tables and notes (section 4), so nothing on screen
belongs to inputs other than the ones in the form. One row is still mislabelled: a 4xx response
*without* a `code` (for example a web host answering `/api/solve` with its own 404 page) reaches
the last line of `solveErrorFor` and shows "Check your inputs: HTTP 404" (weak spot 1).

### 4. Inside the component: starting, cancelling and the first run

The component's side of a run is three small functions. `runSolve` builds the body and turns each
callback into state changes:

📍 [`frontend/src/App.jsx:155-184`](../frontend/src/App.jsx#L155-L184)
```jsx
  // Start one run with the current inputs; every state change happens in a callback, after the
  // matching response has arrived.
  const runSolve = (controller) => {
    const body = JSON.stringify({
      pot: Number(pot),
      bet_size: Number(betSize),
      fold_equity: Number(foldEquity),
      hand: hand.trim(),
      opponent_model: opponentModel,
    });
    fetchSolveAndAnalysis(body, controller.signal, {
      onSolved: (data) => {
        setSolveError(null);
        setSolveData(data);
        setIsLoading(false);
      },
      onSolveFailed: (error) => {
        // Clear the old results: they belong to different inputs than the ones on screen now.
        setSolveError(error);
        setSolveData(null);
        setAiAdvice(null);
        setIsLoading(false);
        setIsAiLoading(false);
      },
      onAnalysis: (advice) => {
        setAiAdvice(advice);
        setIsAiLoading(false);
      },
    });
  };
```

As soon as the numbers are in, `isLoading` goes false and the page renders them; the analysis is
still on its way. `startSolve` is what the button calls:

📍 [`frontend/src/App.jsx:186-195`](../frontend/src/App.jsx#L186-L195)
```jsx
  // Start a run from a click: cancel any run still in flight, then show the loading state.
  const startSolve = () => {
    currentRun.current?.abort();
    const controller = new AbortController();
    currentRun.current = controller;
    setIsLoading(true);
    setIsAiLoading(true);
    setSolveError(null);
    runSolve(controller);
  };
```

Why cancel? The button is disabled only while `/api/solve` is pending. The analysis can take seconds
(an LLM call), so a user can click again while the first analysis is still out. Without the abort,
the first analysis could land *after* the second run's, and the notes would describe the wrong
hand. A test holds the first analysis back, clicks again, then releases it, and checks that "First
run" never appears ([App.test.jsx:149-170](../frontend/src/App.test.jsx#L149-L170)).

The first run starts on mount:

📍 [`frontend/src/App.jsx:197-220`](../frontend/src/App.jsx#L197-L220)
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

- The effect solves once when the page opens, so the page is never empty. It sets no state itself
  (the loading flags already start `true`), and `useEffectEvent` (see the concept box) lets it read
  the current inputs without listing them as dependencies. That is what keeps `npm run lint` silent
  (lesson 12, section 6).
- Its cleanup aborts the run. In development StrictMode mounts twice, so the first run is
  cancelled; a test checks that ([App.test.jsx:172-180](../frontend/src/App.test.jsx#L172-L180)).
- **Derived values** are recomputed on every render instead of being stored in state, so they can
  never disagree with `solveData`. `?.` returns `undefined` while `solveData` is still `null`.
- `pct` is the one number the UI computes itself: it is a **string** (`"100.0"`), which is why the
  status column compares `Number(cat.pct) === 100` ([:499](../frontend/src/App.jsx#L499),
  [:508](../frontend/src/App.jsx#L508)).

### 5. From JSON to screen

With the UI defaults (pot 100,000, bet 50,000, 35% folds, `As Kh Qd`, range model), here is every
key of the `/api/solve` answer and where it ends up:

| JSON key | Example value | Shown as | Where |
|----------|---------------|----------|-------|
| `hand_evaluation.decision` | `"RAISE"` | "Raise / all-in", green (red for `CHECK/FOLD`) | [:212](../frontend/src/App.jsx#L212), [:408-413](../frontend/src/App.jsx#L408-L413) |
| `.hand` · `.canonical_id` · `.score_name` | `As Kh Qd` · `Q-K-A` · `Liêng Q-K-A` | the line under the verdict | [:415-419](../frontend/src/App.jsx#L415-L419) |
| `.ev` | `131876.0` | "+131,876 VND", and again in the summary | [:426](../frontend/src/App.jsx#L426), [:463-464](../frontend/src/App.jsx#L463-L464) |
| `.profitable_fold_zones` | `[[0.0, 1.0]]` | "…when the opponent folds 0%–100%", and the green bar | [:429](../frontend/src/App.jsx#L429), [:329-343](../frontend/src/App.jsx#L329-L343) |
| `.showdown_equity` | `0.9952` | "Showdown equity 99.5%" | [:450](../frontend/src/App.jsx#L450) |
| `.equity_vs_random` | `0.9969` | "…· 99.7% vs. a random hand" (range model only) | [:453-456](../frontend/src/App.jsx#L453-L456) |
| `summary.opponent_model`, `.fold_equity` | `"range"`, `0.35` | "vs. the top 65% that call" | [:453-454](../frontend/src/App.jsx#L453-L454) |
| `summary.range_coverage_percent` | `100.0` | "Range coverage 100.0%" | [:440](../frontend/src/App.jsx#L440) |
| `summary.profitable_combinations` | `22100` | "22,100 of 22,100 combos are +EV" | [:443](../frontend/src/App.jsx#L443) |
| `summary.pure_bluff_break_even_fold_equity` | `0.3333` | "Bluff break-even 33.3%" | [:472](../frontend/src/App.jsx#L472) |
| `summary.category_breakdown[]` | 4 rows | the coverage table | [:498-513](../frontend/src/App.jsx#L498-L513) |
| `top_hands[]` (30 sent) | `A-A-A` first | the first **10** rows of the second table, with `showdown_equity` as the equity column | [:539-552](../frontend/src/App.jsx#L539-L552) |

Sent but never read: in `hand_evaluation` `category`, `category_name`, `is_profitable`,
`break_even_fold_equity` and `profitable_from_fold_equity`; in `summary` `pot`, `bet_size`,
`final_pot`, `total_canonical_classes`, `profitable_classes`, `total_combinations`, `highest_ev_*`
and `threshold_*` (15 of the 29 fields); and `top_hands[].decision`, since the table reads
`is_profitable` ([:548](../frontend/src/App.jsx#L548)). The "of 22,100" is written into the
translation ([i18n.js:51](../frontend/src/i18n.js#L51)) instead.

With an empty hand field, `hand_evaluation` is `null`: the verdict and profit map disappear, equity
shows `N/A`, and the summary and tables still show the whole-range results.

### 6. The left column: one `Stepper`, presets as data, and the profit map

The pot and the bet use the same small component:

📍 [`frontend/src/App.jsx:92-122`](../frontend/src/App.jsx#L92-L122)
```jsx
function Stepper({ id, label, value, onChange }) {
  return (
    <div className="input-wrapper stepper">
      <button
        type="button"
        className="stepper-btn"
        aria-label={`${label} −${AMOUNT_STEP / 1000}k`}
        onClick={() => onChange(Math.max(MIN_AMOUNT, value - AMOUNT_STEP))}
      >
        −
      </button>
      <input
        id={id}
        type="number"
        className="input-field"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        step={AMOUNT_STEP}
        min={MIN_AMOUNT}
      />
      <button
        type="button"
        className="stepper-btn"
        aria-label={`${label} +${AMOUNT_STEP / 1000}k`}
        onClick={() => onChange(value + AMOUNT_STEP)}
      >
        +
      </button>
    </div>
  );
}
```

- `Stepper` receives everything as **props** (`id`, `label`, `value`, `onChange`) and owns no state.
  `App` renders it twice: `<Stepper id="pot-input" label={t.potLabel} value={pot} onChange={setPot} />`
  ([:256](../frontend/src/App.jsx#L256)) and the same for the bet ([:273](../frontend/src/App.jsx#L273)).
- The input is **controlled** (see the concept box). Minus stops at `MIN_AMOUNT` (1,000), plus has
  no upper limit, both by `AMOUNT_STEP` (10,000, [:11-13](../frontend/src/App.jsx#L11-L13)). A test
  clicks minus from 100,000 and from 5,000 ([App.test.jsx:117-129](../frontend/src/App.test.jsx#L117-L129)).
- `min` only affects the browser's own arrows, which CSS hides (lesson 14). Clearing the field gives
  `Number("")` = 0, and the server's 400 catches it (section 3).
- The buttons have an `aria-label` ("Current pot (VND) −10k"), and `<label htmlFor="pot-input">`
  ([:255](../frontend/src/App.jsx#L255)) links the label to the field. The tests find the buttons
  by exactly that name.

The presets are data at the top of the file:

📍 [`frontend/src/App.jsx:15-23`](../frontend/src/App.jsx#L15-L23)
```jsx
const POT_PRESETS = [50000, 100000, 200000, 500000];
const BET_PRESET_MULTIPLES = [0.5, 1, 2]; // bet = multiple × pot
const HAND_PRESETS = [
  { cards: "As Kh Qd", labelKey: "presetLiengQKA" },
  { cards: "7s 7h 7d", labelKey: "presetSap7" },
  { cards: "Js Qh Kd", labelKey: "presetLiengJQK" },
  { cards: "9s 10h Kd", labelKey: "presetDiem9" },
  { cards: "2s 3h 5d", labelKey: "presetDiem0" },
];
```

Each list becomes buttons with one `.map`: pot presets at [:258-267](../frontend/src/App.jsx#L258-L267),
bet presets at [:275-287](../frontend/src/App.jsx#L275-L287) and hand presets at
[:359-368](../frontend/src/App.jsx#L359-L368). A hand preset stores an i18n **key**, not a label, so
the text comes from `t[labelKey]`. A bet preset computes its amount from the pot
(`Math.round(pot * multiple)`), looks active only while the bet equals it exactly, and gets its label
from `t.betPresetLabel(...)` with the multiple formatted for the locale: "0.5x pot" in English,
"0,5x pot" in Vietnamese. The model buttons ([:314-326](../frontend/src/App.jsx#L314-L326)) form a
`role="group"` with `aria-pressed`, so assistive technology announces which one is on.

The profit map draws each zone with inline percentages:

📍 [`frontend/src/App.jsx:329-343`](../frontend/src/App.jsx#L329-L343)
```jsx
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
```

A one-point zone such as `[1, 1]` is drawn 1% wide instead of invisible. The marker follows the
slider **live**, while the zones change only after the next "Run solver". For K-Q-3 with a
pot-sized bet the zones are `[[0, 0.08], [0.51, 1]]` (lesson 07): two green stretches.

### 7. Translations: one message per error code

All copy lives in [i18n.js](../frontend/src/i18n.js): `STRINGS.en` and `STRINGS.vi`, 84 keys each.
Twelve values are functions. Six take a parameter (`betPresetLabel`, `invalidHand`,
`invalidParams`, `vsCallingRange`, `vsRandomShort`, `aiTransportFault`) and six take none
(`solverOffline`, `serverError`, `badResponse`, `aiNoAdvice`, `aiUnreachable`, `aiRateLimited`).
The solve errors sit together:

📍 [`frontend/src/i18n.js:31-35`](../frontend/src/i18n.js#L31-L35)
```js
    solverOffline: () => "Can't reach the solver. Start the backend on port 5000 and try again.",
    invalidHand: (detail) => `Check your hand: ${detail}`,
    invalidParams: (detail) => `Check your inputs: ${detail}`,
    serverError: () => "The solver hit an internal error. Try again; if it keeps happening, check the backend log.",
    badResponse: () => "The solver sent a response this page couldn't read. Try again.",
```

The render calls every message the same way:

📍 [`frontend/src/App.jsx:381-385`](../frontend/src/App.jsx#L381-L385)
```jsx
          {solveError && (
            <div className="terminal-alert" role="alert">
              {t[solveError.key](solveError.detail)}
            </div>
          )}
```

1. **Messages with a variable part are functions**, because word order differs between languages.
2. **Even fixed messages are functions**, so the render never asks "is this one a function?". A
   zero-parameter function ignores `detail`.
3. **State stores the key, not the sentence.** Switching to VI re-translates a visible error:
   "Kiểm tra lại bài: Invalid card 'Xh': Invalid rank 'X'. …". The server's part stays English.
4. **One message per code** (DESIGN.md §6). The server no longer adds its own "Invalid hand: "
   prefix, so the text is the UI's prefix plus the evaluator's message, nothing stacked.

The notes drawer shows the `model` the API reported in its header ([:574](../frontend/src/App.jsx#L574))
and `aiAdvice.text` if the server sent some (`??`), else a translated notice
([:581](../frontend/src/App.jsx#L581)). Without an API key the header says
`rule-based-solver-engine (OPENROUTER_API_KEY not configured)`, and the text is the Vietnamese
rule-based answer from `_fallback_advice` ([app.py:543](../backend/app.py#L543)), Markdown `**` and
all, in both languages.

### 8. `format.js`, and the tests

📍 [`frontend/src/format.js:1-11`](../frontend/src/format.js#L1-L11)
```js
// Pure formatting helpers, kept outside React so they can be unit-tested without a browser.

export function formatMoney(num, locale) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat(locale).format(Math.round(num));
}

export function formatZones(zones) {
  const pct = (f) => `${Math.round(f * 100)}%`;
  return zones.map(([start, end]) => (start === end ? pct(start) : `${pct(start)}–${pct(end)}`)).join(" · ");
}
```

`Intl.NumberFormat` is the built-in locale formatter (`131,876` in `en-US`, `131.876` in `vi-VN`),
and `t.locale` ([i18n.js:5](../frontend/src/i18n.js#L5)) picks the locale. From `node`:
`formatMoney(2812.5, "vi-VN")` → `"2.813"` and `formatZones([[0.34, 1]])` → `"34%–100%"`.

[format.test.js](../frontend/src/format.test.js) pins four behaviours: the separators, rounding with
the minus sign, `"0"` before data, and zone formatting including a one-point zone (`"100%"`). The
other small file checks the dictionaries:

📍 [`frontend/src/i18n.test.js:5-13`](../frontend/src/i18n.test.js#L5-L13)
```js
// key -> "string" | "function", so a missing key or a wrong kind of value shows up in the diff
const shape = (dictionary) =>
  Object.fromEntries(Object.entries(dictionary).map(([key, value]) => [key, typeof value]));

test("every language defines exactly the English keys, with the same kinds of values", () => {
  for (const lang of LANGUAGES) {
    assert.deepEqual(shape(STRINGS[lang]), shape(STRINGS.en), `language "${lang}"`);
  }
});
```

`shape` turns `{ fold: "Fold", invalidHand: (d) => … }` into `{ fold: "string", invalidHand:
"function" }`, so one `deepEqual` catches a missing key, an extra key, and a string where a function
belongs. Comparing shapes instead of values lets the wording differ freely. The second test
([:15-23](../frontend/src/i18n.test.js#L15-L23)) calls every function that takes a parameter with
`"DETAIL-123"` and checks the result contains it, which catches a translation that forgets
`${detail}`. Neither test can see a key that no code uses.

[App.test.jsx](../frontend/src/App.test.jsx) renders the real component in jsdom (lesson 12) with
`fetch` replaced:

📍 [`frontend/src/App.test.jsx:40-55`](../frontend/src/App.test.jsx#L40-L55)
```jsx
const reply = (status, body) => ({ ok: status < 400, status, json: async () => body });

// Answer each POST by path; `routes[path]` is a reply, or a function (call index) => reply/Promise.
function mockFetch(routes) {
  const calls = [];
  const fetchMock = vi.fn((url, options) => {
    const path = new URL(url, "http://localhost").pathname;
    calls.push({ path, body: JSON.parse(options.body), signal: options.signal });
    const route = routes[path];
    const count = calls.filter((c) => c.path === path).length - 1;
    const result = typeof route === "function" ? route(count) : route;
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}
```

`reply` fakes just the part of a `Response` the app uses (`ok`, `status`, `json()`). A route can be
a fixed reply, an `Error` (to simulate "no answer"), or a function of the call number, which lets one
test answer the first solve with 200 and the second with 400. `calls` records each request's path,
parsed body and `signal`, so tests can check what was sent and what was aborted. The 12 tests find
elements the way a user would (`getByRole("button", { name: "Run solver" })`, `findByRole("alert")`)
rather than by class name. 8 of them fail on the `App.jsx` that came before these fixes.

---

## 💡 Concept: `useState`, `useEffect` and `useRef`

```jsx
const [pot, setPot] = useState(100000);  // value + setter; calling setPot re-runs App() with the new value
useEffect(() => { … }, [lang]);          // run after a render in which lang changed
useEffect(() => { …; return cleanup; }, []); // run once after the first render; cleanup when it goes away
const currentRun = useRef(null);         // a box: currentRun.current survives renders, changing it doesn't re-render
```

`App` is a function that React calls again whenever state changes. Local variables (`t`, `handEval`)
are recalculated each time; only `useState` values and refs survive between calls. Assigning to
state directly does nothing on screen. Hooks must run in the same order on every render (lesson 12).

## 💡 Concept: `useEffectEvent`

An effect lists the values it reads in its dependency array, and re-runs when one changes. Sometimes
you want "run once, but use whatever the inputs are *now*". `useEffectEvent(fn)` (React 19.2) wraps
`fn` so that it always sees the latest props and state, yet is not a dependency. Call it only from
inside effects. Here it lets the mount effect read `pot`, `hand` and the rest without re-solving on
every keystroke.

## 💡 Concept: controlled inputs

`<input value={hand} onChange={(e) => setHand(e.target.value)} />`: the state is the single source
of truth, and the input only displays it. So a preset button that calls `setHand("7s 7h 7d")` updates
the text field with no extra code. For `type="number"`, `e.target.value` is still a **string**
(`""` when empty or invalid), which is why `Stepper` wraps it in `Number(…)`.

## 💡 Concept: `async` / `await`, `fetch` and `AbortController`

`fetch(url, options)` returns a **Promise**, a value that arrives later. Inside an `async` function,
`await` pauses until it arrives, like a blocking call in Python, but without freezing the page.
`fetch` rejects (throws) only on network failure. Any HTTP status, even 500, counts as a response, so
you check `res.ok` (true for 200–299). `await res.json()` reads and parses the body, and throws if it
is not JSON. `JSON.stringify(obj)` is `json.dumps`.

`const c = new AbortController()` gives a `c.signal` to pass to `fetch`. `c.abort()` makes a pending
`fetch` (or its `.json()`) reject with an `AbortError` and sets `c.signal.aborted` to `true`. It
cannot un-send a request that already reached the server; it only stops the page from using the
answer.

---

## Design decisions

- **One component, plus plain functions beside it.** Easy to search, almost no props to thread
  through. The network round trip (`fetchSolveAndAnalysis`) and the error mapping (`solveErrorFor`)
  sit outside `App` and hold no state, so they read top to bottom without React in the way. The
  cost: `App` is still a 468-line function.
- **The backend computes, the frontend formats.** An earlier version guessed the per-category counts
  in the browser and got Đĩ wrong. Now `category_breakdown` comes from the server, and the analysis
  is recomputed there too, from the inputs alone.
- **Numbers first, analysis second.** `onSolved` runs before the analysis is requested, so a slow or
  failing LLM never delays or hides the EV.
- **Every run can be cancelled.** One `AbortController` per run, aborted by the next click or by
  unmounting. The alternative, ignoring stale answers by comparing request IDs, needs the same
  bookkeeping and still lets the stale requests finish.
- **Keys in state, text at render time.** Errors and notices survive a language switch.
- **The range model by default.** The UI assumes the opponent folds their weakest hands, the stricter
  case for medium hands (README: real players sit between the two). The API defaults to `random`.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: lint warnings on the mount effect.** It used to call `handleSolve()`, which set state
  synchronously and was missing from the dependency list. The effect now sets no state and calls a
  `useEffectEvent` ([App.jsx:197-208](../frontend/src/App.jsx#L197-L208)); `npm run lint` has 0
  warnings and fails on any new one (lesson 12).
- ✅ **Fixed: stale results after an error.** The verdict for the previous hand stayed next to the
  red box. `onSolveFailed` now clears `solveData` and `aiAdvice` ([:171-178](../frontend/src/App.jsx#L171-L178)).
  Pinned by "an invalid hand shows its message and clears the old verdict"
  ([App.test.jsx:80-94](../frontend/src/App.test.jsx#L80-L94)).
- ✅ **Fixed: misleading error labels.** A 500 used to read "Invalid input: HTTP 500", and a garbled
  200 "Can't reach the solver". `solveErrorFor` ([:38-45](../frontend/src/App.jsx#L38-L45)) and the
  inner `try` now give each case its own message. Pinned by the three-row table test
  ([App.test.jsx:96-104](../frontend/src/App.test.jsx#L96-L104)).
- ✅ **Fixed: stacked prefixes.** "Invalid input: Invalid hand: Invalid rank 'X'…" had three
  authors. The API now sends the evaluator's message as is with `code: "invalid_hand"`
  ([app.py:190-191](../backend/app.py#L190-L191)) and the UI adds one prefix. Pinned by the exact
  text checked at [App.test.jsx:92](../frontend/src/App.test.jsx#L92).
- ✅ **Fixed: a hard-coded model label.** The notes header always said "OpenRouter · Llama 3.1 8B
  Instruct", even for the rule-based fallback. It now shows the `model` field
  ([:574](../frontend/src/App.jsx#L574)). Pinned by "the notes show the model the API reports"
  ([App.test.jsx:131-138](../frontend/src/App.test.jsx#L131-L138)).
- ✅ **Fixed: a late analysis could overwrite a newer one.** Each run has its own `AbortController`
  ([:186-195](../frontend/src/App.jsx#L186-L195)). Pinned by [App.test.jsx:149-170](../frontend/src/App.test.jsx#L149-L170).
- ✅ **Fixed: copy-pasted presets.** Five hand buttons, three bet buttons and two steppers were
  hand-written blocks. They are now data plus `.map` ([:15-23](../frontend/src/App.jsx#L15-L23)) and one
  `Stepper` ([:92-122](../frontend/src/App.jsx#L92-L122)).
- ✅ **Fixed: unused translation keys.** `liveSolver`, `classesLoaded`, `matrixId` and `topHandsId`
  were deleted from both languages (the 🧪 script below now finds none).
- ✅ **Fixed: most strings outside `i18n.js`.** The bet preset labels, hand preset labels and `VND`
  are keys now (`betPresetLabel`, `preset*`, `currency`, [i18n.js:22-28](../frontend/src/i18n.js#L22-L28)).
- ✅ **Fixed: a wrong footnote and subtitle.** "Monte Carlo" became "Exact enumeration, 455 canonical
  classes" ([i18n.js:38](../frontend/src/i18n.js#L38)) and "GTO solver" became "Expected-value
  solver" ([i18n.js:8](../frontend/src/i18n.js#L8)).
- ✅ **Fixed: the Vite proxy was unused** (lesson 12).

Still open:

1. **A 4xx without a `code` is called an input problem.** Only the 5xx branch of `solveErrorFor`
   checks for a `code` ([:42](../frontend/src/App.jsx#L42)); a 404 or 405 from something that isn't
   the API ends at [:44](../frontend/src/App.jsx#L44) as "Check your inputs: HTTP 404". *Fix:*
   treat any response without a `code` as "not the solver" (exercise 6).
2. **Raw Markdown, in one language.** The notes ([:581](../frontend/src/App.jsx#L581)) show the
   analysis, `**bold**` markers included, as plain text, in Vietnamese for both languages. The
   offline answer even has a "GTO Insight" heading ([app.py:543-571](../backend/app.py#L543-L571)),
   which DESIGN.md §6 rules out for UI copy. *Fix:* render the bold markers (exercise 8); ask the
   backend for the UI's language; reword the fallback.
3. **The server's detail stays English.** In Vietnamese mode the prefix is translated but "Invalid
   card 'Xh': …" is not. *Fix:* translate per `code` and drop the detail for codes the UI fully
   understands, or let the API take a language.
4. **A few strings still bypass `i18n.js`.** The `k` in the pot presets ([:265](../frontend/src/App.jsx#L265))
   and in the stepper labels ([:98](../frontend/src/App.jsx#L98), [:115](../frontend/src/App.jsx#L115)).
   *Fix:* exercise 7.
5. **Two defaults for one setting.** The UI starts on `"range"` ([:132](../frontend/src/App.jsx#L132))
   and the API defaults to `"random"` ([app.py:254](../backend/app.py#L254)): +131,876 versus +132,097
   for the same request without the field. Deliberate (lesson 17 lists it as a design decision), but
   it surprises anyone comparing the UI with `curl`.

---

## 🧪 Try it

Run from `frontend/`.

```bash
npm test 2>&1 | grep -E 'Test Files|Tests '
```

```
 Test Files  3 passed (3)
      Tests  18 passed (18)
```

Call the helpers yourself, and list the translation keys that `App.jsx` never mentions:

```bash
node --input-type=module -e '
import { formatMoney, formatZones } from "./src/format.js";
import { STRINGS } from "./src/i18n.js";
import fs from "node:fs";
console.log(formatMoney(131876, "en-US"), formatMoney(131876, "vi-VN"), formatZones([[0, 0.08], [0.51, 1]]));
console.log(STRINGS.vi.invalidHand("Invalid rank X"));
console.log(Object.keys(STRINGS.en).length, Object.values(STRINGS.en).filter((v) => typeof v === "function").length);
const src = fs.readFileSync("./src/App.jsx", "utf8");
console.log(Object.keys(STRINGS.en).filter((k) => !src.includes("t." + k) && !src.includes(`"${k}"`)));
'
```

```
131,876 131.876 0%–8% · 51%–100%
Kiểm tra lại bài: Invalid rank X
84 12
[]
```

(The last check counts a key as used when `App.jsx` contains `t.<key>` or `"<key>"`: the presets and
`solveErrorFor` name their keys as strings.)

In the browser (`npm run dev` with Flask running), type `As Xh Qd` and click "Run solver". The red
box says "Check your hand: Invalid card 'Xh': Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A.",
the verdict and both tables' rows disappear, and the summary falls back to `0.0%`, `N/A` and `0`.
Switch to VI: the red box changes language, the backend's part does not.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You type `As Kh` (two cards) and click "Run solver". What exactly does the red box
say, and what happens to the verdict? Check in the browser.

<details><summary>Solution</summary>

`Check your hand: Hand string 'As Kh' must contain exactly 3 cards, found 2.` The prefix comes from
`invalidHand` in `i18n.js`, chosen because the API answered `code: "invalid_hand"`
([app.py:190-191](../backend/app.py#L190-L191)); the rest is the evaluator's message
([evaluator.py:437](../backend/src/evaluator.py#L437)). The verdict disappears, because
`onSolveFailed` clears `solveData`.
</details>

**🟢 2. Predict.** You click "At random" and run the solver with the other defaults. Which summary
rows change, and to what?

<details><summary>Solution</summary>

Showdown equity becomes **99.7%** with the note "vs. a random hand"
([:453-457](../frontend/src/App.jsx#L453-L457)), and EV becomes **+132,097** in the verdict and in
its row. Coverage (100.0%) and bluff break-even (33.3%) stay: at a half-pot bet with 35% folds,
every hand is +EV under both models.
</details>

**🟢 3. Predict.** What do `formatMoney(-27894.5, "en-US")` and `formatZones([[1, 1]])` return?
Check with `node --input-type=module -e '…'` as in 🧪.

<details><summary>Solution</summary>

`"-27,894"`, because `Math.round` rounds halves toward +∞. And `"100%"`, because a zone with
`start === end` is printed once ([format.test.js:21](../frontend/src/format.test.js#L21)).
</details>

**🟡 4. Break the parity test.** Delete `fold: "Bỏ",` from the Vietnamese dictionary
([i18n.js:181](../frontend/src/i18n.js#L181)) and run `npm test`. What does the failure tell you?

<details><summary>Solution</summary>

`Tests  1 failed | 17 passed (18)`. "every language defines exactly the English keys" fails with
`AssertionError: language "vi"` and a diff containing `-   "fold": "string",`: English has the key
and Vietnamese does not. Without the test, `t.fold` would be `undefined`, which React renders as
nothing: an empty Action cell for every unprofitable row in Vietnamese. The App tests don't notice,
because they run in English. Undo with `git checkout -- frontend/src/i18n.js`.
</details>

**🟡 5. Break the error mapping.** In `solveErrorFor` ([:42](../frontend/src/App.jsx#L42)), make
every 5xx mean "offline": `if (status >= 500) return { key: "solverOffline" };`. Predict which test
fails and what it prints, then run `npm test`.

<details><summary>Solution</summary>

Exactly one: "a server error shows the matching message". It expected the alert to contain
`internal error` and received `Can't reach the solver. Start the backend on port 5000 and try
again.` That is the old mislabelling: a crash inside Flask sent the user looking for a server that
was running. The 502 case still passes, because it really is "offline". Undo with
`git checkout -- frontend/src/App.jsx`.
</details>

**🟡 6. Close weak spot 1.** Add a fourth row to the table test at
[App.test.jsx:96-100](../frontend/src/App.test.jsx#L96-L100):
`["a 4xx that did not come from the API", reply(404, {}), "Can't reach the solver"]`. See it fail,
then change `solveErrorFor` so it passes without breaking the other 18.

<details><summary>Solution</summary>

Before the change it fails with `Received: Check your inputs: HTTP 404`. Check for the code first:

```jsx
function solveErrorFor(status, body) {
  if (!body.code) return { key: "solverOffline" };
  if (status >= 500) return { key: "serverError" };
  if (body.code === "invalid_hand") return { key: "invalidHand", detail: body.error };
  return { key: "invalidParams", detail: body.error };
}
```

All 19 tests pass. The `HTTP ${status}` fallback is gone, because every response from the API has
a `code`. You could also add a separate message ("Something other than the solver answered"), since
"Start the backend on port 5000" is a development hint. Undo with
`git checkout -- frontend/src/App.jsx frontend/src/App.test.jsx`.
</details>

**🔴 7. The last `k`s.** Move the thousands suffix into `i18n.js` (both languages, one function
such as `thousands: (n) => \`${n}k\``), and use it for the pot presets
([:265](../frontend/src/App.jsx#L265)) and the stepper labels. Check: `npm test` and `npm run lint`
pass unchanged.

<details><summary>Solution</summary>

Add `thousands: (n) => \`${n}k\`,` to `en` and `vi` (next to `currency`). The presets become
`{t.thousands(v / 1000)}`. `Stepper` can't see `t`, so give it a prop: `stepText`, used as
``aria-label={`${label} −${stepText}`}`` and ``+${stepText}``, and pass
`stepText={t.thousands(AMOUNT_STEP / 1000)}` from both call sites. The labels stay "Current pot (VND)
−10k", so the stepper test still finds its button, and the parity tests check that both languages
define the new function and include its parameter. Undo with
`git checkout -- frontend/src/App.jsx frontend/src/i18n.js`.
</details>

**🔴 8. Render the bold markers.** Show `**…**` parts of the analysis as `<strong>` instead of
literal asterisks, without a Markdown library. Write the test first: an analysis of
`"Play **RAISE** now."` must render `RAISE` in a `<strong>` and no `**` anywhere.

<details><summary>Solution</summary>

```jsx
// The analysis marks emphasis with **…**; show those parts in bold and everything else as text.
function BoldText({ text }) {
  return text.split("**").map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part));
}
```

and at [:581](../frontend/src/App.jsx#L581):

```jsx
{!aiAdvice ? t.notesEmpty : aiAdvice.text ? <BoldText text={aiAdvice.text} /> : t[aiAdvice.key](aiAdvice.detail)}
```

Splitting on `**` puts every marked part at an odd index. React escapes the strings, so this is safe
even for text from the LLM (unlike `dangerouslySetInnerHTML`). The test:

```jsx
test("bold markers in the analysis become <strong>", async () => {
  const user = userEvent.setup();
  mockFetch({ "/api/solve": reply(200, SOLVE_OK), "/api/analyze": reply(200, { advice: "Play **RAISE** now.", model: "m" }) });
  render(<App />);
  await user.click(screen.getByRole("button", { name: /Show analysis notes/ }));
  expect((await screen.findByText("RAISE")).tagName).toBe("STRONG");
  expect(screen.queryByText(/\*\*/)).not.toBeInTheDocument();
});
```

19 tests pass and lint stays silent. Undo with
`git checkout -- frontend/src/App.jsx frontend/src/App.test.jsx`.
</details>

---

## ❓ Quiz

1. Why is `solveError` stored as `{ key, detail }` rather than as the finished sentence?
2. `fetch` succeeded and the status is 400. Which branch runs, and why didn't the `catch` fire?
3. Aborting the controller already makes a pending `fetch` reject. Why does
   `fetchSolveAndAnalysis` still check `signal.aborted` after every `await`?
4. The profit-map marker moves while you drag the slider, but the green zones do not. Why?
5. What can `i18n.test.js` detect, and what can it not?

<details><summary>Answers</summary>

1. So that it is translated at render time: switching language re-translates an error that is
   already showing. A stored sentence would stay in the old language.
2. The `if (!solveRes.ok)` branch at [:57](../frontend/src/App.jsx#L57), which hands the status and
   body to `solveErrorFor`. `fetch` throws only when no HTTP response arrives. A 400 is a normal
   response with `ok === false`.
3. An abort only rejects what is still pending. If a response arrived just before the abort, the
   `await` resumes normally, and without the check the old run would call its callbacks and
   overwrite the newer run's state. And when the abort does reject, the `catch` blocks would report
   it as `solverOffline` or `aiTransportFault`; the checks keep those quiet too.
4. The marker reads `foldEquity` state directly ([:340](../frontend/src/App.jsx#L340)). The zones
   come from `solveData`, which changes only when a new `/api/solve` answer arrives.
5. It detects a key missing from (or added to) one language, a string where the other has a function,
   and a message that drops its parameter. It cannot detect wrong wording or unused keys.
</details>

---

## Recap

- `App` holds 12 pieces of state (six inputs, six results) and one ref, the current run's
  `AbortController`. Everything else is derived on render.
- `fetchSolveAndAnalysis`, outside the component, makes two requests: `/api/solve` (numbers, shown
  at once), then `/api/analyze` (notes; the server recomputes them from the same five inputs). It
  reports through callbacks and goes quiet once its run is aborted.
- A click aborts the previous run; the mount effect's cleanup aborts the StrictMode duplicate. A
  failed solve clears the old results.
- Each API error `code` maps to one i18n message; the server's text is only the detail. A 4xx
  without a code is still reported as an input problem.
- Everything the UI shows comes from the server (the map in section 5). 15 of the 29 summary and
  evaluation fields are sent but unused.
- Copy lives in `i18n.js` as two 84-key dictionaries. `format.js` holds the pure helpers.
  `i18n.test.js` compares the dictionaries' *shapes*, and `App.test.jsx` drives the real component
  with `fetch` mocked.

**Next:** [14 — Styling and DESIGN.md](14-styling.md)
