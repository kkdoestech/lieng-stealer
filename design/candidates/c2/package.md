# Candidate B — Instrument Slab

One square-cornered slab owns the top of the results column and is the only bordered region on the
page: 1px `--line` frame, 2px kind-coloured left edge, `--bg-raised` surface, radius 0. Inside it,
three full-bleed hairline bands — **answer**, **sizing ladder**, **evidence** — hold a two-axis
answer, a three-row bar-and-number ladder on one shared `ev_ratio` scale, and one muted evidence
block. Everything below the slab is rule-separated text: no second box.

Base shape in one sentence: *the page is a document, and the slab is the one place the answer is
printed.*

---

## 1. Problem

Constraints that forced this shape, in the order they bit.

**From the four acceptance criteria (GROUNDING §1).** The verdict (EV, win rate, action) must be the
three most dominant things in the results column; every number must be mono and tabular so figures
align; the ladder must make "why not Large?" answerable without reading prose; the assumption line
must be visible but subordinate. Today the EV and the verb tie at 20px, the win rate lives two blocks
below in a HUD grid, the EV is printed twice, and the assumption line is a 12px sentence glued under
a 13px one.

**From the contract (GROUNDING §2, `backend/src/advice.py`).** The UI renders `Recommendation` and
`Rung` verbatim. Available: `action`, `kind`, `reason`, `amount`, `ev`, `ev_ratio`,
`equity_when_called`, `win_rate_defined`, `robust`, `why`, `ladder[3]` (`ev`, `ev_ratio`,
`worst_ev_ratio`, `robust`, `eligible`, `blocked_by`), and `summary` (`pot`, `fold_equity`,
`opponent_model`, `sizing`, `range_coverage_percent`, `bet_recommended_percent`,
`pure_bluff_break_even_fold_equity`, `action_counts`, `category_breakdown`). Nothing is computed in
JS and no field is invented. Two figures are therefore genuinely *unused* today by the verdict and
worth keeping: `advice.ev_ratio` (the pot-relative size of the answer) and `rung.worst_ev_ratio`
(the robustness number GROUNDING §6.5 calls the strongest "why not Large" signal).

**From the pinned tests (`frontend/src/App.test.jsx`).** These bind the shape harder than any style
rule, and every one of them is honoured below:

| test line | assertion | consequence for this design |
| :--- | :--- | :--- |
| 185–186 | `findByRole("heading", {name:"All in"})`, `getAllByText(/\+164,064/)` | the verb stays an `<h2>`, its accessible name is the action label alone (kind tag must be a *sibling* of the `h2`, never inside); the hero EV may move but must survive |
| 254 | `closest(".verdict-card")` has no "Bluff" when the answer is Check | the kind chip is suppressed on `CHECK`; no other node inside the slab may print the kind word |
| 305–317 | `getByText(/33,000/).closest(".ladder-rung")` has `.chosen`, `●`, "Small bet", "EV -11,995" | the recommended **amount appears as a direct text node exactly once in the document** (so the answer half must not reprint it); `.ladder-rung`, `.chosen`, `.rung-blocked` class names stay; the `●`/`○` marks stay; the EV string stays `EV {signedMoney}` |
| 331–336 | exactly **two** nodes match `/nobody calls at this setting/`; `getAllByText("Showdown equity")[0].closest(".hud-card")` is that figure | the win-rate figure becomes the slab's second hero figure and keeps the class hook `.hud-card` plus the label text `Showdown equity`; nothing else may print `winRateUndefined` |
| 344–347 | the assumption sentence is findable once | the assumption line is rendered exactly once |
| 192–196 | `thresholdNote(...)` sentence verbatim | the threshold sentence stays a full rendered line |

**From the hard rules (GROUNDING §5).** Dark near-black canvas, charcoal surfaces, hairlines, no
glow, no glass, no gradient, no shadow; square corners; no emoji; emerald = Value, amber = Thin,
gray = Check; mono for every number; no Inter, no Roboto.

**What DESIGN.md says that the user's new rules, the tests, or AGENTS.md override** (noted because
this package deliberately contradicts them):

| DESIGN.md | status | why |
| :--- | :--- | :--- |
| §3 "Nothing bigger" than `1.25rem/600` | **superseded** | the new rules demand a dominant verdict; this package sets verb 40px, hero 44px |
| §3 "Smallest text 13px, never smaller" | **superseded** | the shipped token layer and the dark-terminal look already use 10–11px labels; this package sets an **11px floor** and fixes GROUNDING's 10px complaint |
| §3 "One family … Segoe UI, **Roboto**" | **superseded** | Roboto is banned; mono is a second family, not "only for real code" |
| §1 "No cards by default … only controls, the error message and the open notes panel get a box" | **superseded** | the user asked for a Verdict Card; this package makes exactly one box and removes the others |
| §1 "no 'terminal', 'radar', 'HUD', 'telemetry' or 'engine' styling or copy" | **half superseded** | the *copy* ban holds (no visible such words); the *class-name* vocabulary stays because `App.test.jsx` selects on `.hud-card` and renaming buys nothing |
| §2 Ayu Dark palette | **superseded** | the working tree already ships the near-black + emerald/amber/gray/terracotta tokens |
| §1 "radius is `3px` everywhere" | **superseded** | `--radius: 0px` |
| §6 "No `●`, `[ ]` or `>` decorations" | **qualified** | `●`/`○` are information here (eligible/blocked, test-pinned), not decoration; no literal bracket characters are ever printed — the kind tag's 1px border *is* the bracket |
| §4 "Caller range … separate from fold frequency" | **superseded** | AGENTS.md §2.2: `fold_equity` is the only caller assumption; the slider only displays it |

---

## 2. Usage

Call sites, in render order inside `section.results-container`:

```jsx
{/* 1. the answer — the only bordered region on the page */}
{advice && <VerdictSlab advice={advice} summary={summary} handEval={handEval} t={t} />}

{/* 2. no hand entered: same slab, same frame, no right half, no ladder */}
{solveData && !handEval && (
  <EmptyVerdict summary={summary} actionCounts={actionCounts} t={t} />
)}

{/* 3. range-wide figures: three key/value pairs in whitespace, no box */}
{summary && <RangeRow summary={summary} t={t} />}
```

Leaf call sites inside `VerdictSlab`:

```jsx
<div className="ladder-strip">
  {advice.ladder.map((rung) => (
    <RungRow key={rung.action} rung={rung} chosen={rung.action === advice.action} t={t} />
  ))}
</div>

<div className="hud-card slab-rate">
  <span className="verdict-label">{t.showdownEquity}</span>
  <div className="slab-rate-value">{winRateText}</div>
  <div className="slab-rate-sub">{winRateSub}</div>
</div>
```

Unchanged call sites: `ControlPanel` internals, both tables, the notes drawer, `Stepper`.

---

## 3. Shape

### 3.1 Component hierarchy with props

```
App                                  (owns lang, pot, bet, hand, foldEquity, model, solveData, …)
└─ section.results-container
   ├─ VerdictSlab        advice, summary, handEval, t
   │  ├─ div.verdict-answer          [grid col 1]
   │  │  ├─ SlabAnswer   advice, handEval, t
   │  │  │  ├─ span.verdict-label         t.recommendedAction
   │  │  │  ├─ h2.verdict-title           t.actionLabel[advice.action]
   │  │  │  ├─ span.kind-chip             t.kindLabel[advice.kind]   (omitted when action === "CHECK")
   │  │  │  └─ div.verdict-meta           handEval.hand, .canonical_id, .score_name
   │  │  └─ VerdictWhy   advice, summary, t
   │  │     └─ p.verdict-why              whyLine(t, advice, summary)   (one text node)
   │  ├─ div.verdict-figures         [grid col 2, right-aligned stack]
   │  │  ├─ SlabFigures  advice, handEval, t
   │  │  │  ├─ span.verdict-label         t.expectedValueTag
   │  │  │  ├─ div.verdict-ev             signedMoney(advice.ev) + ev-currency span
   │  │  │  ├─ div.ev-caption             t.evAtRecommendedSize + " · " + t.evRatioPot(advice.ev_ratio)
   │  │  │  ├─ div.ev-caption             t.evAtYourBetSize(handEval.ev)     (only when ≠ advice.ev)
   │  │  │  └─ div.hud-card.slab-rate     ← the pinned selector hook
   │  │  │     ├─ span.verdict-label      t.showdownEquity
   │  │  │     ├─ div.slab-rate-value     percent(equity_when_called) | t.winRateUndefined
   │  │  │     └─ div.slab-rate-sub       t.vsCallingRange(..) · t.vsRandomShort(..)
   │  ├─ SizingLadder    advice, t
   │  │  └─ div.ladder-strip
   │  │     └─ RungRow   rung, chosen, t     ×3
   │  │        ├─ span.ladder-mark         rung.eligible ? "●" : "○"
   │  │        ├─ span.ladder-label        t.actionLabel[rung.action]
   │  │        ├─ EvBar  ratio=rung.ev_ratio, worstRatio=rung.worst_ev_ratio, chosen, muted
   │  │        │  ├─ span.bar-fill         style: left/width from evBarGeometry()
   │  │        │  └─ span.bar-zero, span.bar-unit     (1px ticks)
   │  │        ├─ span.ladder-amount       formatMoney(rung.amount) + currency
   │  │        ├─ div.ladder-ev            `${t.evTag} ${signedMoney(rung.ev)}`
   │  │        ├─ div.ladder-worst         `${t.worstEvTag} ${signedMoney(rung.worst_ev_ratio * pot)}`
   │  │        └─ p.ladder-phrase          rung.eligible ? null : t.blocked[rung.blocked_by]
   │  └─ EvidenceBand    advice, summary, t
   │     ├─ p.assumption-row       assumptionLine(t, summary)          ← rendered once
   │     ├─ div.evidence-line      four mono key/value pairs
   │     └─ p.ladder-note          t.thresholdNote(minEdge, foldStep)
   ├─ EmptyVerdict       summary, actionCounts, t        (same frame, .is-empty .is-check)
   ├─ RangeRow           summary, t
   │  └─ div.range-item  ×3: (t.colCoverage, range_coverage_percent)
   │                        (t.betRecommended, bet_recommended_percent)
   │                        (t.bluffThreshold, pure_bluff_break_even_fold_equity)
   ├─ category table      (unchanged)
   ├─ top-hands table     (unchanged)
   └─ notes drawer        (unchanged)
```

Free functions, unchanged or added, module scope in `App.jsx`:

```js
whyLine(t, advice, summary)          // unchanged
assumptionLine(t, summary)           // unchanged
percent / wholePercent / signedMoney // unchanged
evBarGeometry(ratio) -> {left, width} // NEW: the only place the bar domain exists
```

### 3.2 Data flow: `advice` → leaf

