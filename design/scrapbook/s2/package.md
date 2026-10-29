# S2 — LAYERED DESK

Three sheets of paper on a near-black board: Verdict Card, Sizing Ladder and Assumption Note are
staggered, rotated and overlapped — tape strips as their DOM siblings, a dashed spine behind, and the
assumption note tucked under the ladder's left edge.

## 1. Problem — what chose the shape

1. **Pinned paper, not panels** (rubric 1) on `#0a0a0a`; square corners; no gradient/blur/emoji/images.
2. **Content is unbounded**: server copy is 60–140 chars, VI runs 1.3–2× EN, and the assumption
   sentence rewraps to 4 lines at 390 — a sheet whose height is not content-derived clips a glyph or
   covers one.
3. **Eight literal pins** (`GROUNDING §2.3`): `.verdict-card` survives; the `h2` name is exactly the
   verb; `.ladder-rung` keeps `chosen`/`rung-blocked` and `●`/`○`; one element holds `EV -11,995`;
   exactly two `nobody calls at this setting` nodes; `.hud-card` wraps the showdown cell; `getByText`
   sees **direct text nodes only**, so every asserted sentence stays one unsplit node.
4. **Accents are scarce semantics** (emerald=Value, amber=Thin, violet=Bluff, grey=Check) and 11–13px
   text clears 4.5:1 on whatever it lands on; **one DOM at 1360/1025/640/390**, no horizontal scroll at
   390, no JS measurement.

**The decision this package turns on:** a reserved-height absolute canvas is arithmetically incompatible
with (2). `min-height` is never contributed to by absolutely positioned children, so the desk's bottom
edge is fiction once the why line gains a line, and a sibling's hand-picked `top: 46%` lands inside the
grown sheet. Sheets therefore **stay in flow** (heights still pure CSS — `auto` grid tracks); *overlap*
comes from negative margins + `z-index`; `position: absolute` is reserved for what can never cover text:
tape, sticker, spine.

## 2. Usage

```jsx
/* right column of <main className="terminal-grid"> */
<Desk advice={advice} handEval={handEval} summary={summary} t={t} kindClass={KIND_CLASSES[advice.kind]} />
  <VerdictCard advice={advice} handEval={handEval} summary={summary} t={t} />  {/* + <Tape/> sibling */}
  <LadderSheet advice={advice} t={t} />                                       {/* + <Tape/> sibling */}
  <AssumptionNote summary={summary} t={t} />
<VerdictEmpty summary={summary} actionCounts={actionCounts} t={t} />
<HudGrid advice={advice} handEval={handEval} summary={summary} t={t} />
<LedgerSheet tag={t.matrixTag} rows={categoryRows} t={t} />
<TopHandsLedger rows={solveData?.top_hands ?? []} t={t} />
<NotesDrawer open={isNotesOpen} onToggle={() => setIsNotesOpen(!isNotesOpen)} note={aiAdvice} loading={isAiLoading} t={t} />
```

`App` keeps every piece of state and every effect verbatim; it only *places* components.

## 3. Shape — hierarchy, props, helpers

```
App (state unchanged)
└─ section.results-container
   ├─ Desk              advice handEval summary t kindClass   → kindTone()
   │  ├─ span.desk-spine                              (aria-hidden, z 0, dashed)
   │  ├─ div.desk-layer--verdict       rotate −1.1°  z 3
   │  │  ├─ <VerdictCard/> .verdict-card   (pin 2: the class survives)
   │  │  └─ <Tape className="tape--top"/>  sibling, z 6    → whyLine() signedMoney() percent() formatZones()
   │  └─ div.desk-layer--lower        grid 34.7% | 1fr · margin-top −14px
   │     ├─ div.desk-layer--ladder    rotate +1.4°  z 4 · margin-left −40px
   │     │  ├─ <Tape className="tape--seam"/> sibling, z 6
   │     │  └─ <LadderSheet/> .ladder-sheet > .ladder-strip > .ladder-rung ×3  → formatMoney() signedMoney()
   │     └─ div.desk-layer--note      rotate −2.4° translateY(−22px) z 2      → assumptionLine()
   ├─ <VerdictEmpty/> .verdict-banner.verdict-empty (role="status")
   ├─ <HudGrid/>      .hud-metrics-grid > .hud-card ×4                        → percent() signedMoney()
   ├─ <LedgerSheet/> <TopHandsLedger/>  .ledger-sheet > .panel-header + .tactical-table
   └─ <NotesDrawer/>  .drawer-toggle-btn + .drawer-content  (controlled; no state)
```

