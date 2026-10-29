# DESIGN.MD: WEB UI SPECIFICATION

Liêng Scope is a decision terminal for a Liêng solver. One answer per hand: **what to do**, **how
much**, **what it earns**, **how sure we are**, and **why not the bigger bet**. The interface exists
to make that chain readable in one glance and verifiable in one more.

This file is the authority for the UI. It supersedes the older Ayu Dark / "plain tool page" spec:
the tool keeps the same data and the same prohibitions on fakery, but it now has a deliberate,
documented design system. Every rule below is enforceable in review.

---

## 1. Design position

1. **One answer, one evidence chain.** The verdict region is the only thing on the page allowed to
   be loud. Everything else is a quiet ledger that supports it.
2. **Numbers are the product.** The type system gives all numerals one voice (monospace, tabular,
   right-aligned). Prose explains; numbers decide.
3. **Colour is scarce and semantic.** No colour is decorative. Four semantic hues exist, and they
   appear only inside the verdict region. Interaction colour is a separate, single accent.
4. **Hierarchy from type and surface, not from boxes.** Near-black canvas, charcoal surfaces at
   three steps, 1px hairlines, 2px semantic rules. No shadows, no gradients, no gloss.
5. **Square and technical.** Radius is `0`. Density is a technical document, not a marketing page.
6. **No decoration.** No emoji, no icon fonts, no fake status, no animation.

### The one-line test

> If a Liêng player glances for one second, they must come away with the verb, the EV, and the win
> rate — in that order — and nothing else must compete for that glance.

---

## 2. Design rules (mandatory)

### 2.1 Canvas and surfaces

Near-black canvas, not pure black. Elevation is a surface step plus a hairline; shadows are banned.

| Token | Value | Role |
| :--- | :--- | :--- |
| `--bg` | `#0a0b0d` | Page canvas. |
| `--bg-raised` | `#0f1114` | Panels and the verdict region. |
| `--bg-inset` | `#0c0e10` | Inputs, the chosen ladder row. |
| `--bg-hover` | `#16191d` | Hover on controls, rows, chips. |
| `--line` | `#1d2126` | 1px separators, table rows. |
| `--line-strong` | `#2a2f36` | Control borders, the hairline that must be seen. |
| `--focus` | `#6e93b8` | The only interaction accent: `:focus-visible` outlines. Nothing else. |

Rules:

- The canvas never sits below the header; the header is one 44px strip with a 1px bottom hairline.
- The verdict region is the **only** bordered surface in the results column. It is square, 1px
  `--line`, `--bg-raised`, and carries a 2px semantic rule on its left edge.
- Inputs and the chosen ladder row are `--bg-inset`: recessed, not lifted.
- Hover changes `background` only. Never size, position, shadow, or border-width.

### 2.2 Typography: two voices

| Voice | Family | Carries |
| :--- | :--- | :--- |
| UI (grotesque) | `--font-ui` | Wordmark, action verb, section labels, body prose. |
| Data (monospace) | `--font-mono` | **Every numeral**, hand notation, canonical ids, currency, tags, thresholds. |

Stacks (no web fonts; the tool must work offline):

```css
--font-ui:   "Segoe UI Variable Text", "Segoe UI", -apple-system, "Helvetica Neue", "Noto Sans", Arial, sans-serif;
--font-mono: "Cascadia Mono", "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
```

**Forbidden faces: Inter, Roboto.** Do not name them, and do not list a generic that resolves to
Roboto by default. The mono face is the product's identity: numbers are what this tool is.

Type scale (px, weight, tracking, line-height):

| Step | Family | Size | Weight | Tracking | LH | Used for |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| `display` | mono | 40 | 500 | -0.02em | 1.0 | Hero EV. The largest element on the page. |
| `title` | UI | 26 | 600 | -0.015em | 1.1 | The action verb (`<h2>`). |
| `metric` | mono | 24 | 500 | -0.01em | 1.05 | Win rate beside the hero EV. |
| `heading` | UI | 12 | 600 | -0.005em | 1.2 | Section headings ("Coverage by category"). |
| `figure` | mono | 14 | 500 | 0 | 1.25 | Ladder and table numerals. |
| `body` | UI | 14 | 400 | 0 | 1.55 | Why line, notes, prose. |
| `body-sm` | UI | 12.5 | 400 | 0 | 1.5 | Assumption sentence, stat sublabels. |
| `label` | UI | 11 | 500 | 0.08em, uppercase | 1.2 | Field labels, column heads, tags. |
| `micro` | mono | 11 | 400 | 0 | 1.45 | Hand line, thresholds, footnotes, units. |

Hard rules:

- Nothing in the results column is larger than `display`; nothing below the verdict is larger than
  `figure` except the stat strip's 16px values.
- Negative tracking only on `display`, `title`, `metric`. Uppercase labels take positive tracking.
- No text below 11px. (The old 10px labels are retired.)
- `font-variant-numeric: tabular-nums` is on every mono element, inherited from `body`.
- Headings are 500–600 weight; body is 400. No synthetic bold, no all-caps body.

