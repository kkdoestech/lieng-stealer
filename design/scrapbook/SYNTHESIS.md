# Scrapbook direction — arena record and override

Process record for [`../SCRAPBOOK.md`](../SCRAPBOOK.md). Grounding: [`GROUNDING.md`](GROUNDING.md).
Candidate packages: [`s1/package.md`](s1/package.md) (407 lines), [`s2/package.md`](s2/package.md)
(389 lines).

## Phase B — two structurally opposed candidates

| | S1 — pinned pinboard | S2 — layered desk |
| :--- | :--- | :--- |
| Layout engine | 12-col grid, named areas, shared row bands | grid rows + negative margins + z-index |
| Hypothesis | grid + transforms, overlap via row bands | absolute desk canvas |
| Where it ended | as hypothesised | **rejected absolute** with arithmetic (absolute children add no height; VI copy shifts the pile into "EXPECTED VALUE") |
| Paper | cream notes, dark slabs, paper-under-sheet shadow | cream sheets, carbon ledgers, `Δ=(w/2)sinθ` overlap invariant |
| Tests | zero edits (kept `EV ` inline, `.hud-card`) | zero edits (same strategy) |

Both scored **12/12** on the grounding rubric (scrapbook composition, typography system, colour
discipline, paper materiality, contract/test fit, resilience). They converged independently on cream
paper, grid-with-negative-margins, and a test-transparent DOM — a strong agreement signal.

## Synthesis decision (before the override)

**Base = S1.** Tie broken on materiality depth and motif discipline: S1 produced the paper-vs-page
argument (a shadow and a tilt require light paper), the tokenized tilt system (one media query
flattens it), the anti-clipping rule, the motif budget, and an explicit accent may/may-not list.
Grafted from **S2**: the overlap-invariant slack table, the rule that the marker must be neutral (a
yellow highlighter would collide with amber = Thin), the Vietnamese-subset font risk, and — the
decisive one — the **text-node law**: decoration may never print a numeral, and numeral-bearing prose
must stay one text node, because jsdom ignores CSS but matches the DOM.

## User override (current direction)

The user then replaced the material direction: keep the dark theme, apply the reference's unhinged
scrapbook energy — **emojis yes, doodles yes, rotations yes** — with dark pastel notes, neon accents
and a dotted dark mat. That keeps the arena's structure and replaces its colour/type system:

- **Kept:** the 12-column board, shared row bands, negative-margin overlap, tokenized tilts,
  anti-clipping rule, motif budget, overlap-slack table, one DOM at every width, and the
  test-transparent DOM (zero assertion edits).
- **Changed:** cream paper → dark rose polaroid / dark mustard sticky / dark violet scrap; soft
  under-sheet shadow → `4px 4px 0 #000`; muted accents → neon `#00ffa3 / #ffcc00 / #c96bff`;
  Space Grotesk → Caveat + Patrick Hand; no emoji → emoji section labels; no doodles → squiggle /
  star / arrow SVGs. The hard rule that survives: **mono for every numeral, nothing else**.
- **Rejected from both:** cream paper (user override), dark charcoal notes (tilt/shadow invisible on
  near-black), absolute collage canvas (clips at 390), the old 4-cell HUD (duplicates the verdict).

## Verification recorded

- Contrast measured on the new palette: ink 15.1:1 and muted 8.8:1 on rose; neon stamp text
  15.1 / 13.3 / 6.7:1; chalk on carbon 13.4:1. Neon is never small text on pastel.
- Test impact: none. All eight pins mapped in `SCRAPBOOK.md` §8, including the singleton wager and the
  two-copy "nobody calls" rule.
- `npm run lint` was green before the plan; `npm test` cannot run in this sandbox (Vite spawns piped
  child processes; documented EPERM boundary), so the assertion map is the verification artifact.
- Fonts (Caveat, Patrick Hand, JetBrains Mono) are a **dependency**: not in the repo yet, offline app,
  so they must be self-hosted as woff2 with Vietnamese subsets or the fallback stack ships.