| component | props | pure helpers |
| :--- | :--- | :--- |
| `Desk` | `advice, handEval, summary, t, kindClass` | `kindTone(kind)` |
| `VerdictCard` | `advice, handEval, summary, t` | `whyLine`, `signedMoney`, `percent`, `formatZones` |
| `LadderSheet` | `advice, t` | `formatMoney`, `signedMoney` |
| `AssumptionNote` | `summary, t` | `assumptionLine` |
| `VerdictEmpty` / `HudGrid` | `summary, actionCounts, t` / `advice, handEval, summary, t` | `assumptionLine`, `percent`, `signedMoney` |
| `LedgerSheet` / `TopHandsLedger` | `tag, rows, t` | `CATEGORY_LABELS`, `CATEGORY_DESC_KEYS` |
| `Tape` / `KindSticker` / `NotesDrawer` | `className` / `kind, t` / `open, onToggle, note, loading, t` | — |

`signedMoney`, `wholePercent`, `kindTone` move to `format.js` (unit-tested, React-free); `whyLine`,
`assumptionLine`, `solveErrorFor`, `fetchSolveAndAnalysis` move into their components unchanged.
**No component gains state**; `whyLine`/`assumptionLine` run once per render, as now.

## 4. Wireframes (1 char ≈ 10px)

**1360** — control 341 | results 1019 (pad 20) | desk 979 wide, height = content.

```
  y21       ╔╦╦ tape--top  104×30  rotate −7°  ╦╦╗                             ④
  y34 ┌──────────────────────────────────────────────────────────────┐
      │▐ RECOMMENDED ACTION    ┃ marker band #cfc3a6                  │ ← verdict
      │▐ ALL IN  ⌐BLUFF¬ sticker (top −15, left −12, rotate −5°)       │   rotate −1.1°
      │▐ As Kh Qd · Q-K-A · Liêng Q-K-A                                │   z 3 · pad 34/34/44
      │▐                                  EXPECTED VALUE              │   corner Δy ±9.4
      │▐                                     +164,064 VND  26px mono   │
      │▐ why caption — mono 13/1.6, 1–2 lines                          │
      └──────────────────────────────────────────────────────────────┘
            ╔╦╦ tape--seam 104×30 (net −5.6°) top −26 ╦╦╗                     ⑤
      ┌──────────────────────┐╔═══════════════════════════════════════╗
      │ ASSUMPTION  manila   │║ SIZING LADDER                         ║ ← ladder
      │ rotate −2.4°         │║ ┌──────────┬─────────┬──────────────┐ ║   rotate +1.4° z 4
      │ translateY(−22px)    │║ │● SMALL   │○ LARGE  │○ ALL IN      │ ║   margin-left −40
      │ z 2 · pad 26/48/24   │║ │33,000 VND│75,000   │100,000       │ ║   margin-top −14
      └──────────────────────┘║ │EV +120,932│EV …    │EV …          │ ║
       x0                  340║ └──────────┴─────────┴──────────────┘ ║
       ↑ tucked 40px under ──╫── the ladder's left edge               ║
                             ╚═══════════════════════════════════════╝
                             x300                                   x979
```

**390** — results pad 12, desk 366, everything `position: static`, all angles 0.

