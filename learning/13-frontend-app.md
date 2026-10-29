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

The whole UI is one file, 592 lines: some data and four plain functions at the top, then the `App`
component. It keeps the inputs and the last answer in state, sends two requests per "Run solver",
and draws everything from the answer. The EV, zones and category counts all come from the backend.
Its own jobs are input, errors, translation and formatting.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [App.jsx:1-36](../frontend/src/App.jsx#L1-L36) | Imports, `API_BASE`, steppers' limits, presets as data, label maps, `loadSavedLang`. |
| 2 | [App.jsx:38-99](../frontend/src/App.jsx#L38-L99) | `solveErrorFor` and `fetchSolveAndAnalysis`: two fetches, every way to fail, and the abort checks. |
| 3 | [App.jsx:101-131](../frontend/src/App.jsx#L101-L131) | `Stepper`, the one component used twice. |
| 4 | [App.jsx:133-162](../frontend/src/App.jsx#L133-L162) | All state, the `currentRun` ref, and the effect that saves the language. |
| 5 | [App.jsx:164-229](../frontend/src/App.jsx#L164-L229) | `runSolve`, `startSolve`, the mount effect, and the derived values. |
| 6 | [App.jsx:231-412](../frontend/src/App.jsx#L231-L412) | The header and the left column: steppers, presets, slider, model toggle, profit map. |
| 7 | [App.jsx:414-599](../frontend/src/App.jsx#L414-L599) | The right column: verdict, summary rows, two tables, notes. |
| 8 | [i18n.js](../frontend/src/i18n.js) and [i18n.test.js](../frontend/src/i18n.test.js) | Two dictionaries with the same 84 keys, and the test that enforces it. |
| 9 | [format.js](../frontend/src/format.js), [format.test.js](../frontend/src/format.test.js) and [App.test.jsx](../frontend/src/App.test.jsx) | The two pure helpers, and the 37 tests. |

---

## Walkthrough

### 1. The state

Every `useState` call gives one value and its setter (see the concept box). There are twelve:

| State | Initial value | Changed by | Read by |
|-------|---------------|-----------|---------|
| `lang` | saved choice or `"en"` | language toggle [:243](../frontend/src/App.jsx#L243) | `t` [:135](../frontend/src/App.jsx#L135), the effect [:155-162](../frontend/src/App.jsx#L155-L162) |
| `pot` | `100000` | the pot `Stepper` [:265](../frontend/src/App.jsx#L265), presets [:272](../frontend/src/App.jsx#L272) | request body [:168](../frontend/src/App.jsx#L168), bet presets [:286](../frontend/src/App.jsx#L286) |
| `betSize` | `50000` | the bet `Stepper` [:283](../frontend/src/App.jsx#L283), presets [:292](../frontend/src/App.jsx#L292) | request body [:169](../frontend/src/App.jsx#L169), preset highlight [:291](../frontend/src/App.jsx#L291) |
| `hand` | `"As Kh Qd"` | typing [:364](../frontend/src/App.jsx#L364), presets [:374](../frontend/src/App.jsx#L374) | request body [:171](../frontend/src/App.jsx#L171), preset highlight [:373](../frontend/src/App.jsx#L373) |
| `foldEquity` | `0.35` | slider [:313](../frontend/src/App.jsx#L313) | request body, `35%` badge [:304](../frontend/src/App.jsx#L304), profit marker [:350](../frontend/src/App.jsx#L350) |
| `opponentModel` | `"range"` | model buttons [:331](../frontend/src/App.jsx#L331) | request body, `aria-pressed` [:330](../frontend/src/App.jsx#L330) |
| `isLoading` | `true` | `startSolve` [:200](../frontend/src/App.jsx#L200), callbacks [:178](../frontend/src/App.jsx#L178), [:185](../frontend/src/App.jsx#L185) | button label and `disabled` [:386-388](../frontend/src/App.jsx#L386-L388) |
| `isAiLoading` | `true` | `startSolve` [:201](../frontend/src/App.jsx#L201), callbacks [:186](../frontend/src/App.jsx#L186), [:190](../frontend/src/App.jsx#L190) | notes drawer [:589](../frontend/src/App.jsx#L589) |
| `solveData` | `null` | callbacks [:177](../frontend/src/App.jsx#L177), [:183](../frontend/src/App.jsx#L183) | derived values [:219-229](../frontend/src/App.jsx#L219-L229), top hands [:530](../frontend/src/App.jsx#L530) |
| `aiAdvice` | `null` | callbacks [:184](../frontend/src/App.jsx#L184), [:189](../frontend/src/App.jsx#L189) | notes drawer [:586](../frontend/src/App.jsx#L586), [:593](../frontend/src/App.jsx#L593) |
| `isNotesOpen` | `false` | drawer button [:575](../frontend/src/App.jsx#L575) | drawer [:577-581](../frontend/src/App.jsx#L577-L581) |
| `solveError` | `null` | `startSolve` [:202](../frontend/src/App.jsx#L202), callbacks [:176](../frontend/src/App.jsx#L176), [:182](../frontend/src/App.jsx#L182) | error box [:391-395](../frontend/src/App.jsx#L391-L395) |

The first six are **inputs**. The last six describe **what happened**. Results are never edited by
hand: they are replaced as a whole when an answer arrives. `isLoading` and `isAiLoading` start as
`true` because the first solve begins as soon as the page mounts (section 4).

One more value is not state: `currentRun = useRef(null)` ([:153](../frontend/src/App.jsx#L153))
holds the `AbortController` of the run in progress. Changing a ref does not re-render; it is a box
that survives between renders (see the concept box).

The language is loaded once and saved on every change:

📍 [`frontend/src/App.jsx:88-95`](../frontend/src/App.jsx#L88-L95)
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

`useState(loadSavedLang)` at [:134](../frontend/src/App.jsx#L134) passes the function itself, so React
calls it only on the first render. `localStorage` survives reloads but can throw (some private
modes), hence the `try/catch` here and in the effect at [:155-162](../frontend/src/App.jsx#L155-L162),
which also sets `<html lang>` for screen readers. An unknown saved value falls back to English.
`t = STRINGS[lang]` ([:135](../frontend/src/App.jsx#L135)) is the dictionary every label reads.

### 2. `fetchSolveAndAnalysis`, step 1: `/api/solve`

The round trip lives **outside** the component. It holds no state; it reports each step through
three callbacks and stops calling them as soon as its `signal` is aborted:

📍 [`frontend/src/App.jsx:107-133`](../frontend/src/App.jsx#L107-L133)
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
      if (!signal.aborted) onSolveFailed(solveErrorFor(errorBody));
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

📍 [`frontend/src/App.jsx:97-105`](../frontend/src/App.jsx#L97-L105)
```jsx
// Map a failed /api/solve response to the message shown under the button ({ key, detail }).
// The API answers every error with { error, code }. A response without a code did not come from
// Flask (e.g. the dev proxy's 502, or a 404 from the wrong server), so the solver isn't reachable.
function solveErrorFor(body) {
  if (!body.code) return { key: "solverOffline" };
  if (body.code === "invalid_hand") return { key: "invalidHand", detail: body.error };
  if (body.code === "invalid_params") return { key: "invalidParams", detail: body.error };
  return { key: "serverError" };
}
```

Every API error is `{"error": "...", "code": "..."}` (lesson 10), so the UI decides on the `code`
alone, never on the status, and shows the server's `error` only as the detail. No `code` means
something other than Flask answered. The two input codes get the server's detail; any other code
(`internal_error`, `not_found`, …) is the solver's fault, not the user's. The UI always sends all
five fields, so the backend's defaults never apply. Note `opponent_model`: the UI starts on
`"range"`, and so does the API ([app.py:321](../backend/app.py#L321)), so the same Q-K-A shows
**+131,876** in the UI and from a bare `curl`. Add `"opponent_model": "random"` to the curl body and
it shows **+132,101** instead (lesson 07).

### 3. Step 2: `/api/analyze`, and every way to fail

📍 [`frontend/src/App.jsx:135-150`](../frontend/src/App.jsx#L135-L150)
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
checks the body has exactly those five keys ([App.test.jsx:142-149](../frontend/src/App.test.jsx#L142-L149)).
`onSolved` has already run, so whatever happens to the analysis, the numbers stay on screen.

Every path below is covered by a test or was reproduced with `fetch` mocked; the backend texts are
the real ones:

| What happened | Caught at | State | Text shown (English) |
|---------------|-----------|-------|----------------------|
| Bad hand `As Xh Qd` → 400 `invalid_hand` | [:58-61](../frontend/src/App.jsx#L58-L61), [:43](../frontend/src/App.jsx#L43) | `solveError = {invalidHand, detail}`, old results cleared | Check your hand: Invalid card 'Xh': Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A. |
| Pot field emptied → `Number("")` is 0 → 400 `invalid_params` | [:44](../frontend/src/App.jsx#L44) | `{invalidParams, detail}` | Check your inputs: Pot and bet_size must be strictly greater than zero. |
| Server crash → 500 `internal_error` (or any other API code) | [:45](../frontend/src/App.jsx#L45) | `{serverError}` | The solver hit an internal error. Try again; if it keeps happening, check the backend log. |
| Flask down behind the dev proxy → 502, empty body | [:42](../frontend/src/App.jsx#L42) (no `code`) | `{solverOffline}` | Can't reach the solver. Start the backend on port 5000 and try again. |
| A web host that doesn't route `/api` answers with its own 404 page | [:42](../frontend/src/App.jsx#L42) (no `code`) | `{solverOffline}` | same |
| No HTTP answer at all, `fetch` throws | outer `catch` [:69-71](../frontend/src/App.jsx#L69-L71) | `{solverOffline}` | same |
| 200, but the body is not valid JSON | inner `catch` [:65-67](../frontend/src/App.jsx#L65-L67) | `{badResponse}` | The solver sent a response this page couldn't read. Try again. |
| Analyze answers 429 (rate limit) | [:93](../frontend/src/App.jsx#L93) | `aiAdvice = {aiRateLimited}` | Too many analysis requests. Wait a minute, then run the solver again. |
| Analyze answers another non-2xx (e.g. 502 `upstream_error`) | [:93](../frontend/src/App.jsx#L93) | `aiAdvice = {aiUnreachable}` | Couldn't reach the AI analysis service. The numbers above are unaffected. |
| Analyze answers 200 with empty `advice` | [:91](../frontend/src/App.jsx#L91) | `aiAdvice = {aiNoAdvice}` | The analysis came back empty. |
| Analyze request fails in transit | [:95-96](../frontend/src/App.jsx#L95-L96) | `aiAdvice = {aiTransportFault, detail}` | Analysis request failed: Failed to fetch |
| A newer run started, or the page unmounted | the `signal.aborted` checks | nothing changes | (the newer run's results) |

A failed solve also clears the old verdict, tables and notes (section 4), so nothing on screen
belongs to inputs other than the ones in the form. The status no longer decides anything: a 404 page
from a web host used to fall through to "Check your inputs: HTTP 404", and now reads "Can't reach the
solver" like the proxy's 502. That message's "port 5000" hint is only right in development (weak
spot 3).

### 4. Inside the component: starting, cancelling and the first run

The component's side of a run is three small functions. `runSolve` builds the body and turns each
callback into state changes:

📍 [`frontend/src/App.jsx:215-246`](../frontend/src/App.jsx#L215-L246)
```jsx
  // Start one run with the current inputs; every state change happens in a callback, after the
  // matching response has arrived. The API takes one opponent assumption: fold_equity. The
  // calling range the UI shows next to it is derived from that same number, never sent.
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

📍 [`frontend/src/App.jsx:247-256`](../frontend/src/App.jsx#L247-L256)
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
run" never appears ([App.test.jsx:151-172](../frontend/src/App.test.jsx#L151-L172)).

The first run starts on mount:

📍 [`frontend/src/App.jsx:258-277`](../frontend/src/App.jsx#L258-L277)
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
  const advice = handEval?.advice;
  const actionCounts = summary?.action_counts;

  const zones = handEval?.profitable_fold_zones;

```

- The effect solves once when the page opens, so the page is never empty. It sets no state itself
  (the loading flags already start `true`), and `useEffectEvent` (see the concept box) lets it read
  the current inputs without listing them as dependencies. That is what keeps `npm run lint` silent
  (lesson 12, section 6).
- Its cleanup aborts the run. In development StrictMode mounts twice, so the first run is
  cancelled; a test checks that ([App.test.jsx:174-182](../frontend/src/App.test.jsx#L174-L182)).
- **Derived values** are recomputed on every render instead of being stored in state, so they can
  never disagree with `solveData`. `?.` returns `undefined` while `solveData` is still `null`.
- `pct` is the one number the UI computes itself: it is a **string** (`"100.0"`), which is why the
  status column compares `Number(cat.pct) === 100` ([:509](../frontend/src/App.jsx#L509),
  [:518](../frontend/src/App.jsx#L518)).

### 5. From JSON to screen

With the UI defaults (pot 100,000, bet 50,000, 35% folds, `As Kh Qd`, range model), here is every
key of the `/api/solve` answer and where it ends up:

| JSON key | Example value | Shown as | Where |
|----------|---------------|----------|-------|
| `hand_evaluation.advice` | `{"action": "ALL_IN", "kind": "VALUE", "amount": 100000.0, …}` | the recommendation the card renders, with the ladder behind it | [:274](../frontend/src/App.jsx#L274) |
| `.hand` · `.canonical_id` · `.score_name` | `As Kh Qd` · `Q-K-A` · `Liêng Q-K-A` | the line under the verdict | [:425-429](../frontend/src/App.jsx#L425-L429) |
| `.ev` | `131876.0` | "+131,876 VND", and again in the summary | [:436](../frontend/src/App.jsx#L436), [:473-474](../frontend/src/App.jsx#L473-L474) |
| `.profitable_fold_zones` | `[[0.0, 1.0]]` | "…when the opponent folds 0%–100%", and the green bar | [:439](../frontend/src/App.jsx#L439), [:339-353](../frontend/src/App.jsx#L339-L353) |
| `.showdown_equity` | `0.9952` | "Showdown equity 99.5%" | [:460](../frontend/src/App.jsx#L460) |
| `.equity_vs_random` | `0.9969` | "…· 99.7% vs. a random hand" (range model only) | [:463-466](../frontend/src/App.jsx#L463-L466) |
| `summary.opponent_model`, `.fold_equity` | `"range"`, `0.35` | "vs. the top 65% that call" | [:463-464](../frontend/src/App.jsx#L463-L464) |
| `summary.range_coverage_percent` | `100.0` | "Range coverage 100.0%" | [:450](../frontend/src/App.jsx#L450) |
| `summary.profitable_combinations` | `22100` | "22,100 of 22,100 combos are +EV" | [:453](../frontend/src/App.jsx#L453) |
| `summary.pure_bluff_break_even_fold_equity` | `0.3333` | "Bluff break-even 33.3%" | [:482](../frontend/src/App.jsx#L482) |
| `summary.category_breakdown[]` | 4 rows | the coverage table | [:508-523](../frontend/src/App.jsx#L508-L523) |
| `top_hands[]` (30 sent) | `A-A-A` first | the first **10** rows of the second table, with `showdown_equity` as the equity column | [:550-563](../frontend/src/App.jsx#L550-L563) |

Sent but never read: in `hand_evaluation` `category`, `category_name`, `random_hand_equity`,
`is_profitable`, `break_even_fold_equity` and `profitable_from_fold_equity`; in `summary` `pot`,
`bet_size`, `final_pot`, `total_canonical_classes`, `profitable_classes`, `total_combinations`,
`bet_ladder`, `highest_ev_*` and `threshold_*`; and in `advice`, `robust`. The page renders
`advice.action`, `.kind`, `.amount`, `.reason`, `.why`, the three `ladder` rows, and `sizing` for
the numbers behind them, so the thresholds are read from the response instead of typed into the
page. The "of 22,100" is written into the translation
([i18n.js:55](../frontend/src/i18n.js#L55)) instead.

With an empty hand field, `hand_evaluation` is `null`: the verdict and profit map disappear, equity
shows `N/A`, and the summary and tables still show the whole-range results.

### 6. The left column: one `Stepper`, presets as data, and the profit map

The pot and the bet use the same small component:

📍 [`frontend/src/App.jsx:152-182`](../frontend/src/App.jsx#L152-L182)
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
  ([:265](../frontend/src/App.jsx#L265)) and the same for the bet ([:283](../frontend/src/App.jsx#L283)).
- The input is **controlled** (see the concept box). Minus stops at `MIN_AMOUNT` (1,000), plus has
  no upper limit, both by `AMOUNT_STEP` (10,000, [:11-13](../frontend/src/App.jsx#L11-L13)). A test
  clicks minus from 100,000 and from 5,000 ([App.test.jsx:119-131](../frontend/src/App.test.jsx#L119-L131)).
- `min` only affects the browser's own arrows, which CSS hides (lesson 14). Clearing the field gives
  `Number("")` = 0, and the server's 400 catches it (section 3).
- The buttons have an `aria-label` ("Current pot (VND) −10k"), and `<label htmlFor="pot-input">`
  ([:264](../frontend/src/App.jsx#L264)) links the label to the field. The tests find the buttons
  by exactly that name.

The presets are data at the top of the file:

📍 [`frontend/src/App.jsx:15-24`](../frontend/src/App.jsx#L15-L24)
```jsx
const POT_PRESETS = [50000, 100000, 200000, 500000];
const BET_PRESET_MULTIPLES = [0.33, 0.75, 1];
const HAND_PRESETS = [
  { cards: "As Kh Qd", labelKey: "presetLiengQKA" },
  { cards: "7s 7h 7d", labelKey: "presetSap7" },
  { cards: "Js Qh Kd", labelKey: "presetLiengJQK" },
  { cards: "9s 10h Kd", labelKey: "presetDiem9" },
  { cards: "2s 3h 5d", labelKey: "presetDiem0" },
];

```

The bet multiples are the policy's three rungs (0.33, 0.75 and the whole pot), so a preset can
never ask for a size the ladder does not price (lesson 07, section 8). A hand preset stores an
i18n **key**, not a label, so the text comes from `t[labelKey]`. A bet preset computes its amount
from the pot (`Math.round(pot * multiple)`), looks active only while the bet equals it exactly, and
gets its label from `t.betPresetLabel(...)` with the multiple formatted for the locale: "0.33x pot"
in English, "0,33x pot" in Vietnamese.

Each list becomes buttons with one `.map`: pot presets at [:325-337](../frontend/src/App.jsx#L325-L337),
bet presets right below them and hand presets further down. The model buttons form a `role="group"`
with `aria-pressed`, so assistive technology announces which one is on. Their text carries the fold
rate, `Folds weakest 35% first` and `Folds 35% regardless of hand`, so the chips and the numbers
below them always agree.

The profit map draws each zone with inline percentages:

📍 [`frontend/src/App.jsx:418-432`](../frontend/src/App.jsx#L418-L432)
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

All copy lives in [i18n.js](../frontend/src/i18n.js): `STRINGS.en` and `STRINGS.vi`, 104 keys each.
29 values are functions, 23 of which take a parameter (`betPresetLabel`, `invalidHand`,
`invalidParams`, `vsCallingRange`, `vsRandomShort`, `modelRange`, `modelRandom`, the two model
assumption lines, the advice reason lines), and six take none (`solverOffline`, `serverError`,
`badResponse`, `aiNoAdvice`, `aiUnreachable`, `aiRateLimited`). The solve errors sit together:

📍 [`frontend/src/i18n.js:40-44`](../frontend/src/i18n.js#L40-L44)
```js
    solverOffline: () => "Can't reach the solver. Start the backend on port 5000 and try again.",
    invalidHand: (detail) => `Check your hand: ${detail}`,
    invalidParams: (detail) => `Check your inputs: ${detail}`,
    serverError: () => "The solver hit an internal error. Try again; if it keeps happening, check the backend log.",
    badResponse: () => "The solver sent a response this page couldn't read. Try again.",
```

The render calls every message the same way:

📍 [`frontend/src/App.jsx:470-474`](../frontend/src/App.jsx#L470-L474)
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

The notes drawer shows the `model` the API reported in its header ([:586](../frontend/src/App.jsx#L586))
and `aiAdvice.text` if the server sent some (`??`), else a translated notice
([:593](../frontend/src/App.jsx#L593)). Without an API key the header says
`rule-based-solver-engine (OPENROUTER_API_KEY not configured)`, and the text is the Vietnamese
rule-based answer from `_fallback_advice` ([app.py:563](../backend/app.py#L563)), Markdown `**` and
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

📍 [`frontend/src/App.test.jsx:156-171`](../frontend/src/App.test.jsx#L156-L171)
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
parsed body and `signal`, so tests can check what was sent and what was aborted. The 31 App tests find
elements the way a user would (`getByRole("button", { name: "Run solver" })`, `findByRole("alert")`)
rather than by class name. 8 of the first 12 fail on the `App.jsx` that came before those fixes.

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
  case for medium hands (README: real players fold a mix). The API and the CLI start on `range` too, so
  one request gives the same numbers on all three surfaces.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: lint warnings on the mount effect.** It used to call `handleSolve()`, which set state
  synchronously and was missing from the dependency list. The effect now sets no state and calls a
  `useEffectEvent` ([App.jsx:206-217](../frontend/src/App.jsx#L206-L217)); `npm run lint` has 0
  warnings and fails on any new one (lesson 12).
- ✅ **Fixed: stale results after an error.** The verdict for the previous hand stayed next to the
  red box. `onSolveFailed` now clears `solveData` and `aiAdvice` ([:180-187](../frontend/src/App.jsx#L180-L187)).
  Pinned by "an invalid hand shows its message and clears the old verdict"
  ([App.test.jsx:80-94](../frontend/src/App.test.jsx#L80-L94)).
- ✅ **Fixed: misleading error labels.** A 500 used to read "Invalid input: HTTP 500", and a garbled
  200 "Can't reach the solver". `solveErrorFor` ([:38-46](../frontend/src/App.jsx#L38-L46)) and the
  inner `try` now give each case its own message. Pinned by the table test, whose first three rows
  are the network failure, the 500 and the proxy's 502
  ([App.test.jsx:96-106](../frontend/src/App.test.jsx#L96-L106)).
- ✅ **Fixed: stacked prefixes.** "Invalid input: Invalid hand: Invalid rank 'X'…" had three
  authors. The API now sends the evaluator's message as is with `code: "invalid_hand"`
  ([app.py:205-206](../backend/app.py#L205-L206)) and the UI adds one prefix. Pinned by the exact
  text checked at [App.test.jsx:92](../frontend/src/App.test.jsx#L92).
- ✅ **Fixed: a hard-coded model label.** The notes header always said "OpenRouter · Llama 3.1 8B
  Instruct", even for the rule-based fallback. It now shows the `model` field
  ([:586](../frontend/src/App.jsx#L586)). Pinned by "the notes show the model the API reports"
  ([App.test.jsx:133-140](../frontend/src/App.test.jsx#L133-L140)).
- ✅ **Fixed: a late analysis could overwrite a newer one.** Each run has its own `AbortController`
  ([:195-204](../frontend/src/App.jsx#L195-L204)). Pinned by [App.test.jsx:151-172](../frontend/src/App.test.jsx#L151-L172).
- ✅ **Fixed: copy-pasted presets.** Five hand buttons, three bet buttons and two steppers were
  hand-written blocks. They are now data plus `.map` ([:15-23](../frontend/src/App.jsx#L15-L23)) and one
  `Stepper` ([:101-131](../frontend/src/App.jsx#L101-L131)).
- ✅ **Fixed: unused translation keys.** `liveSolver`, `classesLoaded`, `matrixId` and `topHandsId`
  were deleted from both languages (the 🧪 script below now finds none).
- ✅ **Fixed: most strings outside `i18n.js`.** The bet preset labels, hand preset labels and `VND`
  are keys now (`betPresetLabel`, `preset*`, `currency`, [i18n.js:31-37](../frontend/src/i18n.js#L31-L37)).
- ✅ **Fixed: a wrong footnote and subtitle.** "Monte Carlo" became "Exact enumeration, 455 canonical
  classes" ([i18n.js:42](../frontend/src/i18n.js#L42)) and "GTO solver" became "Expected-value
  solver" ([i18n.js:8](../frontend/src/i18n.js#L8)).
- ✅ **Fixed: the Vite proxy was unused** (lesson 12).
- ✅ **Fixed: a 4xx without a `code` was called an input problem.** Only the 5xx branch used to check
  for a `code`, so a 404 or 405 from something that isn't the API read "Check your inputs: HTTP 404".
  `solveErrorFor` now takes only the body: no `code` → `solverOffline` ([:42](../frontend/src/App.jsx#L42)),
  the two input codes → their messages, any other code → `serverError` ([:43-45](../frontend/src/App.jsx#L43-L45)).
  Pinned by two new table rows: a bare 404 shows "Can't reach the solver", and a 404 carrying the
  API's `not_found` code shows the internal-error message ([App.test.jsx:100-101](../frontend/src/App.test.jsx#L100-L101)).
- ✅ **Fixed: "GTO" in the notes.** The offline answer's third heading was "GTO Insight", which
  DESIGN.md §6 rules out ([DESIGN.md:88](../DESIGN.md#L88)). It is now "Nhận định chiến thuật"
  ([app.py:588](../backend/app.py#L588)), and the LLM prompt asks for "[Lời khuyên chiến thuật]"
  instead of "[Lời khuyên GTO]" ([app.py:559](../backend/app.py#L559)). No test pins the wording.

Still open:

1. **Raw Markdown, in one language.** The notes ([:593](../frontend/src/App.jsx#L593)) show the
   analysis, `**bold**` markers included, as plain text, in Vietnamese for both languages (the
   offline answer is built by `_fallback_advice`, [app.py:563-591](../backend/app.py#L563-L591)).
   *Fix:* render the bold markers (exercise 8); ask the backend for the UI's language.
2. **The server's detail stays English.** In Vietnamese mode the prefix is translated but "Invalid
   card 'Xh': …" is not. *Fix:* translate per `code` and drop the detail for codes the UI fully
   understands, or let the API take a language.
3. **"Can't reach the solver" gives a development hint everywhere.** Every response without a `code`
   ends in `solverOffline` ([:42](../frontend/src/App.jsx#L42)), whose text says "Start the backend
   on port 5000". That fits the dev proxy's 502, but not a production host answering `/api` with its
   own 404 page, where the backend may be running fine and the routing is what's wrong. *Fix:*
   exercise 6.
4. **A few strings still bypass `i18n.js`.** The `k` in the pot presets ([:274](../frontend/src/App.jsx#L274))
   and in the stepper labels ([:107](../frontend/src/App.jsx#L107), [:124](../frontend/src/App.jsx#L124)).
   *Fix:* exercise 7.
5. ✅ **Fixed: two defaults for one setting.** The UI started on `"range"` while the API defaulted to
   `"random"` ([app.py:321](../backend/app.py#L321)), so the same request without the field showed
   +131,876 in the UI and +132,101 from `curl`. Version 3.1.0 made `range` the default on both sides,
   so the two now agree; `"opponent_model": "random"` still gives the +132,101 numbers.

---

## 🧪 Try it

Run from `frontend/`.

```bash
npm test 2>&1 | grep -E 'Test Files|Tests '
```

```
 Test Files  3 passed (3)
      Tests  37 passed (37)
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
([app.py:205-206](../backend/app.py#L205-L206)); the rest is the evaluator's message
([evaluator.py:437](../backend/src/evaluator.py#L437)). The verdict disappears, because
`onSolveFailed` clears `solveData`.
</details>

**🟢 2. Predict.** You click **Folds 35% regardless of hand** and run the solver with the other
defaults. Which summary rows change, and to what?

<details><summary>Solution</summary>

Showdown equity becomes **99.7%** with the note "vs. a random hand"
([:463-467](../frontend/src/App.jsx#L463-L467)), and EV becomes **+132,101** in the verdict and in
its row. Coverage (100.0%) and bluff break-even (33.3%) stay: at a half-pot bet with 35% folds,
every hand is +EV under both models.
</details>

**🟢 3. Predict.** What do `formatMoney(-27894.5, "en-US")` and `formatZones([[1, 1]])` return?
Check with `node --input-type=module -e '…'` as in 🧪.

<details><summary>Solution</summary>

`"-27,894"`, because `Math.round` rounds halves toward +∞. And `"100%"`, because a zone with
`start === end` is printed once ([format.test.js:21](../frontend/src/format.test.js#L21)).
</details>

**🟡 4. Break the parity test.** Delete `statusZero: "Bỏ bài",` from the Vietnamese dictionary
([i18n.js:243](../frontend/src/i18n.js#L243)) and run `npm test`. What does the failure tell you?

<details><summary>Solution</summary>

```
 Test Files  1 failed | 2 passed (3)
      Tests  1 failed | 36 passed (37)
```

"every language defines exactly the English keys" fails with
`AssertionError: language "vi"` and a diff containing `-   "statusZero": "string",`: English has the
key and Vietnamese does not. Without the test, `t.statusZero` would be `undefined`, which React
renders as nothing: the status chip is empty for every category with no profitable combo, in
Vietnamese. The App tests don't notice, because they run in English. Undo with
`git checkout -- frontend/src/i18n.js`.
</details>

**🟡 5. Break the error mapping.** In `solveErrorFor`, change the last line
([:45](../frontend/src/App.jsx#L45)) to `return { key: "solverOffline" };`, so that every API error
that isn't about the input means "offline". Predict which tests fail and what they print, then run
`npm test`.

<details><summary>Solution</summary>

Two: "a server error shows the matching message" and "an API error that isn't about the input shows
the matching message" (`Tests  2 failed | 18 passed (20)`). Both expected the alert to contain
`internal error` and received `Can't reach the solver. Start the backend on port 5000 and try
again.` That is the old mislabelling: a crash inside Flask sent the user looking for a server that
was running. The 502 and bare-404 rows still pass, because they really did not come from Flask.
Undo with `git checkout -- frontend/src/App.jsx`.
</details>

**🟡 6. Tell "wrong server" from "offline".** Weak spot 3: a production host's own 404 page reads
"Can't reach the solver. Start the backend on port 5000". Make a response without a `code` show a
new message, "Something other than the solver answered (HTTP 404). Check that /api reaches the
backend.", except for 502, 503 and 504, which a proxy sends when it can't reach the backend. Write
the test first: in the table at [App.test.jsx:96-106](../frontend/src/App.test.jsx#L96-L106), make
the bare-404 row expect `"Something other than the solver answered (HTTP 404)"`. See it fail, then
make all 37 tests pass.

<details><summary>Solution</summary>

Before the change the row fails with `Received: Can't reach the solver. Start the backend on port
5000 and try again.` (`Tests  1 failed | 19 passed (20)`). `solveErrorFor` needs the status back
for this one decision:

```jsx
function solveErrorFor(status, body) {
  if (!body.code) return status >= 502 && status <= 504 ? { key: "solverOffline" } : { key: "notSolver", detail: `HTTP ${status}` };
  // … the three lines for codes stay as they are
}
```

and the call at [:60](../frontend/src/App.jsx#L60) becomes `solveErrorFor(solveRes.status, errorBody)`.
Add the message to both languages in `i18n.js`, next to `solverOffline`:

```js
    notSolver: (detail) => `Something other than the solver answered (${detail}). Check that /api reaches the backend.`,
    notSolver: (detail) => `Một máy chủ khác đã trả lời thay bộ giải (${detail}). Kiểm tra /api có dẫn tới backend không.`,
```

(the first line in `en`, the second in `vi`). All 37 tests pass and `npm run lint` stays silent. Skip
the Vietnamese line and the parity test fails instead. Undo with
`git checkout -- frontend/src/App.jsx frontend/src/App.test.jsx frontend/src/i18n.js`.
</details>

**🔴 7. The last `k`s.** Move the thousands suffix into `i18n.js` (both languages, one function
such as `thousands: (n) => \`${n}k\``), and use it for the pot presets
([:274](../frontend/src/App.jsx#L274)) and the stepper labels. Check: `npm test` and `npm run lint`
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

and at [:593](../frontend/src/App.jsx#L593):

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

21 tests pass and lint stays silent. Undo with
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
2. The `if (!solveRes.ok)` branch at [:58](../frontend/src/App.jsx#L58), which hands the body to
   `solveErrorFor`. `fetch` throws only when no HTTP response arrives. A 400 is a normal
   response with `ok === false`.
3. An abort only rejects what is still pending. If a response arrived just before the abort, the
   `await` resumes normally, and without the check the old run would call its callbacks and
   overwrite the newer run's state. And when the abort does reject, the `catch` blocks would report
   it as `solverOffline` or `aiTransportFault`; the checks keep those quiet too.
4. The marker reads `foldEquity` state directly ([:350](../frontend/src/App.jsx#L350)). The zones
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
- Each API error `code` maps to one i18n message; the server's text is only the detail. A response
  without a code, whatever its status, did not come from Flask and reads "Can't reach the solver".
- Everything the UI shows comes from the server (the map in section 5). 15 of the 29 summary and
  evaluation fields are sent but unused.
- Copy lives in `i18n.js` as two 84-key dictionaries. `format.js` holds the pure helpers.
  `i18n.test.js` compares the dictionaries' *shapes*, and `App.test.jsx` drives the real component
  with `fetch` mocked.

**Next:** [14 — Styling and DESIGN.md](14-styling.md)
