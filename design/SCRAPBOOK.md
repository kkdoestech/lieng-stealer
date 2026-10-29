# SCRAPBOOK.MD: the "dark pastel scrapbook" overhaul

Supersedes the visual layer of `DESIGN.md` (dark-saas) **and** the cream-paper direction in the
earlier draft of this file. User override, now the governing brief: keep the dark theme, but make it
the exact playful scrapbook of `tiboandpoteto.com` — **emojis yes, doodles yes, rotations yes**.

Functional laws still bind: copy via `i18n.js`, numbers unchanged, no recomputed EV, no fake status,
and **no test edits** (see §8). The overhaul is presentation only; `App.jsx` keeps its state and
fetching untouched.

The one-line test:

> Squint: a dark desk with a dotted-grid mat, a dark-rose polaroid, a dark-mustard sticky note and a
> dark-violet scrap tucked onto it — and the big mono EV still lines up perfectly.

---

## 1. Design position

1. **Dark scrapbook, not dark SaaS.** Near-black canvas with a subtle dotted-paper grid; the notes on
   it are *dark pastel* paper — rose, mustard, violet — with bright thick borders and hard black
   drop shadows. The page is still dark; the notes are still colorful.
2. **Unhinged layout, disciplined numbers.** Everything is tilted, taped, overlapping, doodled — but
   every numeral is JetBrains Mono on a shared right edge, so the data stays readable.
3. **Emojis are labels, not claims.** Emojis mark the section kickers (🃏, 📉, 💖, 🤖) and a few
   sticker accents. They never appear in a number, a sentence, or a test-pinned string.
4. **Three neon accents, three pastel notes.** Emerald `#00ffa3`, amber `#ffcc00`, violet `#c96bff`
   are the only semantic colours, and they are *neon*: solid stamp fills, 2px rules, tape strips,
   marker underlines. The card pastels are decorative paper tints, not semantics.
5. **Handmade type, monospace data.** Caveat + Patrick Hand for everything human; JetBrains Mono
   **only** for numerals. That single rule is what keeps the joke from eating the tool.
6. **Raw.** `border-radius: 0` (or a hand-cut 2px at most on stickers), 2–4px solid bright borders,
   `box-shadow: 4px 4px 0 #000`, no gradients (the dotted mat is a dot pattern, not a colour fade),
   no blur.

---

## 2. Material system

### 2.1 Tokens

```css
:root {
  /* page: dark desk with a dotted scrapbook mat */
  --page:        #121212;
  --dot:         #2a2a2a;      /* dot grid, 22px pitch, 1.2px dots */
  --dot-strong:  #343434;      /* larger 110px pitch dots */
  --carbon:      #1a1a1a;      /* dark data slabs: stat strip, ledgers */
  --carbon-2:    #202020;
  --hair-dark:   #343434;

  /* dark pastel paper: one tint per component */
  --paper-rose:    #2a1722;    /* verdict polaroid */
  --paper-mustard: #2b2513;    /* sizing sticky */
  --paper-violet:  #221a30;    /* assumption scrap */
  --paper-rose-2:  #331c2a;    /* polaroid chin, chosen row */
  --paper-lit:     #3a2433;    /* hover / selected scrap */

  /* bright edges on dark paper */
  --edge-bright: #f2f2f2;      /* thick card border */
  --edge-bright-2: #d8d8d8;
  --ink:         #f6f2ec;      /* text on pastel paper: 15.1:1 on rose */
  --ink-muted:   #c4b8bf;      /* 8.8:1 */
  --ink-faint:   #9c8f96;      /* non-essential only */

  /* semantic neon (only place colour means something) */
  --value: #00ffa3;            /* black text on it 15.1:1 */
  --thin:  #ffcc00;            /* black 13.3:1 */
  --bluff: #c96bff;            /* black 6.7:1 */
  --check: #9aa0a6;            /* no-action gray */
  --bad:   #ff5c5c;
  --stamp-ink: #080808;

  /* stationery */
  --tape:        #d9c9a3;      /* cream washi */
  --tape-2:      #c9b6d8;      /* lilac washi */
  --tape-edge:   #b8a982;
  --marker:      #ffcc00;      /* neon highlighter — only under a non-numeric word */
  --hard:        #000000;      /* the mandated hard shadow */
  --focus:       #f2f2f2;      /* focus ring on dark */
  --focus-paper: #ffffff;

  --radius: 0px;
  --shadow-hard: 4px 4px 0 var(--hard);
  --shadow-hard-lg: 6px 6px 0 var(--hard);

  --font-hand:  "Caveat", "Segoe Script", "Comic Sans MS", cursive;
  --font-print: "Patrick Hand", "Comic Sans MS", "Segoe Print", cursive;
  --font-mono:  "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;

  /* every angle is a token: one media query flattens the whole tilt system */
  --tilt-verdict: -2deg;
  --tilt-ladder:  1.5deg;
  --tilt-slip:   -1.5deg;
  --tilt-stamp:   3deg;
  --tilt-tape:   -6deg;
  --tilt-doodle:  8deg;
  --nudge-ladder-x: -18px;
  --nudge-ladder-y:  16px;
  --nudge-slip-x:     8px;
  --overlap-seam:    22px;
}
```

Rules:

- **The dotted mat is a pattern, not a gradient:** two `radial-gradient(circle, var(--dot) 1.2px,
  transparent 1.3px)` layers at 22px and 110px pitch over `--page`. No colour blending.
