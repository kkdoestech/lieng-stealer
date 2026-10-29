# S1 — PINNED PINBOARD

## 1. Problem

- The results column must read as **notes taped to a dark board** while staying a data instrument: 8 literal test pins (§2.3), every numeral mono and unchanged, no recompute, all copy via `i18n.js`.
- **`transform` is paint-only.** A rotation cannot re-wrap a line, change a width, or alter a text node, so the rotation budget is assert-safe by construction. That is why rotation — not a new DOM — carries the tilt.
- **One DOM is a test law.** `App.test.jsx` renders one DOM in jsdom with no CSS applied; a breakpoint-specific second DOM would duplicate `33,000`, `EV -11,995` and the "nobody calls" phrase and break pins 3–7 at once.
- **Grid, not absolute.** Absolute cards need fixed heights, but the ladder's blocked rows and both ledgers have server-driven heights; and a rotated absolute box is excluded from scroll height, so `390` clips or scrolls sideways. Overlap therefore comes from shared row bands + negative margins + `translate`, never from `position: absolute` on a card.
- Numbers are the product (`DESIGN.md` §1): material and composition carry the scrapbook, not decoration. No gradient, no blur, no emoji, no image, `--radius: 0`.
- Space Grotesk / JetBrains Mono are **not in the repo** — flagged in §9. One `--font-*` pair with system fallbacks, so the app ships before the `woff2` files land.
- Floors: text ≥ `4.5`:`1`, `:focus-visible` on every control, `role="alert"` for errors, no horizontal scroll at `390`, tilts zeroed under `prefers-reduced-motion: reduce`.

## 2. Usage

```jsx
<section className="results-board" aria-label={t.boardAria}>
  <BoardKicker t={t} />                                                    {/* r1, cols 1-6 */}
  {advice && <VerdictNote advice={advice} handEval={handEval} t={t} />}
  {solveData && !handEval && <VerdictEmpty t={t} summary={summary} actionCounts={actionCounts} />}
  {advice && <SizingCard ladder={advice.ladder} chosen={advice.action} kind={advice.kind} t={t} />}
  {summary && <AssumptionSlip text={assumptionLine(t, summary)} t={t} />}
  <StatTabs advice={advice} handEval={handEval} summary={summary} t={t} />
  <CoverageLedger rows={categoryMatrix} t={t} />
  {solveData?.top_hands && <TopHandsLedger hands={solveData.top_hands} t={t} />}
  <NotesDrawer open={isNotesOpen} onToggle={() => setIsNotesOpen(!isNotesOpen)} advice={aiAdvice} loading={isAiLoading} t={t} />
</section>
```
The ladder and assumption line **leave** `.verdict-card` and become grid items; `.verdict-card` survives as the hero note's class (pin 2).

## 3. Shape

```
App.jsx  (state, fetch, abort, lang — unchanged; shrinks ~200 lines)
├─ AppHeader            t, lang, onToggleLang
├─ ControlPanel         (logic unchanged; dark "index card", flat, no tilt)
└─ section.results-board   ← the 12-column grid
   ├─ BoardKicker        t                        .board-kicker > .kicker-rule
   ├─ VerdictNote        advice, handEval, t      .verdict-card.paper.paper--torn + toneClass(advice)
   │  ├─ KindStamp       action, kind, t          .kind-stamp   (null when action === "CHECK")
   │  ├─ TapeStrip       aim                      .tape          (aria-hidden, decor only)
   │  ├─ VerdictHero     advice, handEval, t      .verdict-hero > .verdict-verb | .verdict-figures
   │  └─ WhyNote         sentence                 .verdict-why  (single text node)
   ├─ VerdictEmpty       t, summary, actionCounts .verdict-empty.paper
   ├─ SizingCard         ladder, chosen, kind, t  .ladder-card.paper + toneClass(advice)
   │  ├─ TapeStrip       aim="seam"               .tape--seam
   │  ├─ RungRow ×3      rung, chosen, t          .ladder-rung[.chosen|.rung-blocked]
   │  └─ ThresholdNote   minEdge, foldStep        .ladder-note
   ├─ AssumptionSlip     text, t                  .assumption-slip.paper.paper--torn
   ├─ StatTabs           advice, handEval, summary, t → HudCell ×4 (label, value, sub, tone)  .hud-card
   ├─ CoverageLedger / TopHandsLedger   rows, t   .ledger (dark slab, flat)
   └─ NotesDrawer        open, onToggle, advice, loading, t
```

