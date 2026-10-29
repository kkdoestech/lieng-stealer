# Phase A — Grounding: the Liêng Scope verdict surface

Read this before sketching. It is the shared evidence base for every architect candidate. The
workspace is `C:\Users\Admin\Desktop\lieng-stealer`; open the files named below yourself.

---

## 1. What the page is

A decision-support tool for the Vietnamese card game Liêng. The user enters the pot, a bet size or
fold rate, and a 3-card hand. The backend returns, for that one hand, a single frozen recommendation:
**one action** (check / small / large / all-in), **one wager amount**, **one EV number**, the
**win rate** behind it, and a **three-rung ladder** pricing every size it rejected. The page's entire
job is to make that one answer, and the reason for it, readable in a few seconds. Everything else on
the page (range tables, top hands, AI notes) is secondary context.

The user has asked for four specific properties, which are the acceptance criteria for the layout:

1. **Verdict Card** — EV number, win rate, and recommended action (Value / Thin / Bluff) are
   visually dominant.
2. **Monospace numerals everywhere** so EV values align perfectly between rows.
3. **Sizing Ladder** — clearly shows *why* the AI chose Small over Large or All-In, e.g. by showing
   each option's EV.
4. **Assumption Line** (e.g. "Folds weakest 35% first") — clearly visible but secondary to the
   verdict.

## 2. The contract the UI renders

The UI must not compute domain numbers. It renders what `/api/solve` returns. Trace:

```
App.jsx runSolve()
  → POST /api/solve  → solveData.hand_evaluation.advice   (a Recommendation)
  → POST /api/analyze → aiAdvice.text                      (notes drawer only, never the verdict)
```

`Recommendation` is defined in `backend/src/advice.py` (frozen dataclass) and pinned by
`frontend/src/solve-contract.json` + `frontend/src/App.test.jsx`:

| field | type | meaning | must reach the UI as |
| :--- | :--- | :--- | :--- |
| `action` | `CHECK \| SMALL_BET \| LARGE_BET \| ALL_IN` | the command | the one dominant verb |
| `kind` | `VALUE \| THIN_VALUE \| BLUFF` | the argument (why we bet) | colour + label; never gates EV |
| `reason` | closed enum, 9 values | which rule fired | the one-sentence *why* line |
| `amount` | number | wager in VND (0 for check) | mono, currency suffix |
| `ev` | number | recommended action's EV | **hero number** |
| `ev_ratio` | number | `ev / pot` | optional secondary |
| `equity_when_called` | number | win rate at the assumed fold rate | **hero number** |
| `win_rate_defined` | bool | false when nobody can call | render a phrase, never "0%" |
| `robust` | bool | worst stress cell does not lose | small status mark |
| `why` | `{fold_component, call_component, net}` | EV split | optional, supports the why line |
| `ladder[3]` | `Rung` | small / large / all-in, in order | **Sizing Ladder** |

Each `Rung` (same file):

| field | meaning |
| :--- | :--- |
| `action`, `amount` | the option and its price |
| `ev`, `ev_ratio` | its EV in the centre cell and as `ev / pot` |
| `worst_ev_ratio` | EV / pot in the worst ±10-point fold-rate cell — the robustness number |
| `robust` | `worst_ev_ratio >= 0` |
| `eligible` | may this rung be the answer |
| `blocked_by` | `EV_BELOW_FLOOR \| NEEDS_BIGGER_EDGE \| BLUFF_TOO_SMALL_ONLY \| null` |

`summary` also carries `fold_equity`, `pot`, `opponent_model` (`range` | `random`), and `sizing`
(the nine policy thresholds). **The Assumption Line** is built from `opponent_model` + `fold_equity`:
`modelAssumptionRange(foldPct)` / `modelAssumptionRandom(foldPct)` in `frontend/src/i18n.js`.

Invariants that a design must not break:

- The verdict and the table row are the **same object** — never recompute a rung in JS.
- All copy goes through `t.*` keys in `frontend/src/i18n.js` (EN + VI must stay in sync). New strings
  require a new key in both languages, and VI wording is not to be improvised.
- `App.test.jsx` asserts against literal numbers and visible text (`Recommended action`, `Small bet`,
  `folds weakest …`). A styling change must not change numbers; a copy change must update tests.
- Colour names the **kind of hand**, not whether advice is "good". A bluff is a real play.

## 3. Current component tree (HEAD + working tree)

`frontend/src/App.jsx` is one 758-line component. Structure, in render order:

