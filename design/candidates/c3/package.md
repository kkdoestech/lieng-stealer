# Candidate C3 — NUMBER-FIRST POSTER

Structural hypothesis, explored and then adapted where the evidence forced it: **typography carries the
hierarchy, surfaces do not.** The top of the results column is a poster block with no border and no
surface. The EV is the largest type in the product; the action verb sits directly above it as the
number's *scope*; the win rate sits beside it at half the EV's size. Kind is a 2px rule under the
poster with its label set *on* the rule, not in a chip. The assumption is its own labelled row above
that rule. The ladder is a five-column aligned grid with hairlines only. The why sentence follows the
ladder. The four-cell HUD becomes one low stat line. Everything below is resolvable as a diff to
`frontend/src/App.jsx`, `frontend/src/App.css`, `frontend/src/index.css`, `frontend/src/i18n.js` plus
three new presentational modules.

---

## 1. Problem

Five constraints, in the order they shaped the shape.

1. **The page has one job.** GROUNDING §1: make one action, one wager, one EV and the three rungs
   readable in a few seconds. Today neither the verb nor the EV dominates (`App.css` sets both at
   `20px`) and the win rate is missing from the card entirely — it lives two blocks down in a
   `.hud-card`. The fix is not "bigger": it is *one* largest element and a descending scale under it.
2. **Numerals are the argument, so they get the geometry.** Every number must be mono and tabular
   (user rule 2), which means numbers can be trusted to align. If they align on one axis, the axis
   itself becomes structure: the hero, the amount column, the EV column, the worst-case column and
   the gap column all hang from the same right edge. Type, not boxes, then does the grouping.
3. **The surface budget is already spent.** `.verdict-card` is the only bordered box on the page
   (GROUNDING §4) and therefore the only element *competing* with the poster. Removing its surface
   and its padding-box makes the poster the page's voice and demotes the two tables to the appendix
   — which is also what `DESIGN.md` §1 already asked for ("no cards by default"). The verdict stays a
   *card* in the only senses that survive scrutiny: one named landmark, one coloured edge, one
   arithmetic argument.
4. **Kind must colour, action must command.** The domain splits `action` (the command) from `kind`
   (the argument) and `advice.py` keeps `kind` on a check precisely so a caller *can* say "check,
   because this is a bluff". A chip can hold both; a rule cannot, so the rule carries the kind, the
   verb carries the action, and the one case where they disagree (a check whose kind is BLUFF) is
   resolved in §5.4 — forced, not chosen, by `App.test.jsx`.
5. **The existing tests are part of the contract.** `App.test.jsx` pins more than GROUNDING §2 lists:
   the rung container classes (`ladder-rung`, `chosen`, `rung-blocked`), the literal `●`/`○` marks,
   the contiguous string `EV -11,995`, exactly two occurrences of `nobody calls at this setting`,
   exactly one node matching `/33,000/`, a heading whose accessible name is `All in`, and *no* `Bluff`
   text inside a check's `.verdict-card`. Every one of those constraints is load-bearing in the design
   below; §8 lists them as risks with their mitigations. `npm test` is read-only for this candidate.

Superseded prohibitions from the older spec are listed in §5.9.

---

## 2. Usage

The call sites come first, because the poster is defined by what it is *given*, not by what it draws.
All three components are presentational: no state, no effects, no fetches, no domain arithmetic
except the display arithmetic named in §3.3.

```jsx
// App.jsx — results column, in order. `advice`, `handEval`, `summary` are the response's own
// objects; `t` is STRINGS[lang]. Nothing is recomputed here.

<section className="results-container">
  {advice && (
    <VerdictPanel
      advice={advice}        /* Recommendation: action, kind, reason, amount, ev, equity_when_called,
                                win_rate_defined, robust, why, ladder[3]                        */
      handEval={handEval}    /* hand, canonical_id, score_name, ev, sensitivity, profitable_fold_zones */
      summary={summary}      /* pot, fold_equity, opponent_model, sizing, …                     */
      t={t}
    />
  )}

  {solveData && !handEval && (
    <VerdictEmpty summary={summary} actionCounts={actionCounts} t={t} />
  )}

  <StatLine advice={advice} handEval={handEval} summary={summary} t={t} />

  {/* unchanged: coverage table, top-hands table, notes drawer */}
</section>
```

```jsx
// VerdictPanel.jsx — internal composition. The poster and the ladder share one grid template, which
// is the whole alignment mechanism (§5.6).

<section className={`verdict-card ${kindClassFor(advice)}`} aria-labelledby="verdict-verb">
  <PosterHead advice={advice} handEval={handEval} t={t} />
  <AssumptionRow t={t} summary={summary} />
  <KindRule advice={advice} t={t} />
  <SizingLadder advice={advice} summary={summary} t={t} />
  <p className="verdict-why">{whyLine(t, advice, summary)}</p>
  <p className="verdict-evidence">{evidenceLine(t, advice, handEval, summary)}</p>
  <p className="ladder-note">{t.thresholdNote(…, …)}</p>
</section>
```