Pure helpers — no new state anywhere; `App.jsx` only loses lines:

| helper | file | returns |
| :--- | :--- | :--- |
| `formatMoney`, `signedMoney`, `percent`, `wholePercent`, `formatZones` | `format.js` | unchanged |
| `whyLine(t, advice, summary)`, `assumptionLine(t, summary)` | `verdict.js` (moved out of `App.jsx`) | one string each |
| `toneClass(advice)` | `verdict.js` | `kind-value` \| `kind-thin` \| `kind-bluff` \| `kind-none` (CHECK ⇒ `kind-none`) |
| `rungView(rung, chosen, t)` | `verdict.js` | `{ mark, label, amount, ev, stateText }`, `ev` = `"EV " + signedMoney(rung.ev)` **as one string** |
| `stampFor(advice, t)` | `verdict.js` | `{ text }` \| `null` |

Angles, nudges and overlap depths are CSS custom properties, never JSX values.

## 4. Wireframes
### 1360px — 12 columns × `64.8px`, gutter `18px`, board padding `20 / 22 / 28`

```
 340px CONTROLS │ RESULTS BOARD 976px
 (dark, flat)   │ c1    c2    c3    c4    c5    c6    c7  │ c8    c9   c10   c11   c12
 ╔════════════╗ ├──────────────────────────────────────────────────────────────────────────
 ║ INPUTS  [0]║ │ [1] ● PINNED RESULTS ────────                r1 26px, cols 1-6
 ║ pot · bet  ║ │  ╱[5]▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▜  [2] VERDICT NOTE, 562px
 ║ fold·model ║ │ ╱   ▐ RECOMMENDED ACTION     [4] VALUE ▐     7 cols, rot -1.2deg
 ║ hand       ║ │╱    ▐ All in                 +164,064 ▐     translate 0,0, z 3
 ║ [RUN]      ║ │     ▐ As Kh Qd · Q-K-A · Liêng Q-K-A   ▐     origin 50% 0
 ║            ║ │     ▐ You win about 99.5% when called,  ▐     pad 26/40/22/24
 ║ specs      ║ │      ╲▄▄▄▄▄▄ torn edge 9px ▄▄▄▄▄▄▄╱   ┌───────────╲[3] LADDER
 ║            ║ │  ┌[6]▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▜ ╲[7]│ SIZING    ╲ 396px, 5 cols
 ║            ║ │ ╱   ▐ ASSUMPTION                    ▐  ╲  │ ● Small bet ╲ rot +0.9deg
 ║            ║ │╱    ▐ The opponent folds their       ▐   ╲ │   33,000    ╲ translate
 ║            ║ │     ▐ weakest 35% of hands and…      ▐    ╲│ ○ Large bet ╲ -22px, 18px
 ║            ║ │     ╲▄▄▄ torn ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄╱      │     margins ╲ z 4
 ║            ║ │  ┌──────────────┬───────────┬──────────┐ │ We recommend only…│
 ║            ║ │  │[8] Hands bet │ Showdown  │    EV     │ └──────────────────╱
 ║            ║ │  │    71.6%     │   99.5%   │ +164,064  │   ← dark slab, flat, 1-12
 ║            ║ │  └──────────────┴───────────┴──────────┘
 ║            ║ │  ┌ [9] COVERAGE BY CATEGORY ── dark slab, flat, 976px ───────────┐
 ╚════════════╝ │  │ … SÁP / LIÊNG / ĐĨ / ĐIỂM …                                 │
                └──────────────────────────────────────────────────────────────────
```