```
App
├─ header.terminal-header          wordmark, subtitle, EN/VI toggle
└─ main.terminal-grid              grid-template-columns: 340px 1fr
   ├─ section.control-panel        pot, bet, fold slider, model toggle,
   │                               call-range slider, profit map, hand input,
   │                               Run button, error, engine specs
   └─ section.results-container
      ├─ div.verdict-card.[kind-*]   ← exists already
      │  ├─ .verdict-banner
      │  │  ├─ left:  .verdict-label "Recommended action"
      │  │  │         .verdict-title <h2> action verb
      │  │  │         .kind-chip  Value | Thin value | Bluff
      │  │  │         .verdict-meta  hand · canonical id · score name
      │  │  └─ right: .verdict-label "Expected value"
      │  │            .verdict-ev   hero EV + currency
      │  │            .verdict-breakeven ×3  (profitable-when, sensitivity, ev-at-your-size)
      │  ├─ p.verdict-why            one-sentence reason (13px)
      │  ├─ p.verdict-assumption     the Assumption Line (12px muted)
      │  ├─ div.ladder-strip         3 × .ladder-rung (mark, label, amount, ev, blocked reason)
      │  └─ p.ladder-note            thresholds note (11px muted)
      ├─ div.verdict-empty          no-hand fallback (same shape, gray left rule)
      ├─ div.hud-metrics-grid       4 × .hud-card: coverage%, equity, EV, bluff break-even
      ├─ tables ×2                  coverage by category, top 10 hands
      └─ div.notes-drawer-container AI analysis disclosure
```

**Gaps versus the four acceptance criteria** (this is what the new plan must close):

- **Win rate is not in the Verdict Card.** It sits in a `.hud-card` two blocks below, while the
  card's headline EV appears twice (card + HUD). The card is not yet *the* verdict.
- The hero EV and the action verb are both 20px — neither dominates. There is no single largest
  typographic element on the results column.
- The ladder shows EV per rung but no comparison (no delta, no ordering emphasis); the blocked
  reason is a sentence fragment under a struck-through number. "Why not Large?" is readable only by
  reading all three cells. It also duplicates the amount already shown as the hero.
- The Assumption Line is 12px muted directly under a 13px body line — subordinate, but visually
  attached to the *why* sentence rather than separated as its own evidence line.

## 4. Existing style layer (working tree, uncommitted restyle)

`frontend/src/index.css` tokens now in place — this is the base, not a blank page:

```css
--bg:#0a0b0d; --bg-raised:#0f1114; --bg-inset:#0c0e10; --bg-hover:#16191d;
--line:#1d2126; --line-strong:#2a2f36;
--text:#c8ccd2; --text-strong:#eceef1; --muted:#7c848e; --faint:#565d66;
--value:#3fb27f;  /* emerald  */
--thin:#d0a15a;   /* amber    */
--check:#8a9199;  /* gray     */
--bluff:#b96e5e;  /* muted terracotta — a bluff is a play, not a warning */
--bad:#c4554d; --focus:#6e93b8;
--radius:0px;
--font-ui: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
--font-mono: "Cascadia Mono", "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
```

`frontend/src/App.css` (1090 lines) already implements: square surfaces, 1px hairlines, surface
ladder `--bg` / `--bg-raised` / `--bg-inset` / `--bg-hover`, `--kind` custom property set by
`.kind-value/.kind-thin/.kind-bluff/.kind-none` and read by `.verdict-card` (left 2px rule) and
`.ladder-rung.chosen` (top 2px rule), mono for every number, a 4-cell `.hud-metrics-grid` with 1px
internal rules, and responsive breakpoints at 1024 / 640px.

**Known slack in the current CSS**: 62 distinct `font-size` declarations between 10–20px, label
sizes at 10px are below a comfortable floor for a 1360px screen, `.hud-metrics-grid` repeats the EV
the card already shows, and the `.verdict-card` is the only bordered box on the page while the
verdict-empty fallback duplicates it with a different class.

## 5. Hard constraints

From the user (mandatory, override older docs):

- dark-saas / Linear-inspired: near-black canvas, charcoal surfaces, hairline separators, one
  accent family, no heavy shadow, no glassmorphism, no gradient backgrounds.
- **No Inter. No Roboto.** No default-AI font stack.
- **No purple / violet gradients.** (Purple is banned outright per `DESIGN.md` §1.)
- **No generic rounded cards.** Current radius token is `0px`; either keep square or justify a
  deliberate, small, non-generic radius.