```jsx
// SizingLadder.jsx — one row per rung. The chosen test is the same identity the product promises:
// the card and the table row are the same object (GROUNDING §2), so no rung is ever re-priced.

{advice.ladder.map((rung) => {
  const chosen = advice.action !== "CHECK" && rung.action === advice.action;
  const gap    = canShowGap(advice, rung);           // number | null — see §3.3
  return (
    <div
      key={rung.action}
      className={`ladder-rung${chosen ? " chosen" : ""}${rung.eligible ? "" : " rung-blocked"}`}
    >
      <span className="ladder-mark">{rung.eligible ? "●" : "○"}</span>
      <span className="ladder-option">{t.actionLabel[rung.action]}</span>
      <span className="ladder-amount">{formatMoney(rung.amount, t.locale)}{" "}
        <span className="ev-currency">{t.currency}</span></span>
      <span className="ladder-ev"><span className="vh">EV </span>{signedMoney(rung.ev, t.locale)}</span>
      <span className="ladder-worst">{signedMoney(worstEv(rung, summary), t.locale)}</span>
      <span className="ladder-verdict">
        {chosen && <span className="ladder-chosen">{t.ladderChosen}</span>}
        {!rung.eligible && <span className="ladder-blocked">{t.blocked[rung.blocked_by]}</span>}
        {gap !== null && <span className="ladder-gap">{t.rungGap(signedMoney(gap, t.locale))}</span>}
      </span>
    </div>
  );
})}
```

---

## 3. Shape

### 3.1 Component hierarchy with props

```
App                                        (owns lang, inputs, solveData, error — unchanged)
├─ header.terminal-header                  (unchanged)
├─ section.control-panel                   (unchanged: pot, bet, fold slider, model, call range,
│                                           profit map, hand input, Run, error, specs)
└─ section.results-container               (unchanged wrapper, minus the padding it gives back)
   ├─ VerdictPanel            ← NEW module frontend/src/verdict/VerdictPanel.jsx
   │  │  props: advice, handEval, summary, t
   │  │  root:  <section class="verdict-card kind-*" aria-labelledby="verdict-verb">  (no border, no surface)
   │  ├─ PosterHead            (same file)
   │  │     props: advice, handEval, t
   │  │     └─ holding meta · label EXPECTED VALUE · label WHEN CALLED
   │  │        h2#verdict-verb.poster-verb        ← t.actionLabel[action]      (15/700/0.14em)
   │  │        div.poster-hero.hero-xl|l|m        ← signedMoney(advice.ev) + t.currency (44/500)
   │  │        div.poster-win                     ← winFigure(advice, t)       (24/500)
   │  ├─ AssumptionRow         (same file)
   │  │     props: summary, t
   │  │        span.assumption-tag ← t.opponentFolds
   │  │        p.assumption-text   ← assumptionLine(t, summary)
   │  ├─ KindRule              (same file)
   │  │     props: advice, t
   │  │        div.poster-rule.css-class-carries--kind
   │  │        span.kind-tag ← t.kindLabel[advice.kind]   (omitted when action === CHECK)
   │  ├─ SizingLadder          ← NEW module frontend/src/verdict/SizingLadder.jsx
   │  │     props: advice, summary, t
   │  │        div.ladder-strip (role=list) > div.ladder-head-row + 3 × div.ladder-rung
   │  ├─ p.verdict-why         ← whyLine(t, advice, summary)            (14/400, 62ch)
   │  ├─ p.verdict-evidence    ← evidenceLine(t, advice, handEval, summary)   (11 mono)
   │  └─ p.ladder-note         ← t.thresholdNote(minEdge, foldStep)      (11/400)
   ├─ VerdictEmpty            ← NEW module frontend/src/verdict/VerdictEmpty.jsx
   │     props: summary, actionCounts, t   (boxless; gray rule; no kind; t.recommendedAction kept here)
   ├─ StatLine                ← NEW module frontend/src/verdict/StatLine.jsx
   │     props: advice, handEval, summary, t
   │        div.hud-metrics-grid > 3 × div.hud-card
   │          span.stat-label + span.hud-value (mono) [+ span.hud-phrase when win rate undefined]
   ├─ coverage table          (unchanged)
   ├─ top-hands table         (unchanged)
   └─ notes drawer            (unchanged)
```

Pure helpers move out of `App.jsx` into **`frontend/src/verdict/verdict-format.js`** so that no
component makes a formatting decision inline: `signedMoney`, `percent`, `wholePercent`, `whyLine`,
`assumptionLine`, `evidenceLine`, `winFigure`, `worstEv`, `rungGap`, `heroStep`, `kindClassFor`,
`isCheck`. This is a *move*, not a rewrite: `whyLine` and `assumptionLine` keep their bodies verbatim
so the pinned sentences in `App.test.jsx` cannot change.

### 3.2 Data flow, `advice` → leaf

