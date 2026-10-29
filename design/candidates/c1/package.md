# Candidate A — The ledger masthead

**Shape in one sentence.** The verdict is not a box: it is an unboxed masthead band at the top of the
results column, delimited by three `--line-strong` rules and nothing else, whose two loudest elements
are the action verb and the hero EV (44px mono, right-aligned on the same edge as the money column of
the three-row sizing ledger immediately below it) — so the results column reads top-to-bottom as one
financial statement, not as a stack of cards.

---

## 1. Problem

The four acceptance criteria (GROUNDING §1) are a *hierarchy* problem, not a decoration problem: verb,
EV and win rate must win the glance; every number must align; the ladder must answer "why not Large?" by
itself; the assumption line must be visible but subordinate. `App.css` currently cannot express that
hierarchy because it expresses hierarchy with **boxes**: the verdict is the only bordered surface in the
results column, the ladder is three bordered cells inside it, the HUD is a fourth bordered grid, and the
empty state is a fifth box with a different class for the same geometry (GROUNDING §4 "known slack").

Five constraints shaped the shape:

1. **One object, one number, one place.** `advice` is the frozen `Recommendation`; the ladder row and the
   verdict are the same object. No component may recompute a rung. Two display derivations are
   permitted and both have precedent in `App.jsx`: `worst_ev_ratio * pot` (already used by
   `whyCheckFragile`) and `rung.ev - advice.ev` (a difference of two returned numbers, not a policy
   result).
2. **The test file pins more than the copy.** `App.test.jsx` pins, by class and by literal text:
   `.verdict-card` as an ancestor of the `<h2>` (`:254`); `.ladder-rung` as the closest ancestor of the
   amount, the blocked phrase, `●`, `○`, class `chosen`, class `rung-blocked` (`:305–316`); the literal
   string `EV -11,995` **inside the rung element** (`:316`); `.hud-card` as the element holding the
   win-rate figure labelled `Showdown equity`, and it must not contain `0.0%` (`:330–336`); and exactly
   **two** occurrences of "nobody calls at this setting" (why line + that figure, `:331`). This is the
   single hardest constraint on the shape: it forbids a header row (a bare `EV` cell would need the test
   edited), it forbids renaming `.verdict-card`, and it forbids a third rendering of the undefined-win-
   rate sentence.
3. **390px is a design target, not a squeeze.** No horizontal page scroll; the verdict must still be
   dominant there.
4. **The existing token base is the base.** `index.css` already has the surface ladder, hairlines,
   `--radius: 0`, `--value/--thin/--check/--bluff` and both font stacks. This package adds spacing and
   type *steps* only; it adds no font, no hue, no shadow, no gradient, no radius.
5. **`advice.robust` is a tautology.** `_blocker` requires `worst_ratios[index] >= min_edge_ratio > 0`
   for any eligible rung, and a check is constructed with `robust=True`; therefore `advice.robust` is
   always `true`. Printing a "robust" badge would be fake status in the strict sense of the old spec,
   so the number that makes robustness true (`worst_ev_ratio * pot`) is shown instead.

### Grounding red flags, and how this package adapts

- **GROUNDING §6.4 says the HUD grid's "one non-duplicated figure (coverage)" may be dropped.** It is
  two figures (coverage *and* bluff break-even), and a third one (win rate) is not merely duplicated —
  it is *missing* from the card and must move into it. Adapted: the grid dissolves, all three survivors
  move into a footnote strip under the statement, and the fourth HUD cell (the EV) is deleted outright.
- **The HUD grid cannot vanish completely.** `.hud-card` is pinned by `:333–335`. Adapted: the *grid*
  vanishes; the class survives on the masthead's win-rate figure, whose rules are rewritten. I do not
  rename it, because a rename buys nothing visually and costs an edit to the file that also pins the
  verdict's sentences.
- **`DESIGN.md` changed under this session.** At 20:15 it was the 96-line Ayu Dark "plain tool page"
  spec named in my brief; at 20:21 another author replaced it with a 570-line plan that keeps a
  bordered verdict card, moves "the state line" into the ladder's first cell, and proposes editing
  `App.test.jsx` (`:316`, `:330–336`). I designed against the file my brief names and its prohibitions,
  and flag the three direct conflicts in §7 and §8 rather than silently adopting them.
- **Superseded prohibitions in the older Ayu Dark spec**, noted per my brief: §3 "nothing bigger than
  1.25rem" is superseded by the user's dominance requirement (this package uses 44px); §2's Ayu palette
  is superseded by the `index.css` tokens; §1's "radius 3px" is superseded by `--radius: 0`; §1's "no
  HUD/terminal/engine vocabulary" stands and this package adds no new name in that vocabulary (it keeps
  one legacy name, `.hud-card`, only as a test hook); §6's "no `●` decoration" is superseded by
  `App.test.jsx:307`, which asserts the mark — the `●`/`○` pair is data (eligible / blocked), not
  decoration, and stays.

### The five forced decisions, resolved