| # | item | transform | note |
| :-- | :--- | :--- | :--- |
| [1] | board kicker | `rotate(-0.4deg)` on its `2px` rule, width `62%` | a drawn line that stops short; no rotated glyphs |
| [2] | verdict note | `rotate(-1.2deg) translate(0, 0)`, origin `50% 0` | widest, tallest card: the whole angle budget, one rotated plane for all its text |
| [3] | ladder card | `rotate(+0.9deg) translate(-22px, 18px)` | opposite sign crosses the seam; `-22px` dives into the verdict's `40px` end padding; `+18px` kills any shared top edge |
| [4] | kind stamp | `rotate(+2.4deg)`, `top: -15px`, `right: 18px` | 4–9 mono caps; x-height drift `60px × sin2.4° = 2.5px` |
| [5] [7] | tape | `rotate(-3.5deg)`, `104 × 26`, `top: -13px` | no glyphs — the only `3.5deg` on the page; the seam strip holds two sheets |
| [6] | assumption slip | `rotate(-0.6deg) translate(6px, 0)`, `margin-block-start: -26px` | slides **under** the verdict's torn edge (z 2 < 3) |
| [8] [9] | stat strip, ledgers | `none` | reference data is etched on the board; only the answer is paper |

### 390px — one column, `366px` inside, padding `14`: **no rotation, no nudges**

```
 ┌────────────────────────────────┐
 │ ● PINNED RESULTS ────────       │  [1] rule only, -0.4deg
 │ ╱▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀╜   │  [2] rot 0, translate 0,0, inset 0
 │  ▐ RECOMMENDED ACTION  [4] VALUE ▐  [4] stamp rot 0
 │  ▐ All in                     ▐ │
 │  ▐ As Kh Qd · Q-K-A           ▐ │
 │   ╲▄▄▄ torn ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄╱    │
 │ ┌▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▜   │  [3] rot 0, translate 0,0, inset 8px
 │ │ SIZING LADDER               │  │      margin-block-start -26px
 │ │ ● Small bet  33,000    EV … │  │
 │ │ ○ Large bet  75,000    EV … │  │
 │ │ We recommend only when…     │  │
 │ └─────────────────────────────╜  │
 │ ┌▛▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▜   │  [6] rot 0, inset 2px
 │ │ ASSUMPTION — the opponent folds │
 │ │ their weakest 35% of hands…    │
 │ └─────────────────────────────╜  │
 │ ┌ Hands bet │ Showdown │ EV ┐   │  [8] flat dark slab, 2×2 below 640
 │ └ COVERAGE ─ table scrolls ──┘   │  [9]
 └────────────────────────────────┘
```
At `390` the stagger survives as **asymmetric insets** (`0 / 8px / 2px` inline-start): `420 × sin(0.6°) = 4.4px` of bbox growth no longer fits a 12px gutter once a card is full-bleed. Nothing is centered at any width.

## 5. Styling plan
### 5.1 Tokens (`index.css`) — page / paper / ink / accents

```css
:root {
  --page: #0a0a0a;  --page-raised: #121110;  --page-lift: #191614;  --grid-line: #262220;
  /* paper: cream notes, plus the under-sheet that acts as the shadow */
  --paper: #efe7d6;  --paper-2: #e4d9c2;  --paper-edge: #c9bda1;  --paper-rule: #cdbfa4;
  --ink: #17130f;  --ink-muted: #5b5147;  --ink-faint: #8a7d6c;   /* 15.4 / 6.3 / 3.6 on paper */
  /* accents: full vibrance is a FILL; ink on paper uses the darkened twin */
  --value: #3fb27f;  --value-ink: #1a6b43;   /* 5.3:1 on paper */
  --thin:  #d0a15a;  --thin-ink:  #8a5a12;   /* 4.8:1 on paper */
  --bluff: #8b5cf6;  --bluff-ink: #6b3fd4;   /* 5.2:1 on paper, 4.7:1 on page */
  --check: #8a9199;  --check-ink: #4b5158;
  --stamp-ink: #0b0b0b;                      /* on the solid block: 7.2 / 8.2 / 4.6 / 6.2:1 */
  --tape-on-paper: #cfc0a0;  --marker: #f2d06b;  --marker-soft: #f7e3a1;  --radius: 0px;
  --bad: #d0685e;  --focus: #6e93b8;  --focus-on-paper: #4a6f96;
  --font-ui: "Space Grotesk", "Segoe UI Variable Text", "Segoe UI", -apple-system, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "JetBrains Mono", "Cascadia Mono", "SF Mono", Consolas, "Liberation Mono", monospace;
  /* every angle is a token, so one media query zeroes the tilt system */
  --tilt-verdict: -1.2deg;  --tilt-ladder: 0.9deg;  --tilt-slip: -0.6deg;
  --tilt-stamp: 2.4deg;  --tilt-tape: -3.5deg;  --tilt-rule: -0.4deg;
  --nudge-ladder: -22px;  --nudge-ladder-y: 18px;  --nudge-slip: 6px;
  --overlap-seam: 26px;  --edge-gutter: 0px;  --card-bleed: 22px;
}
```