### 2.3 Colour: semantic law

Two strictly partitioned systems. They never mix.

**A. Kind hues — the argument for betting.** Used *only* inside the verdict region.

| Token | Value | Meaning | Contrast on `--bg-raised` |
| :--- | :--- | :--- | ---: |
| `--value` | `#3fb27f` | **Value** — ahead when called. Use for the kind tag and card rule. | 7.1:1 |
| `--thin` | `#d0a15a` | **Thin** — marginal edge, keep it small. | 8.0:1 |
| `--check` | `#8a9199` | **Check / no action** — gray states the absence of a bet. | 5.9:1 |
| `--bluff` | `#b96e5e` | **Bluff** — no showdown value; folds pay. A real play, not a warning. | 4.9:1 |

**B. Interaction / system colour.**

| Token | Value | Use |
| :--- | :--- | :--- |
| `--focus` | `#6e93b8` | Focus rings only. |
| `--bad` | `#d0685e` | Errors and invalid input only. (Raised from `#c4554d` to pass AA at 5.5:1.) |

Rules:

1. **Colour names the argument, never the size of the number.** The hero EV, the win rate, and the
   verb are `--text-strong`. A big green number is banned.
2. **Emerald = Value, amber = Thin, gray = Check.** Bluff is muted terracotta: it is a legitimate
   action whose profit comes from folds, so it must not read as an error, and it must not read as
   amber "thin value" either.
3. **Where the hues may appear:** the card's 2px left rule; the kind tag (border + text); the chosen
   rung's 2px rule and its "Chosen" label. **Nowhere else.** No coloured table cells, no coloured
   HUD numbers, no coloured links.
4. **The CHECK conflict is resolved by the action.** When `action === CHECK` the card tone is
   `--check` and the kind tag is **not rendered** (a check's explanation is a sentence, not a label;
   pinned by `App.test.jsx`). When the action is a bet, the tone is the kind's hue.
5. Green/red do not appear in tables at all. Direction of an EV is carried by its sign and its
   column alignment, not by colour. This is what keeps the page muted and lets the verdict's colour
   mean something.
6. The profit map in the controls is the one exception: `--value` at 45% opacity marks the fold-rate
   stretches where the user's own bet size pays. It is the same meaning (plus-EV), so it may reuse
   the hue.
7. Never convey meaning by colour alone: the kind tag spells "Value", the chosen rung spells
   "Chosen", errors are also announced with `role="alert"`.

### 2.4 Geometry and spacing

- **Radius `0`** everywhere: cards, chips, tags, inputs, buttons. Square is the signature.
- **Hairlines are 1px** (`--line` inline, `--line-strong` for control borders). Semantic rules are
  2px, and only on the verdict card's left edge and the chosen ladder row.
- **No box-shadow** on any surface. No gradients anywhere. No backdrop blur.
- Spacing scale (px): `2, 4, 6, 8, 12, 16, 24, 32`. Use 4/8/12/16 inside components, 16/24 between
  blocks, 24/32 inside the verdict hero.
- Card padding `16px` (12px at ≤640). Table rows `40px` in the verdict ladder, `30px` in data tables.
- Controls: 32px tall; the Run button 36px; slider track 2px with a 10px square thumb.

### 2.5 Prohibitions and their replacements

| Banned | Replacement in this design |
| :--- | :--- |
| Inter, Roboto | The two stacks in §2.2. The mono face carries the identity. |
| Purple / violet, any gradient | Flat surfaces only. Semantic hues are the only colour, and they are muted. |
| Generic rounded cards | One square, hairline-bordered verdict region. Every other block is separated by spacing and hairlines. |
| Emoji / icon fonts | Typographic marks only. The ladder uses `●` (eligible) / `○` (blocked) because they are information, not decoration. No other glyph is an icon. |
| Drop shadows, glass, glow | Surface steps + 1px hairlines. |
| Entrance animation, spinners, pulsing dots | Static states. The only motion is `background-color`/`color` on hover and focus, and it must be ≤120ms or absent. |
| Fake status ("LIVE", "AI-powered") | Nothing that checks nothing. The notes drawer shows its model name because the server returned it. |
| Raw enum codes in copy | Map every code to a sentence or a label (e.g. sensitivity status must not print `ROBUST_BET`). |

One specific instance of fake status, verified in `advice.py`: **`Recommendation.robust` is always
`true` by construction** — an eligible rung must clear `min_edge_ratio` (0.05) in its worst stress
cell, and a check is constructed with `robust=True`. It is therefore never displayed. Per-rung risk
is carried by the worst-of-three number; `Rung.robust` can be `false` for a blocked rung, but the
number that produced it is already on screen, so no badge is needed there either.

### 2.6 The numeral law

All numbers, without exception, are `--font-mono`, tabular, and right-aligned in their column.

