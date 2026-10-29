# Phase A — Grounding: the "playful scrapbook" overhaul

Read this before sketching. It is the shared evidence base for the architect candidates. The
workspace is `C:\Users\Admin\Desktop\lieng-stealer`; open the files named below yourself.

This plan **replaces the visual layer** of the committed dark-saas spec (`DESIGN.md`). The
functional laws in that file still bind: all copy via `i18n.js`, no recomputed EV, no fake status,
every numeral in the data mono face, tests stay green. Only the look changes — and it changes a lot.

---

## 1. The brief

Overhaul the whole UI into the "playful scrapbook" aesthetic of `tiboandpoteto.com`: a lovingly
unhinged scrapbook where pages are physical notes pinned onto a board, with tape, sticker labels,
marker highlights, tilted paper and hand-annotated asides. Mandatory rules from the user:

1. **Asymmetric scrapbook layout.** No standard centered grid. Use CSS Grid or absolute positioning
   to *stagger* the Verdict Card, Sizing Ladder and Assumption Line. Subtle CSS rotations
   (e.g. `rotate(-1.5deg)`) so they read as pinned notes.
2. **Typography.** A modern, slightly quirky sans for headings (e.g. **Space Grotesk**) and a strict
   monospace for **all** numbers (e.g. **JetBrains Mono**).
3. **Colours.** Base background near-black `#0a0a0a`. Bright, energetic pops: **emerald = Value**,
   **amber = Thin**, **vibrant violet = Bluff**.
4. **Raw aesthetic.** No generic rounded corners. Solid borders and subtle drop shadows so elements
   read as physical paper.
5. **No emojis, no gradients.**

### What the reference actually is