**Paper vs page: off-white notes on the near-black page.** (a) A physical shadow needs a lighter surface: the note's shadow is a *second cream sheet* (`--paper-edge`), which would be invisible under a charcoal note; a dark note on `#0a0a0a` is seen by its border alone, which reads as a UI panel. (b) Tilt is perceived from edges: a `15.5`:`1` cream edge makes a `1.2deg` tilt legible, a `#1b1814` edge does not. (c) `11–13px` text: `#17130f` on `#efe7d6` is `15.4`:`1` and at `-webkit-font-smoothing: auto` keeps stroke weight better than light-on-dark small mono. Accents stay pops: cream is neutral, each accent owns at most a `104 × 26` tape, a `~72 × 20` stamp or a `3px` rule, and the board stays the majority surface (controls, gutters, ledgers).

### 5.2 The board grid (the layout engine)

```css
.results-board {
  display: grid;  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-rows:
    [kicker-r] minmax(26px, auto)  [note-r]  minmax(0, auto)  [band-r] minmax(64px, auto)
    [slip-r]   minmax(0, auto)     [hud-r]   minmax(0, auto)  [cov-r]  minmax(0, auto)
    [top-r]    minmax(0, auto)     [notes-r] minmax(0, auto);
  grid-template-areas:
    "kick kick kick kick kick kick  .    .    .    .    .    ."
    "ver  ver  ver  ver  ver  ver   ver  lad  lad  lad  lad  lad"
    "ver  ver  ver  ver  ver  ver   ver  lad  lad  lad  lad  lad"
    "sli  sli  sli  sli  sli  .     .    lad  lad  lad  lad  lad"
    "hud  hud  hud  hud  hud  hud   hud  hud  hud  hud  hud  hud"
    "cov  cov  cov  cov  cov  cov   cov  cov  cov  cov  cov  cov"
    "top  top  top  top  top  top   top  top  top  top  top  top"
    "not  not  not  not  not  not   not  not  not  not  not  not";
  column-gap: 18px;  row-gap: 0;  align-content: start;
  padding: 20px 22px 28px;  background: var(--page);
}
.results-board > .verdict-card     { grid-area: ver; z-index: 3; }
.results-board > .ladder-card      { grid-area: lad; z-index: 4; }
.results-board > .assumption-slip  { grid-area: sli; z-index: 2; }
.results-board > .hud-metrics-grid { grid-area: hud; z-index: 1; }
```
`ver` spans rows 2–3 and `lad` spans rows 2–4: the two notes **share a row band**, so the ladder's own height sizes row 4 for the slip. No card is ever `position: absolute`; only collage furniture inside a card is.

### 5.3 Stagger, overlap, and the anti-clipping rule

```css
.verdict-card, .ladder-card, .assumption-slip {
  position: relative;             /* tape / stamp / torn edge are absolute INSIDE the card */
  transform-origin: 50% 0;        /* rotate about the pin at the top edge */
  transform: rotate(var(--tilt)) translate(var(--nx, 0), var(--ny, 0)); }
.verdict-card    { --tilt: var(--tilt-verdict); padding: 26px 40px 22px 24px; }
.ladder-card     { --tilt: var(--tilt-ladder); --nx: var(--nudge-ladder); --ny: var(--nudge-ladder-y); padding: 30px 20px 26px; }
.assumption-slip { --tilt: var(--tilt-slip); --nx: var(--nudge-slip);
                   margin-block-start: calc(-1 * var(--overlap-seam)); padding: 32px 22px 20px; }
```