```
┌────────────────────────────────────────┐
│ ╔ tape 84×22, left 14, top −10, 0° ╗   │ hangs into the 14px gap, inside bounds
│ RECOMMENDED ACTION                     │
│ BLUFF  (sticker static, above the h2)  │
│ ALL IN                       24px SG   │
│ As Kh Qd · Q-K-A · Liêng Q-K-A         │
│ EXPECTED VALUE   +164,064 VND 22px mono│
│ why caption mono 13/1.6 — 4–5 lines    │
└────────────────────────────────────────┘ 6px 6px 0 #221f1b
┌────────────────────────────────────────┐
│ SIZING LADDER    1 column, 1px hair    │
│ ● SMALL BET  33,000 VND  EV +120,932   │
│ ○ LARGE BET  75,000 VND  EV −11,995    │
│ ○ ALL IN    100,000 VND  EV …          │
│ threshold note (mono 11)               │
└────────────────────────────────────────┘
┌────────────────────────────────────────┐ ← torn top edge (clip-path)
│ Assumption: the opponent folds their   │ tape at left 14, inside
│ weakest 35% of hands and calls with    │ full width, pad 22
│ the best 65%.                          │
└────────────────────────────────────────┘
```

Callouts: ① verdict `rotate(-1.1deg)` ② ladder `rotate(1.4deg)` + `margin-inline-start:-40px` +
`margin-block-start:-14px` ③ note `rotate(-2.4deg) translateY(-22px)` ④⑤ tapes `rotate(-7deg)` (⑤ nets
−5.6° inside the +1.4° parent) ⑥ sticker `rotate(-5deg)` ⑦ spine `1px dashed` at `left:8.5%`, z 0
⑧ seam = `row-gap 22px − 14px` = 8px visible.

## 5. Styling plan

### 5.1 Tokens (`index.css`)

```css
:root{
  --page:#0a0a0a;
  --paper:#f4efe4; --paper-lit:#fbf7ee; --manila:#efe6d0;   /* pasted sheets */
  --carbon:#171513; --carbon-lit:#211d19;                    /* ledger, controls */
  --ink:#14110e; --ink-soft:#4a4238; --chalk:#efe8da; --chalk-soft:#b3a89a;
  --rule:#14110e; --hair:#cbc2ae; --hair-dark:#2f2a24;
  --under:#221f1b;   /* hard offset shadow = the sheet beneath */
  --tape:#e8dfc6; --tape-edge:#cbbfa2; --marker:#cfc3a6; --spine:#332f29;
  --value:#16b981; --value-ink:#0b6b4a; --value-lit:#3ddc9b;
  --thin:#e0a13a;  --thin-ink:#8a5a06;  --thin-lit:#f0b64d;
  --bluff:#8b5cf6; --bluff-ink:#5b21b6; --bluff-lit:#a78bfa;
  --check:#8a8378; --error:#b3251b; --error-lit:#ff6b5e;
  --focus-on-paper:#0a0a0a; --focus-on-dark:#f4efe4;
  --font-display:"Space Grotesk","Segoe UI Variable Display",system-ui,sans-serif;
  --font-mono:"JetBrains Mono","Cascadia Mono",Consolas,monospace;
  --tilt-v:-1.1deg; --tilt-l:1.4deg; --tilt-n:-2.4deg;
  --seam:22px; --tuck:14px; --tuck-x:40px; --pad:34px; --pad-b:44px;
}
```

**Paper vs page.** The three verdict sheets are **cream paper / near-black ink**; HUD tickets, both
tables, the drawer and the controls are **carbon / chalk**. Why: (a) paper needs material — a charcoal
note on `#0a0a0a` has no edge and no shadow, cream carries both; (b) on cream one 8px emerald rule and
one violet sticker are ~3% of the surface, so accents stay *pops*, where a lit-on-charcoal card glows as
a whole; (c) the smallest text is the ladder's 11px EV line — ink on cream is **16.4:1**,
cream-on-charcoal tops out at 13.6:1 — and cream rationed to three sheets keeps the screen dark.