| field | travels as | rendered by | as |
| :--- | :--- | :--- | :--- |
| `action` | prop | `SlabAnswer` | `t.actionLabel[action]` inside `<h2 class="verdict-title">`; also `chosen` test in `SizingLadder` |
| `kind` | prop | `VerdictSlab` | `KIND_CLASSES[kind]` → sets `--kind` on the root; `SlabAnswer` prints `t.kindLabel[kind]` **only when `action !== "CHECK"`** |
| `reason` | prop | `VerdictWhy` | `whyLine()` → one text node |
| `amount` | via `rung.amount` only | `RungRow` | `formatMoney` + currency, right-aligned |
| `ev` | prop | `SlabFigures` | hero: `signedMoney(ev)` at 44px mono + `t.currency` |
| `ev_ratio` | prop | `SlabFigures` | caption `t.evRatioPot(ev_ratio)` → "1.64× pot" |
| `equity_when_called` + `win_rate_defined` | props | `SlabFigures` | `percent(...)` or `t.winRateUndefined` |
| `robust` | **not rendered** | — | superseded by `rung.worst_ev_ratio` itself (see §6) |
| `why` | **not rendered in this pass** | — | available for a future fold/call split bar; the sum is already the hero EV |
| `ladder[i].ev` | prop | `RungRow` | `EV ±n` mono, right-aligned |
| `ladder[i].ev_ratio` | prop | `EvBar` | fill length on the shared scale |
| `ladder[i].worst_ev_ratio` | prop | `RungRow` | `worst ±n` mono (× pot, then `formatMoney`) |
| `ladder[i].eligible` / `blocked_by` | props | `RungRow` | `●`/`○`, `.rung-blocked`, `t.blocked[...]` |
| `summary.pot` | prop | `EvidenceBand` | `pot 100,000 VND` |
| `summary.fold_equity` + `opponent_model` | props | `EvidenceBand` | `assumptionLine()` (once) — `model range` is *not* also printed, see §6 |
| `summary.profitable_combinations` … `sizing` | prop | `EvidenceBand` | `t.thresholdNote(minEdge, foldStep)` |
| `handEval.hand / canonical_id / score_name` | prop | `SlabAnswer` | one mono meta line |
| `handEval.ev` | prop | `SlabFigures` | `t.evAtYourBetSize(...)` caption when it differs from `advice.ev` |
| `handEval.profitable_fold_zones` | prop | `EvidenceBand` | `pays when 0%–100%` via `formatZones` (keeps the import used; lint) |
| `handEval.call_range_percent`, `equity_vs_random` | props | `SlabFigures` | win-rate sub-caption |
| `summary.range_coverage_percent`, `bet_recommended_percent`, `pure_bluff_break_even_fold_equity` | prop | `RangeRow` | three key/value pairs |

**Formatting ownership.** Each component owns exactly its own strings: `SlabFigures` owns money+currency+ratio caption and the defined/undefined win-rate decision; `RungRow` owns the rung's money, EV and worst formatting; `EvBar` owns the bar domain and nothing else; `EvidenceBand` owns the assumption sentence and the four mono pairs; `RangeRow` owns the three range figures; `VerdictSlab` owns only the class decision (`KIND_CLASSES[kind]` plus `is-check` when `action === "CHECK"`). No component divides `ev / pot` — the ratio fields are used as sent.

### 3.3 The exact `App.jsx` extraction

Keep `App.jsx` as the only file with components; add them **below `Stepper`, above `export default
function App`** (the same pattern `Stepper` already uses, and the reason `App.test.jsx` still imports
`./App.jsx` alone).

```jsx
// ── inserted after Stepper (~L183) ──────────────────────────────────────────────
const BAR_MIN = -1;   // ev/pot at its worst reachable value
const BAR_MAX = 2;    // ev/pot at its best reachable value
const BAR_SPAN = BAR_MAX - BAR_MIN;                       // 3 pot-units

function evBarGeometry(ratio) {
  const clamped = Math.min(Math.max(ratio, BAR_MIN), BAR_MAX);
  const zero = (0 - BAR_MIN) / BAR_SPAN;                  // 1/3 of the track
  const edge = (clamped - BAR_MIN) / BAR_SPAN;
  return { left: `${Math.min(zero, edge) * 100}%`, width: `${Math.abs(edge - zero) * 100}%` };
}

function EvBar({ ratio, muted })   // track + fill + two 1px ticks, aria-hidden
function RungRow({ rung, chosen, t })
function SizingLadder({ advice, t })
function SlabAnswer({ advice, handEval, t })
function SlabFigures({ advice, handEval, t })
function VerdictWhy({ advice, summary, t })
function EvidenceBand({ advice, summary, handEval, t })
function VerdictSlab({ advice, summary, handEval, t })
function EmptyVerdict({ summary, actionCounts, t })
function RangeRow({ summary, t })
```

Replaced render blocks in `App.jsx`:

| current lines | action |
| :--- | :--- |
| 496–574 (`{advice && (<div className="verdict-card …">…` ) | → `{advice && <VerdictSlab advice={advice} summary={summary} handEval={handEval} t={t} />}` |
| 577–596 (`.verdict-banner.verdict-empty`) | → `{solveData && !handEval && <EmptyVerdict … />}` |
| 599–643 (`.hud-metrics-grid` + 4 `.hud-card`) | → `{summary && <RangeRow summary={summary} t={t} />}` |
| 646–753 (tables, drawer) | unchanged |
| L529 `className="mono-green"` on the zone text | → neutral (`formatZones` moves into the evidence line) |
| `KIND_CLASSES`, `whyLine`, `assumptionLine`, `percent`, `wholePercent`, `signedMoney` | unchanged |

App.css then loses `.verdict-banner`, `.verdict-col-right`, `.verdict-breakeven`,
`.hud-metrics-grid`, `.hud-value`, `.hud-subtext`, `.mono-green` and gains the slab rules in §5.

### 3.4 The five hard decisions

**(a) Action wins; kind colours.** The verb is the largest UI-font element on the page
(`verb` 40px/600, `-0.02em`); the kind is an 11px mono tag with a 1px `--kind` border, a *sibling* of
the `h2` so the heading's accessible name stays the bare action (test L185). The 2px left edge and
the chosen row's top rule carry `--kind`. Reason: the action is the only thing the user can *do*;
kind is the argument for it, and one argument word does not deserve the same typographic weight as
the command. Two channels also survive colour blindness: the word says it, the hue confirms it.
`action` is never coloured as text — `--text-strong` for every verb, so the palette stays a
vocabulary of kinds (plus Check, below) and never becomes a good/bad verdict.