Overlap is three deliberate devices: (i) the shared row band; (ii) `--nudge-ladder: -22px`, so the ladder's left edge lands inside the verdict's `40px` end padding and never on its EV; (iii) `margin-block-start: -26px` on the slip, whose top `32px` is tape and blank paper only. **Anti-clipping rule:** a card that dives into a neighbour reserves `padding ≥ overlap + 10px` on the diving edge and puts only tape, a stamp or paper there; every numeral sits ≥ `20px` inside its own box. Rotation slack is budgeted too: `padding-inline-end ≥ bleed + h·sin|θ|/2 + 2px` ⇒ `22 + 430 × sin1.2° / 2 + 2 ≈ 28.5`, and `40` clears it.

### 5.4 Material recipes (flat fill + `clip-path` + `border` + zero-blur shadow)

```css
.paper {                                  /* ink edge on three sides, torn bottom, second sheet below */
  background: var(--paper); color: var(--ink); border: 2px solid var(--ink); border-bottom: 0;
  box-shadow: 6px 7px 0 var(--paper-edge); -webkit-font-smoothing: auto; }
.paper--torn::after {                     /* 22 teeth, alternating 18-100% Y; no image, no gradient */
  content: ""; position: absolute; left: 0; right: 0; bottom: -8px; height: 9px; background: var(--paper);
  clip-path: polygon(0 0, 100% 0, 100% 34%, 95% 100%, 90% 28%, 85% 96%, 80% 22%, 75% 100%, 70% 30%,
    65% 94%, 60% 24%, 55% 100%, 50% 28%, 45% 92%, 40% 22%, 35% 98%, 30% 26%, 25% 90%, 20% 20%,
    15% 100%, 10% 28%, 5% 92%, 0 22%); }
.ledger, .hud-metrics-grid {              /* dark slab: its shadow is the page one step LIGHTER */
  background: var(--page-raised); border: 1px solid var(--grid-line); box-shadow: 5px 5px 0 var(--page-lift); }
.tape {                                   /* flat tone, ragged ends, no glyph, no gradient */
  position: absolute; z-index: 5; width: 104px; height: 26px; background: var(--tape-on-paper);
  border-inline: 1px solid #b8a982; transform: rotate(var(--tilt-tape)); opacity: 0.95;
  clip-path: polygon(0 8%, 3% 0, 97% 0, 100% 10%, 98% 38%, 100% 66%, 97% 94%, 94% 100%, 6% 100%,
    3% 92%, 0 64%, 2% 36%); }
.tape--cap  { top: -13px; left: 50%; margin-left: -52px; }
.tape--seam { top: -13px; left: -18px; }  /* one strip, two sheets */
.mark {                                   /* highlighter: a flat block, stroke overshoots one side */
  position: relative; z-index: 0; background: var(--marker); color: var(--ink);
  padding: 0 3px 1px; margin: 0 -3px; box-decoration-break: clone; }
.mark::before { content: ""; position: absolute; z-index: -1; inset: -2px -5px -1px -2px;
                background: var(--marker); }
.mark--soft { background: var(--marker-soft); }
.kind-stamp {                             /* rubber stamp, solid accent block, 15px over the edge */
  position: absolute; top: -15px; right: 18px; padding: 2px 7px; color: var(--stamp-ink);
  background: var(--kind, var(--check)); border: 2px solid var(--kind, var(--check));
  transform: rotate(var(--tilt-stamp)); font: 500 11px/1.2 var(--font-mono);
  letter-spacing: 0.14em; text-transform: uppercase; }
.kind-value { --kind: var(--value); --kind-ink: var(--value-ink); }
.kind-thin  { --kind: var(--thin);  --kind-ink: var(--thin-ink); }
.kind-bluff { --kind: var(--bluff); --kind-ink: var(--bluff-ink); }
.kind-none  { --kind: var(--check); --kind-ink: var(--check-ink); }
.kicker-rule::after { content: ""; display: block; width: 62%; height: 2px; margin-top: 6px;
                      background: var(--ink); transform: rotate(var(--tilt-rule)); }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.paper :focus-visible { outline-color: var(--focus-on-paper); }
```

Motif budget — a scrapbook stops reading as one when everything is taped: **3 tape strips max** (verdict cap, verdict↔ladder seam, slip), **1 stamp**, **1 torn edge per note**, **≤2 marker highlights per screen** (the wordmark, and the "at your bet size" aside). Banned as noise: tape on ledgers or the control panel, torn edges on dark slabs, marker on numerals, rotation on any table cell, blur of any kind, stacked stamps.