- **Card pastels are decorative.** A rose card does not mean Value; the neon stamp does. The three
  pastels are assigned per component, not per kind, so the layout stays legible across states.
- **Bright borders + pure-black hard shadow** are the physical tell. On `#121212` the shadow is
  subtle (that is what "hard, solid" means here); the 3–4px bright border does the lifting.
- **Neon is a fill, never body text.** Neon on pastel card = low contrast for 11px text; neon appears
  as stamp backgrounds (black `--stamp-ink` text), 2px rules, tape and marker. The one exception:
  neon `--value` may underline a number in the ladder (2px), never set its glyphs.
- Emojis are text glyphs in labels only. Never inside a `<h2>`, a numeric cell, or a pinned sentence.
- No gradients, no blur, no glass. Torn edges, folded corners and washi ends are `clip-path` +
  solid borders. (`radial-gradient` above is a dot pattern; keep it to the two mat layers.)

### 2.2 Surfaces by component

| Element | Surface | Border | Shadow |
| :--- | :--- | :--- | :--- |
| Verdict **polaroid** | `--paper-rose` + bright chin strip | `4px solid var(--edge-bright)` | `6px 6px 0 #000` |
| Sizing **sticky note** | `--paper-mustard` | `3px solid var(--edge-bright)` | `4px 4px 0 #000` |
| Assumption **scrap** | `--paper-violet` | `2px solid var(--edge-bright-2)` | `4px 4px 0 #000` |
| Stat strip | `--carbon` | `1px solid var(--hair-dark)` | `4px 4px 0 #000` |
| Ledger slabs (tables) | `--carbon` | `1px solid var(--hair-dark)` | `4px 4px 0 #000` |
| Control desk | `--page` | separated by a 2px `--hair-dark` rule | — |

---

## 3. Typography

Three faces, and one hard rule: **monospace only for numerals.**

| Voice | Face | Carries |
| :--- | :--- | :--- |
| Script display | **Caveat** 600/700 | wordmark, action verb, section titles, the CHOSEN stamp, big doodle labels |
| Hand print | **Patrick Hand** 400 | kickers/labels, body prose, assumption sentence, notes, ledger headers |
| Data | **JetBrains Mono** 400/500/600 | **every numeral**: EV, win rate, amounts, ladder EVs, worst-of-3, deltas, percentages, table numbers, ids |

Self-hosted (offline app), OFL; **verify Vietnamese glyph coverage** (`ĐĨ`, `SÁP`, `Cược hù`) before
merge. Fallbacks are metric-safe, so the layout holds if the fonts are not yet in the repo:

```css
--font-hand:  "Caveat", "Segoe Script", "Comic Sans MS", cursive;
--font-print: "Patrick Hand", "Comic Sans MS", "Segoe Print", cursive;
--font-mono:  "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
```

| Step | Family | Size / weight / tracking | Use |
| :--- | :--- | :--- | :--- |
| `wordmark` | Caveat | 30 / 700 / 0.02em | header |
| `verb` | Caveat | 56 / 700 / 0 | action `<h2>` |
| `ev` | JetBrains Mono | 46 / 600 / -0.03em | hero EV — largest number on the page |
| `rate` | JetBrains Mono | 24 / 500 / -0.01em | win rate |
| `card-title` | Caveat | 30 / 700 / 0 | "Sizing ladder 📉" |
| `kicker` | Patrick Hand | 13 / 400 / 0.06em uppercase | 🃏 RECOMMENDED ACTION, stamps, column heads |
| `figure` | JetBrains Mono | 14 / 500 / 0 | ladder and ledger numerals |
| `body` | Patrick Hand | 15 / 400 / 0 / 1.45 | why sentence, assumption, notes |
| `small` | Patrick Hand | 13 / 400 / 0 / 1.4 | captions, thresholds |
| `micro` | Patrick Hand | 12 / 400 / 0.02em | units, meta |

Hard rules: no numeral outside JetBrains Mono; no 10px text; Caveat never used for a number or a
long body paragraph; the EV remains the single largest object.

---

## 4. Composition

### 4.1 The desk

`#121212` + two dot-pattern layers. The results column is a 12-column board; the three notes are
separate grid items with their own tilt and nudge. Overlap comes from shared row bands and negative
margins — **never** from `position: absolute` on a card (an absolute rotated card contributes no
scroll height, so it clips at 390).

```css
.results-board {
  position: relative;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-rows:
    [kick-r] minmax(30px, auto) [note-r] minmax(0, auto) [band-r] minmax(0, auto)
    [slip-r] minmax(0, auto) [hud-r] minmax(0, auto) [cov-r] minmax(0, auto)
    [top-r]  minmax(0, auto) [notes-r] minmax(0, auto);
  grid-template-areas:
    "kick kick kick kick kick kick  .    .    .    .    .    ."
    "ver  ver  ver  ver  ver  ver   ver  lad  lad  lad  lad  lad"
    "ver  ver  ver  ver  ver  ver   ver  lad  lad  lad  lad  lad"
    "sli  sli  sli  sli  sli  .     .    lad  lad  lad  lad  lad"
    "hud  hud  hud  hud  hud  hud   hud  hud  hud  hud  hud  hud"
    "cov  cov  cov  cov  cov  cov   cov  cov  cov  cov  cov  cov"
    "top  top  top  top  top  top   top  top  top  top  top  top"
    "not  not  not  not  not  not   not  not  not  not  not  not";
  column-gap: 18px; row-gap: 0; align-content: start;
  padding: 22px 22px 30px;
}
.results-board > .verdict-card    { grid-area: ver; z-index: 3; }
.results-board > .ladder-card     { grid-area: lad; z-index: 4; }
.results-board > .assumption-slip { grid-area: sli; z-index: 2; }
.results-board > .hud-strip       { grid-area: hud; z-index: 1; }
```