**(a) Action vs kind — the verb wins, the kind colours.** The verb is the `<h2>` at 32px/600 in
`--text-strong`, followed on the same baseline by the kind as a *word*, not a bordered chip: 11px
uppercase, 0.1em, in `--kind`. The verb is 2.9× the kind word (32px vs 11px) and the only element in
the band set in the UI face at title size; the kind is one token of colour attached to it. Reason: the
domain separates the command from the argument (`advice.py` `Action` vs `Kind`), and a boxed chip
competes with the box-free band — the word does the same job with typography.

**(b) The "gray for Check" conflict — colour follows the action when the action is CHECK, else the
kind; and a check renders no kind word.** Implementation is one line: `accentClass(advice)` returns
`KIND_CLASSES[advice.kind]` unless `advice.action === "CHECK"`, in which case it returns `kind-none`,
which already maps to `--check`. Reasons: (i) gray names the absence of a bet, which is the one thing
true of every check, while `BLUFF` on a check would label a play the user is not being told to make —
and `App.test.jsx:254` forbids the word inside `.verdict-card` anyway; (ii) the backend's own
`Kind` docstring invites "check, because this is a bluff", and that sentence is exactly what the why
line delivers with numbers ("Betting earns +13,550 if they fold 35%, but only +250 if they fold 25%").
The argument is kept; the label is dropped.