- **Money**: integer VND via `formatMoney(value, locale)`. The unit (`VND`) appears **once** per
  group: as a suffix on the hero EV, and in the ladder's column subheads. Cells hold bare numbers.
  In monospace, `+` and `-` occupy the same advance as a digit, so signs align.
- **EV values are always signed**: `+164,064`, `−11,995`. Deltas are signed too.
- **Percentages**: one decimal for win rate / equity (`99.5%`), whole numbers for fold rates and
  slider badges (`35%`).
- **Alignment**: right-aligned, not decimal-point aligned — locale separators differ (`.` vs `,`) and
  tabular figures already fix the digit grid. Never justify a numeral cell.
- **No numeral carries semantic colour.** A negative EV is not red; it is a number with a minus.
- **Never recompute in the UI.** Display `ev`, `ev_ratio`, `worst_ev_ratio`, `amount`, and
  `equity_when_called` exactly as returned. (`worst_ev_ratio * pot` is the one permitted
  multiplication for display, and it lives in `verdict.js`.)

### 2.7 Accessibility floor

- Text contrast ≥4.5:1 on its surface; large numerals ≥3:1. Measured: `--text` 11.7, `--muted` 5.0,
  `--value` 7.1, `--thin` 8.0, `--check` 5.9, `--bluff` 4.9, `--bad` 5.5 on `--bg-raised`.
- `--faint` is non-information (placeholders/disabled only); it is never body copy.
- Focus: 1px `--focus` outline, 1px offset, on every control and link-like button
  (`:focus-visible`). Never remove an outline without a replacement.
- The verdict action is an `<h2>`; the ladder is a real `<table>` with `<caption>` and `<th
  scope="col">`; the stat strip is a definition list or a labelled group.
- Toggles keep `aria-pressed`; errors keep `role="alert"`.
- No horizontal page scroll at 390px; wide data tables scroll inside their own wrapper.

---

## 3. The verdict layout

### 3.1 Block order in the results column

1. **Verdict region** — hero, why sentence, assumption line, sizing ladder, threshold note.
2. **Stat strip** — three contextual figures (no duplication of the verdict).
3. Coverage by category (table).
4. Most profitable hands (table).
5. Analysis notes (collapsed).

Rule: the verdict region is never split across the fold at 1360×768, and the assumption line is
always visible without scrolling.

### 3.2 Verdict region anatomy at 1360px

Results column inner width ≈988px. Card padding 16. Content width ≈954px.