### 5.5 Ladder rows inside a rotated card

The whole card — column heads and numbers together — carries exactly one `rotate(0.9deg)`; nothing nested is rotated, so the mono digit grid stays internally aligned and no line re-wraps. Rows are real rows: `.ladder-strip` becomes one column and each `.ladder-rung` its own 3-column grid, so CSS changes and the DOM does not.

```css
.ladder-strip { display: grid; grid-template-columns: minmax(0, 1fr); row-gap: 0; }
.ladder-rung { display: grid; grid-template-columns: minmax(0, 1fr) 78px 96px; column-gap: 10px;
               align-items: baseline; padding: 9px 0; border-top: 1px solid var(--paper-rule); }
.ladder-head    { grid-column: 1; }
.ladder-amount  { grid-column: 2; text-align: right; }   /* tabular mono, one right edge */
.ladder-ev      { grid-column: 3; text-align: right; }   /* "EV " + signed, ONE text node */
.ladder-blocked { grid-column: 1 / -1; font-size: 11px; color: var(--ink-muted); }
.ladder-rung.chosen { background: var(--paper-2); border-left: 3px solid var(--kind); padding-left: 9px; }
.ladder-rung.chosen .ladder-label { color: var(--ink); font-weight: 600; }
.ladder-rung.rung-blocked .ladder-amount, .ladder-rung.rung-blocked .ladder-ev { color: var(--ink-muted); }
```

### 5.6 Type scale (self-hosted `woff2`, `font-display: swap`, system fallbacks)

| step | family | px | wt | tracking | lh | used for |
| :--- | :--- | ---: | ---: | :--- | ---: | :--- |
| `stamp` | mono | `11` | `500` | `0.14em` | `1.2` | kind stamp, kickers, column heads, units, blocked phrase |
| `verb` | UI | `30` | `600` | `-0.02em` | `1.1` | the `<h2>` action verb |
| `figure-lg` | mono | `34` | `600` | `-0.02em` | `1.0` | hero EV |
| `figure` | mono | `13` | `500` | `0` | `1.25` | ladder numbers, hud values, ledger numerals |
| `note` | UI | `12.5` | `400` | `0` | `1.55` | why sentence, empty-state body, assumption (`12`) |

Nothing below `11px` (the old `10px` labels retire). Every numeral: `--font-mono`, `tabular-nums`, right-aligned. Spacing `2 4 6 8 12 16 20 26 36`.

### 5.7 Class inventory per component

| component | classes |
| :--- | :--- |
| board | `.results-board`, `.board-kicker`, `.kicker-rule` |
| material | `.paper`, `.paper--torn`, `.tape`, `.tape--cap`, `.tape--seam`, `.mark`, `.mark--soft`, `.kind-value/-thin/-bluff/-none` |
| VerdictNote | `.verdict-card` (kept), `.verdict-empty`, `.kind-stamp` (replaces `.kind-chip`), `.verdict-hero`, `.verdict-verb`, `.verdict-label`, `.verdict-title`, `.verdict-meta`, `.holding-tag/-sep/-score`, `.verdict-figures`, `.verdict-ev`, `.ev-currency`, `.verdict-breakeven`, `.mono-green`, `.verdict-why` |
| SizingCard | `.ladder-card`, `.ladder-strip`, `.ladder-rung[.chosen|.rung-blocked]`, `.ladder-head`, `.ladder-mark`, `.ladder-label`, `.ladder-amount`, `.ladder-ev`, `.ladder-blocked`, `.ladder-note` |
| AssumptionSlip | `.assumption-slip`, `.assumption-label`, `.assumption-text` (replaces `.verdict-assumption`) |
| StatTabs | `.hud-metrics-grid` (kept), `.hud-card` (kept — pin 7), `.hud-value`, `.hud-phrase`, `.hud-subtext`, `.green-metric` |
| ledgers, drawer | `.ledger`, `.table-wrapper`, `.tactical-table`, `.mono-num`, `.mono-canonical`, `.dim-cell`, `.desc-cell`, `.bold-num`, `.chip-full`, `.chip-zero`, `.notes-drawer-container`, `.drawer-toggle-btn`, `.drawer-content`, `.telemetry-body` |