| leaf | source field | formatting decision, owned by |
| :--- | :--- | :--- |
| `h2.poster-verb` | `advice.action` | `t.actionLabel[action]`; `kindClassFor` decides only the colour context. Uppercase is CSS, so the accessible name stays `All in` (test-pinned). |
| hero figure | `advice.ev` | `signedMoney(ev, t.locale)` + `t.currency` suffix; `heroStep()` picks the size class from the *formatted string length*, not from the viewport alone. |
| hero figure, check | `advice.ev === 0` | `isCheck()` demotes the numeral to the figure step and promotes the verb (§5.5). |
| win figure | `advice.equity_when_called` guarded by `advice.win_rate_defined` | `percent()` → `99.5%`; when `win_rate_defined === false` → `t.notAvailable`, never `0%` and never the long sentence (§5.3). |
| kind tag | `advice.kind` | `t.kindLabel[kind]`, suppressed entirely when `action === CHECK`. |
| rule colour | action **or** kind | `kindClassFor(advice)`: `kind-none` on `CHECK`, else `KIND_CLASSES[kind]`. |
| assumption | `summary.opponent_model`, `summary.fold_equity` | `assumptionLine(t, summary)` — unchanged string, unchanged owner. |
| rung option / mark | `rung.action`, `rung.eligible` | `t.actionLabel`, `●`/`○` (pinned literals). |
| rung amount | `rung.amount` | `formatMoney` + `t.currency` — **the only place the wager appears on the page** (§8). |
| rung EV | `rung.ev` | `signedMoney`; the `.vh` "EV " prefix keeps the screen-reader cell readable and the pinned contiguous string `EV -11,995` intact. |
| rung worst | `rung.worst_ev_ratio × summary.pot` | `worstEv()`. The sign *is* the status: a negative worst-case number means the rung is not robust at fold −10, so no extra mark is drawn. |
| rung verdict | `rung.eligible`, `rung.blocked_by`, `advice.ev`, `advice.action` | `t.ladderChosen` / `t.blocked[blocked_by]` / `t.rungGap(delta)`; `canShowGap()` returns `null` for the chosen row and for a check (`advice.ev` is `0` by definition on a check and is not a rung price, so it must never become a baseline). |
| stat line | `summary.bet_recommended_percent`, `handEval.showdown_equity`, `summary.pure_bluff_break_even_fold_equity` | `toFixed(1)` / `percent()`; undefined win rate → `t.winRateUndefined` (this is one of the two permitted occurrences). |

### 3.3 The one piece of arithmetic, and its defence