```
┌ .verdict-card  bg-raised · 1px line · 2px --kind left rule · radius 0 ─────────────────┐
│                                                                                        │
│ RECOMMENDED ACTION                     EXPECTED VALUE            WIN RATE WHEN CALLED  │
│ All in   [ VALUE ]                     +164,064 VND               99.5%                 │
│ As Kh Qd · Q-K-A · Liêng Q-K-A         at your bet size: +131,876                      │
│                                                                                        │
│ You win about 99.5% when called, so the all-in is worth the risk even if they fold      │
│ 10% less than you think.                                                               │
│ ────────────────────────────────────────────────────────────────────────────────────── │
│ ASSUMPTION   The opponent folds their weakest 35% of hands and calls with the best 65%. │
│ ────────────────────────────────────────────────────────────────────────────────────── │
│ SIZING LADDER                                                             amounts in VND │
│ SIZE                        BET            EV              WORST OF 3 READS         │
│ ● All in                 100,000      +164,064           +154,076                      │
│   Chosen                                                                               │
│ ○ Large bet               75,000      +147,970           +140,480                      │
│   −16,094 vs chosen                                                                    │
│ ○ Small bet               33,000      +120,932           +117,639                      │
│   −43,132 vs chosen                                                                    │
│ ────────────────────────────────────────────────────────────────────────────────────── │
│ We recommend a bet only when it earns at least 5% of the pot and still earns it if the │
│ opponent folds 10% less than you think.                                                │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

Proportions at 1360: hero block ~60% height of the card's top section; the hero EV is set at 40px so
it is roughly 2.9× the body text; the action verb 26px; the win rate 24px. Nothing below the card
exceeds 16px.

### 3.3 Hero

- **Left**: `label` "Recommended action" → `<h2>` action verb (`title`, `--text-strong`) → kind tag
  (inline, 1px `--kind`, `--kind` text, mono 10–11 uppercase, padding 1px 6px — **omitted when the
  action is CHECK**) → hand line (`micro`, `--muted`): `As Kh Qd · Q-K-A · Liêng Q-K-A`.
- **Right**: two figures on one baseline group, right-aligned: **Expected value** (`display` mono,
  signed money, `--text-strong`, unit `VND` in `micro`/`--muted`) and **Win rate when called**
  (`metric` mono). Under the EV, one `micro` `--muted` caption line:
  `at the recommended size · 1.64× pot` (the ratio is `advice.ev_ratio`, the only display use of that
  field); when `handEval.ev !== advice.ev`, a second line reads `at your bet size: +131,876`.
- When `win_rate_defined === false`, the win-rate figure is replaced by the sentence
  `winRateUndefined` in `body-sm`/`--muted` (never "0.0%").
- The hero uses `grid-template-columns: minmax(0,1fr) auto` with `align-items: start`; the right
  group is `display:flex; gap:32px; align-items:flex-end;`.
- **On a CHECK the EV figure is demoted**, not removed: same slot and label, `metric` size,
  `--muted` ink, and the EV caption is suppressed. `advice.ev = 0` for a check is a sentinel in the
  policy, not a measured expectation; at `display` size it would state the opposite of the verdict.
- **The kind tag is a sibling of the `<h2>`, never a child.** The heading's accessible name must stay
  exactly the action word (`getByRole("heading", { name: "All in" })` is pinned). Same for the hand
  line: outside the heading.
- **The recommended amount appears exactly once on the page — in the ladder row.** Do not repeat it
  beside the verb: `getByText(/33,000/)` is pinned and a second match throws.

### 3.4 The why sentence

One sentence, `body`, `--text`, `max-width: 72ch`, 12px below the hero. It comes from
`whyLine(t, advice, summary)` and quotes the response's own numbers. It stays neutral: the kind hue
belongs to the card edge, not to the prose.

### 3.5 The assumption line (secondary, but unmissable)

- Its own row, hairline above, `margin-top: 12; padding-top: 12`.
- Two-column grid: `label` "ASSUMPTION" (11px, uppercase, 0.08em, `--muted`) in a 96px column, then
  the sentence in `body-sm` `--muted` — full width, never truncated, never folded into the why line.
- Content: `modelAssumptionRange(foldPct)` / `modelAssumptionRandom(foldPct)` — the response's own
  model and fold rate.
- Secondary by hierarchy (muted colour, 12.5px, no colour, no surface), not by hiding. It sits above
  the ladder because it qualifies every number below it.

### 3.6 The sizing ladder

Purpose: answer **"why this size and not the other two"** without prose. It is a 3-row table, one row
per rung, in policy order (small → large → all-in).

Markup: `<table class="ladder">` with `<caption class="ladder-caption">Sizing ladder</caption>`,
a visible section label row, then `<thead>`/`<tbody>`. Rows are `.ladder-rung` (test hook).

Columns:

| Column | Content | Treatment |
| :--- | :--- | :--- |
| **Size** | `●`/`○` mark + size label; second line: the rung's state | size label uses `body` at 600; state line uses `micro`. |
| **Bet** | `amount` bare number | `figure` mono, right |
| **EV** | `ev` signed | `figure` mono, right |
| **Worst of three** | `worst_ev_ratio * pot`, signed | `figure` mono, right, `--muted` |

The third column is the **minimum** EV across the centre cell and the two ±10-point stress cells —
that is what `worst_ev_ratio` means in `advice.py`. **Never label it with one fold rate** ("folds 10%
less"): the contract returns only the minimum, not which cell produced it, so such a header can state
a falsehood. Header subheads (`micro`, `--muted`): under Bet and EV the unit `VND`; under the third
column `worstHint` = "weakest of centre, ±10 pts". A right-aligned `micro` line above the table reads
"amounts in VND".

State line, in priority order:

1. Chosen rung → **`Chosen`** in `--kind`, mono 11, uppercase.
2. Blocked rung → the `t.blocked[blocked_by]` phrase ("not worth the extra risk" / "needs a bigger
   edge" / "bluffs stay small") in `micro` `--muted`.
3. Eligible but not chosen → `outcomeDelta(ev - chosen.ev)` = "−16,094 vs chosen" in `micro`
   `--muted`.

Styling:

- Chosen row: `background: --bg-inset`; 2px `--kind` on the first cell's left edge; the size label in
  `--text-strong`; numbers stay `--text-strong`.
- Blocked row: numbers in `--muted`; **no strikethrough** (a struck number is harder to read and the
  state line already says why).
- All numeric cells share a fixed width token (BET `9ch`, EV `11ch`, WORST `11ch` at `figure`), so
  EV digits line up row to row. Right-aligned.
- The `● / ○` marks are 11px mono, `--check`; they encode eligibility (a blocked rung cannot be the
  answer) and are the only glyphs in the UI.
- No vertical borders; 1px `--line` between rows and under the header only.

### 3.7 Why this ladder shape

Rows, not three columns: a column of EVs aligns on the digit; three side-by-side cells do not. The
third column is the minimum the policy actually gates on (`min_edge_ratio` must hold in the centre
cell **and** in the worst of the ±10-point stress cells), so it is the honest second number — more
useful than a delta. It is deliberately not attributed to a fold rate: the response exposes only the
minimum. The order small → large → all-in mirrors the policy's walk and lets the eye climb to the
answer.

### 3.8 Stat strip, tables, notes

- **Stat strip** (`3 cells`, hairline top and bottom, no surface): *Hands worth a bet*
  (`bet_recommended_percent`, sub `combosWorthBet`), *Range coverage*
  (`range_coverage_percent`), *Bluff break-even* (`pure_bluff_break_even_fold_equity`, sub
  `bluffThresholdSub`). Values `figure` at 16px mono; labels `label`; vertical 1px rules between
  cells. It replaces the old 4-card HUD grid: the EV and the equity moved into the verdict hero, so
  the strip must not repeat them.
- **Data tables** keep the existing structure and numbers. Restyle only: header `label`; row 30px;
  numerals `figure` right-aligned; EV/status cells **neutral** (no green/red); hover `--bg-hover`.
- **Notes drawer**: 1px top hairline, toggle in `micro` uppercase, content in `body`. It is the last
  thing on the page and never above the verdict.

---

## 4. Component hierarchy

### 4.1 Target tree

```
App.jsx                              state, fetching, lang, shell composition
├─ AppHeader                         wordmark, subtitle, EN/VI toggle
├─ ControlPanel                      inputs (pot, bet, fold, model, call range, hand)
│  ├─ Stepper                        (−) number (+), amount fields
│  ├─ PresetChips                    plain bordered chips (pot, bet multiples, hands, model)
│  ├─ ProfitMap                      zones + marker
│  ├─ RunButton                      + inline error (role=alert)
│  └─ EngineSpecs                    footnote rows
└─ ResultsPanel
   ├─ VerdictCard                    ← new; owns the whole answer region
   │  ├─ VerdictHero                 action verb, kind tag, hand line, EV, win rate
   │  ├─ WhyLine                     one sentence from whyLine()
   │  ├─ AssumptionLine              labelled evidence row
   │  ├─ SizingLadder                ← new; 3-row table
   │  │  └─ RungRow ×3               mark, size label + state line, bet, EV, worst case
   │  └─ ThresholdNote               the 5% / ±10pt sentence
   ├─ StatStrip                      ← new; replaces hud-metrics-grid
   ├─ CoverageTable
   ├─ TopHandsTable
   └─ NotesDrawer