**One hue, two tints** — the rule that makes accents legal: the bright hue is for **fills, rules and
tape on paper** and for **glyphs on carbon**; the `-ink` tint is the only glyph-safe colour on cream.
Measured — on paper: ink 16.4, ink-soft 8.6, value-ink 5.7, thin-ink 5.2, bluff-ink 7.8, error 5.7; on
carbon: chalk 14.9, chalk-soft 7.8, value-lit 10.3, bluff-lit 6.7, error-lit 6.5, check 4.9.

**Violet `#8b5cf6`** (ink `#5b21b6`, lit `#a78bfa`) appears **only** struck to the word "Bluff": the
verdict sheet's 8px left rule, the kind sticker's 2px border, the seam tape's fill, `kindBluff` cells.
Never on a CHECK (the desk carries `kind-none`; the sticker is not rendered), never in an error (brick
`--error`, only under Run, `role="alert"`), never on the control panel, never as a focus ring, never as
a wash. Error and bluff differ by hue, placement and copy ("Bluff" / "Cược hù" is a play, not a fault).

### 5.2 Layout — the desk

```css
.results-container{display:flex;flex-direction:column;gap:18px;padding:18px 20px 28px;
  overflow-y:auto;overflow-x:clip;background:var(--page);}
.desk{position:relative;display:grid;grid-template-columns:1fr;row-gap:var(--seam);
  padding:34px 0 0;}                                 /* room for tape + sticker above sheet 1 */
.desk::before{content:"";position:absolute;inset:10px auto 26px 8.5%;width:0;
  border-left:1px dashed var(--spine);z-index:0;pointer-events:none;}   /* the spine */
.desk-layer{position:relative;z-index:2;min-width:0;}
.desk-layer--verdict{transform:rotate(var(--tilt-v));z-index:3;}
.desk-layer--lower{display:grid;grid-template-columns:34.7% 1fr;align-items:start;
  margin-block-start:calc(var(--tuck) * -1);}
.desk-layer--ladder{grid-column:2;z-index:4;transform:rotate(var(--tilt-l));
  margin-inline-start:calc(var(--tuck-x) * -1);}
.desk-layer--note{grid-column:1;z-index:2;transform:rotate(var(--tilt-n)) translateY(-22px);}
```

Responsive, one DOM. **≤1279**: `--tilt-v:-.8deg; --tilt-l:1deg; --tilt-n:-1.7deg; --seam:18px;
--tuck-x:30px; --pad:26px; --pad-b:34px`. **≤1024** static single column: `row-gap:16px;
padding-top:20px`, spine `display:none`, `.desk-layer--lower{grid-template-columns:1fr;row-gap:16px;
margin-block-start:0}`, both children `.desk-layer--ladder,.desk-layer--note{grid-column:auto}` (else
`grid-column:2` resurrects an implicit second column), ladder `margin-inline-start:0`, note
`padding-right:24px`, tilts `-.6/.5/-.4deg`.
**≤640** every `transform:none` (layers, tapes, sticker) with `.ladder-strip{grid-template-columns:1fr}`,
`.hud-metrics-grid{grid-template-columns:repeat(2,1fr)}`, sticker `position:static`; under
`@media (prefers-reduced-motion:reduce)` all tilts are `none` while margins stay.

### 5.3 Material recipes (flat only)