**(c) Bluff's colour — keep `--bluff: #b96e5e`, muted terracotta, and keep it away from `--bad`.**
Reasons: it is already a token and measures 5.0:1 on `--bg` (the band's surface) — it is not
emerald (good), not amber (thin), not gray (check), and it is not a warning red. The collision risk is
`--bad: #c4554d`, two muted reds in one view. Resolved structurally, not by re-tinting: **no money
figure inside the statement is coloured by sign** (no green `+`, no red `−`), and `--bad` is used only
for `role="alert"` copy. With sign colour gone, `--bad` never appears in the statement and terracotta is
unambiguous.

**(d) The ladder's second number — the delta against the answer, in the money line, next to the EV;
worst-case EV is demoted to the memo line.** Rationale: EV is the column that must align with the hero
(rightmost); the delta is the only number that makes the answer's advantage *arithmetic* rather than
mental subtraction (−16,094 vs +164,064); `worst_ev_ratio` is the strongest why-not signal but the
contract does not say **which** stress cell produced it, so it is printed as money
(`worst_ev_ratio * pot`) under a label that makes no claim about the fold rate. Two consequences I
accept: the delta column is suppressed on a check (there, `advice.ev === 0`, so `Δ` would duplicate the
EV column digit for digit); and `worst case` sits at 11–12px under the EV, not in its own column.

**(e) Verdict dominance at 390px — dominance by isolation and a straight edge, not by absolute size.**
At 390px the EV stays the largest glyph run (40px, still 2.7× the 15px row numerals), is alone on its
line, and stays right-aligned on the same edge as every ladder EV below it; the verb drops to 28px and
the win rate to 20px, so the *order* (44 : 32 : 24) is preserved at (40 : 28 : 20) rather than
re-sorted; the win rate moves *below* the EV (`column-reverse`) so the EV keeps the strong top-right
corner. In a rung the EV keeps the end of the row's first line and the amount and Δ move down to the
second, because an option plus three numbers on one 366px line would squeeze the EV to the win rate's
size — the one thing the narrow layout must not do.

---

## 2. Usage

One call site in `App.jsx`, replacing the current `.verdict-card` block:

```jsx
{advice && (
  <Verdict advice={advice} handEval={handEval} summary={summary} zones={zones} t={t} />
)}
```

`Verdict` composes the two ruled bands and owns the accent scope, so `--kind` reaches the ledger too:

```jsx
function Verdict({ advice, handEval, summary, zones, t }) {
  return (
    <div className={`verdict ${accentClass(advice)}`}>
      <VerdictMasthead advice={advice} handEval={handEval} summary={summary} zones={zones} t={t} />
      <SizingLedger advice={advice} pot={summary.pot} t={t} />
    </div>
  );
}
```

The other two render sites (no hand entered; the footnote strip) stay in `App.jsx`:

```jsx
{solveData && !handEval && <MastheadEmpty summary={summary} actionCounts={actionCounts} t={t} />}
{solveData && <EvidenceStrip advice={advice} handEval={handEval} summary={summary} t={t} />}
```

And the row map inside `SizingLedger`, the only place `Rung` is read:

```jsx
<ol className="ledger-rows" aria-label={t.ladderTag}>
  {advice.ladder.map((rung) => (
    <LedgerRow
      key={rung.action}
      rung={rung}
      pot={pot}
      answerEv={advice.ev}
      showDelta={advice.action !== "CHECK"}
      isChosen={rung.action === advice.action}
      t={t}
    />
  ))}
</ol>
```

`whyLine`, `assumptionLine`, `percent`, `wholePercent`, `signedMoney`, `KIND_CLASSES` and `formatZones`
stay where they are. Everything is presentational; no state is added anywhere.

---

## 3. Shape

### 3.1 Hierarchy with props

```
App                                   state, fetching, lang, shell               (unchanged)
└─ section.results-container
   ├─ Verdict                         advice, handEval, summary, zones, t
   │  │                                owns: the --kind scope, the accent resolution
   │  ├─ VerdictMasthead              advice, handEval, summary, zones, t
   │  │  ├─ header.verdict-head
   │  │  │  ├─ div.verdict-verb-block
   │  │  │  │  ├─ span.fig-label        t.recommendedAction
   │  │  │  │  ├─ h2.verdict-title      t.actionLabel[advice.action]      ← test: heading
   │  │  │  │  ├─ span.kind-word        t.kindLabel[advice.kind]          ← omitted on CHECK
   │  │  │  │  └─ div.verdict-meta      amount · hand · canonical · score
   │  │  │  └─ div.verdict-figures
   │  │  │     ├─ Figure  fig--win  hud-card   label t.showdownEquity + win rate  ← test hook
   │  │  │     └─ Figure  fig--display         label t.expectedValueTag + advice.ev
   │  │  ├─ p.verdict-why              whyLine(t, advice, summary)
   │  │  └─ div.verdict-evidence
   │  │     ├─ Figure  evidence-item   label t.assumptionTag  + assumptionLine(...)
   │  │     └─ Figure  evidence-item   label t.paysWhenTag    + formatZones(zones)
   │  └─ SizingLedger                 advice, pot, t
   │     ├─ div.ledger-caption        t.ladderTag · t.ladderCaption
   │     └─ ol.ledger-rows
   │        └─ LedgerRow ×3           rung, pot, answerEv, showDelta, isChosen, t
   │           ├─ span.rung-mark       ● | ○
   │           ├─ span.rung-option     t.actionLabel[rung.action]
   │           ├─ span.rung-amount     amount + t.currency
   │           ├─ span.rung-delta      signedMoney(rung.ev - answerEv)      ← hidden on CHECK
   │           ├─ span.rung-ev         "EV " + signedMoney(rung.ev)          ← literal, test
   │           └─ span.rung-memo       memo phrase · "worst case" + signedMoney(worst_ev_ratio*pot)
   ├─ MastheadEmpty                   summary, actionCounts, t
   │                                   no-hand band: t.noHandTitle / t.noHandBody /
   │                                   t.actionCountsLine + assumptionLine()
   ├─ EvidenceStrip                   advice, handEval, summary, t
   │                                   hands worth a bet · EV at your bet size ·
   │                                   bluff break-even · t.thresholdNote(...)
   ├─ coverage table / top-hands table (unchanged markup)
   └─ notes drawer                     (unchanged)
```

`Figure` is the one shared atom: `({ label, value, sub, variant, tone, className, children })`. It owns
no formatting — it renders a label, a mono value and an optional sub-line, and it is why the masthead's
win-rate slot, the hero EV, the evidence items and the ladder numerals all share one anatomy.

### 3.2 Data flow, field by field

| Field | Reaches | Formatted by | Form |
| :--- | :--- | :--- | :--- |
| `advice.action` | `VerdictMasthead` `<h2>`, `SizingLedger` row match | `t.actionLabel[action]` | "All in" / "Small bet" |
| `advice.kind` | `Verdict` accent class, `Masthead` kind word | `KIND_CLASSES[kind]` | `kind-value` → `--value` |
| `advice.amount` | masthead meta line (bet only) | `formatMoney` + `t.currency` | `100,000 VND`, mono 11 |
| `advice.ev` | masthead hero figure | `signedMoney` | `+164,064`, 44px mono |
| `advice.equity_when_called`, `win_rate_defined` | masthead win-rate figure | `percent` or `t.winRateUndefined` | `99.5%` / the sentence |
| `advice.reason` | `whyLine` → `.verdict-why` | `whyLine` (unchanged) | one sentence, 13px |
| `advice.ladder[i]` | `LedgerRow` | per cell, below | 3 rows, contract order |
| `rung.amount` | `.rung-amount` | `formatMoney` + currency | `100,000 VND` |
| `rung.ev` | `.rung-ev` | `t.evTag` + `signedMoney` | `EV +164,064` |
| `rung.ev - advice.ev` | `.rung-delta` | `signedMoney` | `-16,094` |
| `rung.worst_ev_ratio * pot` | `.rung-memo` | `signedMoney` | `worst case +154,076` |
| `rung.eligible`, `rung.blocked_by` | `.rung-mark`, `.rung-memo`, classes | ternary + `t.blocked[...]` | `●`/`○`, "not worth the extra risk" |
| `summary.opponent_model`, `fold_equity` | `.verdict-evidence` | `assumptionLine` (unchanged) | one sentence |
| `summary.sizing.*` | `EvidenceStrip` | `t.thresholdNote` (unchanged) | one sentence |
| `handEval.*` | meta line, evidence, strip | existing helpers | as today |

### 3.3 Ownership

| Decision | Owner |
| :--- | :--- |
| Which accent a verdict gets (`CHECK` → gray, else kind) | `Verdict` — `accentClass(advice)` |
| Whether the kind word exists at all | `VerdictMasthead` — `advice.action !== "CHECK"` |
| Whether the delta column exists | `SizingLedger` — `advice.action !== "CHECK"` |
| One rung → six display values (mark, option, amount, delta, ev, memo) | `LedgerRow` — `rungView(rung, answerEv, pot, t)` |
| Which sentence explains the answer | `whyLine` (unchanged, already in `App.jsx`) |
| Money/percent/sign text | `format.js` (`formatMoney`) + `signedMoney`/`percent` in `App.jsx` |
| Fetching, aborting, loading/error | `App.jsx` only (untouched) |

`rungView` is a pure function beside `whyLine`: it returns
`{ mark, option, amount, delta, ev, memo, chosen, blocked }` from one `Rung`, so no two call sites can
format the same rung differently — the same "one object, one row" invariant the backend keeps between
`Recommendation` and the 455-class table.

### 3.4 i18n keys

**Reused unchanged (21):** `recommendedAction`, `expectedValueTag`, `showdownEquity`, `vsCallingRange`,
`vsRandomShort`, `evAtRecommendedSize`, `evTag`, `currency`, `actionLabel`, `kindLabel`, `blocked`,
`winRateUndefined`, `assumptionSensitivity`, `betRecommended`, `combosWorthBet`, `bluffThreshold`,
`bluffThresholdSub`, `thresholdNote`, `noHandTitle`, `noHandBody`, `actionCountsLine`. Every existing
why/assumption sentence (`whyLine`, `assumptionLine`, `profitableWhen`) is untouched, so the pinned copy
in `App.test.jsx` cannot drift.

**New (12) — names and EN gloss only; VI wording needs a native pass:**

| Key | Shape | EN gloss |
| :--- | :--- | :--- |
| `assumptionTag` | string | "Assumption" (label of the evidence row) |
| `paysWhenTag` | string | "Pays when they fold" (label before `formatZones`) |
| `ladderTag` | string | "Sizing ladder" (the ledger's caption) |
| `ladderCaption` | string | "Δ measured against the answer" |
| `amountTag` | string | "amount" (inline label in a rung's money line) |
| `deltaTag` | string | "Δ" (inline label) |
| `worstTag` | string | "worst case" (inline label before the stress EV) |
| `rungChosen` | string | "the answer" |
| `rungEarnsLess` | string | "earns less than the answer" |
| `rungClearsFloor` | string | "clears the floor, but the answer is bigger" |
| `evAtYourSizeTag` | string | "EV at your bet size" (footnote figure) |
| `sensitivityTag` | string | "Assumption sensitivity" (footnote figure) |

`rungClearsFloor` exists for a reachable case the current UI cannot describe: an eligible rung *below*
the answer whose EV is not lower (the policy walks down from the largest size the win rate allows, so
EV is not monotone in size). No rung may claim "earns less" without the number to back it.

---

## 4. Wireframe

### 1360px

Results column = 1020px; statement is full-bleed (`margin-inline: -16px`), content inset 16px on both
sides, so every right edge below is the *same* edge. `═` is a `--line-strong` rule, `─` a `--line` rule.

```
+----------------------------+----------------------------------------------------------------------------------+
|LIÊNG SCOPE   Expected-value solver for Liêng                                                             EN|VI|
+----------------------------+----------------------------------------------------------------------------------+
|INPUTS      (340px)         |RECOMMENDED ACTION                                    WIN RATE      EXPECTED VALUE|
|                            |All in   VALUE                                           99.5%        +164,064 VND|
|                            |32/600 UI                                          24/500 mono   44/600 mono = max|
|                            |100,000 VND · As Kh Qd · Q-K-A · Liêng Q-K-A                                      |
|                            |           vs. the top 65% that call · 99.7% vs. a random hand                    |
|                            |                                                           at the recommended size|
|                            |sub-lines: 11/400 mono, --muted; the EV is the page max                           |
|pot, bet, presets           |                                                                                  |
|fold + call range           |You win about 99.5% when called, so the all-in is worth the risk even             |
|profit map                  |if they fold 10% less than you think.                                             |
|                            |13/400 UI, --text                                                                 |
|                            |──────────────────────────────────────────────────────────────────────────────────|
|                            |ASSUMPTION    The opponent folds their weakest 35% of hands and calls             |
|                            |              with the best 65%.                                                  |
|                            |11/500 label        12.5/400 UI, --muted                                          |
|                            |PAYS WHEN THEY FOLD   0%–100%     11/500 label + 12/400 mono                      |
|                            |══════════════════════════════════════════════════════════════════════════════════|
|hand input                  |SIZING LADDER                                        Δ measured against the answer|
|RUN SOLVER                  |11/500 label        11/400 mono, --muted                                          |
|engine specs                |                                                                                  |
|                            |●  ALL IN       amount 100,000 VND            Δ        0               EV +164,064|
|                            |   the answer                                                  worst case +154,076|
|                            |──────────────────────────────────────────────────────────────────────────────────|
|                            |○  LARGE BET    amount  75,000 VND            Δ  -16,094               EV +147,970|
|                            |   earns less than the answer                                  worst case +140,480|
|                            |──────────────────────────────────────────────────────────────────────────────────|
|                            |○  SMALL BET    amount  33,000 VND            Δ  -43,132               EV +120,932|
|                            |   earns less than the answer                                  worst case +117,639|
|                            |══════════════════════════════════════════════════════════════════════════════════|
|                            |                                                                                  |
|                            |HANDS WORTH A BET  EV AT YOUR BET SIZE   BLUFF BREAK-EVEN                         |
|                            |71.6%              +131,876 VND          33.3%                                    |
|                            |of 22,100 combos   at 50,000 VND         fold rate for 0 points                   |
|                            |We recommend a bet only when it earns at least 5% of the pot and still            |
|                            |earns it if the opponent folds 10% less than you think.                           |
|                            |══════════════════════════════════════════════════════════════════════════════════|
|                            |                                                                                  |
|                            |COVERAGE BY CATEGORY   [ existing boxed table, restyled only ]                    |
+----------------------------+----------------------------------------------------------------------------------+
```

Largest-element ladder: EV 44 > verb 32 > win rate 24 > row numerals 15 > why 13 > memo 12 >
meta/label 11. The EV and the three row EVs share one right edge (`+164,064` / `+147,970` /
`+120,932` terminate on the same column of digits); the `worst case` numbers terminate on that edge too.
Row order is the contract's order (small → large → all-in): no JavaScript reorders rungs.

### 390px

```
|════════════════════════════════════════|
|control panel above: unchanged          |
|...                                     |
|════════════════════════════════════════|
|RECOMMENDED ACTION                      |
|All in   VALUE                 28/600 UI|
|100,000 VND · As Kh Qd · Q-K-A          |
|· Liêng Q-K-A       11/400 mono, --muted|
|                                        |
|40/600 mono                 +164,064 VND|
|11/500 label              EXPECTED VALUE|
|11/400 mono      at the recommended size|
|20/500 mono                        99.5%|
|11/500 label                    WIN RATE|
|               vs. the top 65% that call|
|               · 99.7% vs. a random hand|
|                                        |
|You win about 99.5% when called, so the |
|all-in is worth the risk even if they   |
|fold 10% less than you think.           |
|────────────────────────────────────────|
|ASSUMPTION                              |
|The opponent folds their weakest 35% of |
|hands and calls with the best 65%.      |
|PAYS WHEN THEY FOLD   0%–100%           |
|════════════════════════════════════════|
|SIZING LADDER                           |
|Δ measured against the answer           |
|                                        |
|● ALL IN                        +164,064|
|  amount 100,000 VND   Δ 0              |
|  the answer              worst +154,076|
|────────────────────────────────────────|
|○ LARGE BET                     +147,970|
|  amount  75,000 VND   Δ -16,094        |
|  earns less than the answer            |
|                          worst +140,480|
|────────────────────────────────────────|
|○ SMALL BET                     +120,932|
|  amount  33,000 VND   Δ -43,132        |
|  earns less than the answer            |
|                          worst +117,639|
|════════════════════════════════════════|
|HANDS WORTH A BET                  71.6%|
|EV AT YOUR BET SIZE         +131,876 VND|
|BLUFF BREAK-EVEN                   33.3%|
|We recommend a bet only when it earns…  |
|────────────────────────────────────────|
```

At 390 the EV is still the largest thing on the page (40 > 28 > 20), alone on its line, and its right
edge is the ladder's right edge. A row becomes a three-area grid — option + EV / amount + Δ /
memo + worst — and the memo wraps to a second line when the phrase is long ("earns less than the
answer", 26 characters), which is why the drawing is four lines tall there. Nothing is hidden at any
width, so the DOM is identical at both and only the grid changes.

---

## 5. Styling plan

### 5.1 Tokens

No new colour, no new font, no radius, no shadow.

| Token | Use in this package |
| :--- | :--- |
| `--bg` | the statement's own canvas: the band and the ladder rows are **transparent** |
| `--bg-inset` | the chosen rung only (recessed, as today) |
| `--bg-raised` | *not used by the verdict*; stays on the appendix tables |
| `--line` | row dividers, the why/evidence split, footnote rules |
| `--line-strong` | the three statement rules: band top, band→ledger boundary, ledger bottom |
| `--text-strong` | verb, hero EV, chosen row numerals, all money |
| `--text` | why sentence, eligible non-chosen rungs |
| `--muted` | labels, memo lines, sub-lines, blocked-row numerals, assumption |
| `--faint` | the `○` mark of a blocked rung only (non-information) |
| `--value/--thin/--bluff/--check` | via `--kind`; three uses only (see 5.3) |
| `--focus` | focus rings (unchanged) |
| `--font-ui`, `--font-mono` | unchanged stacks; no web font is added |
| `--col-pad: 16px` (12px ≤640) | **new**: the one inset the statement and the ladder share |

New spacing steps (4px base with 2/6 for hairlines and tight stacks): `--s1: 2, --s2: 4, --s3: 6,
--s4: 8, --s5: 12, --s6: 16, --s7: 24, --s8: 32`.

### 5.2 Type scale (named steps)

No text below 11px; the old 10px label size is retired inside the statement.

| Step | px | weight | letter-spacing | line-height | family | used for |
| :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| `display` | 44 | 600 | −0.02em | 1.05 | mono | hero EV (40 at ≤640) |
| `title` | 32 | 600 | −0.015em | 1.1 | UI | action verb `<h2>` (28 at ≤640) |
| `metric` | 24 | 500 | 0 | 1.15 | mono | win rate (20 at ≤640) |
| `num` | 15 | 500 | −0.01em | 1.35 | mono | ladder amount, Δ, EV, worst (600 for EV and the chosen row) |
| `body` | 13 | 400 | 0 | 1.55 | UI | the why sentence |
| `body-sm` | 12.5 | 400 | 0 | 1.5 | UI | assumption sentence, memo lines |
| `row` | 12 | 600 | 0.06em, uppercase | 1.3 | UI | rung option name |
| `label` | 11 | 500 | 0.1em, uppercase | 1.2 | UI | every figure label, column labels, hypothesis tags |
| `micro` | 11 | 400 | 0 | 1.45 | mono | meta line, units, sub-lines, footnote figures |

Rule: negative tracking only on `display` and `title`; uppercase labels take positive tracking; numbers
are always `--font-mono` with `font-variant-numeric: tabular-nums` (already inherited from `body`).

### 5.3 The kind → colour map (three uses, no more)

| Condition | `--kind` | Where it appears |
| :--- | :--- | :--- |
| `action !== CHECK`, kind `VALUE` | `--value` #3fb27f | (1) the kind word, (2) the chosen rung's 2px left rule, (3) the chosen rung's `●` |
| `action !== CHECK`, kind `THIN_VALUE` | `--thin` #d0a15a | same three |
| `action !== CHECK`, kind `BLUFF` | `--bluff` #b96e5e | same three |
| `action === CHECK` (any kind) | `--check` #8a9199 | (2) and (3) only — no kind word, and no rung is `chosen` |
| no `advice` (`MastheadEmpty`) | `--check` | nothing: the empty band carries no `--kind` use |

Contrast, measured on the band's `--bg` surface: `--value` 7.4:1, `--thin` 8.3:1, `--check` 6.2:1,
`--bluff` 5.0:1, `--muted` 5.2:1, `--text` 12.2:1, `--text-strong` 16.9:1. Every hue passes AA at 11px.

Rejected: colouring the hero EV with `--kind`. A 44px chromatic money figure converts a *classification*
(what kind of hand) into an *evaluation* (the number is good). The EV is `--text-strong`; the colour
stays on the argument.

### 5.4 Surfaces, hairlines, spacing

- Band and ledger: no fill, no border, `border-radius: 0`, no shadow. The three `--line-strong` rules are
  the only structural line at 1px-plus-nothing weight; there are no 2px *rules* except the chosen row's
  accent on its left edge.
- Band internal rhythm: headline `20px 16px 16px`; why line `margin-top: 12`; evidence row
  `padding: 12px 16px` with `border-top: 1px solid var(--line)`.
- Ledger: caption `10px 16px`, rows `10px 16px`, `border-bottom: 1px solid var(--line)`, last row none;
  the ledger closes with `--line-strong`.
- Alignment is produced by **one shared right inset (`--col-pad`) + right-aligned tabular mono**, never by
  shared grid tracks and never by decimal padding. Locale separators differ (`.` vs `,`), so
  digit-grid alignment via tabular figures is the only correct mechanism.
- Hover: `--bg-hover` on a ledger row only; no size, border, or position change.

### 5.5 CSS classes per component

- **Verdict**: `.verdict` (the `--kind` scope; `margin-inline: calc(-1 * var(--col-pad))`),
  `.kind-value`, `.kind-thin`, `.kind-bluff`, `.kind-none` (existing, unchanged).
- **VerdictMasthead**: `.verdict-card` (kept: test hook), `.verdict-head`, `.verdict-headline`,
  `.verdict-verb-block`, `.verdict-title`, `.kind-word`, `.verdict-meta`, `.verdict-meta-sep`,
  `.verdict-amount`, `.verdict-figures`, `.fig`, `.fig--display`, `.fig--win`, `.fig--inline`,
  `.fig-label`, `.fig-value`, `.fig-sub`, `.fig-phrase`, `.ev-currency`, `.hud-card` (kept on the
  win-rate figure only), `.verdict-why`, `.verdict-evidence`, `.evidence-item`, `.evidence-label`,
  `.evidence-text`.
- **SizingLedger**: `.sizing-ledger`, `.ledger-caption`, `.ledger-caption-note`, `.ledger-rows`,
  `.ladder-rung`, `.chosen`, `.rung-blocked`, `.rung-line-1`, `.rung-line-2`, `.rung-mark`,
  `.rung-option`, `.rung-amount`, `.rung-delta`, `.rung-ev`, `.rung-memo`, `.rung-worst`.
- **LedgerRow**: no class of its own beyond the row state (`.chosen`, `.rung-blocked`, `.is-eligible`).
- **MastheadEmpty**: `.verdict-card`, `.verdict-empty`, `.is-empty`, `.verdict-title`, `.verdict-meta`.
- **EvidenceStrip**: `.evidence-strip`, `.strip-item`, `.strip-label`, `.strip-value`, `.strip-sub`,
  `.strip-note`.
- **Removed from `App.css`** (this is where the CSS gets smaller): `.verdict-banner`,
  `.verdict-col-right`, `.verdict-breakeven`, `.kind-chip`, `.ladder-strip`, `.ladder-head`,
  `.ladder-label`, `.ladder-amount`, `.ladder-ev`, `.ladder-blocked`, `.ladder-note`,
  `.hud-metrics-grid`, `.hud-value`, `.hud-subtext`, `.mono-green` — fifteen classes, plus the
  `.ladder-rung.chosen` and `.kind-*` rules rewritten rather than kept. `.hud-card` is **rewritten**
  (a stale `display:flex; padding:12px; border-left:1px` would wreck the band). The appendix tables'
  own classes (`.tactical-table`, `.mono-num`, `.positive-ev`, `.negative-ev`, `.chip-full`,
  `.chip-zero`) are **not** touched by this package — see §8, question 7.

### 5.6 Responsive

| Width | Behaviour |
| :--- | :--- |
| ≥1281px | headline = verb (1fr) + figures (row: win rate then EV, `margin-left:auto`) |
| 1025–1280px | figures wrap under the verb block, still right-aligned (`flex-wrap` + `margin-left:auto`) |
| ≤1024px | shell stacks (unchanged); the statement is now full page width |
| ≤640px | `--col-pad: 12px`; `display` 40, `title` 28, `metric` 20; figures `column-reverse` (EV on top, right-aligned); a ledger row becomes a three-area grid (option + EV / amount + Δ / memo + worst) with the memo allowed to wrap; the evidence row stacks; the footnote strip becomes label/value rows with hairlines |

---

## 6. Tradeoffs accepted

- We accept a legacy class name (`.verdict-card`) on an element that is deliberately no longer a card,
  in exchange for `App.test.jsx` staying green with **zero** test edits.
- We accept the win-rate figure keeping the `.hud-card` class *and* the existing `Showdown equity` label
  rather than a new "Win rate" label, in exchange for no new copy in a slot the test already pins.
- We accept four inline figure labels per ladder row (the word "amount", "Δ", "EV", "worst case" repeat
  three times) in exchange for one DOM that works at 1360 and at 390 without a header row to hide and
  without hiding a number.
- We accept the delta as the second number and `worst_ev_ratio * pot` demoted to the memo line, in
  exchange for "why not Large" being arithmetic (−16,094) and the answer's own EV never sharing a column
  with a derivative.
- We accept losing red/green sign colour on money inside the statement, in exchange for emerald meaning
  exactly one thing (Value) and `--bad` never appearing next to terracotta.
- We accept that `advice.robust` is not shown anywhere, in exchange for not printing a badge that is
  `true` in every response the policy can produce.
- We accept dropping the strikethrough on a blocked rung's EV, in exchange for numerals that stay
  comparable at a glance; the minus sign and the muted ink carry the loss.
- We accept that the worst-case figure is not attributed to a fold rate (the contract does not expose
  which stress cell produced it), in exchange for not printing a claim the response cannot support.
- We accept an `<ol>` instead of a `<table class="ladder">`, in exchange for a two-line row that holds a
  phrase and a number without spanning cells; a `<table>` with `<th>` would either duplicate the literal
  `EV` in every cell or force an edit to the test that pins `EV -11,995`.
- We accept a taller verdict block (~150px, four text tiers) in exchange for the verb, the EV, the win
  rate, the why sentence and the assumption sentence each owning their own tier instead of sharing a
  banner.
- We accept full-bleed statement rules above boxed, inset appendix tables, in exchange for the
  "document, then appendix" reading order.
- We accept one more new helper (`rungView`) and twelve new i18n keys, in exchange for no formatting
  decision living in two places.

---

## 7. Alternatives considered

**Whole shape A — the bordered verdict card (the current shape, tuned; and the shape the rewritten
`DESIGN.md` now specifies).** One square `--bg-raised` card with a 2px `--kind` left rule, the ladder as
a `<table>` with Size/Bet/EV/Worst-case columns and a state line under the size, a three-cell stat strip
below. It is a good plan and it closes the four gaps. It lost here for three reasons: (i) the card is the
only loud surface on the page, so it is bounded by its own border instead of by the column's rules — the
verdict stops where the box stops, and the ladder has to become a *nested* table with a second border
inside the first; (ii) putting the folded state line ("−16,094 vs chosen") in the first cell leaves the
money columns with no comparison to read down, so "why not Large" is again a sentence rather than a
column; (iii) its worst-case column forces a fourth column at 1360 that must be *dropped* at ≤768, i.e.
a number disappears on narrow screens. My ledger keeps every number at every width.

**Whole shape B — sticky trade ticket.** A pinned 300px ticket on the right of the results column holding
verb, EV, win rate and a four-line ladder, with the tables scrolling beside it. It lost: at 1360 it would
leave 688px for the ladder and the two data tables (which need ~820px for seven columns), it introduces
a second scroll context, and at ≤1024px it degenerates into exactly the band this package proposes —
so it pays for a large-screen-only structure with a whole extra layout.

**Whole shape C — the ladder as three equal cards (the current `.ladder-strip`).** Kept as columns:
three cells side by side, each holding option, amount, EV and a blocked reason. It lost because the
reader's question is a *comparison across* sizes: three columns of unequal-length text have no shared
baseline for the EVs (each cell's EV sits under a different amount and a different reason line), which
is precisely the failure the rubric calls "comparable at a glance".

**Local alternative for the second number — worst-case EV as its own column (GROUNDING §6.5's default
reading).** Serious contender, and it is what the rewritten `DESIGN.md` chooses. It lost on three
counts: the contract does not say which stress cell produced `worst_ev_ratio`, so a `worst case` column
either lies about the fold rate or says nothing about it; it costs a fourth column that must be dropped
at 390; and it does not by itself answer "why not Large" — it needs the delta anyway, which is why that
plan also prints "−16,094 vs chosen". I keep the numbers and drop the column.

**Local alternative for colour — the hero EV in the kind colour.** Rejected: see §5.3.

---

## 8. Open questions and risks

1. **`DESIGN.md` was replaced mid-session by another author** (Ayu Dark spec → a 570-line bordered-card
   plan that also proposes editing `App.test.jsx`). Should the owner treat that file as the base plan,
   and if so, which of the three direct conflicts is the base's: bordered card vs unboxed band; a
   `<table>` ladder with a header row vs labelled figures; and editing the two pinned assertions
   (`EV -11,995`, `.hud-card`)?
2. **On a check, the hero EV is 0 by definition.** Is a 44px `0` the honest thing to show, or should the
   band say in words why checking is right (a new key, e.g. "a check adds nothing; the small bet does
   not survive a worse read")? Today the answer lives only in the why sentence and the ladder.
3. **Does the delta belong on a check after all?** I suppress it because `advice.ev === 0` makes it a
   copy of the EV column; but "Δ +13,550" is also the story of `CHECK_ASSUMPTION_FRAGILE`. Which
   reading does the owner prefer: a column with one meaning, or a column that repeats itself on checks?
4. **Is `Δ` acceptable copy?** It is a mathematical symbol, not decoration, but the old spec bans glyph
   decoration outright. The alternative is the word "vs answer" in every cell (wider, weaker).
5. **VI wording for the twelve new keys** must be written by a native reviewer; I have deliberately not
   improvised it (GROUNDING §2, "VI wording is not to be improvised").
6. **`sensitivity.status` is a raw enum** (`ROBUST_BET`). I move it into the footnote strip unchanged
   rather than invent three sentences; if raw enums are banned, this needs three keys and a mapping.
7. **The appendix tables still colour EV by sign** (`positive-ev`/`negative-ev`) while their Action column
   colours by kind — the same table says emerald twice. Neutralising the two sign classes is a two-line
   change; should it ride along or stay out of scope?
8. **The masthead's win-rate sub-line** ("vs. the top 65% that call · 99.7% vs. a random hand") is 48
   characters in a narrow slot. Is it evidence worth the band's width, or should it move to the footnote
   strip and leave the band with four words?
9. **Full-bleed rules at ≤1024px**: the statement's rules then run to the page edges and the block becomes
   a mid-page divider between controls and results. Acceptable, or should the block be inset at that
   width alone?

---

## 9. Next implementation step

Extract `Verdict`, `VerdictMasthead`, `SizingLedger`, `LedgerRow`, `MastheadEmpty` and `EvidenceStrip`
inside `App.jsx` behind the data already on screen — keeping every pinned hook (`.verdict-card`,
`.ladder-rung`, `chosen`, `rung-blocked`, `●`/`○`, the literal `EV <signed>`, `.hud-card`) and the twelve
new `t.*` keys in §3.4 — then rewrite `App.css`'s verdict block against §5.5 and delete the fifteen
retired
classes, in the order `App.jsx` → `App.css` → `index.css` (spacing/type steps) → `i18n.js`, with the
backend untouched.