```

Minimum viable extraction (the change this plan authorises): `VerdictCard.jsx`,
`SizingLadder.jsx`, `AssumptionLine.jsx`, `StatStrip.jsx`. Control-panel extraction is optional and
should not ride along — one concern per change.

### 4.2 Props and data flow

```jsx
<VerdictCard advice={advice} handEval={handEval} summary={summary} t={t} />
<VerdictHero advice={advice} handEval={handEval} t={t} />
<AssumptionLine text={assumptionLine(t, summary)} t={t} />
<SizingLadder ladder={advice.ladder} chosen={advice.action} pot={summary.pot} t={t} />
<StatStrip summary={summary} t={t} />
```

- `advice` is the frozen `Recommendation` from `/api/solve`; `summary` carries `pot`,
  `fold_equity`, `opponent_model`, `sizing`, `bet_recommended_percent`, `range_coverage_percent`,
  `pure_bluff_break_even_fold_equity`.
- `handEval` supplies `hand`, `canonical_id`, `score_name`, `ev` (at the user's bet size),
  `profitable_fold_zones`, `sensitivity`.
- Components receive domain objects and `t`; they never receive pre-rendered numbers except through
  the pure view helpers.

### 4.3 Ownership

| Decision | Owner |
| :--- | :--- |
| Money/percent/sign formatting | `format.js` — `formatMoney`, `signedMoney`, `percent`, `wholePercent` |
| Which tone a verdict gets; kind tag text; rung state lines; worst EV | `verdict.js` — `cardTone(advice)`, `rungView(rung, chosen, pot, t)` |
| Which sentence explains the answer | `verdict.js` — `whyLine(t, advice, summary)` (moved from `App.jsx`) |
| Markup and class names | the component files |
| Fetching, aborting, loading/error state | `App.jsx` only |

`rungView` is the deep module of this change: it turns a `Rung` into
`{ mark, sizeLabel, stateText, stateTone, bet, ev, worstEv }`, so no component re-derives policy or
formatting. Components stay dumb.

### 4.4 Files and CSS split

| File | Contents |
| :--- | :--- |
| `src/index.css` | Tokens, resets, base typography, focus, selection, scrollbars. No component rules. |
| `src/App.css` | Shell, header, controls, stat strip, data tables, notes, shell breakpoints. |
| `src/verdict.css` | Verdict card, hero, kind tag, assumption row, ladder, threshold note. Imported by `VerdictCard.jsx`. |
| `src/verdict.js` | `cardTone`, `rungView`, `whyLine`, `assumptionLine` (pure, unit-testable). |
| `src/format.js` | Formatting helpers only. |

Rationale: the verdict is the only region with its own colour semantics and its own type scale above
`title`; keeping it out of the 1,090-line `App.css` keeps the cascade honest and lets the rest of the
app stay quiet.

---

## 5. Styling plan

### 5.1 Token changes

1. `--bad: #c4554d → #d0685e` (AA at 5.5:1 for error text at 11–12px).
2. `--faint: #565d66 → #626973`; document that it is placeholder/disabled only.
3. Remove the generic `system-ui` from `--font-ui` and put `-apple-system` explicitly (no path may
   resolve to Roboto by default).