Removed: `.verdict-banner`, `.verdict-col-right`, `.verdict-assumption`, `.kind-chip`.

### 5.8 Breakpoints and comfort

```css
@media (max-width: 1024px) {
  .results-board { grid-template-columns: minmax(0, 1fr); grid-template-rows: repeat(8, minmax(0, auto));
    grid-template-areas: "kick" "ver" "lad" "sli" "hud" "cov" "top" "not";
    --tilt-verdict: -0.6deg; --tilt-ladder: 0.5deg; --tilt-slip: -0.4deg;
    --nudge-ladder: 14px; --nudge-ladder-y: 0; --nudge-slip: 26px; --edge-gutter: 12px; }
  .paper { max-width: calc(100% - 2 * var(--edge-gutter)); }  /* 420·sin0.6° = 4.4px << 12px */
}
@media (max-width: 640px) {
  .results-board { padding: 14px 14px 22px; --overlap-seam: 0px; --nudge-ladder: 0px; --nudge-slip: 0px; }
  .verdict-card, .ladder-card, .assumption-slip { transform: none; }  /* no AA smearing at small size */
  .verdict-card { margin-inline-start: 0; }  .ladder-card { margin-inline-start: 8px; }
  .assumption-slip { margin-inline-start: 2px; }                      /* asymmetry without rotation */
  .hud-metrics-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .results-board { --tilt-verdict: 0deg; --tilt-ladder: 0deg; --tilt-slip: 0deg;
                   --tilt-stamp: 0deg; --tilt-tape: 0deg; --tilt-rule: 0deg; }
}
```

No `transition` is ever declared on `transform`, so nothing animates; reduced motion still zeroes the angles because a static tilt is a comfort preference.

### 5.9 Violet for Bluff

`--bluff: #8b5cf6` (`4.7`:`1` on `--page`), paper twin `--bluff-ink: #6b3fd4` (`5.2`:`1`). **May appear only:** the kind stamp's solid block (near-black caps at `4.6`:`1`), the verdict note's `3px` start rule, the chosen rung's `3px` rule, one tape strip on a bluff verdict, and the kind word in the top-hands ledger. **May not appear:** on the assumption slip, any input or button, any error box or `role="alert"` region, any area larger than `104 × 26`, or the same element as `--bad`. It cannot read as an error: far in hue from `#d0685e` and from the focus blue; always inside the same rubber-stamp form the emerald and amber use (form says "category"); the word Bluff / Cược hù is always inside that block; and a CHECK renders no stamp at all.

### 5.10 States

| state | treatment |
| :--- | :--- |
| loading / re-run | previous note stays; `t.solveBusy` on the disabled button; no skeleton, no spinner |
| error | `role="alert"` slab in `--bad` under the button; verdict note absent |
| no hand | `.verdict-empty.paper` — same torn geometry, `--check` rule, heading `t.noHandTitle` |
| `win_rate_defined === false` | phrase in exactly **two** text nodes: `.verdict-why` and `.hud-value`; the hero never prints `0.0%` |
| `action === CHECK` | `kind-none` tone, no stamp, demoted EV figure, no rung carries `chosen` |
| negative EV rung | signed numeral in `--ink-muted`; never red, never struck |

### 5.11 Test pins — this design changes **no** assertion

Neither `:316` nor `:330–336` needs an edit, and nothing else does.

| pin | how it holds |
| :--- | :--- |
| 1 verb `<h2>` | `.verdict-title` stays an `<h2>` whose only child is `t.actionLabel[action]`; the stamp is an absolutely positioned **sibling** |
| 2 no "Bluff" on a CHECK | `stampFor()` returns `null` for CHECK; `.verdict-card` keeps its class name |
| 3 `33,000` once | the amount renders **only** in `.ladder-amount`; the note never repeats it |
| 4 `chosen` / `rung-blocked` / `●` `○` | class names and glyphs unchanged; only the row grid around them changes |
| 5 `EV -11,995` contiguous | `rungView.ev` is one string `"EV " + signedMoney(...)` in one element; the ASCII hyphen still comes from `formatMoney` |
| 6 "nobody calls" ×2 | one in `.verdict-why`, one in `.hud-value`; slip and hero add none |
| 7 `.hud-card` | class kept verbatim on the showdown-equity cell, holding the phrase and no `0.0%` |
| 8 direct text nodes | each pinned string is the sole text child of its element; decorations are pseudo-elements or `aria-hidden` spans, which add no text |