`tiboandpoteto.com` is an unofficial fan scrapbook of public exchanges between two people. Its
visible traits (from the live site's content and structure): a giant playful wordmark; sticker-like
labels and count badges ("days since they last talked", "103 replies"); pages that read as individual
scrapbook entries with a `reply` / `shoutout` / `how it started` kicker; pasted-in quoted cards;
alternating bright team blocks; heavy emoji use; informal lowercase copy; "tap a page" affordances;
a pop counter and stats page. The design language is *collage*: nothing is centered, everything looks
taped or stuck on, and the copy is personal and slightly unhinged.

**Adaptation constraints:** emojis and gradients are banned here, the product is a data instrument
(pot/EV/fold-rate), and the copy must stay plain and truthful (no "unhinged" voice in functional
labels). The scrapbook feeling must therefore come from **material and composition**, not from
sticker emoji or playful false claims: tilted paper, tape strips, solid 2px borders, hard offset
shadows, stamped/rotated labels, marker-highlight blocks, torn/dashed edges, and hand-drawn-ish
underlines built from CSS borders (no images required).

---

## 2. The system the plan must fit

### 2.1 Rendered data (do not recompute, do not invent)

`App.jsx` fetches `POST /api/solve` and renders one frozen `Recommendation`
(`backend/src/advice.py`, pinned by `frontend/src/solve-contract.json`):

| field | use |
| :--- | :--- |
| `action` | `CHECK \| SMALL_BET \| LARGE_BET \| ALL_IN` — the command, the dominant verb |
| `kind` | `VALUE \| THIN_VALUE \| BLUFF` — emerald / amber / violet |
| `reason` | closed enum → one sentence via `t.why*` (`whyLine()` in `App.jsx`) |
| `amount`, `ev`, `ev_ratio` | the wager, its EV, EV-to-pot |
| `equity_when_called`, `win_rate_defined` | the win rate; when false, a sentence replaces 0% |
| `ladder[3]` | `Rung`: `action, amount, ev, ev_ratio, worst_ev_ratio, eligible, blocked_by` |
| `summary` | `pot`, `fold_equity`, `opponent_model` (`range`/`random`), `sizing`, `bet_recommended_percent`, `range_coverage_percent`, `pure_bluff_break_even_fold_equity` |

Facts already established in this repo (use them, don't re-derive):

- `worst_ev_ratio` is the **minimum** over the centre and ±10-point stress cells. Never label it
  with one fold rate.
- `Recommendation.robust` is always true by construction; never display it.
- For a CHECK, `ev = 0` is a sentinel, not a measurement.
- For a fixed fold cell, EV is linear in bet size, so an eligible rung below the chosen size always
  earns less; "−X vs chosen" is always negative when it appears.

### 2.2 Current component tree (App.jsx, 758 lines, one component)

```
App
├─ header.terminal-header           wordmark, subtitle, EN/VI toggle
└─ main.terminal-grid               340px | 1fr
   ├─ section.control-panel        pot, bet, fold slider, model toggle, call range,
   │                               profit map, hand input, Run button, error, engine specs
   └─ section.results-container
      ├─ .verdict-card             hero (action h2, kind chip, hand line, EV, win rate),
      │                            why line, assumption line, .ladder-strip (3 cells), note
      ├─ .verdict-empty            no-hand fallback
      ├─ .hud-metrics-grid         4 cells: hands worth a bet / showdown equity / EV / bluff break-even
      ├─ coverage table, top-hands table
      └─ notes drawer
```

The overhaul restructures presentation only: state, fetching, abort logic, and copy helpers stay.

### 2.3 Test pins that constrain the DOM (Testing Library, `App.test.jsx`)

These are literal and unforgiving; the plan must keep every one green (updating an assertion is
allowed only if named explicitly, and **no displayed number may change**):

1. `findByRole("heading", { name: "All in" })` (and "Small bet" / "Check") — the action verb is an
   `<h2>` whose accessible name is exactly the verb. A kind label/annotation inside it breaks this.
2. `getByRole("heading", { name: "Check" }).closest(".verdict-card")` must not contain the text
   "Bluff" — a CHECK carries `kind=BLUFF` but must not name it. So `.verdict-card` survives as the
   card's class, and the kind sticker is suppressed on a check.
3. `getByText(/33,000/).closest(".ladder-rung")` — **the wager text appears exactly once on the
   page**, inside a `.ladder-rung`; a second copy anywhere throws.
4. `.ladder-rung` must carry `chosen` / `rung-blocked` classes and the literal marks `●` / `○`.
5. One rung must contain the contiguous string `EV -11,995` — the label and number in one element
   with a real space, ASCII hyphen (not U+2212).
6. `getAllByText(/nobody calls at this setting/)` has length **exactly 2**.
7. `getAllByText("Showdown equity")[0].closest(".hud-card")` must exist and contain the
   undefined-win-rate sentence.
8. `getByText` matches **direct text nodes only**: a string split across siblings is invisible, and
   the same string in two sibling nodes breaks `getBy…`.

Deciding to change assertions 5–7 is allowed but must be called out as a test change; assertions
1–4 and 8 are non-negotiable DOM laws.

### 2.4 Runtime constraints

- **Offline app.** No webfonts from a CDN at runtime. Space Grotesk and JetBrains Mono must be
  self-hosted as `woff2` under `frontend/src/assets/fonts/`, declared with `@font-face`
  (`font-display: swap`), with system fallback stacks. Both are OFL-licensed. **Flag the asset
  acquisition as a dependency**: the fonts are not in the repo yet, so the first implementation step
  either adds the binary files or ships the fallback stack behind a single `--font-*` token.
- **Build/lint gates:** `npm run build`, `npm run lint` (any warning fails), `npm test`.
- **Responsive:** one column ≤1024px; no horizontal page scroll at 390px.
- **Accessibility:** `:focus-visible` ring on every control; text contrast ≥4.5:1; no meaning by
  colour alone (the kind is labelled, not just coloured); errors in `role="alert"`; static rotations
  are allowed but must stay small and must be removed under
  `@media (prefers-reduced-motion: reduce)` as a comfort fallback.
- **No gradients, no emoji, no icon fonts, no images required.** Tape, torn edges, underlines and
  highlights must be CSS-only (`transform`, `border`, `clip-path`, flat `background`, `opacity`).

---

## 3. Decisions each candidate must make explicitly

1. **Paper vs page.** On a `#0a0a0a` base, what is the paper? Dark warm charcoal notes with cream
   ink, or off-white notes with near-black ink? Either can work; decide, and justify against (a)
   "physical paper" shadows need a lighter surface than the page, (b) the accents must stay *pops*,
   not become the dominant colour, (c) legibility of 11–13px body and table text.
2. **Stagger mechanism.** CSS Grid with explicit `grid-area` placements + `transform` offsets, or a
   `position: relative` canvas with absolutely positioned cards. State the responsive collapse rule
   and how overlap is prevented from clipping the ladder's numbers at 1360 and 390.
3. **Rotation budget.** Exact angles per card and per decoration; how text stays legible; what
   straightens at which breakpoint; whether the *table rows* inside a rotated card stay legible.
4. **Violet.** "Vibrant violet for Bluff" supersedes the previous ban, but it must not be mistaken
   for an error state; state its exact hex and where it may appear.
5. **Marker / tape / torn-edge motifs.** Concrete CSS recipes (flat colours only). Where does each
   motif appear, how many per screen (a scrapbook stops reading as a scrapbook when everything is
   taped), and which motifs are banned as noise?
6. **Component extraction.** The hierarchy proposal must name components, props and the pure
   formatting helpers they call. `App.jsx` may shrink; it may not gain state.

## 4. Grading rubric (used to pick the base in Phase D)

Score 0–2 each; 12 max.

1. **Scrapbook composition.** The three named components are genuinely staggered (not a centered
   stack), rotations/overlaps are deliberate and consistent, one glance reads "pinned notes".
2. **Typography system.** Space Grotesk / JetBrains Mono roles are explicit, with a named scale and
   fallbacks; every numeral is mono; no stray proportional numerals.
3. **Colour discipline.** `#0a0a0a` base, emerald/amber/violet assigned exactly to Value/Thin/Bluff,
   accents used as small pops (tape/sticker/highlight), contrast verified, CHECK handled as gray.
4. **Paper materiality.** Solid borders, hard (subtle) offset shadows, square corners, CSS-only tape/
   edges; no gradient or blur anywhere; no emoji.
5. **Fit to the contract and tests.** Real fields only, no recompute, i18n keys, the §2.3 pins
   satisfied or explicitly amended; states (loading/error/no-hand/nobody-calls/negative EV) covered.
6. **Resilience.** Responsive plan at 1360/1024/640/390, reduced-motion straightening, focus states,
   no overlap-clipping, print-irrelevant but scroll-safe.

---

## 5. Output

Write exactly one file: `design/scrapbook/c<N>/package.md` (create dirs if needed), sections:

1. **Problem** — the constraints that shaped the shape.
2. **Usage** — component call sites first, e.g. `<VerdictCard advice={advice} … />`.
3. **Shape** — component hierarchy with props, and the pure helpers each component calls.
4. **Wireframes** — annotated ASCII at 1360px and 390px, with transform angles and offsets numbered.
5. **Styling plan** — tokens (`--paper`, `--ink`, `--tape`, accent hexes), the CSS Grid/absolute
   layout declarations, `transform`/`box-shadow`/`border` recipes, class list per component, type
   scale, spacing.
6. **Tradeoffs accepted** — one bullet each, "we accept X in exchange for Y".
7. **Alternatives considered** — at least one whole-shape alternative and why it lost.
8. **Open questions and risks** — phrased as questions.
9. **Next implementation step** — one sentence.

**Do not modify any application file** (`App.jsx`, `App.css`, `index.css`, `i18n.js`, tests, backend)
and do not run the dev server. Write only your `package.md`. Keep the package under ~320 lines —
dense and concrete, not prose.