4. Keep `--radius: 0px`. Keep `--value/--thin/--check/--bluff` as-is (all pass contrast).
5. Optional: add spacing tokens `--s1…--s6` (4/8/12/16/24/32) if the CSS starts repeating gaps;
   not required for the first pass.

### 5.2 Cascade rules

- Tokens only in `index.css`; no hex/rgba literals in `App.css` or `verdict.css`.
- `.kind-*` classes set `--kind` and nothing else; consumers read `var(--kind, var(--check))`.
- The card tone comes from the action when the action is CHECK, else from the kind:
  `cardTone(advice)` returns `verdict-card is-check` for a check, else `verdict-card kind-*`.
  `.verdict-card.is-check { --kind: var(--check); }` is declared **after** the `.kind-*` classes and
  out-specifies them, so the precedence lives in the CSS, not in a comment.
- No `!important`. No inline styles for layout (the profit map's `left`/`width` inline positioning is
  the existing, accepted exception).

### 5.3 Class inventory (new/changed)

`.verdict-card`, `.verdict-card.is-check`, `.kind-value/-thin/-bluff`, `.verdict-hero`,
`.verdict-action`, `.verdict-title`, `.kind-tag`, `.verdict-hand`, `.verdict-figures`,
`.verdict-figure`, `.verdict-figure-label`, `.verdict-ev`, `.verdict-ev-value`, `.verdict-ev-unit`,
`.verdict-ev-alt`, `.verdict-winrate`, `.verdict-why`, `.assumption-row`, `.assumption-label`,
`.assumption-text`, `.ladder`, `.ladder-caption`, `.ladder-meta`, `.ladder-head`, `.ladder-rung`
(keep), `.ladder-rung.chosen` (keep), `.ladder-rung.rung-blocked` (keep), `.ladder-mark`,
`.ladder-size`, `.ladder-state`, `.ladder-num`, `.threshold-note`, `.stat-strip`, `.stat-cell`,
`.stat-label`, `.stat-value`, `.stat-sub`.

Removed: `.hud-metrics-grid`, `.hud-card`, `.hud-value`, `.hud-subtext`, `.hud-phrase`,
`.positive-ev`, `.negative-ev`, `.chip-full`, `.chip-zero`, `.ladder-amount`, `.ladder-ev`,
`.ladder-blocked`, `.verdict-banner`, `.verdict-col-right`, `.verdict-breakeven`.

### 5.4 Responsive plan

- **≥1025px**: 340px controls + results column (unchanged shell). Ladder shows all four columns.
- **≤1024px**: one column; controls above results (unchanged).
- **≤768px**: the **worst-of-three** column collapses into the rung's state line as
  `worstTag` + value ("worst +154,076"), so no figure disappears — it relocates. Size, Bet, EV stay
  as columns.
- **≤640px**: card padding 12; hero stacks (action block → EV figure → win rate figure); `display`
  32px, `title` 22px, `metric` 20px; assumption row becomes one column (label above text); stat
  strip becomes stacked rows (label left, value right, hairlines between); ladder numerics 12px.
- **≤480px**: side padding 12; `display` 28px; data tables scroll inside `.table-wrapper`.

Wireframe at 390:

```
┌──────────────────────────────────┐
│▌ RECOMMENDED ACTION              │
│▌ All in  [ VALUE ]               │
│▌ As Kh Qd · Q-K-A · Liêng Q-K-A  │
│                                  │
│ EXPECTED VALUE                   │
│ +164,064 VND                     │
│ WIN RATE WHEN CALLED             │
│ 99.5%                            │
│                                  │
│ You win about 99.5% when called, │
│ so the all-in is worth the risk  │
│ even if they fold 10% less…      │
│ ──────────────────────────────── │
│ ASSUMPTION                       │
│ The opponent folds their weakest │
│ 35% of hands and calls with the  │
│ best 65%.                        │
│ ──────────────────────────────── │
│ SIZING LADDER       amounts VND  │
│ SIZE          BET        EV      │
│ ● All in   100,000  +164,064     │
│   Chosen                         │
│ ○ Large     75,000  +147,970     │
│   −16,094 vs chosen              │
│ ○ Small     33,000  +120,932     │
│   −43,132 vs chosen              │
└──────────────────────────────────┘
```

### 5.5 States