### 4.2 Tilt, stagger, overlap

```css
.verdict-card, .ladder-card, .assumption-slip {
  position: relative;
  transform-origin: 50% 8%;
  transform: rotate(var(--tilt)) translate(var(--nx, 0), var(--ny, 0));
}
.verdict-card    { --tilt: var(--tilt-verdict); padding: 24px 30px 0; }
.ladder-card     { --tilt: var(--tilt-ladder);
                   --nx: var(--nudge-ladder-x); --ny: var(--nudge-ladder-y);
                   padding: 28px 20px 22px; }
.assumption-slip { --tilt: var(--tilt-slip); --nx: var(--nudge-slip-x);
                   margin-block-start: calc(-1 * var(--overlap-seam));
                   padding: 26px 20px 18px; }
```

- Verdict polaroid: 7 of 12 columns, rotate **−2°**, taped at the top, bright 4px border, and a
  polaroid chin along the bottom holding the hand line.
- Sizing sticky: 5 columns, rotate **+1.5°**, nudged `(-18px, 16px)` so its top-left corner crosses the
  verdict's bright border — the two notes share a row band, so the sticky's height sizes the slip's row.
- Assumption scrap: 5 columns, rotate **−1.5°**, `margin-top: -22px` so it slides *under* the verdict
  polaroid's bottom edge (z 2 < 3). Only its tape band is hidden.
- Stat strip and ledgers: **straight**, dark carbon, hard shadow. The straight dark data layer is the
  foil that makes the tilted pastel notes read as paper.