```css
.verdict-card,.ladder-sheet{position:relative;background:var(--paper);color:var(--ink);
  border:2px solid var(--rule);border-radius:0;box-shadow:6px 6px 0 var(--under);
  padding:var(--pad) var(--pad) var(--pad-b);}
.verdict-card{border-left:8px solid var(--kind,var(--check));}
.kind-value{--kind:var(--value);--kind-ink:var(--value-ink);}
.kind-thin{--kind:var(--thin);--kind-ink:var(--thin-ink);}
.kind-bluff{--kind:var(--bluff);--kind-ink:var(--bluff-ink);}
.kind-none{--kind:var(--check);--kind-ink:var(--check);}      /* CHECK = grey, no violet */

/* tape: sibling of the sheet, absolute against the content-sized layer (inset edge survives clip) */
.tape{position:absolute;z-index:6;width:104px;height:30px;pointer-events:none;background:var(--tape);
  box-shadow:inset 0 0 0 1px var(--tape-edge);
  clip-path:polygon(0 4px,3% 0,97% 2px,100% 0,100% 26px,97% 30px,3% 28px,0 30px);}
.tape--top {left:40%;top:-13px;transform:rotate(-7deg);}
.tape--seam{left:38%;top:-26px;transform:rotate(-7deg);background:var(--kind,var(--tape));}
.tape--note{left:14px;top:-11px;transform:rotate(-4deg);}

/* torn edge: clip-path on a paper plate, so the parent keeps its offset shadow */
.assumption-note{position:relative;padding:26px 48px 24px 26px;color:var(--ink);
  box-shadow:5px 5px 0 var(--under);}
.assumption-note::before{content:"";position:absolute;inset:0;background:var(--manila);
  box-shadow:inset 2px 0 0 var(--rule),inset -2px 0 0 var(--rule),inset 0 -2px 0 var(--rule);
  clip-path:polygon(0 6px,4% 0,9% 7px,15% 1px,22% 8px,30% 2px,38% 9px,46% 2px,54% 8px,
    62% 1px,70% 7px,78% 2px,86% 8px,93% 2px,100% 6px,100% 100%,0 100%);}
.assumption-note > *{position:relative;}                      /* text above the plate */

/* marker: grey-tan, never a semantic hue, so it cannot be read as a kind */
.marker{background:var(--marker);padding:1px 7px 2px;
  box-decoration-break:clone;-webkit-box-decoration-break:clone;}

.kind-sticker{position:absolute;left:-12px;top:-15px;z-index:5;padding:4px 10px;
  background:var(--paper-lit);color:var(--ink);border:2px solid var(--kind,var(--check));
  box-shadow:3px 3px 0 var(--under);transform:rotate(-5deg);font-family:var(--font-mono);
  font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;}

.hud-metrics-grid{display:grid;grid-template-columns:repeat(4,1fr);background:var(--carbon);
  border:1px solid var(--hair-dark);box-shadow:5px 5px 0 var(--under);}
.hud-card{padding:14px;border-left:1px solid var(--hair-dark);border-top:1px dashed #3a342c;}
.ledger-sheet{box-shadow:5px 5px 0 var(--under);}
.tactical-table{background:var(--carbon);color:var(--chalk);}
.tactical-table td{border-bottom:1px solid var(--hair-dark);}
```

**The overlap invariant — why no digit is ever covered.** With `Δ = (w/2)·sin|θ|` as the corner rise:

| overlay | max intrusion | lands in | slack |
| :--- | ---: | ---: | ---: |
| tape--top over the verdict's top border | 13px | 34px top padding | 21 |
| ladder over the verdict's bottom (`14+9.4+8.3`) | 32px | 44px bottom padding | 12 |
| ladder over the note's right edge (`--tuck-x`) | 40px | 48px right padding | 8 |
| note over the verdict's bottom (`22+7.0+9.4`) | 16px | 44px bottom padding | 28 |
| sticker over the verdict's top-left | 15px | 34px padding / desk top pad | 19 |

So: no sheet carries text in its first `--pad` / last `--pad-b` band; **no text-bearing element tilts
more than 2.4°** (anything ≥4° is a 30px-tall decoration); the ladder is the lowest sheet in the pile
*and* the topmost in z; **tables are never rotated**; every sheet keeps `overflow: visible`, no height.

### 5.4 Type scale and the numeral law

| token | face | size / leading | use |
| :--- | :--- | :--- | :--- |
| `--fs-wordmark` / `--fs-verb` | Space Grotesk 700 | 30 / .95 −.03em · 30 / 1.1 −.02em | `LIÊNG SCOPE` + marker underline; the `h2` |
| `--fs-figure` / `--fs-hud` | JetBrains Mono 600 | 26 / 1.15 · 22 / 1.2 | verdict EV; HUD figures |
| `--fs-amount` / `--fs-micro` | JetBrains Mono 600 / 400 | 14 / 1.3 · 11 / 1.5 | `.ladder-amount`; ladder EV, threshold note, cells |
| `--fs-kicker` | Space Grotesk 600 | 10 / 1, +.16em, upper | kickers, `.panel-tag` |
| `--fs-body` / `--fs-caption` / `--fs-note` | Grotesk 400 / Mono 400 / Mono 400 | 13 / 1.55 · 13 / 1.6 · 12.5 / 1.55 | numeral-free prose; why line; assumption note |