| State | Behaviour |
| :--- | :--- |
| First load / re-run | Button reads "Calculating…" and is disabled; the previous verdict stays until the new one arrives (no skeleton, no spinner). |
| Solve error | Error box under the button (`role="alert"`), old results cleared, verdict region absent. |
| No hand entered | `.verdict-empty` block with the same card geometry, gray rule, "No hand entered", assumption line, action-counts sentence. |
| `win_rate_defined === false` | Win-rate figure replaced by the sentence; the hero never prints "0.0%". |
| `action === CHECK` | Gray rule, no kind tag. **The EV figure is demoted** to `metric` (24px, `--muted`): `advice.py` sets `ev = 0` as a sentinel for a check, not as a measurement, so a 40px "+0 VND" would assert the opposite of what the policy decided. The win-rate figure stays the largest numeral; the ladder still shows all three rungs and why they lost; no row is "Chosen". |
| Negative EV on a rung | Signed number in `--muted` for blocked rungs; never red. |

---

## 6. Copy and i18n

- All strings live in `frontend/src/i18n.js`, EN and VI with the same keys. No literals in JSX. No
  raw enum codes on screen.
- New keys (EN shown; VI mirrors, and VI wording needs a native pass):
  - `sizesTag` "Sizing ladder"
  - `amountsIn(currency)` "amounts in {currency}"
  - `colSize` "Size", `colBet` "Bet", `colWorst` "Worst of 3", `worstHint` "weakest of centre, ±10 pts", `worstTag` "worst"
  - `chosen` "Chosen", `outcomeDelta(amount)` "{amount} vs chosen"
  - `winRateLabel` "Win rate when called"
  - `evRatioPot(ratio)` "{ratio}× pot"
  - `assumptionTag` "Assumption"
  - `rangeCoverage` "Range coverage"
  - `sensitivityLabel: { ROBUST_BET, ROBUST_NO_BET, ASSUMPTION_SENSITIVE }` mapped to sentences
- Copy rules stay: plain words, verbs first, sentence case, no `//`, `[ ]` decoration, no claims the
  code does not support (no "live", no "GTO").

---

## 7. Test impact

Markup changes touch these assertions; each is a deliberate update, and **no number may change**:

| `App.test.jsx` | Now | After |
| :--- | :--- | :--- |
| `:305–307` | `getByText(/33,000/).closest(".ladder-rung")`, class `chosen`, contains `●` | Unchanged — keep `.ladder-rung`, `.chosen`, `●`/`○` |
| `:313–315` | `rung-blocked`, contains `○`, `75,000` | Unchanged |
| `:316` | contains `"EV -11,995"` | Contains `"-11,995"` (the column head carries "EV"; the cell is a bare numeral) |
| `:330–336` | "nobody calls" twice; `.hud-card` holds the equity | **Count stays 2** — the phrase already appears in the why sentence, and the second copy moves from the HUD card into the hero's win-rate figure, so the assertion becomes: both occurrences are inside `.verdict-card`, and the card contains no `0.0%`. The `.hud-card` selector is replaced by `.verdict-winrate`. |
| `:185`, `:254` | `<h2>` "All in"/"Check"; check card has no "Bluff" | Unchanged |

Three markup laws follow from how Testing Library matches, and they bind the implementation:

1. **Any string a test locates must appear as a direct text node exactly once.** `getByText` matches
   an element's own text nodes, not descendants' — so a string split across two flex children is
   invisible to it, and the same string in two siblings makes the query throw. This is why the
   amount lives only in the ladder row, and why the ladder's EV cell must be **one element** with
   the sign and digits in the same text node.
2. **The action verb stays an `<h2>` whose accessible name is the bare verb.** A kind tag or a
   subtitle inside it changes the name and breaks `getByRole("heading", …)`.
3. **`●` / `○` are not decoration and are not removable** without updating `:307`/`:314`. They encode
   eligibility; the "Chosen" label encodes the pick.

`format.test.js`/`i18n.test.js` should stay green; adding the same keys to both languages keeps the
parity test green.

---

## 8. Implementation sequence

1. `index.css`: apply token changes (§5.1) and remove `system-ui` from the UI stack.
2. `verdict.js`: move `whyLine`/`assumptionLine` out of `App.jsx`; add `cardTone`, `rungView`; unit
   tests for the three pure functions (they need no DOM).
3. `verdict.css`: write the verdict styles against the new class inventory.
4. `VerdictCard.jsx` + `SizingLadder.jsx` + `AssumptionLine.jsx`: build against the sketch, wired to
   `verdict.js`.
5. `App.jsx`: replace the inline verdict/HUD markup with `VerdictCard` + `StatStrip`; keep the fetch
   logic untouched.
6. `i18n.js`: add the keys in both languages.
7. `App.test.jsx`: apply the §7 updates.
8. Delete the dead CSS classes; `npm run lint` (zero warnings) and `npm run build`.
9. Visual check at 1360 and 390; confirm no number changed versus `solve-contract.json`.

## 9. Review checklist