**Anti-clipping:** padding ≥ overlap + 10px on any diving edge; numerals stay ≥16px inside their own
box; the sticky's numerals are lowest sheet + highest z (4). Rotation slack:
`padding-inline-end ≥ 22 + h·sin|θ|/2 + 2` (verdict at 46px EV: 22 + 430·sin2°/2 + 2 ≈ 32; padding 30 +
the polaroid's inner padding clears it).

### 4.3 Responsive

```css
@media (max-width: 1279px) {
  :root { --tilt-verdict: -1.5deg; --tilt-ladder: 1.1deg; --tilt-slip: -1.1deg; }
}
@media (max-width: 1024px) {
  .results-board { grid-template-columns: 1fr;
    grid-template-areas: "ver" "lad" "sli" "hud" "cov" "top" "not"; }
  .verdict-card    { transform: rotate(-1.2deg); margin-inline-end: 5%; }
  .ladder-card     { transform: rotate(1deg);   margin: -20px 0 0 4%; }
  .assumption-slip { transform: rotate(-1deg);  margin: -14px 7% 0 0; }
}
@media (max-width: 640px) {          /* straighten: legibility beats tilt on a phone */
  .verdict-card, .ladder-card, .assumption-slip,
  .tape, .kind-stamp, .doodle { transform: none; }
  .verdict-card { margin: 0; }
  .ladder-card  { margin: 14px 0 0; }
  .assumption-slip { margin: 10px 0 0; }
  .kind-stamp { position: static; display: inline-block; margin-bottom: 8px; }
  /* type: ev 46→34, verb 56→38, rate 24→20, figures 14→13 */
}
@media (prefers-reduced-motion: reduce) {
  .verdict-card, .ladder-card, .assumption-slip,
  .tape, .kind-stamp, .doodle { transform: none; }
}
```

One DOM at every width; only the grid template and the `--tilt-*` tokens change. No horizontal page
scroll at 390.

---

## 5. Component hierarchy

```
App.jsx                          state, fetching, abort, lang — unchanged
├─ ScrapbookHeader               Caveat wordmark 🃏, squiggle rule, EN/VI sticker tabs
├─ ControlDesk (340px, straight, dark dotted mat)
│  ├─ Stepper                    − / + square tape buttons around a mono field
│  ├─ StickerButton              presets, model toggle, language (selected = neon-taped label)
│  ├─ Slider                     dark track + square bright knob
│  ├─ ProfitMap                  dark track, neon-emerald pays-zones, bright marker
│  ├─ RunButton                  bright sticker, hard shadow, press effect (🃏)
│  └─ EngineSpecs                🤖 mono footnote
└─ ResultsBoard                  .results-board (12-col)
   ├─ VerdictPolaroid            advice, handEval, summary, t   → grid-area ver
   │  ├─ Tape (top-center), Stamp "🃏 RECOMMENDED ACTION", KindStamp (neon)
   │  ├─ ActionVerb              <h2> Caveat verb (test pin, bare name)
   │  ├─ SquiggleDoodle          SVG wave in --kind under the verb
   │  ├─ EvBlock                 46px mono + unit + ratio caption + at-your-size line
   │  ├─ WinRateCell             .hud-card hook + "Showdown equity" (plain) + 24px mono
   │  ├─ WhyLine                 Patrick Hand sentence
   │  └─ PolaroidChin            bright strip with mono hand line "As Kh Qd · Q-K-A"
   ├─ SizingSticky               ladder, chosen, pot, t          → grid-area lad
   │  ├─ Tape ×2 (corners, washi), Sticker "📉 SIZING LADDER", StarDoodle
   │  ├─ LadderRows              <ol> of 3 × .ladder-rung (test pins)
   │  │  └─ RungRow              ●/○ · name · amount · "EV ±…" · worst-of-3 · state
   │  ├─ CurvedArrowDoodle       SVG arrow from the chosen EV toward the verdict
   │  └─ ThresholdNote
   ├─ AssumptionScrap            opponent_model + fold_equity, t  → grid-area sli
   │  ├─ Tape, Sticker "💖 ASSUMPTION", torn edge
   │  └─ AssumptionText
   ├─ HudStrip                   dark carbon: hands worth a bet · range coverage · bluff break-even
   ├─ LedgerSheet ×2             dark carbon tables (straight) 🤖
   └─ NotesDrawer                analysis notes
```

### 5.1 Props and ownership

```jsx
<VerdictPolaroid advice={advice} handEval={handEval} summary={summary} t={t} />
<SizingSticky ladder={advice.ladder} chosen={advice.action} pot={summary.pot} t={t} />
<AssumptionScrap text={assumptionLine(t, summary)} t={t} />
<HudStrip summary={summary} t={t} />
```

| Decision | Owner |
| :--- | :--- |
| Money/percent/sign formatting | `format.js` |
| Tone (CHECK → gray, else neon kind), stamp text + emoji, rung state, worst-of-3 | `scrapbook.js` — `toneClass(advice)`, `stampFor(advice)`, `rungView(rung, chosen, pot, t)` |
| Which sentence explains the answer | `scrapbook.js` — `whyLine`, `assumptionLine` |
| Doodles | presentational `Doodle` atoms (inline SVG, `aria-hidden`) |
| Fetching / loading / errors | `App.jsx` only |

### 5.2 Files

| File | Contents |
| :--- | :--- |
| `src/index.css` | tokens, dot-mat, `@font-face`, reset, base type, focus |
| `src/styles/scrapbook.css` | board, polaroid, sticky, scrap, tape, stamps, doodles, ladder rows, dark slabs, controls reskin, breakpoints |
| `src/components/scrapbook/VerdictPolaroid.jsx` | hero + win-rate cell + why + chin |
| `src/components/scrapbook/SizingSticky.jsx` | ladder rows |
| `src/components/scrapbook/AssumptionScrap.jsx` | violet scrap |
| `src/components/scrapbook/HudStrip.jsx` | dark stat strip |
| `src/components/scrapbook/Stationery.jsx` | `Tape`, `Stamp`, `KindStamp`, `Doodle` atoms |
| `src/scrapbook.js` | `toneClass`, `stampFor`, `rungView`, `whyLine`, `assumptionLine` |

`App.jsx` loses its verdict/ladder/HUD markup (~200 lines) and gains no state.

---

## 6. The hero components

### 6.1 Verdict polaroid (7 columns ≈ 560px, rotate −2°)

```
              ░░░ washi tape ░░░
  ╔ 4px bright border · dark-rose paper · 6px 6px 0 #000 ═══════════╗
  ║  🃏 RECOMMENDED ACTION                       [ VALUE ] ← neon   ║
  ║  All in                                       stamp, rotated    ║
  ║  ~~~~~~~~~ neon squiggle doodle under the verb ~~~~~~~~~        ║
  ║  EXPECTED VALUE                 SHOWDOWN EQUITY                 ║
  ║  +164,064 VND                   99.5%                           ║
  ║  at the recommended size · 1.64× pot                            ║
  ║  You win about 99.5% when called, so the all-in is worth the    ║
  ║  risk even if they fold 10% less than you think.   ✶            ║
  ╠ bright polaroid chin ═══════════════════════════════════════════╣
  ║  As Kh Qd · Q-K-A · Liêng Q-K-A                (mono 12)        ║
  ╚═════════════════════════════════════════════════════════════════╝
```

- EV is 46px JetBrains Mono, bright off-white on dark rose (12.4:1); the win rate is 24px mono on the
  same row; Caveat verb 56px above.
- The chin is the polaroid tell: a `--paper-rose-2` strip with a bright 4px bottom border, holding the
  hand metadata in mono.
- Sticker/kind stamp: neon solid fill, near-black caps, rotated +3°, hanging over the border.
- CHECK: no kind stamp, gray tone, EV demoted to 24px `--ink-muted` (`ev = 0` is a sentinel).
- `win_rate_defined === false`: the cell shows the sentence, twice on the page (why + cell), per §8.

### 6.2 Sizing sticky (5 columns ≈ 396px, rotate +1.5°, overlapping the polaroid's corner)

```
      ░ washi ░                          ░ washi ░
  ╔ 3px bright border · dark-mustard paper · 4px 4px 0 #000 ═══════╗
  ║  📉 SIZING LADDER                        amounts in VND        ║
  ║  ● Small bet        33,000   EV +120,932                       ║
  ║     worst +117,639              -43,132 vs chosen   ✶          ║
  ║  ○ Large bet        75,000   EV +147,970                        ║
  ║     worst +140,480              -16,094 vs chosen               ║
  ║  ● All in          100,000   EV +164,064                        ║
  ║     worst +154,076        [ CHOSEN 🃏 ]  ← neon wash + caveat    ║
  ║  ── dashed hand rule ─────────────────────────────────────────  ║
  ║  We recommend a bet only when it earns at least 5% of the pot…  ║
  ╚═════════════════════════════════════════════════════════════════╝
```

- Rows are `<li class="ladder-rung">` in an `<ol>` — a pasted receipt list, not a table. Each row is a
  CSS grid `minmax(0,1fr) 78px 96px` plus a full-width second line for `worst …` and the state.
- Inline labels `EV +147,970` / `worst +140,480` are each one text node — this keeps the pinned
  `EV -11,995` assertion green.
- Chosen row: `--paper-rose-2` wash + `3px` neon start rule + Caveat `[CHOSEN 🃏]` stamp rotated −3°.
  Blocked rows: numerals in `--ink-muted`, phrase replaces the delta, no strikethrough.
- `●`/`○` stay (test-pinned, information-bearing).

### 6.3 Assumption scrap (5 columns, rotate −1.5°, tucked under the polaroid)

```
   ░ washi ░
  ╔ 2px bright border · dark-violet paper · torn bottom ═══════════╗
  ║  💖 ASSUMPTION                                                ║
  ║  The opponent folds their weakest 35% of hands and calls with  ║
  ║  the best 65%.                                                 ║
  ╚════════════════════════════════════════════════════════════════╝
```

Visible, labelled, secondary; its top band slides under the polaroid (z 2 < 3) and holds tape only.

### 6.4 Dark data layer

- HudStrip: `--carbon`, 3 cells, dashed dividers — *hands worth a bet* 71.6%, *range coverage* 100%,
  *bluff break-even* 12.5%. No EV, no equity duplication.
- Ledgers: `--carbon`, straight, `1px --hair-dark` rules, mono numerals right-aligned, Patrick Hand
  headers. The old `.hud-metrics-grid` becomes this strip; `.hud-card` survives on the polaroid's
  win-rate cell (§8).

---

## 7. Styling recipes (concrete)

### 7.1 The dotted mat

```css
.page {
  background-color: var(--page);
  background-image:
    radial-gradient(circle, var(--dot) 1.2px, transparent 1.3px),
    radial-gradient(circle, var(--dot-strong) 1.6px, transparent 1.7px);
  background-size: 22px 22px, 110px 110px;
  background-position: 0 0, 0 0;
}
```
(These are dot *patterns*, not colour gradients; no fade, no blend.)

### 7.2 Polaroid and sticky

```css
.polaroid {
  position: relative;
  background: var(--paper-rose);
  border: 4px solid var(--edge-bright);
  border-bottom: 0;
  border-radius: 0;
  box-shadow: 6px 6px 0 var(--hard);
}
.polaroid__chin {
  display: flex; align-items: center;
  margin-inline: -30px; margin-top: 18px;
  padding: 12px 30px;
  background: var(--paper-rose-2);
  border-block: 4px solid var(--edge-bright);
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.02em;
}
.sticky {
  position: relative;
  background: var(--paper-mustard);
  border: 3px solid var(--edge-bright);
  border-radius: 0;
  box-shadow: 4px 4px 0 var(--hard);
}
.scrap {
  position: relative;
  background: var(--paper-violet);
  border: 2px solid var(--edge-bright-2);
  border-radius: 0;
  box-shadow: 4px 4px 0 var(--hard);
}
```

### 7.3 Washi tape

```css
.tape {
  position: absolute; z-index: 7; width: 112px; height: 26px;
  background: var(--tape);
  border-inline: 1px dashed var(--tape-edge);          /* washi's woven edge */
  box-shadow: 2px 2px 0 rgb(0 0 0 / 40%);
  transform: rotate(var(--tilt-tape)); opacity: 0.95;
  clip-path: polygon(0 8%, 3% 0, 97% 0, 100% 10%, 98% 38%, 100% 66%, 97% 94%,
    94% 100%, 6% 100%, 3% 92%, 0 64%, 2% 36%);           /* ragged ends */
}
.tape--top    { top: -13px; left: 50%; margin-left: -56px; }
.tape--corner { top: -12px; left: -18px; }
.tape--lilac  { background: var(--tape-2); }
```

### 7.4 Neon stamps and stickers

```css
.kind-stamp {
  position: absolute; top: -16px; right: 20px; z-index: 8;
  padding: 3px 9px 1px;
  background: var(--kind, var(--check)); color: var(--stamp-ink);
  border: 2px solid var(--hard);
  transform: rotate(var(--tilt-stamp));
  font: 400 13px/1.2 var(--font-print); letter-spacing: 0.06em; text-transform: uppercase;
}
.chosen-stamp {
  display: inline-block; padding: 0 6px;
  background: var(--kind); color: var(--stamp-ink);
  border: 2px solid var(--hard); transform: rotate(-3deg);
  font: 700 22px/1.1 var(--font-hand);
}
```

### 7.5 Doodles (inline SVG, `aria-hidden`)

- **Squiggle under the verb:** one `<path d="M2 8 Q 22 0 42 8 T 82 8 T 122 8">` in `--kind`, 3px
  round stroke, `preserveAspectRatio="none"`, width 100%.
- **Star:** a 12px `<path>` four-point star in `--thin`, rotated `--tilt-doodle`, tucked near the
  ladder corner.
- **Curved arrow:** one `<path>` + arrowhead lines in `--edge-bright-2`, from the chosen EV toward the
  polaroid; `opacity: .7`.
- These are static SVGs, no animation, no external files.

### 7.6 Ladder rows / chosen state

```css
.ladder-strip { display: grid; grid-template-columns: minmax(0, 1fr); row-gap: 0; }
.ladder-rung {
  display: grid; grid-template-columns: minmax(0, 1fr) 78px 96px; column-gap: 10px;
  align-items: baseline; padding: 9px 0;
  border-top: 1px dashed rgb(242 242 242 / 22%);
}
.ladder-amount, .ladder-ev { text-align: right; font-family: var(--font-mono); }
.ladder-rung.chosen {
  background: var(--paper-rose-2);
  border-left: 3px solid var(--kind);
  border-top-style: solid;
  padding-left: 9px;
}
.ladder-rung.rung-blocked .ladder-amount,
.ladder-rung.rung-blocked .ladder-ev { color: var(--ink-muted); }
```

### 7.7 Controls and header (dark, straight, tactile)

- Inputs: `--carbon` inset, `2px solid var(--hair-dark)`, bright text, Patrick Hand 15px; mono for
  amounts; focus `2px solid var(--focus)` offset 2px.
- Presets/toggles: dark square chips with `1px dashed var(--hair-dark)`; selected = neon-taped label
  (`background: var(--kind)` only for the model toggle? no — selected uses `--tape` cream, kind stays
  semantic only in notes).
- Run button: bright `--edge-bright` fill, black text, `4px 4px 0 #000`; press = `translate(2px,2px)` +
  shadow collapse (80ms; none under reduced motion).
- Header: Caveat wordmark "LIÊNG SCOPE 🃏", squiggle rule, EN/VI as two taped stickers.
- Ledgers: mono numerals, Patrick Hand headers, no colour by sign.

### 7.8 Motion & accessibility

- Only interactive elements move (button press, chip select). Notes do not animate; doodles do not
  animate; no entrance animations.
- `prefers-reduced-motion: reduce` zeroes every tilt token and transition.
- Focus ring: `2px solid var(--focus)` at 2px offset on dark; `--focus-paper` on bright borders.
- Tape/doodles/stamps are `aria-hidden` decoration and add no text nodes.
- Emojis are inside labels that already name the section in words, so nothing depends on an emoji.
- Contrast: ink 15.1:1 / muted 8.8:1 on rose; neon stamp text 15.1 / 13.3 / 6.7:1; dark slab text
  ≥13:1. Neon is never used for small text on pastel.

---

## 8. Test and copy impact

**None.** Presentation-only, and the plan is test-transparent:

| Pin | How it holds |
| :--- | :--- |
| verb is an `<h2>` with the bare action name | emoji/stamp are siblings, never inside the `<h2>` |
| CHECK note must not contain "Bluff" | `stampFor()` returns `null` on CHECK; `.verdict-card` kept |
| `33,000` appears once | only in `.ladder-amount`; no amount beside the verb |
| `.ladder-rung` / `chosen` / `rung-blocked` / `●` `○` | unchanged class names and glyphs |
| `EV -11,995` contiguous | `rungView.ev = "EV " + signedMoney(...)` in one element |
| exactly two "nobody calls" | why line + win-rate cell; stickers add no sentence |
| `.hud-card` + "Showdown equity" | kept on the polaroid's win-rate cell; label stays **plain** (no emoji) |
| direct text nodes | every pinned string stays the sole text child of its element |

Emojis live in label keys only — `recommendedAction` "Recommended action 🃏", `sizingTag` "Sizing
ladder 📉", `assumptionTag` "Assumption 💖", `notesTitle` "Analysis 🤖" — never in a sentence that a
test matches. New keys beyond those: `chosenTag`, `worstTag`, `rangeCoverage`. Numbers unchanged.

**Text-node law (this is the trap decoration creates).** jsdom ignores CSS but not DOM, so scroll
decoration must never add text:

1. **No decorative tape, receipt, sticker or doodle may print a numeral.** A taped "100,000 VND" label
   is the natural scrapbook instinct and it makes `getByText(/33,000/)` ambiguous — the wager is a
   singleton. Decorations are pseudo-elements or `aria-hidden` empty spans.
2. **A prose line carrying a numeral stays one unbroken text node.** The why sentence and the
   assumption sentence are matched whole; never split them into a kicker + `<span>` to style a number.
   If a numeral must be styled, it must already be its own element (the EV, the rung cells).
3. **Emojis add text, so they go in labels only** — never inside a pinned string, never inside the
   `<h2>`.

---

## 9. Implementation sequence

1. `index.css`: the token block + dotted mat + `@font-face` (or fallback-first). Verify Vietnamese.
2. `styles/scrapbook.css`: 12-col board, polaroid/sticky/scrap shells, tape/washi, neon stamps,
   doodles, ladder rows, dark slabs. **Judge the composition against current markup before extracting
   components.**
3. `scrapbook.js`: `whyLine`, `assumptionLine`, `toneClass`, `stampFor`, `rungView` + unit tests.
4. Extract `VerdictPolaroid`, `SizingSticky`, `AssumptionScrap`, `HudStrip`, `Stationery`; rewire
   `App.jsx`; keep every test hook.
5. Reskin header + control desk.
6. `i18n.js`: the label keys with emojis, EN + VI.
7. Delete retired CSS; `npm run lint`, `npm run build`, `npm test` unchanged.
8. Visual pass at 1360 / 1024 / 640 / 390 + reduced-motion pass; confirm numbers unchanged.

## 10. Review checklist

- [ ] `#121212` page with a subtle dark dot grid; no other pattern.
- [ ] Verdict = dark-rose polaroid with bright 4px border + chin; ladder = dark-mustard sticky with
      bright 3px border; assumption = dark-violet scrap; all with `4px 4px 0 #000` hard shadow.
- [ ] Notes staggered, rotated (−2° / +1.5° / −1.5°) and overlapping; data slabs straight.
- [ ] Caveat + Patrick Hand for human text; JetBrains Mono for **every** numeral; EV is largest.
- [ ] Washi tape on corners (max 3 strips); emojis only in section labels; doodles: squiggle, star,
      arrow — all decorative and `aria-hidden`.
- [ ] Neon emerald/amber/violet/check as semantic fills only; CHECK = gray, no kind stamp.
- [ ] No gradients (dot pattern only), no blur, no glass; borders 2–4px solid; radius 0.
- [ ] Assumption line visible (12–13px), tucked but readable.
- [ ] Ladder shows all three options with EV + worst-of-3; chosen unmistakable; non-chosen rows say why.
- [ ] 390: tilt 0, no overlap, no horizontal scroll; reduced motion flattens all tilts.
- [ ] `npm run lint`, `npm run build`, `npm test` pass with no edits; numbers unchanged.

---

## 11. Rationale: the direction change, alternatives, tradeoffs, open questions

### 11.1 Why this direction supersedes the cream-paper draft

The architect arena produced two strong plans (S1 "pinned pinboard", S2 "layered desk", both 12/12 on
the rubric; see [`design/scrapbook/SYNTHESIS.md`](scrapbook/SYNTHESIS.md)). Both independently chose
**cream paper notes on a black board** — and that was the right call for a *physical-paper* read.
The user then overrode the palette direction: keep the dark theme and apply the reference's unhinged
scrapbook energy with dark pastel notes, emojis, doodles and neon. That override keeps the arena's
load-bearing structure and discards its paper colour:

**Kept from S1:** the 12-column board with shared row bands; overlap via negative margins; tokenized
tilts (one media query flattens them); anti-clipping rule; motif budget; the test-transparent DOM.
**Kept from S2:** the overlap-invariant slack table; neutral-not-semantic marker rule (now moot in
colour, kept in spirit); Vietnamese-subset font check; DOM reading order.
**Changed by the override:** cream paper → dark pastel notes; soft undertone shadow → the mandated
`4px 4px 0 #000`; muted inks → bright off-white ink; Space Grotesk → Caveat/Patrick Hand; no emoji →
emoji labels; no doodles → squiggle/star/arrow SVGs; muted accents → neon.

### 11.2 Alternatives considered

| Alternative | Why it lost |
| :--- | :--- |
| **Cream paper (the arena consensus)** | Right for physical paper, but the user wants the dark theme kept and the reference's unhinged collage energy; dark pastel notes deliver both while `#121212` stays the majority surface. |
| **Absolute-positioned collage canvas** | Rotated absolute cards contribute no scroll height; content growth (VI, long why) clips or forces horizontal scroll at 390. Grid rows + negative margins keep the overlap and the flow. |
| **Light-paper notes on a dark page with no pastel tint** | Reads as a plain document, not a scrapbook; the three pastel tints are what make the notes read as different paper scraps. |
| **Emoji in headings/body** | Banned from test-pinned strings and h2 accessible names; they live only in label keys. |
| **All-neon page (neon accents as card backgrounds)** | Kills the semantic tri-colour and the readability of numbers; neon must stay a small fill so it keeps meaning. |
| **Gradient/glow neon** | Gradient and blur are still banned; saturation + hard borders carry "neon". |

### 11.3 Tradeoffs accepted

- We accept a busier page (tilt, tape, pastel, emoji) in exchange for the reference's vibe, and
  protect data legibility with the mono-only-numerals law and fixed numeral columns.
- We accept dark pastel cards on a near-black page in exchange for keeping the dark theme; the hard
  `4px 4px 0 #000` shadow is subtle there, so bright 2–4px borders do the physical lifting.
- We accept three webfonts (Caveat, Patrick Hand, JetBrains Mono) in exchange for the handmade voice,
  with metric-safe fallbacks and a font asset dependency flagged.
- We accept legacy class names (`.verdict-card`, `.hud-card`, `.ladder-rung`, `chosen`,
  `rung-blocked`) in exchange for zero test edits.
- We accept emojis in labels in exchange for scrapbook playfulness, kept out of every pinned string.
- We accept the dotted mat via `radial-gradient` dot patterns in exchange for the scrapbook-paper
  ground — a pattern, not a colour gradient.

### 11.4 Open questions

- **Fonts:** who provides the three `woff2` files (offline env)? Do they carry Vietnamese subsets?
- **Emoji rendering:** emojis look different per OS (Windows Segoe UI Emoji vs Apple). Should labels
  use emojis only where the difference is harmless (🃏 💖 📉 🤖 are safe), and never emojis that encode
  meaning (a red/green dot)?
- **Pastel assignments:** rose=verdict, mustard=ladder, violet=assumption is fixed; should the verdict
  card tint follow the *kind* instead (e.g., violet tint for a bluff)? Fixed tints keep the semantics
  in the neon stamp; kind-tinted paper is more playful but risks reading as semantics.
- **Rotation budget:** −2° / +1.5° satisfy the brief; does the verdict want −2.5° for more "unhinged",
  and does that still clear the anti-clipping slack?
- **Worst-of-3 on the ladder:** a new displayed number (deferred by both candidates); keep it as the
  policy's real gate, or stay strictly presentation-only?
- **`DESIGN.md` disposition:** delete after merge, keep on its branch, or keep for a "print/document"
  theme?

### 11.5 Next implementation step

Add the token block, the dotted mat and the three note shells (polaroid / sticky / scrap) with tape and
tilts against today's markup, and re-measure the anti-clipping slack in a browser before extracting a
single component.

---

## 12. As built (implementation record)

The user's three answers were applied and the frontend is implemented. Where the as-built code differs
from the plan above, this section is the authority.

### 12.1 Resolved decisions

| Question | Decision as built |
| :--- | :--- |
| Fonts | Self-hosted: `frontend/src/assets/fonts/` holds 8 `woff2` files (Caveat latin/latin-ext; Patrick Hand latin/latin-ext/vietnamese; JetBrains Mono latin/latin-ext/vietnamese), declared in `src/fonts.css` with the Google `unicode-range` subsets. **Caveat ships no Vietnamese subset**, so it is restricted to the Latin-only wordmark; `:lang(vi)` switches the display roles to Patrick Hand, which carries the VI subset. No CDN at runtime. |
| Card pastels | Tinted **by kind**: `.tone-value` (dark emerald `#14251d`), `.tone-thin` (dark amber `#29220f`), `.tone-bluff` (dark violet `#221a33`), `.tone-check` (neutral `#1f1f1f`). The neon stamp/rule still carries the semantic colour; a CHECK gets the neutral tint and no stamp. |
| Worst-of-3 | **Not displayed** — the ladder stays presentation-only. The planned worst-of-3 line and the derived "vs chosen" delta were both dropped: blocked rows show only the existing `t.blocked[...]` phrase, and an eligible-but-not-chosen row shows no state. No payload, schema, or displayed-number change. |

Further as-built choices: the hero's `ev_ratio` caption, the profitable-fold-zone line and the raw
sensitivity enum were not carried over (existing copy and numbers only); `.hud-card` remains on the
verdict's win-rate cell as the test hook, and the old 4-cell HUD became the 3-cell dark `StatStrip`
(hands worth a bet · range coverage · bluff break-even).

### 12.2 Files

| File | Status |
| :--- | :--- |
| `src/verdict.js` | new — `toneClass`, `stampLabel`, `whyLine`, `assumptionLine`, `rungView` (pure) |
| `src/components/VerdictCard.jsx` | new — polaroid, squiggle doodle, kind stamp, `.hud-card` win-rate cell, chin |
| `src/components/SizingLadder.jsx` | new — sticky note + receipt rows (keeps `.ladder-rung`, `chosen`, `rung-blocked`, `●`/`○`, `EV -11,995`) |
| `src/components/AssumptionSlip.jsx` | new — labelled scrap |
| `src/components/StatStrip.jsx` | new — dark 3-cell reference strip |
| `src/format.js` | `percent`, `wholePercent`, `signedMoney` moved here from `App.jsx` |
| `src/App.jsx` | result markup replaced by the four components; state/fetching untouched; ~225 lines removed |
| `src/index.css` | tokens, dot mat, type roles, `:lang(vi)` display fallback |
| `src/fonts.css` + `src/assets/fonts/` | new — self-hosted faces |
| `src/App.css` | rewritten — board, notes, tape/stamps, ladder, dark slabs, controls, responsive |
| `src/i18n.js` | added `sizesTag`, `assumptionTag`, `chosenTag`, `rangeCoverage`; 🃏/📉/💖/🤖 on label keys (EN + VI) |
| `src/main.jsx`, `frontend/index.html` | fonts import; `theme-color` `#121212` |
| `src/App.test.jsx` | **untouched** (its working-tree diff predates this work) |

### 12.3 Verification

- `npm run lint` — 0 warnings, 0 errors.
- `npm run build` — passes; the 8 `woff2` files are emitted as hashed assets in `dist/`.
- `npm test` — **37/37 tests pass across 3 files, with no test edits**.
- Numbers are unchanged; the DOM pins (`.verdict-card`, `.hud-card` + "Showdown equity" + two
  "nobody calls" nodes, `.ladder-rung`/`chosen`/`rung-blocked`, `●`/`○`, contiguous `EV -11,995`,
  singleton `33,000`, bare `<h2>`) all hold because the components kept their hooks.
- Browser visual pass (headless Edge against the dev server + Flask): **1360, 1024 and 390** all render
  with `document.documentElement.scrollWidth === innerWidth` (no page overflow); the CHECK state is
  gray with no kind stamp and a demoted EV; the VI state renders every diacritic through Patrick Hand.
  Three defects were found and fixed during the pass: the ladder card covered the win-rate figure and
  the why-line (the board is now verdict 7 cols / ladder 5 cols, with only a 12px nudge into the
  verdict's end padding), the assumption slip was hidden under the polaroid (negative margin removed),
  and the stat strip double-multiplied percentages (`7162.0%` → `71.6%`).
- Reduced motion remains a manual toggle check: the CSS zeroes every tilt and transition.
