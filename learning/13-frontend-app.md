# Lesson 13 — The React app

> **Goal:** read `App.jsx` from top to bottom: its state, the two-step fetch and every error path,
> how each JSON key becomes something on screen, and how `i18n.js` and `format.js` keep text and
> number formatting out of the component.
> **Files:** [`frontend/src/App.jsx`](../frontend/src/App.jsx), [`i18n.js`](../frontend/src/i18n.js),
> [`format.js`](../frontend/src/format.js), [`i18n.test.js`](../frontend/src/i18n.test.js),
> [`format.test.js`](../frontend/src/format.test.js).
> **Time:** ~75 min. **Before this:** [12 — Frontend tooling](12-frontend-tooling.md).

---

## Where this fits

```
                       ┌──────────────── App.jsx (this lesson) ────────────────┐
  click, type, drag ──►│ 12 useState values ──► derived values ──► JSX render  │──► what you see
                       │        ▲                                     │        │
                       │        └──── setters ◄── handleSolve ◄───────┘        │
                       └────────────────────────────┬──────────────────────────┘
       i18n.js: t = STRINGS[lang]                    │ POST /api/solve, then POST /api/analyze
       format.js: formatMoney, formatZones           ▼
                                               app.py (lessons 10–11)
```

The whole UI is one component, `App`, in one 608-line file. It keeps the inputs and the last answer
in state, sends two requests per "Run solver", and draws everything from the answer. The EV, zones
and category counts all come from the backend. Its own jobs are input, errors, translation and formatting.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [App.jsx:1-20](../frontend/src/App.jsx#L1-L20) | Imports, `API_BASE`, label maps, `loadSavedLang`. |
| 2 | [App.jsx:22-48](../frontend/src/App.jsx#L22-L48) | All state, and the effect that saves the language. |
| 3 | [App.jsx:50-114](../frontend/src/App.jsx#L50-L114) | `handleSolve`: two fetches, five ways to fail. |
| 4 | [App.jsx:116-131](../frontend/src/App.jsx#L116-L131) | The mount effect and the derived values. |
| 5 | [App.jsx:164-402](../frontend/src/App.jsx#L164-L402) | The left column: steppers, presets, slider, model toggle, profit map. |
| 6 | [App.jsx:405-604](../frontend/src/App.jsx#L405-L604) | The right column: verdict, summary rows, two tables, notes. |
| 7 | [i18n.js](../frontend/src/i18n.js) and [i18n.test.js](../frontend/src/i18n.test.js) | Two dictionaries with the same 77 keys, and the test that enforces it. |
| 8 | [format.js](../frontend/src/format.js) and [format.test.js](../frontend/src/format.test.js) | The two pure helpers and their 4 tests. |

---

## Walkthrough

### 1. The state

Every `useState` call gives one value and its setter (see the concept box). There are twelve:

| State | Initial value | Changed by | Read by |
|-------|---------------|-----------|---------|
| `lang` | saved choice or `"en"` | language toggle [:148](../frontend/src/App.jsx#L148) | `t` [:24](../frontend/src/App.jsx#L24), the effect [:41-48](../frontend/src/App.jsx#L41-L48) |
| `pot` | `100000` | − / + [:176](../frontend/src/App.jsx#L176), [:193](../frontend/src/App.jsx#L193), typing [:185](../frontend/src/App.jsx#L185), presets [:204](../frontend/src/App.jsx#L204) | request bodies, bet presets |
| `betSize` | `50000` | − / + [:219](../frontend/src/App.jsx#L219), [:236](../frontend/src/App.jsx#L236), typing [:228](../frontend/src/App.jsx#L228), presets [:245-259](../frontend/src/App.jsx#L245-L259) | request bodies |
| `hand` | `"As Kh Qd"` | typing [:329](../frontend/src/App.jsx#L329), presets [:337-365](../frontend/src/App.jsx#L337-L365) | request bodies, preset highlight |
| `foldEquity` | `0.35` | slider [:278](../frontend/src/App.jsx#L278) | request bodies, `35%` badge [:269](../frontend/src/App.jsx#L269), profit marker [:315](../frontend/src/App.jsx#L315) |
| `opponentModel` | `"range"` | model buttons [:296](../frontend/src/App.jsx#L296) | request bodies, `aria-pressed` [:295](../frontend/src/App.jsx#L295) |
| `isLoading` | `false` | `handleSolve` | button label and `disabled` [:376-378](../frontend/src/App.jsx#L376-L378) |
| `isAiLoading` | `false` | `handleSolve` | notes drawer [:594](../frontend/src/App.jsx#L594) |
| `solveData` | `null` | `handleSolve` [:79](../frontend/src/App.jsx#L79) | derived values [:121-131](../frontend/src/App.jsx#L121-L131), top hands [:533](../frontend/src/App.jsx#L533) |
| `aiAdvice` | `null` | `handleSolve` [:100-105](../frontend/src/App.jsx#L100-L105) | notes drawer [:598](../frontend/src/App.jsx#L598) |
| `isNotesOpen` | `false` | drawer button [:581](../frontend/src/App.jsx#L581) | drawer [:583-587](../frontend/src/App.jsx#L583-L587) |
| `solveError` | `null` | `handleSolve` [:53](../frontend/src/App.jsx#L53), [:72](../frontend/src/App.jsx#L72), [:110](../frontend/src/App.jsx#L110) | error box [:381-385](../frontend/src/App.jsx#L381-L385) |

The first six are **inputs**. The last six describe **what happened**. Results are never edited by
hand: they are replaced as a whole when an answer arrives.

The language is loaded once and saved on every change:

📍 [`frontend/src/App.jsx:13-20`](../frontend/src/App.jsx#L13-L20)
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

`useState(loadSavedLang)` at [:23](../frontend/src/App.jsx#L23) passes the function itself, so React
calls it only on the first render. `localStorage` survives reloads but can throw (some private
modes), hence the `try/catch` here and in the effect at [:41-48](../frontend/src/App.jsx#L41-L48),
which also sets `<html lang>` for screen readers. An unknown saved value falls back to English.
`t = STRINGS[lang]` ([:24](../frontend/src/App.jsx#L24)) is the dictionary every label reads.

### 2. `handleSolve`, step 1: `/api/solve`

`handleSolve` starts by setting `isLoading` and `isAiLoading` to `true` and clearing `solveError`
([:51-53](../frontend/src/App.jsx#L51-L53)). Then:

📍 [`frontend/src/App.jsx:56-67`](../frontend/src/App.jsx#L56-L67)
```jsx
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
```

The body always sends all five fields, so the backend's defaults (lesson 10) never apply. Note
`opponent_model`: the UI starts on `"range"`, while the API defaults to `"random"`
([app.py:67](../backend/app.py#L67)). That is why the same Q-K-A shows **+131,876** in the UI but
**+132,097** from a bare `curl` (lesson 07).

📍 [`frontend/src/App.jsx:69-80`](../frontend/src/App.jsx#L69-L80)
```jsx
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

`fetch` only throws when no HTTP answer arrives at all. A 400 is a normal response with
`ok === false`, so it needs this explicit check. The error is stored as a **key plus a detail**, not
as a sentence (section 7). As soon as the numbers are in, `isLoading` goes false and the page
renders them. The analysis has not been requested yet.

### 3. Step 2: `/api/analyze`, and every way to fail

Lines [:83-96](../frontend/src/App.jsx#L83-L96) send the same five fields plus the
`hand_evaluation` and `range_coverage_percent` from step 1. Then:

📍 [`frontend/src/App.jsx:98-113`](../frontend/src/App.jsx#L98-L113)
```jsx
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
```

The inner `try` protects the numbers: whatever happens to the analysis, step 1's results stay on
screen. Every path below was reproduced in a headless browser against the running app (the failing
requests were simulated):

| What happened | Caught at | State | Text shown (English) |
|---------------|-----------|-------|----------------------|
| Bad hand `As Xh Qd` → 400 | [:69-72](../frontend/src/App.jsx#L69-L72) | `solveError = {invalidInput, detail}` | Invalid input: Invalid hand: Invalid rank 'X'. Must be 2-10, T, J, Q, K, or A. |
| Pot field emptied → `Number("")` is 0 → 400 | same | same | Invalid input: Pot and bet_size must be strictly greater than zero. |
| Server crash, 500 with an HTML body | same; `.json()` fails, so `detail` = `HTTP 500` | same | Invalid input: HTTP 500 |
| Flask not running, `fetch` throws | outer `catch` [:109-110](../frontend/src/App.jsx#L109-L110) | `solveError = {solverOffline}` | Can't reach the solver. Start the backend on port 5000 and try again. |
| 200, but the body is not valid JSON | outer `catch` too | same | Can't reach the solver. … |
| Analyze returns non-2xx (e.g. 502) | [:101-102](../frontend/src/App.jsx#L101-L102) | `aiAdvice = {aiUnreachable}` | Couldn't reach the AI analysis service. The numbers above are unaffected. |
| Analyze returns 200 with empty `advice` | [:100](../frontend/src/App.jsx#L100) | `aiAdvice = {aiNoAdvice}` | The analysis came back empty. |
| Analyze request fails in transit | [:104-105](../frontend/src/App.jsx#L104-L105) | `aiAdvice = {aiTransportFault, detail}` | Analysis request failed: Failed to fetch |

Two rows are mislabelled: a 500 is reported as *invalid input*, and a garbled 200 as *offline*. And
after any input error the old results stay: the verdict still says "Raise / all-in" for `As Kh Qd`
next to the red box (weak spot 2, exercise 5).

### 4. The mount effect and derived values

📍 [`frontend/src/App.jsx:116-131`](../frontend/src/App.jsx#L116-L131)
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

- The effect solves once when the page opens, so the page is never empty. In development it runs
  twice (StrictMode, lesson 12).
- **Derived values** are recomputed on every render instead of being stored in state, so they can
  never disagree with `solveData`. `?.` returns `undefined` while `solveData` is still `null`.
- `pct` is the one number the UI computes itself: it is a **string** (`"100.0"`), which is why the
  status column compares `Number(cat.pct) === 100` ([:511](../frontend/src/App.jsx#L511)).

`npm run lint` warns twice about line 118. **`exhaustive-deps`:** the effect uses `handleSolve` but
lists no dependencies (on purpose, to run once, but the linter cannot know). **`set-state-in-effect`:**
`handleSolve` sets state synchronously inside the effect, forcing an extra render. Exercise 8 fixes both.

### 5. From JSON to screen

With the UI defaults (pot 100,000, bet 50,000, 35% folds, `As Kh Qd`, range model), here is every
key of the `/api/solve` answer and where it ends up:

| JSON key | Example value | Shown as | Where |
|----------|---------------|----------|-------|
| `hand_evaluation.decision` | `"RAISE"` | "Raise / all-in", green (red for `CHECK/FOLD`) | [:123](../frontend/src/App.jsx#L123), [:408-413](../frontend/src/App.jsx#L408-L413) |
| `.hand` · `.canonical_id` · `.score_name` | `As Kh Qd` · `Q-K-A` · `Liêng Q-K-A` | the line under the verdict | [:415-419](../frontend/src/App.jsx#L415-L419) |
| `.ev` | `131876.0` | "+131,876 VND", and again in the summary | [:426](../frontend/src/App.jsx#L426), [:463-464](../frontend/src/App.jsx#L463-L464) |
| `.profitable_fold_zones` | `[[0.0, 1.0]]` | "…when the opponent folds 0%–100%", and the green bar | [:429](../frontend/src/App.jsx#L429), [:304-318](../frontend/src/App.jsx#L304-L318) |
| `.showdown_equity` | `0.9952` | "Showdown equity 99.5%" | [:450](../frontend/src/App.jsx#L450) |
| `.equity_vs_random` | `0.9969` | "…· 99.7% vs. a random hand" (range model only) | [:453-456](../frontend/src/App.jsx#L453-L456) |
| `summary.opponent_model`, `.fold_equity` | `"range"`, `0.35` | "vs. the top 65% that call" | [:453-454](../frontend/src/App.jsx#L453-L454) |
| `summary.range_coverage_percent` | `100.0` | "Range coverage 100.0%"; also sent to `/api/analyze` | [:440](../frontend/src/App.jsx#L440), [:94](../frontend/src/App.jsx#L94) |
| `summary.profitable_combinations` | `22100` | "22,100 of 22,100 combos are +EV" | [:443](../frontend/src/App.jsx#L443) |
| `summary.pure_bluff_break_even_fold_equity` | `0.3333` | "Bluff break-even 33.3%" | [:472](../frontend/src/App.jsx#L472) |
| `summary.category_breakdown[]` | 4 rows | the coverage table | [:498-526](../frontend/src/App.jsx#L498-L526) |
| `top_hands[]` (30 sent) | `A-A-A` first | the first **10** rows of the second table | [:552-566](../frontend/src/App.jsx#L552-L566) |

Sent but never read: `hand_evaluation.category`, `.category_name`, `.is_profitable`,
`.break_even_fold_equity`, `.profitable_from_fold_equity`, and in `summary` `pot`, `bet_size`, `final_pot`,
`total_canonical_classes`, `profitable_classes`, `total_combinations`, `highest_ev_*` and `threshold_*`.
The "of 22,100" is written into the translation ([i18n.js:43](../frontend/src/i18n.js#L43)) instead.

With an empty hand field, `hand_evaluation` is `null`: the verdict and profit map disappear, equity
shows `N/A`, and the summary and tables still show the whole-range results.

### 6. The left column: steppers, presets and the profit map

The pot field sits between two buttons: "−" calls `setPot((v) => Math.max(1000, v - 10000))`
([:176](../frontend/src/App.jsx#L176)) and "+" calls `setPot((v) => v + 10000)`
([:193](../frontend/src/App.jsx#L193)). The field itself:

📍 [`frontend/src/App.jsx:180-188`](../frontend/src/App.jsx#L180-L188)
```jsx
              <input
                id="pot-input"
                type="number"
                className="input-field"
                value={pot}
                onChange={(e) => setPot(Number(e.target.value))}
                step="10000"
                min="1000"
              />
```

- The input is **controlled** (see the concept box). `setPot((v) => …)` is the **updater form**:
  React passes the latest value. Minus stops at 1,000, and plus has no upper limit.
- `min="1000"` only affects the browser's own arrows, which CSS hides (lesson 14). Clearing the
  field gives `Number("")` = 0, and the server's 400 catches it (section 3).
- The buttons have an `aria-label` ("Current pot (VND) −10k"), and `htmlFor="pot-input"`
  ([:170](../frontend/src/App.jsx#L170)) links the label to the field.

The bet block ([:212-264](../frontend/src/App.jsx#L212-L264)) repeats the stepper. Its three presets
are hand-written buttons computed from the pot (`Math.round(pot * 0.5)`, `pot`, `pot * 2`), and one
looks active only while the bet equals it exactly. The pot presets use `.map` over
`[50000, 100000, 200000, 500000]` ([:199-208](../frontend/src/App.jsx#L199-L208)). The five hand
presets ([:334-368](../frontend/src/App.jsx#L334-L368)) are copy-pasted blocks (exercise 6). The model
buttons ([:289-301](../frontend/src/App.jsx#L289-L301)) form a `role="group"` with `aria-pressed`, so
assistive technology announces which one is on.

The profit map draws each zone with inline percentages:

📍 [`frontend/src/App.jsx:304-318`](../frontend/src/App.jsx#L304-L318)
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

### 7. Translations: one way to call every message

All copy lives in [i18n.js](../frontend/src/i18n.js): `STRINGS.en` and `STRINGS.vi`, 77 keys each.
Seven values are functions. Four take a parameter (`invalidInput`, `vsCallingRange`,
`vsRandomShort`, `aiTransportFault`) and three take none (`solverOffline`, `aiNoAdvice`, `aiUnreachable`):

📍 [`frontend/src/i18n.js:26-27`](../frontend/src/i18n.js#L26-L27)
```js
    solverOffline: () => "Can't reach the solver. Start the backend on port 5000 and try again.",
    invalidInput: (detail) => `Invalid input: ${detail}`,
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
   "Dữ liệu không hợp lệ: Invalid hand: Invalid rank 'X'. …". The server's part stays English.

The notes drawer ([:598](../frontend/src/App.jsx#L598)) shows `aiAdvice.text` if the server sent
some (`??`), else a translated notice. Without an API key that text is the Vietnamese rule-based
answer from [app.py:369](../backend/app.py#L369), Markdown `**` and all, in both languages.

### 8. `format.js` and the two test files

📍 [`frontend/src/format.js:1-11`](../frontend/src/format.js#L1-L11)
```js
// Pure formatting helpers, kept outside React so they can be unit-tested with `node --test`.

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
other file checks the dictionaries:

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

`shape` turns `{ fold: "Fold", invalidInput: (d) => … }` into `{ fold: "string", invalidInput:
"function" }`, so one `deepEqual` catches a missing key, an extra key, and a string where a function
belongs. Comparing shapes instead of values lets the wording differ freely. The second test
([:15-23](../frontend/src/i18n.test.js#L15-L23)) calls every function that takes a parameter with
`"DETAIL-123"` and checks the result contains it, which catches a translation that forgets
`${detail}`. Neither test can see a key that no code uses.

---

## 💡 Concept: `useState` and `useEffect`

```jsx
const [pot, setPot] = useState(100000);  // value + setter; calling setPot re-runs App() with the new value
useEffect(() => { … }, [lang]);          // run after a render in which lang changed
useEffect(() => { … }, []);              // run once, after the first render
```

`App` is a function that React calls again whenever state changes. Local variables (`t`, `handEval`)
are recalculated each time; only `useState` values survive between calls. Assigning to state
directly does nothing on screen. Hooks must run in the same order on every render (lesson 12).

## 💡 Concept: controlled inputs

`<input value={hand} onChange={(e) => setHand(e.target.value)} />`: the state is the single source
of truth, and the input only displays it. So a preset button that calls `setHand("7s 7h 7d")` updates
the text field with no extra code. For `type="number"`, `e.target.value` is still a **string**
(`""` when empty or invalid), which is why the code wraps it in `Number(…)`.

## 💡 Concept: `async` / `await` and `fetch`

`fetch(url, options)` returns a **Promise**, a value that arrives later. Inside an `async` function,
`await` pauses until it arrives, like a blocking call in Python, but without freezing the page.
`fetch` rejects (throws) only on network failure. Any HTTP status, even 500, counts as a response, so
you check `res.ok` (true for 200–299). `await res.json()` reads and parses the body, and throws if it
is not JSON. `JSON.stringify(obj)` is `json.dumps`.

---

## Design decisions

- **One component.** Easy to search, no props to thread through. The cost: a 608-line function
  whose parts cannot be tested or reused separately.
- **The backend computes, the frontend formats.** An earlier version guessed the per-category counts
  in the browser and got Đĩ wrong. Now `category_breakdown` comes from the server.
- **Numbers first, analysis second.** The analysis has its own `try`, so a slow or failing LLM never
  delays or hides the EV.
- **Keys in state, text at render time.** Errors and notices survive a language switch.
- **Pure helpers in `.js` files**, so that `node --test` can test them (lesson 12).
- **The range model by default.** The UI assumes the opponent folds their weakest hands, the stricter
  case for medium hands (README: real players sit between the two). The API defaults to `random`.

---

## ⚠️ Weak spots

1. **Lint warnings on the mount effect.** [App.jsx:117-119](../frontend/src/App.jsx#L117-L119)
   triggers `set-state-in-effect` and `exhaustive-deps`. *Fix:* exercise 8.
2. **Stale results after an error.** [App.jsx:69-76](../frontend/src/App.jsx#L69-L76) sets the error
   but keeps `solveData` and `aiAdvice`, so the old verdict sits next to "Invalid input". *Fix:*
   clear both (exercise 5).
3. **Misleading error labels.** Any non-2xx, even a 500, becomes "Invalid input: HTTP 500"
   ([:72](../frontend/src/App.jsx#L72)), and any exception in step 1, even a JSON parse error,
   becomes "Can't reach the solver" ([:110](../frontend/src/App.jsx#L110)). *Fix:* branch on
   `status >= 500`, and only treat a `TypeError` from `fetch` as offline.
4. **Stacked prefixes.** [i18n.js:27](../frontend/src/i18n.js#L27) adds "Invalid input: ",
   [app.py:177](../backend/app.py#L177) adds "Invalid hand: ", then comes the evaluator's message
   ([evaluator.py:107](../backend/src/evaluator.py#L107)). In Vietnamese, only the first prefix is
   translated. *Fix:* the server returns an error code and the UI owns the wording.
5. **A hard-coded model label.** [App.jsx:591](../frontend/src/App.jsx#L591) always says
   "OpenRouter · Llama 3.1 8B Instruct", even when the backend used its rule-based fallback and said
   so in the `model` field. *Fix:* exercise 7.
6. **Raw Markdown in the notes.** [App.jsx:598](../frontend/src/App.jsx#L598) shows the analysis,
   `**bold**` markers included, as plain text ([App.css:595](../frontend/src/App.css#L595)), in
   Vietnamese for both languages. The `advice` of a 502 ([app.py:434](../backend/app.py#L434)) is dropped.
7. **Copy-pasted presets.** Five hand buttons ([:334-368](../frontend/src/App.jsx#L334-L368)) and three
   bet buttons ([:242-262](../frontend/src/App.jsx#L242-L262)) differ only in their data. *Fix:* an
   array and `.map` (exercise 6).
8. **Unused translation keys.** `liveSolver`, `classesLoaded` ([i18n.js:9-10](../frontend/src/i18n.js#L9-L10)),
   `matrixId` ([:55](../frontend/src/i18n.js#L55)) and `topHandsId` ([:72](../frontend/src/i18n.js#L72)),
   in both languages, are leftovers from the old design. The parity test cannot notice them.
9. **Strings outside `i18n.js`.** `"0.5x Pot"` … `"2.0x Pot"` ([:247-261](../frontend/src/App.jsx#L247-L261)),
   the `k` suffix ([:206](../frontend/src/App.jsx#L206)) and `VND` ([:426](../frontend/src/App.jsx#L426),
   [:560](../frontend/src/App.jsx#L560)) break DESIGN.md §6: "All UI strings live in `i18n.js`".
10. **Two defaults for one setting.** The UI starts on `"range"` ([:30](../frontend/src/App.jsx#L30))
    and the API defaults to `"random"` ([app.py:67](../backend/app.py#L67)): +131,876 versus +132,097
    for the same request without the field.
11. **A wrong footnote.** "Monte Carlo, canonical classes" ([i18n.js:30](../frontend/src/i18n.js#L30))
    is shown under the button, but the win rates are computed exactly (lesson 04).
12. **The Vite proxy is unused** because of [App.jsx:6](../frontend/src/App.jsx#L6) (lesson 12).

---

## 🧪 Try it

Run from `frontend/`.

```bash
npm test 2>&1 | grep -E '^# (tests|pass|fail)'
```

```
# tests 6
# pass 6
# fail 0
```

Call the helpers yourself, and list the translation keys that `App.jsx` never mentions:

```bash
node --input-type=module -e '
import { formatMoney, formatZones } from "./src/format.js";
import { STRINGS } from "./src/i18n.js";
import fs from "node:fs";
console.log(formatMoney(131876, "en-US"), formatMoney(131876, "vi-VN"), formatZones([[0, 0.08], [0.51, 1]]));
console.log(STRINGS.vi.invalidInput("Invalid hand: x"));
console.log(Object.keys(STRINGS.en).length, Object.values(STRINGS.en).filter((v) => typeof v === "function").length);
const src = fs.readFileSync("./src/App.jsx", "utf8");
console.log(Object.keys(STRINGS.en).filter((k) => !src.includes("t." + k) && !src.includes(`"${k}"`)));
'
```

```
131,876 131.876 0%–8% · 51%–100%
Dữ liệu không hợp lệ: Invalid hand: x
77 7
[ 'liveSolver', 'classesLoaded', 'matrixId', 'topHandsId' ]
```

In the browser (`npm run dev` with Flask running), type `As Xh Qd`, click "Run solver", then
switch to VI. The red box changes language, the backend's part does not, and the verdict for
`As Kh Qd` is still on screen.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** You type `As Kh` (two cards) and click "Run solver". What exactly does the red box
say? Check in the browser.

<details><summary>Solution</summary>

`Invalid input: Invalid hand: Hand string 'As Kh' must contain exactly 3 cards, found 2.`: one
part from `i18n.js`, one from [app.py:177](../backend/app.py#L177), and the rest from
[evaluator.py:410](../backend/src/evaluator.py#L410).
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
([i18n.js:168](../frontend/src/i18n.js#L168)) and run `npm test`. What does the failure tell you?

<details><summary>Solution</summary>

`# pass 5`, `# fail 1`. Test 5 fails with `language "vi"` and a diff containing
`-   fold: 'string',`: English has the key and Vietnamese does not. Without the test, `t.fold` would
be `undefined`, which React renders as nothing: an empty Action cell for every unprofitable row in
Vietnamese. Undo with `git checkout -- frontend/src/i18n.js`.
</details>

**🟡 5. No stale results.** In the `!solveRes.ok` branch ([:69-76](../frontend/src/App.jsx#L69-L76)),
also clear the old answer. Check: type `As Xh Qd`, run, and only the error should remain.

<details><summary>Solution</summary>

Add `setSolveData(null);` and `setAiAdvice(null);` after `setSolveError(…)`. The verdict, profit map
and top-hands table disappear, the coverage table keeps only its header, the summary shows `0.0%`,
`N/A` and `0`, and the notes say "No analysis for this hand yet."
Undo with `git checkout -- frontend/src/App.jsx`.
</details>

**🟡 6. Presets as data.** Replace the five hand-preset buttons
([:334-368](../frontend/src/App.jsx#L334-L368)) with an array and one `.map`. Check: `npm run lint`
shows only the two known warnings, and the buttons behave the same.

<details><summary>Solution</summary>

Define `const HAND_PRESETS = [["As Kh Qd", "Liêng Q-K-A"], ["7s 7h 7d", "Sáp 7"], …];` next to
`CATEGORY_LABELS`. Inside `<div className="preset-chips">`, map it to the same button as before,
with `key={cards}`, `hand === cards` in the class name, `onClick={() => setHand(cards)}` and
`{label}` as the text. 35 lines become 10, and a new preset is one line. Undo with `git checkout -- frontend/src/App.jsx`.
</details>

**🔴 7. Show where the analysis came from.** Keep the `model` field of the `/api/analyze` answer
and show it instead of the hard-coded label at [:591](../frontend/src/App.jsx#L591). Check: with no
API key, the drawer header names the rule-based engine.

<details><summary>Solution</summary>

At [:100](../frontend/src/App.jsx#L100) store `{ text: analyzeJson.advice, model: analyzeJson.model }`,
and render `<span className="drawer-sub">{aiAdvice?.model}</span>`. The header then reads
`rule-based-solver-engine (OPENROUTER_API_KEY not configured)`, and it stays empty for error
notices. Undo with `git checkout -- frontend/src/App.jsx`.
</details>

**🔴 8. Silence the linter honestly.** Remove both warnings on line 118 without an `eslint-disable`
comment and without re-solving on every input change. Check: `npm run lint` prints nothing and the
page still solves on load.

<details><summary>Hints and a solution</summary>

For `exhaustive-deps`, React 19.2's `useEffectEvent` makes a function an effect may call without
listing it. For `set-state-in-effect`, the effect must not set state synchronously. So split
`handleSolve` and start both loading flags as `true`:

```jsx
const handleSolve = () => { setIsLoading(true); setIsAiLoading(true); setSolveError(null); runSolve(); };
const runSolve = async () => { /* the old try/catch body, unchanged */ };
const solveOnMount = useEffectEvent(() => { runSolve(); });
useEffect(() => { solveOnMount(); }, []);
```

with `useState(true)` for `isLoading` and `isAiLoading`, and `useEffectEvent` imported from
`react`. Lint is then silent (exit 0), and the page still opens on "Raise / all-in". Development
still makes two requests, because StrictMode remounts either way.
Undo with `git checkout -- frontend/src/App.jsx`.
</details>

---

## ❓ Quiz

1. Why is `solveError` stored as `{ key, detail }` rather than as the finished sentence?
2. `fetch` succeeded and the status is 400. Which branch runs, and why didn't the `catch` fire?
3. Why are `solverOffline` and `aiUnreachable` functions, although they take no parameter?
4. The profit-map marker moves while you drag the slider, but the green zones do not. Why?
5. What can `i18n.test.js` detect, and what can it not?

<details><summary>Answers</summary>

1. So that it is translated at render time: switching language re-translates an error that is
   already showing. A stored sentence would stay in the old language.
2. The `if (!solveRes.ok)` branch at [:69](../frontend/src/App.jsx#L69). `fetch` throws only when no
   HTTP response arrives. A 400 is a normal response with `ok === false`.
3. So that the render can call every message the same way, `t[key]` with `detail`, without checking its type. A
   function with no parameters ignores the argument.
4. The marker reads `foldEquity` state directly ([:315](../frontend/src/App.jsx#L315)). The zones
   come from `solveData`, which changes only when a new `/api/solve` answer arrives.
5. It detects a key missing from (or added to) one language, a string where the other has a function,
   and a message that drops its parameter. It cannot detect wrong wording or unused keys.
</details>

---

## Recap

- `App` holds 12 pieces of state: six inputs and six results. Everything else is derived on render.
- `handleSolve` makes two requests: `/api/solve` (numbers, shown at once), then `/api/analyze`
  (notes, in its own `try`). Each failure maps to an i18n key, and two are mislabelled.
- Everything the UI shows comes from the server (the map in section 5). Ten `summary` fields are
  sent but unused.
- Copy lives in `i18n.js` as two 77-key dictionaries. State stores keys, and the render looks the
  message up by key and calls it with the detail.
- `format.js` holds the testable helpers. `i18n.test.js` compares the dictionaries' *shapes*.
- Known problems: lint warnings on the mount effect, stale results after an error, stacked error
  prefixes, a hard-coded model label, raw Markdown and copy-pasted presets.

**Next:** [14 — Styling and DESIGN.md](14-styling.md)