- [ ] Canvas is `#0a0b0d`; no surface is pure black.
- [ ] Exactly one bordered region in the results column: the verdict card, radius 0.
- [ ] Hero EV is the largest element; the action verb is an `<h2>`; win rate is the second figure.
- [ ] Every numeral is mono, tabular, right-aligned; `+`/`-` align; no decimal-point justification.
- [ ] Ladder shows all three options with EV and the worst-of-three read; the chosen row is
      unmistakable; every non-chosen row states why in one phrase.
- [ ] Assumption line is visible at 1360 without scrolling, muted, and clearly below the why line.
- [ ] Emerald only on Value; amber only on Thin; gray on Check; bluff terracotta; no coloured table
      cells; no purple; no gradient; no emoji; no Inter/Roboto.
- [ ] CHECK never renders a kind tag; `win_rate_defined === false` never renders 0%.
- [ ] Keyboard focus is visible on every control; errors are `role="alert"`.
- [ ] No horizontal page scroll at 390px.
- [ ] `npm run lint`, `npm run build`, `npm test` pass; every displayed number is unchanged.

---

## 10. Why this shape: alternatives, tradeoffs, open questions

### 10.1 Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| **Three side-by-side ladder cells** (the current strip) | Each EV sits at a different x-origin, so no digit column aligns and the eye must re-anchor three times. A row table gives one right edge and one column — the requirement "EV values align perfectly" is satisfied literally. |
| **Shared-scale EV bars** in the ladder (zero rule at ⅓ of a 3-pot track, fill left for negative) | Defensible and mathematically bounded (`ev_ratio ∈ [−1, +2]`), but it re-encodes the EV column, roughly doubles the ladder's height, and a blocked rung can legitimately carry the longest bar (`NEEDS_BIGGER_EDGE`), so length cannot mean "chosen". Numbers + worst case + a state phrase answer "why not large" more precisely and in less space. Revisit only if the ladder still reads as too abstract. |
| **Keep the 4-card HUD grid** beside the verdict | It repeats the hero's EV and equity, which is exactly what stops the verdict from being dominant. Keep `.hud-card` only as an empty selector hook to avoid touching two test assertions? That makes a class name lie about the DOM and keeps a dead abstraction alive — worse than a two-line test update. |
| **Poster hero at 48–56px** | At 1360×768 a 56px EV plus verb plus caption pushes the assumption line and the first ladder row toward the fold. 40px is already ~2.9× body and reads as the page's largest thing; bigger buys attention by spending the evidence that makes the number trustworthy. |
| **Putting the assumption line in the controls panel** | It is a property of the solution, not of the input, and the user asked for it to be visible next to the verdict while secondary. It sits above the ladder because it qualifies every number below it. |

### 10.2 Tradeoffs accepted

- We accept a taller verdict region (~420px at 1360) in exchange for the answer, the assumption, the
  evidence, and the rule all being visible above the fold without scrolling.
- We accept one colour-bearing region and an otherwise greyscale page, in exchange for the kind
  hues carrying real meaning instead of decorating tables.
- We accept updating two `App.test.jsx` assertions in exchange for removing the duplicated EV/equity
  figures; the numbers themselves are frozen and must not change.
- We accept `worst_ev_ratio × pot` as the only arithmetic in the frontend, in exchange for showing
  the stress-cell number the policy actually gates on.
- We accept square corners and no shadow everywhere, including on the one "card", in exchange for
  the page reading as an instrument rather than a marketing surface.

### 10.3 Open questions

- **Bluff hue:** muted terracotta (`#b96e5e`) is the current token and passes contrast, but it is
  warmer than the "muted, sophisticated" brief may want; the alternative is a dusty rose. Confirm.
- **The "vs chosen" wording:** for an eligible-but-not-chosen rung the state line reads
  "−16,094 vs chosen". Is that clear enough without a delta column, or should the ladder gain a
  fifth numeric column at ≥1200px?
- **Vietnamese copy:** the new keys (`chosen`, `outcomeDelta`, `winRateLabel`, `colWorst`,
  `worstHint`, `worstTag`, `rangeCoverage`, `evRatioPot`, `sensitivityLabel`) need a native pass; the
  existing VI wording must not drift.
- **Sensitivity status:** the response returns `ROBUST_BET` / `ROBUST_NO_BET` /
  `ASSUMPTION_SENSITIVE`; the UI currently prints the raw code in "Assumption sensitivity: …".
  Mapping it to sentences is a copy change, so it is proposed here but not bundled into the layout
  diff. It matters because §2.5 bans raw enum codes on screen.
- **Will the ladder's `●`/`○` survive a product review?** They are the only glyphs in the UI and are
  test-pinned; if removed, the "Chosen" label and the state phrases must carry the whole load.

### 10.4 Next implementation step

Write `src/verdict.js` (`cardTone`, `rungView`, `whyLine`, `assumptionLine`) and its unit tests
first — the components can then be assembled against a tested mapping, and every later CSS decision
stays reversible.

