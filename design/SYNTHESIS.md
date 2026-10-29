# Architect synthesis — the Liêng Scope verdict surface

Process record for the design now written into [`../DESIGN.md`](../DESIGN.md). Phase A grounding is
[`GROUNDING.md`](GROUNDING.md); candidate packages are in [`candidates/`](candidates/).

## Phase B — what came back

Three structurally distinct candidates were spawned through the `architect-runners` overlay (ledger
masthead / instrument slab / number-first poster). All three produced packages; candidate A's landed
late and was evaluated before the plan was committed.

| Candidate | Shape | Status | Size |
| :--- | :--- | :--- | :--- |
| A — Ledger masthead | Full-width hairline masthead, no surface; `ol` ledger rows with delta + worst case | delivered | 620 lines |
| B — Instrument slab | One square bordered slab, three full-bleed bands, row ladder on a shared EV bar scale | delivered | 604 lines |
| C — Number-first poster | Surface-free poster, 46px EV as the largest type, verb as its scope, 2px kind rule | delivered | 602 lines |

## Phase C/D — scoring against the rubric

Rubric from `GROUNDING.md` §7, 0–2 per criterion.

| Criterion | A | B | C |
| :--- | ---: | ---: | ---: |
| 1. Verdict dominance (verb, EV, win rate are the three largest) | 2 | 2 | 1 |
| 2. Numeral alignment (mono, tabular, fixed right-aligned columns) | 2 | 2 | 2 |
| 3. Ladder legibility (EV + why per rung, comparable at a glance) | 2 | 2 | 2 |
| 4. Assumption line visible but secondary | 2 | 2 | 2 |
| 5. Rule compliance (dark, muted, emerald/amber/gray, no banned devices) | 1 | 2 | 1 |
| 6. Fit to the contract (real fields, no recompute, i18n, tests, responsive) | 1 | 1 | 1 |
| **Total** | **10** | **11** | **9** |

- A lost criteria 5 and 6: a surface-free statement band does not satisfy the brief's "Verdict Card",
  and it keeps the legacy `.hud-card` class plus the "Showdown equity" label on a figure that is no
  longer a card, purely to avoid two test edits. Its four inline per-row labels ("amount", "Δ", "EV",
  "worst case", ×3) are noisier than column headers and cost 12 new keys.
- B lost criterion 6 for the same `.hud-card` hook, and its shared-scale EV bars re-encode the EV
  column (see rejections).
- C lost 1 and 5: a 15px verb is smaller than the win-rate figure, and a surface-free poster drops the
  "card".

## Synthesis decision

**Base = B's slab geometry** — it is the shape that satisfies both the brief's "card" wording and the
dominance requirement without a rounded or shadowed surface. The Lead's spec re-derives the type
sizes (EV 40 `display`, verb 26 `title`, win rate 24 `metric`) so the EV is unambiguously the largest
element, where B had the verb at 40 and the EV at 44.

Grafted into the base:

- **From B:** full-bleed hairlines inside one surface; the ladder as *rows* with fixed-width,
  right-aligned numeric columns rather than three cells; `ev_ratio` as the hero caption ("· 1.64×
  pot"); the kind tag as a **sibling** of the `<h2>`; `.is-check` declared after `.kind-*` so
  precedence lives in CSS; the "amount appears exactly once" and "`EV −11,995` must be one text node"
  Testing Library laws.
- **From A:** two corrections. (1) **The third ladder column must not be labelled with a fold rate.**
  `worst_ev_ratio` is the *minimum* across the centre and ±10-point cells; A caught that a header
  saying "folds 10% less" can state a falsehood, so the column is now "Worst of 3" with the hint
  "weakest of centre, ±10 pts". (2) **No figure disappears at narrow widths — it relocates:** at
  ≤768px the worst-of-three value moves into the rung's state line instead of being dropped.
- **From C:** the CHECK state demotes the EV figure instead of printing a 40px `+0`, because
  `advice.ev = 0` is a sentinel for a check, not a measurement; the hero's label must differ from the
  table's "Showdown equity" so the pinned `getAllByText` ordering cannot be disturbed; the
  confirmation (verified here) that moving the undefined-win-rate copy into the hero keeps the
  pinned occurrence count at 2 (hero slot + why sentence).

Rejected and why:

- **B's shared-scale EV bars:** mathematically sound (`ev_ratio ∈ [−1, +2]`) but they re-encode the
  EV column, double the ladder's height, and a blocked rung can carry the longest bar, so length
  cannot mean "chosen". Kept as a documented revisit in `DESIGN.md` §10.1.
- **A's separate delta column:** the delta is already printed in each rung's state line, and the EV
  column plus the "Chosen" mark answer "why not large" by direct comparison; a fifth numeric column
  would spend width restating derived arithmetic. Recorded in `DESIGN.md` §10.1.
- **A's `rungClearsFloor` key** ("eligible but earns no less than the answer"): proposed for a case
  that is not reachable. For a fixed fold cell, `EV` is linear in the bet size with slope
  `2·win − 1` in pot units, so a rung *below* the chosen size can only be eligible when `win > 0.5`,
  where EV strictly increases with size — it always earns less. Every reachable "eligible but not
  chosen" row therefore takes the "−X vs chosen" wording.
- **B's evidence band** repeating pot/model/pays-when: the controls already show pot and model; the
  band adds density without adding a decision.
- **The 40/44px verb from B and the 15px verb from A/C:** both miss the brief's "recommended action
  visually dominant" in opposite directions. Verb at `title` (26px) with EV at `display` (40px) puts
  the command and the number in one glance without either being decoration.
- **C's surface-free poster, verb-as-scope and digit-count type stepping:** the first two drop the
  "card", the third trades a real system (fixed steps) for a computed one.
- **All three candidates' `.hud-card` selector hook:** the class would describe an element that no
  longer exists. Updating two test assertions is the smaller lie — recorded in `DESIGN.md` §7.

## Verification recorded

- `npm run lint` in `frontend/`: 0 warnings, 0 errors (baseline before any UI change).
- `npm test` could not be executed in this environment: Vite spawns piped child processes and the
  sandbox denies the pipe (documented EPERM boundary), not a code failure. The plan therefore lists
  the exact assertions that must be re-run and updated (`DESIGN.md` §7, §9).
- The worst-case attribution rule was verified against `backend/src/advice.py`: `worst` is
  `min(calculate_ev(...) for cell in cells)` with `cells = fold_grid(centre)`, so the response carries
  a minimum over two or three cells, never a named cell.
- The delta-monotonicity argument was checked against `advice.py`: `_start_rung` gates on win rate and
  `_blocker` blocks every rung above the start, so "eligible but not chosen" rungs are always below the
  chosen size in a `win > 0.5` regime.
- Every number in `DESIGN.md` is copied from `solve-contract.json` / `App.test.jsx` fixtures; the
  spec's rule "numbers must not change" is checkable against those fixtures.

## Process note

The requested `frontend-design-excellence` skill is not installed in this session; the available
`dark-saas` style skill was loaded and the user's mandatory rules (no Inter/Roboto, no purple
gradients, no rounded generic cards, no emoji, emerald/amber/gray semantics, mono numerals) were
applied as the governing constraints.