**Numeral law.** Every numeral is JetBrains Mono with `tabular-nums`. A sentence that states a number
cannot have its digits wrapped without splitting the text node (pin 8), so the law becomes: **a prose
line that carries a numeral is set in mono** — `.verdict-why`, `.assumption-note`, `.ladder-note`,
`.ladder-amount`, `.ladder-ev`, `.hud-value`, `.hud-subtext`, every table numeral, every `formatZones`
value. Space Grotesk carries only numeral-free copy (wordmark, verb, kickers, `.ladder-blocked`,
descriptions). **Font flag:** both families are missing from the repo — ship `@font-face`
(`font-display:swap`) with the **Vietnamese subset** first; the fallback stack must ship alone.
Spacing: 4px base; sheets `34/34/44`, rungs `16px 18px 18px`, note `26/48/24/26`; seams 22px; gap 18px.

### 5.5 Class list

| component | classes |
| :--- | :--- |
| `Desk` | `.desk`, `.desk::before`, `.desk-layer` + `--verdict`/`--lower`/`--ladder`/`--note`, `.kind-{value,thin,bluff,none}` on `.desk` |
| `Tape` | `.tape`, `.tape--top`, `.tape--seam`, `.tape--note` (`aria-hidden="true"`) |
| `VerdictCard` | `.verdict-card`, `.verdict-kicker`, `.marker`, `.verdict-title-row`, `.verdict-title`, `.kind-sticker`, `.verdict-meta`, `.holding-tag/-sep/-score`, `.verdict-col-right`, `.verdict-label`, `.verdict-ev`, `.ev-currency`, `.verdict-breakeven`, `.mono-green`, `.verdict-why` |
| `LadderSheet` | `.ladder-sheet`, `.ladder-kicker`, `.ladder-strip`, `.ladder-rung` (+`.chosen`/`.rung-blocked`), `.ladder-head`, `.ladder-mark`, `.ladder-label`, `.ladder-amount`, `.ladder-ev`, `.ladder-blocked`, `.ladder-note` |
| `AssumptionNote` | `.assumption-note` (one `p`, one text node), `.assumption-note::before` |
| `VerdictEmpty` / `HudGrid` | `.verdict-banner`, `.verdict-empty`, `.verdict-label/-title/-meta/-why` · `.hud-metrics-grid`, `.hud-card`, `.hud-label`, `.hud-value` (+`.green-metric`/`.hud-phrase`), `.hud-subtext` |
| `LedgerSheet` | `.ledger-sheet`, `.panel-header`, `.panel-tag`, `.table-wrapper`, `.tactical-table`, `.mono-num`, `.mono-canonical`, `.desc-cell`, `.dim-cell`, `.positive-ev`, `.negative-ev`, `.chip-full`, `.chip-zero`, `.kind-*` cells |
| `NotesDrawer` | `.notes-drawer-container`, `.drawer-toggle-btn`, `.drawer-indicator`, `.drawer-content`, `.drawer-header`, `.drawer-title`, `.drawer-sub`, `.telemetry-loading`, `.telemetry-body` |
| shell | `.terminal-container`, `.terminal-header`, `.terminal-title`, `.terminal-subtitle`, `.lang-toggle`, `.lang-option`, `.terminal-grid`, `.control-panel`, `.results-container` |

### 5.6 The pins, satisfied with no test edit