New i18n keys (names only): `boardAria`, `boardTag`, `sizingTag`, `assumptionTag`, `chosenTag`, `markEligibleAria`, `markBlockedAria`, `notesTag`. No §2.1 field is recomputed and no displayed number changes.

## 6. Tradeoffs accepted

- We accept **light paper on a `#0a0a0a` page** in exchange for tilt and shadow being visible at all.
- We accept **darkened accent twins for ink on paper** in exchange for `4.5`:`1` small text, at two tokens per accent.
- We accept **moving the ladder and assumption line out of `.verdict-card`** in exchange for three independently placed notes; the card stops being one atomic block.
- We accept **only `±1.2deg` of rotation** in exchange for zero reflow, zero clipping and untouched assertions.
- We accept **flat dark ledgers** in exchange for keeping cream a minority surface and the accents as pops.
- We accept **a first-step font dependency** (two `woff2` files) in exchange for the brief's type voice, with same-day fallbacks.
- We accept **`0.9deg` under the ladder's numerals** in exchange for rows that read as pasted paper; `≤640` buys crispness back.
- We accept **a 22-vertex `clip-path`** in exchange for a torn edge with no image request.

## 7. Alternatives considered

- **Positioned collage canvas** (`position: relative` board, every note `position: absolute` at hand-tuned offsets). The obvious scrapbook route; it loses three times. Heights are server-driven (the ladder's blocked rows, both ledgers), so absolute cards need magic heights that break on re-render; a rotated absolute box adds nothing to scroll height, so `390` clips or scrolls sideways; and honest overlap numbers would want a JS measure effect — new state in `App.jsx`, which is forbidden. Grid + `translate` reproduces every overlap it can produce.
- **Dark charcoal notes with cream ink.** The safer cousin of today's tokens, and it kept the accents at their bright contrast. It lost on materiality: on `#0a0a0a` a `#1b1814` note is seen by its border alone, so a `1.2deg` tilt reads as a rendering bug, and a zero-blur shadow has no lighter surface to fall on.
- **One cream card with its three sections rotated inside it.** Cheapest diff, but rotating a child inside a rotated parent stacks angles on the same glyphs, and one card cannot be staggered against itself — the composition would still be a single tilted rectangle, i.e. a centered stack.
- **A row table for the whole board** (`display: table`, rotated rows). Dies like the old strip: a table cannot express a 7/5 split that becomes 12/0 at `1024`.

## 8. Open questions and risks

- Do the two `woff2` files land in the same change, or does the first PR ship fallbacks behind `--font-*` and the fonts follow? The layout is identical either way; only the voice changes.
- Is `7`:`5` the right verdict-to-ladder split at `1360`? The longest EN why-sentence (`CHECK_ASSUMPTION_FRAGILE`, `118` chars) pushes the note to `5` lines — should it become `8`:`4`, and does the ladder then hold three rows without wrapping a label?
- At `≤640` rotation is removed entirely. Is asymmetric inset (`0 / 8 / 2`) enough to keep the mobile page reading as a scrapbook, or should `±0.25deg` survive?
- The `-22px` ladder nudge assumes the verdict keeps `40px` of end padding. Safe once longer VI words are in, or should `--card-bleed` drop to `16px`?
- Should the ladder show `worst_ev_ratio`? It is the number the policy gates on, but it is a **new** displayed number and this package promises the displayed set is unchanged. Deferred.
- `-webkit-font-smoothing: auto` on paper is craft, not standard; on Linux fallbacks dark-on-light may look heavier than the mock. Force `antialiased` instead?
- Does the stamp hanging `15px` above the note survive a `1024–1200` width where the kicker strip sits closer?

## 9. Next implementation step

Extract `whyLine` / `assumptionLine` into `src/verdict.js` with `toneClass`, `rungView` and `stampFor`, add the two `woff2` files and the `--paper` / `--ink` / `--tilt-*` token block, then write `.results-board`'s grid template and the three `.paper` notes against the wireframe before touching a colour on the ledgers.