**(b) "Gray for Check" wins on a Check, and nothing contradicts it.** The edge follows
`--kind` in every state **except** `action === "CHECK"`, where the root also gets `.is-check` and the
edge turns `--check` gray. This is not an aesthetic preference: the pinned test (L254) forbids the
word "Bluff" anywhere inside `.verdict-card` when the answer is Check, so a `CHECK` carrying
`kind=BLUFF` **has no way to name its kind on this surface**. Colouring the edge terracotta would
then be a hue with no label — colour asserting something the page refuses to say. So gray is used
exactly as the user's rule intends: gray *is* the Check verdict's colour. The corner case that
`CHECK_ASSUMPTION_FRAGILE` carries `kind=BLUFF` is resolved by the *sentence*, which already says
where the money would come from ("Betting earns +13,550 if they fold 35%, but only +250 if they fold
25%") — and the hand's kind remains visible wherever kinds are labelled, in the top-hands table.
Consequence: on a Check, no row is `.chosen` (no rung has `action === "CHECK"`), so the ladder shows
three `○` rows and three policy phrases — the page's state is "every size lost", and the slab's gray
edge agrees with all three rows. No surface in the slab spends terracotta on a check.

**(c) Bluff keeps the shipped muted terracotta `#b96e5e`.** Justification: the three kinds
are a *descending scale of showdown value* (win rate ≥ 55% / ≥ 45% / < 45% — the thresholds are in
`AdviceThresholds`), so their hues should read as one progression, not as verdict quality. Emerald →
amber → terracotta is a single warm descent that stays inside a muted, non-neon palette; it is not
purple, and it is deliberately *not* `--bad #c4554d`, which is reserved for negative-EV numbers and
error text. A bluff is a real play with positive EV paid by folds — colouring it like an error would
be a lie the data contradicts (`KIND_CLASSES` and `index.css` already state this rule). Terracotta
and `--bad` are 1px-apart in hue but never adjacent in role: `--bad` never appears in the slab.

**(d) Numbers carry the ladder argument; the bar carries the comparison.** The numbers are primary
and mono, right-aligned in fixed columns so the three `EV` values and the three `worst` values align
on their right edges. The bar's job is only the thing numbers cannot do in one glance: show three
lengths **from one origin on one scale**.

*Scale, justified rather than chosen.* With the repo's EV identity
(`EV = f·P + (1−f)(win·FinalPot − B)`, `FinalPot = P + 2B`), `ev_ratio = EV/P` is **provably bounded
by [−1, +2]**: the worst case loses the whole wager, which is at most one pot (`B ≤ P` at the all-in
rung, and smaller rungs lose less); the best case keeps the 3-pot final pot minus the 1-pot wager.
So the shared domain is exactly the reachable set — no clamping distortion, no data-dependent
rescaling between solves. The track is therefore 3 pot-units wide, with a hard **zero rule at
one-third** and a 1-pot tick at two-thirds:

```
track = 3 pot-units            −1 pot       0        +1 pot      +2 pots
                               ├────────────┼─────────────┼────────────┤
                               0%          33.3%         66.7%       100%
+1.641 (chosen)                ├────────────┼█████████████████▌··········┤
+1.209                         ├────────────┼██████████▌·················┤
−0.119 (blocked)               ├──────█████▌┼·····························┤   ← fill LEFT of zero
```

*Sign handling.* `left = min(zero, edge)`, `width = |edge − zero|` — one formula, so a negative ratio
draws leftward from the same zero rule and its length is still exactly `|ev_ratio| / 3` of the track.
Sign is carried only by direction; no `--bad` fill, because losing money on a size is arithmetic, not
a kind.

*Why bars cannot mislead (or how they are fenced in).* (1) Ticks at 0 and +1 pot mean a length can be
*read* in pots, not only compared, and that unit is the same one the hero EV's caption prints
("· 1.64× pot"). (2) The bars never imply the chosen rung is the longest: the policy can block a
higher-EV rung with `NEEDS_BIGGER_EDGE`, so a longer bar on a struck-through row is a truthful and
useful sight — the eligibility marks, not the length, say who won. (3) At any width where the track
gets short, the numbers still carry the whole argument; the bar is `aria-hidden` and purely
redundant.

**(e) 390px: the slab becomes a stacked document, never a rounded card.** At `≤640px` the two-axis
split collapses to one column; the shared numeral axis switches from the slab's inner **right** edge
to its inner **left** edge (hero EV and win rate both start on the verb's x); the ladder rows keep
their exact column structure minus the bar, which moves to its own full-width line under each row
(the same origin, the same 3-pot span, so the three bars are still directly comparable). The frame
survives untouched: radius 0, 1px border, 2px left edge, full-bleed interior hairlines, 11px label
floor. What makes it a card at 390 is roundness and a floating drop shadow; neither exists. What
makes it a *slab* is that the bands still bleed to the border and the numbers still sit on a
declared axis.

---

## 4. Wireframe

### 4.1 1360px

`terminal-grid` = `340px | 1fr`; `results-container` padding 16 → **slab = 972px**. Slab padding 20;
two-up answer band `1fr 380px`; ladder columns `128 · 1fr(512) · 96 · 104 · 104`.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│▎1px --line frame, 2px --kind left edge, --bg-raised, radius 0                        │
│▎                                                                                     │
│▎  RECOMMENDED ACTION                             EXPECTED VALUE                      │  11/500/0.09em UI  --muted
│▎  All in                                              +164,064                       │  40/600/-0.02em UI  --text-strong
│▎                                                             VND                    │  44/500 mono       --text-strong
│▎  ⟨VALUE⟩  As Kh Qd · Q-K-A · Liêng Q-K-A    at the recommended size · 1.64× pot    │  11/600 mono tag · 12 mono --muted
│▎                                              ───────────────────────────────        │  1px --line, 96px wide
│▎                                              SHOWDOWN EQUITY                        │  11/500/0.09em UI
│▎                                              99.5%                                  │  24/500 mono
│▎                                              vs. the top 65% that call ·            │  12 mono --muted
│▎                                              99.7% vs. a random hand                │
│▎                                                                                     │
│▎  You win about 99.5% when called, so the all-in is worth the risk even if they      │  13/400 UI --text
│▎  fold 10% less than you think.                                                      │  (one text node)
├──────────────────────────────────────────────────────────────────────────────────────┤  full-bleed 1px --line
│▎  ● SMALL BET   ····██████████▌·····  33,000  EV +120,932  worst +117,639            │
│▎  ● LARGE BET   ····████████████▌···  75,000  EV +147,970  worst +140,480            │
│▓▓● ALL IN      ····█████████████▌·· 100,000  EV +164,064  worst +154,076            │  ← .chosen:
│▎                ▲              ▲     ▲                                               │    --bg-inset row,
│▎              −1 pot          0    +1 pot   +2 pots                                  │    2px --kind top rule,
│▎                                                                                     │    --kind bar fill
├──────────────────────────────────────────────────────────────────────────────────────┤
│▎  Assumption: the opponent folds their weakest 35% of hands and calls with the       │  13/400 UI --muted
│▎  best 65%.                                                                          │  + 1px --line-strong bracket
│▎  pot 100,000 VND · model range · pays when 0%–100% · worst cell +1.54× pot          │  11 mono --faint/--muted
│▎  We recommend a bet only when it earns at least 5% of the pot and still earns it    │  11/400 UI --faint
│▎  if the opponent folds 10% less than you think.                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
  ≈ 452px tall (answer band 236, ladder 3×56, evidence band 104)

   40px    verb          ← largest UI text on the page
   44px    hero EV       ← largest text of any kind
   24px    win rate      ← third hero
   13px    ladder EV / worst, why line, assumption
   12px    hand meta, captions, blocker phrases
   11px    tracked labels, evidence pairs, threshold note   ← the floor

  width check: 20 + 380 + 32 + 520 + 20 = 972
```

Chosen-state detail for the `.chosen` row (drawn above as `▓▓`): `--bg-inset #0c0e10` surface, a 2px
`--kind` rule across its top edge (painted by a zero-height `::before`, so no layout shift), `●` and
label at `--text-strong`, bar fill `--kind`. With this fixture every rung is `eligible`, so all three
marks are `●` — three filled marks mean "all three are allowed", and only the rule + surface say
which one the policy took.

The Check state (the other terminus):

```
├──────────────────────────────────────────────────────────────────────────────────────┤
│▎  RECOMMENDED ACTION                             EXPECTED VALUE                      │
│▎  Check                                                  +0  VND                    │  verb is the same 40px
│▎  As Kh Qd · 5-3-2 · Điểm 0                    at the recommended size               │  no kind tag (test L254)
│▎                                              at your bet size: +2,500 VND           │  handEval.ev ≠ advice.ev
│▎                                              SHOWDOWN EQUITY                        │
│▎                                              0.0%  →  replaced by               │
│▎                                              "nobody calls at this setting, …"     │
│▎  Betting earns +13,550 if they fold 35%, but only +250 if they fold 25%. One bad    │
│▎  read from break-even.                                                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│▎  ○ SMALL BET   ····█████▌············  33,000  EV  +13,550  worst +250              │  all ○, no .chosen
│▎    not worth the extra risk                                                         │  12/400 --muted
│▎  ○ LARGE BET   ····················  75,000  EV  -13,750  worst -13,750            │  EV struck through
│▎    not worth the extra risk                                                         │
│▎  ○ ALL IN      ···················· 100,000  EV  -30,000  worst -30,000            │
│▎    not worth the extra risk                                                         │
```

The slab's left edge is `--check` gray in this state and terracotta never appears.

### 4.2 390px

Slab = 390 − 24 = **366px**; inner width 326; padding 18 top/bottom, 16 sides.

```
┌────────────────────────────────────────────┐
│▎1px frame, 2px --kind edge, radius 0        │
│▎                                            │
│▎ RECOMMENDED ACTION                         │  11/500/0.09em
│▎ All in                                     │  28/600/-0.02em
│▎ ⟨VALUE⟩  As Kh Qd · Q-K-A ·               │  11 mono tag
│▎ Liêng Q-K-A                               │  12 mono (meta wraps)
│▎                                            │
│▎ EXPECTED VALUE                             │  11 label
│▎ +164,064 VND                               │  30/500 mono  ← numeral axis = left edge
│▎ at the recommended size · 1.64× pot        │  12 mono --muted
│▎ SHOWDOWN EQUITY                            │  11 label
│▎ 99.5%   vs. the top 65% that call          │  20/500 mono + 12 mono
│▎                                            │
│▎ You win about 99.5% when called, so the    │  13/400 UI, 3 lines
│▎ all-in is worth the risk even if they      │
│▎ fold 10% less than you think.              │
├────────────────────────────────────────────┤
│▎ ● ALL IN                      100,000 VND │  label left, amount right
│▎ EV +164,064      worst +154,076           │  13 mono
│▎ ····█████████████▌·· ····                  │  bar full width, 14 cells
│▎                                            │
│▎ ● LARGE BET                    75,000 VND │
│▎ EV +147,970      worst +140,480           │
│▎ ····████████████▌····                      │
│▎                                            │
│▎ ● SMALL BET                    33,000 VND │
│▎ EV +120,932      worst +117,639           │
│▎ ····██████████▌·····                       │
├────────────────────────────────────────────┤
│▎ Assumption: the opponent folds their       │  13/400 --muted
│▎ weakest 35% of hands and calls with the    │
│▎ best 65%.                                  │
│▎ pot 100,000 VND · model range              │  11 mono, 2 lines
│▎ pays 0%–100% · worst cell +1.54× pot       │
│▎ We recommend a bet only when it earns at   │  11/400 --faint
│▎ least 5% of the pot and still earns it if  │
│▎ the opponent folds 10% less than you think.│
└────────────────────────────────────────────┘
  ≈ 700px tall. No horizontal scroll (widest fixed content: "EV +164,064  worst +154,076" ≈ 246px).

  ladder order at ≤640: the chosen row sorts *first* (JSX order: chosen, then the rest in
  ladder order), so the answer is the first row on a phone and the ladder stays a ladder.

  below the slab (unchanged surface, no box):
  HANDS WORTH A BET                     71.6%
  COVERAGE                             100.0%
  BLUFF BREAK-EVEN                      33.3%
```

---

## 5. Styling plan

### 5.1 Type scale (named steps; only these, in the slab)

| step | px | weight | letter-spacing | family | use |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `verb` | 40 (28 @≤640) | 600 | −0.02em | `--font-ui` | the action verb, `<h2>` |
| `hero` | 44 (30) | 500 | −0.01em | `--font-mono` tabular | hero EV |
| `figure` | 24 (20) | 500 | −0.005em | `--font-mono` tabular | win rate; also the empty-state title (UI 500) |
| `rung` | 13 | 500 | 0 | `--font-mono` tabular | ladder amount, EV, worst |
| `body` | 13 | 400 | 0 | `--font-ui` | why sentence |
| `evidence` | 13 | 400 | 0 | `--font-ui` | assumption sentence |
| `meta` | 12 | 400 | 0 | `--font-mono` tabular | hand meta, EV captions, win-rate sub, blocker phrases |
| `tag` | 11 | 600 | 0.09em | `--font-mono` | kind tag, rung labels (uppercase via CSS, never in the DOM) |
| `micro` | 11 | 500 | 0.09em | `--font-ui` | tracked labels, uppercase |
| `mono-key` | 11 | 400 | 0 | `--font-mono` | evidence pairs, bar-unit annotation |
| `note` | 11 | 400 | 0 | `--font-ui` | threshold sentence |

Families are the existing tokens — `"Segoe UI Variable Text", "Segoe UI", system-ui, …` and
`"Cascadia Mono", "Cascadia Code", "SF Mono", "JetBrains Mono", Consolas, …`. No webfont is loaded,
so there is no Inter and no Roboto anywhere in the cascade. **No 10px text remains in the results
column** (GROUNDING §4's slack); `ladder-label`, `kind-chip`, `verdict-label`, `panel-tag` and the
evidence pairs all move 10 → 11. The controls panel keeps its 10px labels in this diff (out of scope,
noted in §8).

Add to `index.css`:

```css
--fs-11: 11px; --fs-12: 12px; --fs-13: 13px; --fs-24: 24px; --fs-40: 40px; --fs-44: 44px;
--slab-pad: 20px; --slab-gap: 32px;
```

### 5.2 Spacing scale

`4 · 6 · 8 · 12 · 16 · 20 · 24 · 32`. In the slab only: `20` band padding (`--slab-pad`) and slab
sides; `32` the gutter between the two answer halves (`--slab-gap`); `16` ladder row padding-y and
the first-row's top inset; `12` label→value inside a cell and the evidence band's line gap; `8`
tag→verb; `6` label→verb; `4` mark→label. Nothing else is declared. One hairline per band boundary,
full-bleed (`margin: 0 calc(-1 * var(--slab-pad))`), never an inset rule.

### 5.3 Token usage

| element | surface | border | ink |
| :--- | :--- | :--- | :--- |
| slab root | `--bg-raised` | `1px --line`, `border-left: 2px var(--kind, var(--check))`, `--radius` | — |
| slab root `.is-check` / `.is-empty` | `--bg-raised` | left edge forced to `--check` | — |
| answer band | transparent (slab) | — | verb `--text-strong`; label `--muted`; meta `--muted` with `.holding-tag` `--text-strong` |
| kind tag | transparent | `1px var(--kind)` | `--kind` |
| hero EV | — | — | `--text-strong`, currency `--muted` |
| win-rate figure (`.hud-card`) | — | none (it is not a card any more, only a selector hook) | value `--text-strong`, sub `--muted` |
| hairline above ladder | — | `1px --line` | — |
| ladder row | transparent | `1px --line` top; chosen: `--bg-inset` + `2px --kind` top | label `--muted` → chosen `--text-strong`; numbers `--text`/`--text-strong` |
| blocked row | — | — | `--muted` label, `EV` line `line-through`, phrase `--muted` |
| bar track | transparent | `1px --line` left+right caps; ticks `--line` (1 pot) and `--line-strong` (zero) | — |
| bar fill | chosen `--kind`; every other row `--faint` | — | — |
| evidence band | `--bg-inset` (one tone darker than the slab — the *sub* band) | `1px --line` top | assumption `--muted`, bracket `--line-strong`, pairs `--faint` keys / `--text` values, note `--faint` |
| range row | page `--bg` | none | keys `--faint`, values `--text` |

Total accent spend per screen: one `--kind` at 2px, one kind-coloured tag border, one kind-coloured
bar (and the chosen row's rule, same hue). No `--bad` inside the slab. No shadow anywhere.

### 5.4 Kind → colour map

```css
.kind-value { --kind: var(--value); }   /* emerald #3fb27f — Value  */
.kind-thin  { --kind: var(--thin);  }   /* amber   #d0a15a — Thin   */
.kind-bluff { --kind: var(--bluff); }   /* terracotta #b96e5e — Bluff (see §3.4c) */
.kind-none  { --kind: var(--check); }   /* never returned by the API */
.is-check   { --kind: var(--check); }   /* the Check override — see §3.4b */
```

Precedence is deliberate: `.is-check` is declared **after** the kind classes and out-specifies them
(`.verdict-card.is-check`), so a semantic order (answer first, argument second) exists in the CSS
itself, not just in a comment.

### 5.5 CSS class list per component

| component | classes (new in **bold**) |
| :--- | :--- |
| `VerdictSlab` | `.verdict-card`, `.kind-value/.kind-thin/.kind-bluff/.kind-none`, **`.is-check`**, **`.verdict-grid`** (the `1fr 380px` top grid) |
| `SlabAnswer` | **`.verdict-answer`**, `.verdict-label`, `.verdict-title`, `.verdict-title-row`, `.kind-chip`, `.verdict-meta`, `.holding-tag`, `.holding-sep`, `.holding-score` |
| `VerdictWhy` | `.verdict-why` |
| `SlabFigures` | **`.verdict-figures`**, `.verdict-label`, `.verdict-ev`, `.ev-currency`, **`.ev-caption`**, `.hud-card`, **`.slab-rate`**, **`.slab-rate-value`**, **`.slab-rate-sub`** |
| `SizingLadder` | `.ladder-strip` |
| `RungRow` | `.ladder-rung`, `.chosen`, `.rung-blocked`, `.ladder-mark`, `.ladder-label`, `.ladder-amount`, `.ladder-ev`, **`.ladder-worst`**, **`.ladder-phrase`**, `.ev-currency` |
| `EvBar` | **`.ladder-bar`**, **`.bar-fill`**, **`.bar-tick`** (one element, two `::before/::after` ticks) |
| `EvidenceBand` | **`.verdict-evidence`**, **`.assumption-row`**, **`.evidence-line`**, **`.evidence-pair`**, **`.evidence-key`**, **`.evidence-val`**, `.ladder-note` |
| `EmptyVerdict` | `.verdict-card`, `.is-empty`, `.is-check`, **`.verdict-empty-body`**, `.verdict-label`, `.verdict-title`, `.verdict-meta`, `.verdict-assumption` |
| `RangeRow` | **`.range-row`**, **`.range-item`**, **`.range-key`**, **`.range-value`** |

Removed: `.verdict-banner`, `.verdict-col-right`, `.verdict-breakeven`, `.hud-metrics-grid`,
`.hud-value`, `.hud-subtext`, `.mono-green`.

### 5.6 Key CSS mechanics worth pinning down

```css
/* the two edges are the slab's signature; the zero-height rule gives the chosen row its 2px
   without changing row height */
.ladder-rung { position: relative; border-top: 1px solid var(--line); }
.ladder-rung.chosen::before {
  content: ""; position: absolute; inset: 0 0 auto 0; height: 2px; background: var(--kind);
}

/* one scale, two ticks, no gradient */
.ladder-bar { position: relative; height: 9px; border-left: 1px solid var(--line);
              border-right: 1px solid var(--line); }
.ladder-bar::before { /* zero rule  */ content: ""; position: absolute; left: 33.333%;
                      top: -2px; bottom: -2px; width: 1px; background: var(--line-strong); }
.ladder-bar::after  { /* +1 pot tick */ content: ""; position: absolute; left: 66.667%;
                      top: 0; bottom: 0; width: 1px; background: var(--line); }
.bar-fill { position: absolute; top: 0; bottom: 0; background: var(--faint); }
.ladder-rung.chosen .bar-fill { background: var(--kind); }

/* the pinned test asserts the string "EV -11,995" with a real space, so the label and the number
   must stay two text nodes of one element, not two flex children */
.ladder-ev { display: block; font: 500 var(--fs-13)/1.3 var(--font-mono);
             font-variant-numeric: tabular-nums; text-align: right; }

@media (max-width: 640px) {
  .verdict-grid { grid-template-columns: 1fr; }
  .verdict-ev, .slab-rate-value { text-align: left; }      /* axis moves to the left edge */
  .ladder-rung { grid-template-columns: 1fr auto; }
  .ladder-bar { grid-column: 1 / -1; margin-top: 8px; }    /* full width, same scale */
  .ladder-phrase { grid-column: 1 / -1; }
}
```

### 5.7 What the diff touches, in order

1. `index.css` — 8 new tokens (`--fs-*`, `--slab-pad`, `--slab-gap`). Nothing else.
2. `App.css` — the slab block replacing the verdict-card/ladder/hud rules; `.hud-card` reduced to a
   selector hook with no surface; `panel-header`/`table-wrapper` lose their borders in the results
   column (the slab becomes the only bordered region); the 640px block above.
3. `App.jsx` — the extraction in §3.3 and the three call-site swaps.
4. `i18n.js` — the six keys below, EN + VI.

No backend file, no test file, no `solve-contract.json` change.

### 5.8 New i18n keys

| key | EN | VI (draft — needs native sign-off, §8) |
| :--- | :--- | :--- |
| `worstEvTag` | `"worst"` | `"xấu nhất"` |
| `footerPot` | `"pot"` | `"pot"` |
| `footerModel` | `"model"` | `"mô hình"` |
| `footerWorstCell` | `"worst cell"` | `"ô xấu nhất"` |
| `footerPaysWhen` | `"pays when"` | `"có lãi khi"` |
| `evRatioPot` | `(ratio) => \`${ratio}× pot\`` | same, no translation needed |

Reused unchanged: `recommendedAction`, `actionLabel`, `kindLabel`, `blocked`, `expectedValueTag`,
`evTag`, `evAtRecommendedSize`, `evAtYourBetSize`, `winRateUndefined`, `showdownEquity`,
`showdownEquitySub`, `vsCallingRange`, `vsRandomShort`, `currency`, `modelAssumptionRange`,
`modelAssumptionRandom`, `thresholdNote`, `noHandTitle`, `noHandBody`, `actionCountsLine`,
`colCoverage`, `betRecommended`, `bluffThreshold`, `notAvailable`.

---

## 6. Tradeoffs accepted

- We accept that the slab is ~450px tall (about what the old card + HUD grid + their gaps took) in
  exchange for the answer never being interrupted by a second region.
- We accept that the recommendation's `amount` is printed only once, inside the ladder row, in
  exchange for `getByText(/33,000/)` staying unambiguous — and in exchange for the answer half being
  pure command, not a receipt.
- We accept that an *eligible but unchosen* rung shows no phrase, in exchange for the phrase column
  meaning exactly one thing: the three `blocked_by` policy codes, the only information the numbers
  cannot carry. Its "reason for losing" is arithmetic and is on screen twice.
- We accept losing the textual `profitableWhen` sentence from the verdict (it duplicated the profit
  map already drawn in the control panel) in exchange for a four-pair evidence line that fits on one
  line at 1360 and keeps `formatZones` legitimately used.
- We accept keeping the class name `.hud-card` on a figure that is no longer a card, in exchange for
  a pinned test staying green without touching `App.test.jsx`.
- We accept binding the win-rate figure to `advice.equity_when_called` instead of
  `handEval.showdown_equity` (equal in every pinned fixture) in exchange for the page's hero win rate
  being the exact number the recommendation was built from.
- We accept that the bar is compressed on the positive side (a typical ladder spends 74–88% of the
  track) in exchange for an honest, non-rescaling domain proven by the EV identity, plus ticks that
  let a length be read in pots.
- We accept that `advice.robust` and `rung.robust` are not rendered as status marks, in exchange for
  printing the number they summarise (`worst_ev_ratio`) — a boolean is a claim, a number is evidence,
  and DESIGN.md §1 forbids status that carries no information.
- We accept that a CHECK+BLUFF hand loses its kind hue in the slab, in exchange for the surface never
  colouring something it is test-forbidden from naming.
- We accept that the two tables lose their borders, in exchange for the slab being the only bordered
  region (bordering is spent on the verdict, not on the appendix).
- We accept a 512px bar at 1360 (wide enough to read as a progress meter) in exchange for the exact
  cross-row comparison; the ticks, the caps and the mono numbers keep it a scale, not a meter.

---

## 7. Alternatives considered

**A1 — Three vertical cells (the hypothesis as originally drawn).** Rejected after arithmetic
inspection: three side-by-side cells cannot align a number column (three different x origins), and
comparing three horizontal bar *lengths* that start 512px apart is the weakest possible bar reading.
Rows give one origin, one width, one zero rule, and identical `grid-template-columns`, so the three
`EV` values and the three `worst` values align on their right edges — literally what rubric 2 asks
for ("aligns on the digit across rows"). Rows also inherit the 390px layout for free instead of being
a separate construction. The slab, the bands, the kinds and the scale all survive from the hypothesis;
only the ladder's axis direction changed.

**A2 — Two slabs: an answer slab and an evidence slab.** Rejected: two bordered regions mean two
things of equal weight, and the reader has to decide which one is the verdict. It also reproduces
today's exact problem (EV in the card, win rate in another box).

**A3 — No slab at all: a hairline-ruled document** (the aesthetic DESIGN.md §1 asks for). Rejected: it
is the current page minus the box, and the acceptance criteria call for a Verdict *Card* whose three
figures are unmistakably the top of the column. Without a surface, dominance has to come from pure
type scale, which at 44px looks accidental on a page whose other text is 13px.

**A4 — Figure-first stack** (hero EV at 44px on top, the verb beneath it as a caption). Rejected: it
makes the *number* the headline and demotes the command, inverting decision (a). The user asked what
to do — the verb must be the first thing read, even though it is 4px smaller.

**A5 — Keep the four-cell HUD grid and restyle it** (move the win rate into cell 1, put the ladder
underneath). Rejected: it keeps the EV printed twice, which is the single clearest defect GROUNDING
§3 names, and it keeps a second bordered grid on the page.

**A6 — A merged worst-case bar** (fill from zero to `worst_ev_ratio` in strong colour, then to
`ev_ratio` in weak colour) was considered and rejected: it encodes two numbers in one length and
makes "how long is this bar" unanswerable, which is the exact failure mode bars are criticised for.

---

## 8. Open questions and risks

1. **Vietnamese copy for the four new labels.** `worstEvTag: "xấu nhất"` is my draft; `"tệ nhất"` may
   read more naturally for a *value*, and `footerWorstCell: "ô xấu nhất"` assumes "ô" (cell) is the
   right word for "the worst stress cell". GROUNDING says VI wording is not to be improvised — this
   needs a native speaker before the key lands. Fallback that avoids all four keys: drop the mono
   evidence line's pairs to `pot` + `model` only and let the ladder's `EV` lines carry the rest.
2. **Is gray-on-Check right, or should the kind win and the label return?** I resolved it by letting
   the test's silence rule drive the colour. If the test's "no Bluff on a check" rule is ever relaxed,
   the better design is probably the kind-coloured edge *plus* a muted kind tag — colour and label
   together. Which of the two does the user actually want to see on a `CHECK_ASSUMPTION_FRAGILE`?
3. **Does a 512px bar read as a progress meter** at 1360? If it does, the fix is to cap the track at
   ~320px and keep the numerals right-aligned — but then the three bars no longer share both origin
   and width, so it must be capped for all three at once.
4. **Is the evidence band too tall (104px, three lines) to be "thin"?** The alternative is to move the
   `thresholdNote` sentence out of the slab, one hairline lower, as page-level small print.
5. **Should the chosen row sort first at ≤640px?** I assumed yes (the answer above its alternatives),
   but that makes the ladder order differ between breakpoints, and the ladder's order encodes size —
   is a size ladder allowed to reorder itself on a phone?
6. **Will the two tables look orphaned** once they lose their borders? If yes, the cheaper fix is to
   give each table section a 1px `--line` *top* rule and a 32px gap, not a box.
7. **`advice.equity_when_called` vs `handEval.showdown_equity`** — equal in all five pinned fixtures,
   but they are different fields and may diverge for a future model. Which one is the page's "win
   rate" when they disagree? (I bound to the advice's, because the verdict is built on it.)
8. **A hand-crafted fixture could show `.chosen` and `.rung-blocked` on the same row** (the
   parametrised `LARGE_VALUE` case does exactly that). The CSS must let `.chosen` win the rule and
   `.rung-blocked` win the strike-through; is a chosen-but-blocked row a state the API can ever
   produce? If not, should the UI assert that with a dev-only check?

---

## 9. Next implementation step

Write `App.css`'s slab block first — `.verdict-card` grid, the three full-bleed bands, and the
`.ladder-rung` row grid with `.ladder-bar` — against the existing `solve-contract.json` values, then
swap the `App.jsx` call sites and add the six `i18n.js` keys in both languages.