- **No emoji icons.** Marks must be typographic or geometric primitives.
- Muted, sophisticated palette; **emerald = Value, amber = Thin, gray = Check**. Bluff is not named
  by the user — it must be chosen and justified (current token: muted terracotta).
- Monospace for **all** numbers, so EV values align.

From the repo (`AGENTS.md`, `DESIGN.md`, `frontend` tests):

- No global mutable state, no side effects in render; components stay presentational.
- `npm run lint` fails on any warning; `npm test` and `npm run build` must stay green.
- Copyright/copy: plain words, no `//`, `[ ]`, `●`-as-decoration, no fake status, no "GTO".
- Number inputs, labels, focus-visible outlines, and the EN/VI toggle are existing a11y contracts.
- Responsive: single column ≤1024px, narrow ≤640px, no horizontal page scroll at 390px.

## 6. Design tensions to resolve explicitly

1. **Action vs kind.** The user writes "recommended action (Value/Thin/Bluff)", but the domain
   separates the *command* (`action`) from the *argument* (`kind`). A design must show both without
   letting them compete: the verb should win, the kind should colour it.
2. **Check is both an action and a colour.** "gray for Check" maps a colour to the action, while
   emerald/amber map to kinds. Decide whether the left rule follows the *action* (gray whenever the
   answer is check) or the *kind*, and state it — `CHECK_ASSUMPTION_FRAGILE` carries `kind=BLUFF`,
   so the two disagree in real data.
3. **Four kinds, three colours.** `Kind` has VALUE / THIN_VALUE / BLUFF (NONE unused). Name the
   bluff treatment or state that bluff inherits gray.
4. **Duplicate EV.** The hero EV is repeated in the HUD grid; the plan should decide what the HUD
   grid is for once the verdict owns EV.
5. **Ladder evidence.** The strongest "why not Large" signal is `worst_ev_ratio` (robustness at
   fold-rate −10 points), not `ev`. Decide whether the ladder's second number is EV, worst-case EV,
   or a delta — and make the chosen rung's advantage arithmetically visible.

## 7. Grading rubric (used to pick the base in Phase D)

Score each candidate 0–2 per criterion; 12 max.

1. **Verdict dominance.** EV, win rate, and the action verb are the three largest/most contrasty
   things in the results column; a reader gets the answer without scanning. Exact sizes stated.
2. **Numeral alignment.** Every number is mono/tabular; the ladder's EV column aligns on the digit
   across rows and against the hero. No proportional numerals.
3. **Ladder legibility.** Each of the three options shows its EV *and* why it lost (or won) in
   ≤1 short phrase, comparable at a glance without reading prose. Chosen rung is unmistakable.
4. **Assumption line.** Visible without scrolling at 1360px, above the tables; clearly subordinate
   (size/colour/rule), never competing with the why line.
5. **Rule compliance.** Near-black canvas, single accent family, emerald/amber/gray semantics
   honoured, no purple, no Inter/Roboto, no rounded generic card, no emoji, muted palette.
6. **Fit to the contract.** Uses only real fields (`Recommendation`, `Rung`, `summary`), no invented
   API, no JS recomputation of EV, all copy via i18n keys, `win_rate_defined=false` handled,
   responsive at 1360/390, tests can stay green.

---

## How to write your package

Produce one file at your assigned path:

`design/candidates/c<N>/package.md`

Sections, in this order (sentence-case headings):

1. **Problem** — constraints that shaped the shape.
2. **Usage** — the component call site(s) first, e.g. `<VerdictCard advice={advice} summary={summary}
   handEval={handEval} />`; show two or three realistic JSX call sites.
3. **Shape** — component hierarchy tree with props, then the data flow from `advice` to each leaf.
   State which component owns which formatting decision.
4. **Wireframe** — ASCII for 1360px and 390px, with the hero sizes annotated.
5. **Styling plan** — token usage, type scale (named px/weight/letter-spacing steps), spacing scale,
   surface/hairline rules, the kind→colour map, and the CSS class list per component.
6. **Tradeoffs accepted** — one bullet each, form "we accept X in exchange for Y".
7. **Alternatives considered** — at least one whole-shape alternative and why it lost.
8. **Open questions and risks** — phrased as questions.
9. **Next implementation step** — one sentence.

Constraints on your output: **do not modify any application file** (no `App.jsx`, `App.css`,
`index.css`, `i18n.js`) and do not run the dev server. Write only your own `package.md`. Your
package must be implementable as a diff to `App.jsx` + `App.css` + `index.css` (+ i18n keys), in
that order, without touching the backend.