The gap column is `rung.ev − advice.ev` — a subtraction of two *returned* numbers. It is not a
re-price: no `ev()` is called in JS, no rung is re-derived, and the value shown on the chosen row is
`advice.ev` itself (the ladder's chosen rung *is* `advice`, by the one-object invariant).
`App.jsx` today already does this class of display arithmetic twice (`whyLine` reduces over the
ladder to find the best rung; `whyCheckFragile` receives `small.worst_ev_ratio * pot`). Anything more
— a delta *ratio*, a re-ordered ladder, a "would have earned" projection — is out of scope and stays
in `advice.py`, where the policy already owns it.

### 3.4 Exact `App.jsx` extraction

`App.jsx` shrinks from 758 to about 330 lines: shell, header, controls, the two tables, the notes
drawer, fetch plumbing, and six imports. Four modules are created, all presentational:

| file | export | props | lines (est.) |
| :--- | :--- | :--- | :--- |
| `frontend/src/verdict/verdict-format.js` | `signedMoney`, `percent`, `wholePercent`, `whyLine`, `assumptionLine`, `evidenceLine`, `winFigure`, `worstEv`, `rungGap`, `canShowGap`, `heroStep`, `isCheck`, `kindClassFor` | — (pure) | ~95 |
| `frontend/src/verdict/VerdictPanel.jsx` | `default VerdictPanel` + internal `PosterHead`, `AssumptionRow`, `KindRule` | `{ advice, handEval, summary, t }` | ~120 |
| `frontend/src/verdict/SizingLadder.jsx` | `default SizingLadder` | `{ advice, summary, t }` | ~55 |
| `frontend/src/verdict/StatLine.jsx` | `default StatLine` | `{ advice, handEval, summary, t }` | ~35 |
| `frontend/src/verdict/VerdictEmpty.jsx` | `default VerdictEmpty` | `{ summary, actionCounts, t }` | ~30 |

Deleted from `App.jsx`: `whyLine`, `assumptionLine`, `percent`, `wholePercent`, `signedMoney`
(moved), the whole `{advice && …}` card block, the whole `.hud-metrics-grid` block, and the
now-unused `formatZones` import (it moves into `verdict-format.js` with `evidenceLine`).
Unchanged in `App.jsx`: `KIND_CLASSES`, `Stepper`, all fetch logic, all controls, both tables, the
notes drawer, the error path (`solveErrorFor`, `fetchSolveAndAnalysis`).

---

## 4. Wireframe

### 4.1 1360px — controls 340px, results column 1020px (988px of content after 16px padding)

Tracks (one custom property, shared by poster and ladder, §5.6):
`[option 252] [amount 112] [EV 232] [worst 128] [verdict 252]` = 976 + 12 slack.

```
 LIÊNG SCOPE  Expected-value solver for Liêng                                  EN│VI   44px strip
────────────────────────────────────────────────────────────────────────────────────────────────────
 INPUTS 340px                │  RESULTS 1020px                          ┌── content 988px ──┐
                             │                                          │                   │
 POT ………………                  │  As Kh Qd · Q-K-A · Liêng Q-K-A          EXPECTED VALUE   WHEN CALLED
 ▲▼ chips                    │  └────── holding 11 mono/muted ──────┘   10/500/.12em     10/500/.12em
 Bet ………………                  │                                                                  │
 fold slider ────────●───    │                                              ALL IN              │
 calling range ──●───────    │                                              └ 15/700/0.14em ──┘   │
 Hand [As Kh Qd      ]       │                                              DIRECTLY ABOVE ↓      │
 ▸ Run solver                │                                       +164,064 VND      99.5%      │
 specs                       │                                       └─44 mono 500─┘  └24─┘       │
                             │                                       └hero-xl┘  └12 muted┘         │
                             │                                  ══ right edges share ONE axis ══  │
                             │                                                                  │
                             │  OPPONENT FOLDS   Assumption: the opponent folds their weakest 35%  │
                             │  └10/600/.16em┘   └───── 12 mono, muted, one line at 1360 ───────┘ │
                             │                                                                  │
                             ├━━━━━━━━━━━━━━━━━━━━━━━━━━━ VALUE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┤ 2px
                             │                           └label set ON the rule, bg = --bg, 10/600 │
                             │  OPTION          AMOUNT        EV            WORST CASE     WHY      │ 10/500/.12em
                             │────────────────────────────────────────────────────────────────────│ 1px
                             │  ● SMALL BET     33,000 VND    +120,932      +117,639   -43,132 vs  │ 15 mono
                             │                                                                  answer│ 12 mono
                             │────────────────────────────────────────────────────────────────────│
                             │  ○ LARGE BET     75,000 VND    +147,970      +140,480   -16,094 vs  │
                             │                                                                  answer│
                             │────────────────────────────────────────────────────────────────────│
                             │▌ ● ALL IN        100,000 VND   +164,064      +154,076   Chosen     │ 2px --kind
                             │  └ 2px inset --kind spine, no surface ─┘   └─12/600 ──┘            │
                             │                                                                  │
                             │  You win about 99.5% when called, so the all-in is worth the risk  │ 14/400
                             │  even if they fold 10% less than you think.        └ 62ch measure ┘ │
                             │  at your bet size: +131,876 VND · A bet at your size pays when …   │ 11 mono
                             │  We recommend a bet only when it earns at least 5% of the pot and… │ 11/400
                             │────────────────────────────────────────────────────────────────────│ 1px
                             │  HANDS WORTH A BET 71.6%  SHOWDOWN EQUITY 99.5%  BLUFF BREAK-EVEN 33.3% │ 11 label
                             │  └ one line, no cells, no borders; values 13 mono ─────────────────┘ │
                             │────────────────────────────────────────────────────────────────────│
                             │  COVERAGE BY CATEGORY … (table, unchanged)                          │
```

Annotated sizes at 1360: hero **46px / w500 / −0.02em / mono** (clamp `34→46`), win rate
**24px / w500 / −0.015em / mono**, verb **15px / w700 / 0.14em / UI uppercase**, ladder numbers
**15px / w500 / mono**, labels **10px / w500 / 0.12em / UI uppercase**, body **14px / w400 / UI**.
Ratio: EV : win : verb = 46 : 24 : 15 — the EV is exactly 2× the win rate and 3× the verb, which is
what "the three numbers are the composition" means numerically.

The empty left third of the poster is deliberate air, not a missing element: the holding meta anchors
the top-left, the numeral cluster is right-aligned on the EV track, and the 2px rule closes the block
across the full column width, so the block reads as one right-weighted composition rather than a
card with a hole in it (§8 asks whether a 1280px screenshot confirms that).

### 4.2 390px — single column, results 390px (366px of content after 12px padding)

```
 LIÊNG SCOPE                                        EN│VI          44px strip
──────────────────────────────────────────────────────────────────────────────
 INPUTS (stacked, unchanged)
──────────────────────────────────────────────────────────────────────────────
 As Kh Qd · Q-K-A · Liêng Q-K-A                                 11 mono, wraps to 1–2 lines
                                                                              │
                                                    EXPECTED VALUE            │ 10/500/.12em
                                                          ALL IN              │ 15/700/0.14em
                                                     +164,064 VND             │ 32 mono (clamp floor)
                                                              WHEN CALLED     │ 10
                                                          99.5%               │ 24 mono
                                                 └ win rate stack, 12 left ┘  │
                                                                              │
 OPPONENT FOLDS                                                               │ 10/600/.16em
 Assumption: the opponent folds their weakest 35% of hands and calls with     │ 12 mono
 the best 65%.                                                └ 3 lines ┘     │
━━━━━━━━━━━━━━━━━━━━━━━━━━━ VALUE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2px
                                                                              │
 ● SMALL BET                                        33,000 VND                │ 12/600 · 13 mono
   EV +120,932      worst +117,639      -43,132 vs answer                     │ 13 · 12 · 12
────────────────────────────────────────────────────────────────────────────── 1px
 ○ LARGE BET                                        75,000 VND                │
   EV +147,970      worst +140,480      -16,094 vs answer                     │
──────────────────────────────────────────────────────────────────────────────
▌● ALL IN                                          100,000 VND                │ 2px --kind spine
   EV +164,064      worst +154,076      Chosen                                │
──────────────────────────────────────────────────────────────────────────────
 You win about 99.5% when called, so the all-in is worth the risk even if      │ 14/400
 they fold 10% less than you think.
 at your bet size: +131,876 VND · A bet at your size pays when they fold 0–100%
 We recommend a bet only when it earns at least 5% of the pot and still …
──────────────────────────────────────────────────────────────────────────────
 HANDS WORTH A BET 71.6%                                                       │ two lines of 3
 SHOWDOWN EQUITY 99.5%   BLUFF BREAK-EVEN 33.3%                                │
──────────────────────────────────────────────────────────────────────────────
 COVERAGE BY CATEGORY (table scrolls inside .table-wrapper, page does not)
```

At 390 the ladder stops being a grid: each rung becomes **option + amount on line 1, numbers on line
2, verdict on line 3** — the labels `EV` / `worst` reappear inline because the column headers are
gone. The hero stays right-aligned to the container edge and the win rate's figure drops below its
label so the pair never wraps. No horizontal page scroll: `366 ≥ 134 (hero at 32px) + 12 + 88 (win
rate + label)`. A 13-character hero (`+1,640,640,000`) is handled by `heroStep`, not by shrinking the
page.

---

## 5. Styling plan

### 5.1 Tokens — no new colour, no new type, one new utility

`index.css` is used as it stands: `--bg #0a0b0d`, `--bg-raised #0f1114`, `--bg-inset #0c0e10`,
`--bg-hover #16191d`, `--line #1d2126`, `--line-strong #2a2f36`, `--text #c8ccd2`,
`--text-strong #eceef1`, `--muted #7c848e`, `--faint #565d66`, `--value #3fb27f`,
`--thin #d0a15a`, `--check #8a9199`, `--bluff #b96e5e`, `--bad #c4554d`, `--focus #6e93b8`,
`--radius 0px`, `--font-ui` (Segoe UI Variable Text stack), `--font-mono` (Cascadia Mono stack).
No Inter, no Roboto, no purple, no gradient, no shadow, no radius. **The only `index.css` addition is
the `.vh` visually-hidden utility** (§5.8) — the poster is built entirely from tokens that already
exist, which is the cheapest possible proof that it is a typographic design and not a new skin.

`--kind` is set exactly as today, by `.kind-value` / `.kind-thin` / `.kind-bluff` / `.kind-none`, and
read with a fallback (`var(--kind, var(--check))`) by the rule, the kind tag and the chosen row's
spine. **Nothing else in the results column reads `--kind`.**

### 5.2 Named type scale

| step | px @1360 (clamp) | weight | letter-spacing | family | use |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hero-xl` | 46 (34→46) | 500 | −0.02em | mono tabular | hero EV, ≤9 formatted chars |
| `hero-l` | 38 (28→38) | 500 | −0.02em | mono tabular | hero EV, 10–12 chars |
| `hero-m` | 30 (24→32) | 500 | −0.02em | mono tabular | hero EV, ≥13 chars; and the numeral on a **check** |
| `figure` | 24 | 500 | −0.015em | mono tabular | win rate beside the hero (≈0.52 × hero) |
| `verb-neg` | 32 | 650 | 0.02em | UI | the verb **only** when the action is `CHECK` |
| `verb` | 15 | 700 | 0.14em, uppercase | UI | the action verb above the hero |
| `num` | 15 | 500 | 0 | mono tabular | ladder amount / EV / worst |
| `num-sm` | 13 | 500 | 0 | mono tabular | stat-line values; inline `EV`/`worst` labels at ≤640 |
| `row-option` | 12 | 600 | 0.10em, uppercase | UI | `SMALL BET` / `LARGE BET` / `ALL IN` in the ladder |
| `meta` | 11 | 400 | 0.02em | mono | holding meta, evidence line |
| `label` | 10 | 500 | 0.12em, uppercase | UI | column headers, `EXPECTED VALUE`, `WHEN CALLED`, stat labels |
| `tag` | 10 | 600 | 0.16em, uppercase | mono | the kind label set on the rule; the assumption tag |
| `body` | 14 | 400 | 0 | UI | the why sentence (measure `62ch`) |
| `note` | 11 | 400 | 0 | UI | blocker phrase, gap, threshold note |

Four uppercase steps (15 / 12 / 10·600 / 10·500) are separated by size *and* weight, so no two
compete. Every numeral sits on `font-variant-numeric: tabular-nums` (already inherited from `body`,
restated on `.poster-hero`, `.poster-win`, `.ladder-*` so a future reset cannot break alignment).

### 5.3 Spacing scale

Multiples of 4 only: **4 / 8 / 12 / 16 / 24 / 32 / 48**. Roles: `4` label→figure and verb→hero,
`8` inside a numeral unit, `12` rule→header, why→evidence, `16` poster bottom→rule, ladder→why,
`24` holding→numerals, numerals→assumption, region→stat line, stat line→tables, `32`/`48` only
between results-column regions. **No spacing tokens are added to `index.css`**: `App.css` is 1090
lines of raw `px` multiples of 4 and a half-migrated token system would be worse than none. The scale
is a convention, documented here and enforced by review.

### 5.4 The kind → colour map, and the two conflicts

| `advice.action` | `advice.kind` | `--kind` | rule + label | chosen-row spine |
| :--- | :--- | :--- | :--- | :--- |
| `SMALL/LARGE/ALL_IN` | `VALUE` | `--value` #3fb27f | 2px emerald + `VALUE` | emerald |
| `SMALL/LARGE/ALL_IN` | `THIN_VALUE` | `--thin` #d0a15a | 2px amber + `THIN VALUE` | amber |
| `SMALL/LARGE/ALL_IN` | `BLUFF` | `--bluff` #b96e5e | 2px terracotta + `BLUFF` | terracotta |
| `CHECK` | any (incl. `BLUFF`) | `--check` #8a9199 | 2px gray, **no label** | (none — no rung is chosen) |

**(a) Action vs kind.** The verb wins the *sentence* and the rule wins the *colour*: `EXPECTED VALUE`
labels a number whose scope is the verb directly above it, so the command is read first and the kind
is read as the tint of the line that closes the block. They never occupy the same glyph, which is why
they cannot compete. The label on the rule is `t.kindLabel[kind]` — that is the user's "Value / Thin /
Bluff" wording, kept out of the numeral block on purpose.

**(b) Gray for Check vs `kind=BLUFF`.** This is not a free choice. `CHECK_ASSUMPTION_FRAGILE` carries
`kind=BLUFF` in real data (`advice.py` returns the label on a check *by design*, so a caller can say
"check, because this is a bluff"), **and** `App.test.jsx` asserts that a check's `.verdict-card` does
not contain the text `Bluff`. So: **the action wins on a check.** `--kind` becomes `--check`, the
rule turns gray, the kind tag is not rendered, and the bluff-ness is carried by the *sentence*
(`whyCheckFragile` already argues from the responsive-rung numbers). The alternative — colour the
rule by kind and drop the label — would satisfy the test but leave a terracotta rule on a card whose
answer is "don't bet", which reads as *go bet*. The user's own pairing ("gray for Check") is the
tiebreak: gray belongs to the action, emerald/amber to the argument. A check has no argument.

**(c) Bluff's colour.** `--bluff: #b96e5e`, muted terracotta. Three reasons it stays: (i) a bluff is a
play, not a fault, so `--bad` (#c4554d) would be a lie; (ii) it must be distinguishable from `--thin`
amber at 2px, and terracotta is the only hue family left in a palette whose other reserved hues are
green, amber and gray; (iii) it is already the token the working tree ships, so this candidate adds
no palette risk. Separation rule, stated so it can be checked: **`--bad` never appears inside the
verdict region** (only in `.terminal-alert` and the existing negative-EV table cells), so terracotta
on a 2px rule cannot be read as an error. §8 asks whether the hue distance survives at 2px on a
matte display; if it does not, `#a8795f` is the pre-approved fallback.

**(d) A 46px hero, bounded.** The hero is bounded three ways, all checkable in code rather than by
eyeball. **Sign**: `+` for non-negative EV (from `signedMoney`), Intl's ASCII hyphen for negative
(`EV -11,995` — the same character the test pins, so no `−` U+2212 anywhere). **Suffix**: `VND` in
`--muted` at 0.26em of the hero size, baseline-aligned — it never scales with the digits, so the
numeral column stays the numeral column. **Digits**: `heroStep(s)` reads the *formatted* string
length, so `46,064` at 46px and `+1,640,640,000` at 30px occupy the same axis and the same track;
the length rule beats a pure `clamp()` because `clamp()` keys off the viewport, not the number, and a
10× pot would otherwise overflow a 232px EV track at 1360 where there is no width problem at all. A
negative hero is *not* coloured red: the sign carries the direction, colour carries the kind, and a
red 46px number on a "value" verdict would be two claims fighting. **Alignment**: hero, amount, EV,
worst-case and gap columns all right-align on one axis because the poster and the ladder share one
grid template (§5.6); consecutive rows therefore align on the digit, and the hero aligns to the same
edge as the EV column (§4.1's "one axis" annotation).

**(e) Does removing the surface violate "Verdict Card"?** Wording, no; intent, yes if done carelessly.
A card does four things: it groups, it names, it identifies by an edge, and it ranks. This design
keeps all four without a box — grouping by adjacency and one shared grid, naming by
`<section aria-labelledby="verdict-verb">` (a real region landmark whose accessible name is the
answer, `All in`), identity by the 2px full-bleed `--kind` rule that closes the block, and rank by
being the only surface-free block among bordered tables. What the box *was* doing — separating the
verdict from the tables — is now done by the *opposite* means: the tables keep their borders, so the
verdict reads as the page's voice and the tables as its appendix. This also restores `DESIGN.md` §1's
own prohibition ("no cards by default"), which the current `.verdict-card` violates; the user's new
rules supersede nothing here, they agree with the older spec.

### 5.5 The CHECK poster

On `CHECK`, `advice.ev` is `0.0` *by definition* (`advice.py`: "0.0 for a check"), not a measured
result. Rendering that sentinel at 46px would state "checking earns nothing" — the opposite of what
the policy means. So on a check the hierarchy inverts for exactly one reason: **the verb takes
`verb-neg` 32px, both numerals take `figure` 24px, the rule is gray, no kind tag, no chosen row, no
gap column.** The numbers that actually argue for the check are the ladder's (every rung negative or
below the floor) and the why sentence, which is already written to quote the best rung. This is the
one case where the poster is verb-first, and it is verb-first because there is no wager to be
number-first about.

### 5.6 The alignment mechanism (one template, two consumers)

```css
.results-container { --col-option: minmax(132px, 1fr); --col-amount: 112px;
                     --col-ev: clamp(150px, 22vw, 232px); --col-worst: 128px;
                     --col-verdict: minmax(180px, 1fr);
                     --ladder-cols: var(--col-option) var(--col-amount) var(--col-ev)
                                    var(--col-worst) var(--col-verdict); }
.poster, .ladder-strip, .ladder-rung, .ladder-head-row {
                     display: grid; grid-template-columns: var(--ladder-cols); align-items: baseline; }
.poster-hero, .ladder-ev { text-align: right; }   /* one axis, hero and rows */
```

`--col-ev` is the track that pays for the poster: it must hold a 46px hero (≈8 glyphs × 0.6em ≈
221px), so it is far wider than a 15px number needs — and that surplus width *is* the poster's
leading whitespace, spent on the numeral axis rather than on a fifth column. The row's right-aligned
numbers therefore hang at the same edge as the hero's last digit, which is the only alignment claim
this design makes. At ≤1024 the column is 1020→vw and the tracks relax; at ≤640 the ladder leaves the
grid entirely (§4.2) and only the poster's own flex alignment remains.

### 5.7 CSS class list per component

| component | classes (new ✚ / kept ●) | notes |
| :--- | :--- | :--- |
| VerdictPanel | ● `verdict-card` ● `kind-value`/`kind-thin`/`kind-bluff`/`kind-none` ✚ `poster` | `verdict-card` survives as a **region hook only** — `border: 0; background: transparent; padding: 0`. It is kept because `App.test.jsx` calls `.closest(".verdict-card")`. |
| PosterHead | ● `holding-tag` ● `holding-sep` ● `holding-score` ✚ `poster-holding` ✚ `poster-labels` ✚ `poster-label` ✚ `poster-verb` ✚ `poster-verb-lg` ✚ `poster-hero` ✚ `hero-xl`/`hero-l`/`hero-m` ✚ `hero-figure` ● `ev-currency` ✚ `poster-win` ✚ `poster-win-label` | `.poster-label` is one rule, four uses; `.hero-*` are the three `heroStep` sizes |
| AssumptionRow | ✚ `poster-assumption` ✚ `assumption-tag` ✚ `assumption-text` | one line at 1360, 3 lines at 390, never merged into `.verdict-why` |
| KindRule | ✚ `poster-rule` ✚ `kind-tag` | 2px, `margin: 0 -16px` so it bleeds to the column edge |
| SizingLadder | ● `ladder-strip` ● `ladder-rung` ● `chosen` ● `rung-blocked` ● `ladder-mark` ● `ladder-amount` ● `ladder-ev` ● `ladder-blocked` ● `ladder-note` ✚ `ladder-head-row` ✚ `ladder-col` ✚ `ladder-option` ✚ `ladder-worst` ✚ `ladder-verdict` ✚ `ladder-chosen` ✚ `ladder-gap` ✚ `vh` | the six kept names are test-pinned; `●`/`○` stay literal text |
| why / evidence | ● `verdict-why` ✚ `verdict-evidence` | `.verdict-why` keeps its body treatment, gains `max-width: 62ch` |
| StatLine | ● `hud-metrics-grid` ● `hud-card` ● `hud-value` ● `hud-phrase` ✚ `stat-label` | `hud-card` keeps its name because the test queries `.closest(".hud-card")`; it is now an inline stat, not a cell (rename to `.stat` belongs in a commit that also edits the test) |
| VerdictEmpty | ● `verdict-empty` ✚ `poster` ✚ `poster-rule` | boxless, gray rule, `t.recommendedAction` retained here |
| `index.css` | ✚ `.vh` | `position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap` |

### 5.8 The `.vh` label, and why it is not a hack

`App.test.jsx` asserts `blocked[0].toHaveTextContent("EV -11,995")` — a *contiguous* string. Adjacent
`<span>`s concatenate without whitespace in `textContent`, so a visible `EV` column header plus a
numeric cell would produce `EV-11,995` and fail. The cell therefore carries an sr-only `EV ` prefix
plus the number: screen readers announce "EV -11,995" for a cell read in isolation, sighted readers
see the header once instead of five times, and the pinned string is produced honestly. **The trailing
space inside the label span is load-bearing** — write it as `{"EV "}` if JSX trims it.

### 5.9 `DESIGN.md` prohibitions: superseded vs honoured

| `DESIGN.md` | status |
| :--- | :--- |
| §3 "Smallest text 13px, never smaller" / "The verdict and its EV are 1.25rem / 600. Nothing bigger." | **Superseded** by user rule 1 (a dominant verdict). This design needs 10px labels and a 46px hero; both are deliberate and bounded by the scale in §5.2. |
| §3 "One family … no web fonts" (system UI stack only) | **Superseded** by user rule 2 (monospace numerals). Two families are now mandatory; the UI stack is kept as the *text* family and `--font-mono` as the *number* family. Neither is Inter nor Roboto. |
| §2 Ayu palette, `--accent #E6B450`, `--good`/`--bad` only for raise/fold | **Superseded** by the working tree's tokens (`--value`/`--thin`/`--check`/`--bluff`). |
| §6 "No `●` … decorations" | **Superseded** by `App.test.jsx`, which pins `●`/`○` inside `.ladder-rung`. They are re-read here as status marks (filled = may be the answer), not decoration. |
| §1 "No cards by default … only controls, the error and the open notes panel get a box" | **Honoured, and this candidate restores it** — the verdict box and the HUD box both go (§5.4e). |
| §1 "No concept or theme language" / §5 "don't add new names in `terminal-*`/`tactical-*`/`hud-*`" | **Honoured**: new vocabulary is `poster-*`, `ladder-*`, `stat-*`, `hero-*`, `assumption-*`. The two legacy names kept (`verdict-card`, `hud-card`) are test-pinned and flagged for a follow-up rename. |
| §4 control sizing (36px inputs, 40px button), §3 `--active` presets | Out of scope; unchanged. |

### 5.10 New i18n keys (EN + VI, same keys, both objects)

| key | EN | VI | why it cannot be reused |
| :--- | :--- | :--- | :--- |
| `winRateTag` | `When called` | `Khi bị theo` | The literal `Showdown equity` must stay the *first* such text in the document and inside `.hud-card` (test); `equity_when_called` is a different quantity from `showdown_equity`, so the poster needs its own label. VI is assembled from the existing fragment `khi bị theo` (`whyAllInValue`). |
| `ladderChosen` | `Chosen` | `Được chọn` | Rubric 3 needs the chosen rung unmistakable in words, not only in colour. |
| `rungGap` | ``(v) => `${v} vs answer` `` | ``(v) => `${v} so với mức khuyến nghị` `` | The delta needs a direction word; VI reuses `mức khuyến nghị` from `evAtRecommendedSize`. |
| `colAmount` | `Amount` | `Mức cược` | Column header. VI reuses the fragment from `betLabel`. |
| `colWorstEv` | `Worst case` | `Xấu nhất` | Column header for `worst_ev_ratio × pot`. |
| `colWhy` | `Why` | `Lý do` | Column header over the verdict cell (phrase + gap). |

Deliberately **not** added: an option-column header (the `●` + name is self-evident, and a blank
header over a rank-like column is a normal table convention); an assumption tag (the row uses
`t.opponentFolds`, an existing key in both languages, so no VI wording is invented — §8 questions
this); and a `Chosen`-row gap (the answer is the baseline, so its gap is zero by construction).
`t.recommendedAction` moves from the poster to `VerdictEmpty`, where it still labels something.
`t.evAtRecommendedSize` and `t.showdownEquitySub`/`vsRandomShort` lose their old homes; they stay in
the file (harmless) with the first re-used in `VerdictEmpty`'s help text if wanted.

---

## 6. Tradeoffs accepted

- We accept **no visible `Verdict Card` outline** in exchange for the poster being the only
  surface-free block on the page, with a named `<section>` landmark and a 2px kind edge doing the
  grouping.
- We accept **an empty left third of the poster at 1360px** in exchange for one numeral axis that the
  hero and all three rungs share.
- We accept **suppressing the kind entirely on a check** (gray rule, no `BLUFF` tag) in exchange for
  a check card that never argues for a bet it did not recommend — and for a green test.
- We accept **`N/A` in the hero's win-rate slot** when `win_rate_defined` is false in exchange for not
  repeating the explanation sentence a third time (which the test forbids).
- We accept **a `.vh` "EV " prefix in each EV cell** in exchange for a contiguous, screen-reader-legible
  `EV -11,995` and a header that is not repeated five times.
- We accept **dropping the equity-vs-random subtext** and the duplicated HUD EV cell in exchange for a
  stat line that cannot compete with the poster.
- We accept **keeping two legacy class names** (`verdict-card`, `hud-card`) as structural hooks in
  exchange for a diff that leaves `App.test.jsx` untouched.
- We accept **a 2px rule against a page of 1px hairlines** in exchange for the kind being readable at
  a glance without a chip.
- We accept **one subtraction in JS** (`rung.ev − advice.ev`) in exchange for "why not Large?" being
  answered arithmetically rather than by reading three cells.

## 7. Alternatives considered

1. **Sticky verdict bar** (56px strip pinned to the top of the results column: verb · EV · win rate in
   one line, kind as a 2px underline). *Lost* because a bar makes the verdict a banner competing with
   the header strip for the same horizontal emphasis; three numbers on one baseline have no
   hierarchy — the reader picks the leftmost, not the most important — and at 390px a pinned bar eats
   the vertical budget the ladder needs.
2. **Two-figure split poster** (left: verb at 32px; right: EV at 46px; win rate under the verb). *Lost*
   because two elements at 32px+ means no single dominant element (rubric 1), and because it puts the
   verb at the same weight class as the number, which forces the reader to choose between "what do I
   do" and "what is it worth" instead of reading one as the scope of the other.
3. **Minimal repair of the current card** (keep the box, raise the EV to 28px, move the win rate into
   `.verdict-breakeven`). *Lost* because `.verdict-card` is the only bordered box on the page, so
   keeping it keeps the table's visual weight on the verdict; a 28px number beside a 20px verb is a
   *nudge*, not a hierarchy, and the HUD grid would still repeat the EV.
4. **Chip-free but surface-full** (poster on `--bg-raised`, no border). *Lost* because a raised
   surface at the top of a column with no border reads as a selected table row, and because it
   reintroduces the surface ladder that currently makes the verdict and the tables compete.

## 8. Open questions and risks

- Does the poster's empty left third read as intentional composition at 1280–1360px, or as a hole? A
  single screenshot at both widths should settle it; the fallback is to move the assumption sentence
  into that space.
- Is `t.opponentFolds` ("Opponent folds") an acceptable tag for the assumption row, given the sentence
  beneath it already begins "Assumption: the opponent folds…"? The alternative is one new key pair
  (`assumptionTag`) and VI sign-off on `Giả định`.
- Is `N/A` honest enough for an undefined win rate in the hero slot, given that the full sentence is
  pinned to exactly two occurrences elsewhere? A short "no callers" key would fix it and cost one more
  key pair plus VI review.
- Does `--bluff #b96e5e` hold enough distance from `--bad #c4554d` to read as a play rather than an
  error at 2px? Pre-approved fallback: `--bluff: #a8795f`.
- Should the gap be shown as a **ratio** (`−0.16 × pot`) instead of VND, so three different pots are
  comparable? The contract has `ev_ratio` and `worst_ev_ratio`, so both are available.
- Will the five-column grid survive 1025–1200px two-column widths without wrapping the blocker
  phrases into three lines? `--col-verdict: minmax(180px, 1fr)` is the bet; a screenshot at 1100px
  should confirm or move the phrase to a third line.
- Is a 24px `0 VND` the right hero on a check, or should the EV slot be omitted entirely and the
  verb left alone at 32px? (The contract makes `ev = 0` a sentinel, not a measurement.)
- Should `.hud-card` → `.stat` and `.hud-metrics-grid` → `.stat-line` be renamed in this change? It
  requires editing `App.test.jsx`, which is out of scope for this package but should not be deferred
  forever.
- Does the ladder need `role="list"`/`role="listitem"`, or should it become a real `<table>` (with the
  loss of hero alignment)? Today it is unroled divs; this candidate adds the roles but not the table.

## 9. Next implementation step

Create `frontend/src/verdict/verdict-format.js` by moving `whyLine`, `assumptionLine`, `percent`,
`wholePercent` and `signedMoney` out of `App.jsx` verbatim (plus the new `worstEv`, `rungGap`,
`heroStep`, `kindClassFor`), and re-run `npm test` to prove the extraction is behaviour-neutral before
any markup or CSS changes.