| pin | how |
| :--- | :--- |
| 1 verb heading | `<h2 className="verdict-title">{t.actionLabel[advice.action]}</h2>` — no nested node, no `aria-label` |
| 2 `.verdict-card`, no "Bluff" on a CHECK | class kept; sticker still behind `advice.action !== "CHECK"`; kind colour rides on the ancestor `.desk` as a *class*, never as text |
| 3 wager once | `formatMoney(rung.amount)` renders **only** in `.ladder-amount` — no card, tape, ticket, tooltip or receipt may print it again |
| 4 rung classes/marks | existing `.ladder-rung` JSX copied verbatim, `●`/`○` included |
| 5 `EV -11,995` | `.ladder-ev` stays `{t.evTag} {signedMoney(rung.ev, t.locale)}` — one element, ASCII hyphen |
| 6 exactly two "nobody calls" nodes | the why line and the HUD `.hud-value`; note, tapes, stickers add none |
| 7 `.hud-card` | class kept, `Showdown equity` a direct text node, phrase in the same card |
| 8 direct text nodes | each asserted sentence is one element: `.verdict-why`, `.assumption-note`, `.ladder-note`, `.hud-subtext` |

**Test changes required: none.** `App.test.jsx:316` and `:330–336` pass unchanged; no displayed number
moves; new copy is label-only. **New i18n keys (names only):** `whyTag`, `ladderTag`, `assumptionTag`,
`hudTag`.

## 6. Tradeoffs accepted

- Cream on dark for three sheets — material and one loud region; the carbon ledger keeps it a dark tool.
- Grid rows + negative margins instead of literal absolute sheets — growth that cannot collide, same look.
- Six accent tokens (hue × ink/lit) — 4.5:1 at 11px on both materials.
- Mono for numeral-bearing prose — each asserted sentence stays one unbroken node.
- A 40px tuck under the ladder — a 48px right padding, i.e. a note with a visible paper stub.
- DOM order ladder-then-note — correct reading order at ≤1024, desktop columns swapped by `grid-column`.
- No rotation on tables — 11px rows stay level with the eye.

## 7. Alternatives considered

1. **Pure reserved-height absolute canvas** (the hypothesis unrefined): `.desk{position:relative;
   min-height:604px}` with `.desk-layer{position:absolute}` at `top:0 / 46% / 78%`. Rejected on
   arithmetic: absolute children contribute no height, so the desk cannot grow; VI adds ~2 lines to the
   why caption (+44px) and wraps the EV block (+26px), landing the ladder's fixed `top:46%` ~70px
   *inside* the verdict sheet, over `EXPECTED VALUE` — and at 390 the same offsets are 4× denser. Every
   fix is a JS measurement or a `max-height`/`overflow:hidden` clip; both are banned.
2. **Even three-region rule with rotations, no overlap** — safe, but reads as a centred stack; fails
   rubric 1.
3. **Cream page with charcoal ink**, and **all-dark charcoal notes** — the first rejects the mandated
   `#0a0a0a` base; the second has no shadow and no material edge, and the verdict loses its single loud
   region because every accent must be a lit tint.

## 8. Open questions and risks

- Does the two-tint accent rule read as one hue, or as six colours? (Fills-only is the flatter fallback.)
- At 1025–1279 a rung is ~153px wide — enough for VI's `100.000 VND` plus a wrapped blocked reason?
- **Fonts remain an asset dependency**: with only the fallback stack, does the wordmark still feel
  made-by-hand — and do both families include the **Vietnamese subset**, or will `ĐĨ`/`Cược hù` fall
  back mid-word?
- Is a grey-tan marker (`#cfc3a6`) a highlighter, or a smudge beside cream?
- Should the HUD become paper at ≥1025 (four pasted tickets), or does that break the one-loud-region law?
- Three tapes per screen is the budget — is the ledger tab worth one?

## 9. Next implementation step

Move `whyLine`, `assumptionLine`, `signedMoney`, `wholePercent` and the ladder JSX out of `App.jsx` into
`VerdictCard` / `LadderSheet` / `AssumptionNote` with zero markup-visible change, and prove `npm test`
green before a single token is retyped.
