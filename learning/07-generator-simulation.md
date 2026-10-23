# 07 — The Generator (Simulation)

> **Goal:** compute, for each of the 455 hand types, how often it wins against a random opponent, and
> save the results to `data/winrates.json`.
> **You will build:** `backend/src/generator.py`, the data file `backend/data/winrates.json`
> (generated, not typed), and `backend/tests/test_generator.py` (5 tests).
> **Time:** ~2 hours.
> **Prerequisites:** [06](06-combinatorics-canonical-hands.md).

---

## The big picture

This is the **offline** half of the architecture. We run it **once**, it takes about 30 seconds, and it
produces a small file the rest of the program reads.

```
generate_all_canonical_hands()  ──►  455 CanonicalHands
            │
            │  for each hand (in parallel on all CPU cores):
            │     remove its 3 cards from the deck → 49 cards left
            │     compare with every opponent hand: C(49,3) = 18,424 showdowns
            │     count wins / ties / losses
            ▼
   { "Q-K-A": {"equity": 0.9969, "win_rate": 0.9962, ...},  ... 455 entries }
            │
            ▼  json.dump
   backend/data/winrates.json   (~4,100 lines, ~83 KB)
```

---

## Concepts you need

### Win rate, tie rate, loss rate, equity

Play our hand against `n` opponent hands and count:

```
win_rate  = wins   / n
tie_rate  = ties   / n
loss_rate = losses / n          (the three always add up to 1)

equity    = (wins + 0.5 × ties) / n
```

**Equity** treats a tie as "half a win", because in a tie the pot is split. It's the number used in
the EV formula (chapter 9) as `P(Win | Call)`.

### Exact enumeration vs Monte Carlo

There are two ways to find the win rate:

| | **Exact enumeration** | **Monte Carlo** |
|---|---|---|
| Idea | Try **every** opponent hand (18,424 of them) | Try `N` **random** opponent hands |
| Result | the true value | an estimate that gets better as `N` grows |
| Speed | fixed cost (~0.1 s per hand type here) | you choose (`N` = 1,000 is very fast) |
| When to use | when "every case" is small enough to loop over | when the full space is too big (e.g. 5-card poker vs many players) |

Our problem is small enough for exact enumeration, so that's what the official data uses. The code
supports both, because Monte Carlo is the general technique you'll need for bigger games.

**How accurate is Monte Carlo?** By the **law of large numbers**, the estimate approaches the truth as
`N` grows. The typical error (the *standard error*) is about

```
error ≈ sqrt( p × (1 − p) / N )
```

where `p` is the true win rate. Quadrupling `N` only halves the error. Real numbers for hand type
`9-7-7` (true equity 0.3013):

| `N` samples | estimate | error | predicted error |
|-------------|----------|-------|-----------------|
| 100 | 0.2900 | 0.011 | 0.046 |
| 1,000 | 0.3085 | 0.007 | 0.015 |
| 10,000 | 0.3049 | 0.004 | 0.005 |
| 100,000 | 0.3032 | 0.002 | 0.0015 |
| exact (18,424, every hand) | **0.3013** | 0 | — |

### Using several CPU cores: processes

A normal Python program uses **one** CPU core. Your laptop probably has 4–16. Because of Python's *GIL*
(Global Interpreter Lock), threads cannot run Python calculations truly in parallel, but separate
**processes** (separate copies of Python) can.

`concurrent.futures.ProcessPoolExecutor` makes this easy:

```python
from concurrent.futures import ProcessPoolExecutor

def square(x: int) -> int:          # must be a top-level function (see below)
    return x * x

if __name__ == "__main__":
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(square, [1, 2, 3, 4]))   # runs in 4 processes
    print(results)                                           # [1, 4, 9, 16], always in input order
```

Two rules:

1. The function you send to the workers must be defined at the **top level** of a module (not inside
   another function, not a `lambda`), because each worker process must be able to import it by name.
2. Start the pool only under `if __name__ == "__main__":`. On Windows and macOS each worker *re-imports*
   your script; without that guard, every worker would start its own pool, again and again.

`executor.map` returns results **in the same order as the inputs**, even if they finish in a different
order. That keeps our output file in a fixed order.

### JSON files

JSON is a text format that maps cleanly to Python dicts and lists:

```python
import json
data = {"Q-K-A": {"equity": 0.9969, "category": "LIENG"}}
with open("out.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)        # Python → file
with open("out.json", encoding="utf-8") as f:
    again = json.load(f)                # file → Python
```

`indent=2` makes the file human-readable. `with open(...)` closes the file automatically, even if an
error happens.

---

## Step 7.1 — Docstring and imports

📄 **File:** `backend/src/generator.py` — *create this file*

```python
"""Liêng Stealer - Simulation Engine & Offline Data Generator.

Precomputes heads-up showdown equities for all 455 canonical Liêng hands
against random opponent ranges. Supports both Monte Carlo stochastic sampling
and exact combinatorial enumeration (C(49, 3) = 18,424 showdowns per hand).
Serializes results into data/winrates.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

from src.evaluator import Card, Deck, evaluate_hand
from src.hands import (
    CanonicalHand,
    generate_all_canonical_hands,
    get_representative_cards,
)
```

New modules here:

- `argparse`: reads command-line options (Step 7.6).
- `os`: we use `os.cpu_count()` to find how many cores the machine has.
- `random`: random sampling for Monte Carlo.
- `pathlib.Path`: an object-oriented way to work with file paths (`Path("data") / "winrates.json"`).
- `Any`: a type hint meaning "any type". `AGENTS.md` asks to justify it; here it's used for the JSON
  record dict whose values mix `float`, `str` and `int`.

---

## Step 7.2 — `compute_hand_equity`: set-up

📄 **File:** `backend/src/generator.py` — *add to the end*

```python


def compute_hand_equity(
    canonical_hand: CanonicalHand,
    exact: bool = True,
    samples: int = 10000,
    seed: int | None = None,
) -> dict[str, Any]:
    """Calculate heads-up showdown equity for a single canonical hand.

    Args:
        canonical_hand: The CanonicalHand to evaluate.
        exact: If True, iterates all C(49, 3) = 18,424 opponent combinations.
        samples: If not exact, number of random opponent hands to sample.
        seed: Optional RNG seed for deterministic Monte Carlo sampling.

    Returns:
        Dictionary conforming to data/winrates.json schema.
    """
    if seed is not None:
        random.seed(seed)

    hero_cards = get_representative_cards(canonical_hand.canonical_id)
    hero_score = canonical_hand.score

    # Construct the remaining 49-card deck
    hero_set = set(hero_cards)
    remaining_deck = [c for c in Deck.standard_52() if c not in hero_set]

    wins = 0
    ties = 0
    losses = 0
```

**How it works**

- "**Hero**" is poker slang for "the player we're analysing". The opponent is sometimes called
  "villain".
- **Seed:** a random number generator produces the same sequence every time if you give it the same
  starting seed. That makes Monte Carlo runs **reproducible**, which tests need.
- We get real cards for the type (`get_representative_cards`), then build the 49-card deck **without**
  them. Turning `hero_cards` into a `set` first makes the `not in` check O(1) instead of scanning a list.
- The opponent can't hold our cards, so they must be removed. That's why the count is C(49, 3), not
  C(52, 3).

> ⚠️ **Pitfall: `random.seed()` changes global state.** `random.seed(seed)` resets Python's **shared**
> random generator, the one *every* module uses. Any other code that relies on `random` is affected
> too. That breaks the project's own rule ("no global mutable state"). **Better:** create a private
> generator and use it:
>
> ```python
> rng = random.Random(seed)              # private, independent generator
> opp_cards = rng.sample(remaining_deck, 3)
> ```
>
> (Changing this would change which random hands are drawn, so the Monte Carlo test values would shift
> slightly. The exact mode, used for the real data, is unaffected.)

---

## Step 7.3 — Exact enumeration

📄 **File:** `backend/src/generator.py` — *add to the end*

```python

    if exact:
        # Full combinatorial enumeration: C(49, 3) = 18,424 opponent hands
        opponent_combinations = itertools.combinations(remaining_deck, 3)
        total_showdowns = 18424
        for opp_cards in opponent_combinations:
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
```

**How it works**

- `itertools.combinations(remaining_deck, 3)` yields every possible opponent hand **once**, as tuples
  of 3 cards. It doesn't build a list in memory; it produces them one at a time.
- One `evaluate_hand` per opponent hand, then a single comparison between two `HandScore`s, thanks to
  chapter 5's tuple design.

> ⚠️ **Pitfall: a hard-coded number.** `total_showdowns = 18424` is only correct if the remaining deck
> has exactly 49 cards. If someone later added jokers or a 2-player-hand removal, the rates would be
> silently wrong. **Safer:** count as you go (`total_showdowns = wins + ties + losses` after the loop),
> or compute `math.comb(len(remaining_deck), 3)`.

---

## Step 7.4 — Monte Carlo sampling and the result record

📄 **File:** `backend/src/generator.py` — *add to the end*

```python
    else:
        # Monte Carlo random sampling
        total_showdowns = samples
        for _ in range(samples):
            opp_cards = random.sample(remaining_deck, 3)
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1

    win_rate = wins / total_showdowns
    tie_rate = ties / total_showdowns
    loss_rate = losses / total_showdowns
    equity = (wins + 0.5 * ties) / total_showdowns

    return {
        "equity": round(equity, 4),
        "win_rate": round(win_rate, 4),
        "tie_rate": round(tie_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "category": canonical_hand.category.name,
        "multiplicity": canonical_hand.multiplicity,
        "samples": total_showdowns,
    }
```

**How it works**

- Note the `else:` is at the **same indentation as `if exact:`** from the previous step: this chunk
  continues that `if` statement.
- `random.sample(remaining_deck, 3)` picks 3 **different** cards at random (a valid opponent hand).
  Each loop iteration is an independent random game.
- `_` as a loop variable means "I don't need the counter".
- Rates are rounded to 4 decimal places to keep the file small and readable. `category` is stored by
  **name** (`"LIENG"`) because JSON has no enum type.

🧪 **Mini-check** (exact vs Monte Carlo for the best Liêng)

```bash
python -c "
from src.hands import generate_all_canonical_hands
from src.generator import compute_hand_equity
qka = {h.canonical_id: h for h in generate_all_canonical_hands()}['Q-K-A']
print(compute_hand_equity(qka))
print(compute_hand_equity(qka, exact=False, samples=5000, seed=42)['equity'])
"
```

Expected output:

```
{'equity': 0.9969, 'win_rate': 0.9962, 'tie_rate': 0.0015, 'loss_rate': 0.0023, 'category': 'LIENG', 'multiplicity': 64, 'samples': 18424}
0.9973
```

Why does the best Liêng ever **lose** (0.23%)? Every Sáp beats it. With our Q, K and A out of the deck,
the opponent can still hold 10 ranks × 4 = 40 Sáp, plus 1 each of Q-Q-Q, K-K-K and A-A-A (only 3 suits
left of those ranks): **43** hands, and 43 / 18,424 = 0.0023. It **ties** with another Q-K-A made from
the remaining suits: 3 × 3 × 3 = **27** hands, 27 / 18,424 = 0.0015.

---

## Step 7.5 — Running all 455 hands in parallel

📄 **File:** `backend/src/generator.py` — *add to the end*

```python


def _worker_task(args: tuple[CanonicalHand, bool, int, int | None]) -> tuple[str, dict[str, Any]]:
    """Worker task wrapper for ProcessPoolExecutor."""
    canonical_hand, exact, samples, seed = args
    result = compute_hand_equity(canonical_hand, exact=exact, samples=samples, seed=seed)
    return canonical_hand.canonical_id, result


def generate_winrates_database(
    exact: bool = True,
    samples: int = 10000,
    output_path: str | Path = "data/winrates.json",
    workers: int | None = None,
) -> dict[str, Any]:
    """Generate and write the winrates database for all 455 canonical hands.

    Args:
        exact: If True, run complete combinatorial enumeration.
        samples: Number of samples per hand if exact is False.
        output_path: Destination JSON filepath.
        workers: Number of parallel processes (defaults to cpu_count).

    Returns:
        The generated winrates dictionary.
    """
    canonical_hands = generate_all_canonical_hands()
    num_workers = workers or os.cpu_count() or 1

    tasks = [
        (ch, exact, samples, i if not exact else None)
        for i, ch in enumerate(canonical_hands)
    ]

    results: dict[str, Any] = {}
    if num_workers > 1:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            for cid, data in executor.map(_worker_task, tasks):
                results[cid] = data
    else:
        for task in tasks:
            cid, data = _worker_task(task)
            results[cid] = data

    # Ensure destination directory exists
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results
```

**How it works**

- **`_worker_task`** exists because `executor.map` passes **one** argument to the function. We pack
  the four arguments into a tuple and unpack them inside. It's a top-level function so worker
  processes can import it.
- **`workers or os.cpu_count() or 1`**: `or` returns the first "truthy" value. So: use `workers` if
  given; otherwise the number of cores; if that's unknown (`None`), use 1.
- **Seeds:** in Monte Carlo mode each hand gets its own seed (its index `i`), so the whole run is
  reproducible. In exact mode no seed is needed.
- **One process or many:** with 1 worker we skip the pool (simpler to debug; you can use `print` and a
  debugger normally).
- **`mkdir(parents=True, exist_ok=True)`** creates `data/` if missing and doesn't complain if it exists.
- The dict keeps insertion order (guaranteed since Python 3.7), and `executor.map` keeps input order, so
  the JSON file always lists hands in the same order: `2-2-2`, `3-2-2`, `4-2-2`, …

---

## Step 7.6 — A command-line entry point

📄 **File:** `backend/src/generator.py` — *add to the end*

```python


def main(args: Sequence[str] | None = None) -> None:
    """CLI entry point for generator."""
    parser = argparse.ArgumentParser(
        description="Liêng Stealer - Precompute Showdown Equities Database."
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=10000,
        help="Number of Monte Carlo samples per hand (default: 10000).",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Run exact combinatorial enumeration over all C(49, 3) = 18,424 hands.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/winrates.json",
        help="Output filepath (default: data/winrates.json).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help=f"Number of parallel worker processes (default: {os.cpu_count() or 1}).",
    )

    parsed = parser.parse_args(args)
    mode = "Exact Combinatorial Enumeration" if parsed.exact else f"Monte Carlo ({parsed.samples} samples)"
    print(f"Starting equity generation in {mode} across {parsed.workers} workers...")

    results = generate_winrates_database(
        exact=parsed.exact,
        samples=parsed.samples,
        output_path=parsed.output,
        workers=parsed.workers,
    )
    print(f"Successfully generated database for {len(results)} canonical hands -> {parsed.output}")


if __name__ == "__main__":
    main()
```

**How it works**

- **`argparse`** turns `--exact --workers 4` into an object: `parsed.exact == True`,
  `parsed.workers == 4`. It also generates `--help` for free.
  - `type=int` converts the text `"4"` into the integer `4` (and prints an error for `"four"`).
  - `action="store_true"` makes a **flag**: present → `True`, absent → `False`.
  - `--output` becomes `parsed.output` (dashes would become underscores).
- `main(args=None)`: when `args` is `None`, argparse reads the real command line (`sys.argv`). Tests can
  pass a list instead, e.g. `main(["--samples", "100"])`.
- **`if __name__ == "__main__":`**: when you run `python -m src.generator`, Python sets `__name__` to
  `"__main__"` and `main()` runs. When another file does `import src.generator`, nothing runs. It's also
  the guard that `ProcessPoolExecutor` needs.

🧪 **Mini-check**

```bash
python -m src.generator --help
```

Expected output (the default worker count is your number of CPU cores):

```
usage: generator.py [-h] [--samples SAMPLES] [--exact] [--output OUTPUT]
                    [--workers WORKERS]

Liêng Stealer - Precompute Showdown Equities Database.

options:
  -h, --help         show this help message and exit
  --samples SAMPLES  Number of Monte Carlo samples per hand (default: 10000).
  --exact            Run exact combinatorial enumeration over all C(49, 3) =
                     18,424 hands.
  --output OUTPUT    Output filepath (default: data/winrates.json).
  --workers WORKERS  Number of parallel worker processes (default: 4).
```

---

## Step 7.7 — Generate the data

First a **quick Monte Carlo trial** into a scratch file, to see it working:

```bash
python -m src.generator --samples 2000 --output data/winrates_mc.json
```

Expected output (a few seconds; the worker count will match your machine):

```
Starting equity generation in Monte Carlo (2000 samples) across 4 workers...
Successfully generated database for 455 canonical hands -> data/winrates_mc.json
```

Now the **real, exact database**:

```bash
time python -m src.generator --exact
```

Expected output (about 30 seconds on a 4-core laptop; more cores = faster):

```
Starting equity generation in Exact Combinatorial Enumeration across 4 workers...
Successfully generated database for 455 canonical hands -> data/winrates.json
```

Look at the top of the file:

```bash
head -n 18 data/winrates.json
```

```json
{
  "2-2-2": {
    "equity": 0.9974,
    "win_rate": 0.9974,
    "tie_rate": 0.0,
    "loss_rate": 0.0026,
    "category": "SAP",
    "multiplicity": 4,
    "samples": 18424
  },
  "3-2-2": {
    "equity": 0.6661,
    "win_rate": 0.666,
    "tie_rate": 0.0002,
    "loss_rate": 0.3339,
    "category": "DIEM",
    "multiplicity": 24,
    "samples": 18424
  },
```

Even the weakest Sáp (2-2-2) wins 99.74% of the time. It only loses to the 48 bigger Sáp hands
(12 ranks × 4 suit combos) out of 18,424 opponent hands.

Delete the Monte Carlo trial file. It must not be used by the app:

```bash
rm data/winrates_mc.json
```

> ⚠️ **Always generate the official file with `--exact`.** The default mode is Monte Carlo with 10,000
> samples. That file would have slightly different numbers and `"samples": 10000`, and the tests in
> chapters 7, 8 and 13 (which expect exact values like `0.9969` and `"samples": 18424`) would fail.
> A safer design would make `--exact` the default, since it's both correct and fast enough here.

> 🔬 **Reproducibility check.** Exact enumeration has no randomness, so your file should be
> **byte-for-byte identical** to the original:
>
> ```bash
> cmp data/winrates.json /path/to/lieng-stealer/backend/data/winrates.json && echo IDENTICAL
> ```
>
> If it prints `IDENTICAL`, your evaluator, canonical hands and generator are all exactly right. That's a
> very strong end-to-end test of chapters 4–7.

> ⚠️ **Pitfall: the big modelling assumption.** The equity we compute is "how often do I win against
> a **random** hand?" But in the EV formula (chapter 9) we need "how often do I win **when the opponent
> calls**?" Real opponents call with **good** hands and fold bad ones, so the hands that call are
> stronger than random. Our equities are therefore **too optimistic**, especially for medium hands.
> This is the biggest simplification in the whole project. Chapter 17 suggests how to fix it
> (computing equity against a "calling range" such as "the top 40% of hands").

---

## Step 7.8 — The tests

📄 **File:** `backend/tests/test_generator.py` — *create this file*

```python
"""Unit tests for the Simulation Engine & Offline Winrates Generator.

Verifies:
- Exact equity calculations (A-A-A is unbeatable, 2-2-2 beats Q-K-A, Q-K-A beats A-2-3)
- Rate sum invariants: win_rate + tie_rate + loss_rate == 1.0
- Equity formula invariant: equity == win_rate + 0.5 * tie_rate
- Monte Carlo convergence against exact values
- File output integrity & JSON schema conformance for data/winrates.json
"""

import json
from pathlib import Path
import pytest

from src.evaluator import HandCategory
from src.generator import (
    compute_hand_equity,
    generate_winrates_database,
)
from src.hands import (
    generate_all_canonical_hands,
    to_canonical,
    get_representative_cards,
)


@pytest.fixture(scope="module")
def canonical_map() -> dict:
    hands = generate_all_canonical_hands()
    return {h.canonical_id: h for h in hands}
```

**What's a fixture?** `@pytest.fixture` marks a function that **prepares data** for tests. Any test
that has a parameter with the same name (`canonical_map`) receives the fixture's return value.
`scope="module"` means "build it once for this whole file, not once per test", which saves time.

📄 **File:** `backend/tests/test_generator.py` — *add to the end*

```python


class TestGeneratorEngine:
    """Test suite for simulation engine and equity calculations."""

    def test_aaa_exact_equity(self, canonical_map: dict) -> None:
        """A-A-A is the maximum hand in Liêng and can never tie or lose heads-up."""
        aaa = canonical_map["A-A-A"]
        res = compute_hand_equity(aaa, exact=True)
        assert res["equity"] == 1.0
        assert res["win_rate"] == 1.0
        assert res["tie_rate"] == 0.0
        assert res["loss_rate"] == 0.0
        assert res["samples"] == 18424
        assert res["category"] == "SAP"

    def test_equity_hierarchy_monotonicity(self, canonical_map: dict) -> None:
        """Verify strict hierarchical equity relationships:
        A-A-A > 2-2-2 > Q-K-A > A-2-3 > Đĩ > 0 points (Bù).
        """
        aaa = compute_hand_equity(canonical_map["A-A-A"], exact=True)
        two22 = compute_hand_equity(canonical_map["2-2-2"], exact=True)
        qka = compute_hand_equity(canonical_map["Q-K-A"], exact=True)
        a23 = compute_hand_equity(canonical_map["A-2-3"], exact=True)
        qkk = compute_hand_equity(canonical_map["K-K-Q"], exact=True)  # Đĩ

        # Sáp A beats Sáp 2
        assert aaa["equity"] > two22["equity"]
        # Lowest Sáp (2-2-2) beats Highest Liêng (Q-K-A)
        assert two22["equity"] > qka["equity"]
        # Highest Liêng (Q-K-A) beats Lowest Liêng (A-2-3)
        assert qka["equity"] > a23["equity"]
        # Lowest Liêng (A-2-3) beats Đĩ
        assert a23["equity"] > qkk["equity"]
```

📄 **File:** `backend/tests/test_generator.py` — *add to the end*

```python

    def test_rate_invariants(self, canonical_map: dict) -> None:
        """Check mathematical consistency across multiple sample hands."""
        test_keys = ["A-A-A", "Q-K-A", "A-2-3", "9-8-7", "K-K-Q", "10-J-K"]
        for key in test_keys:
            if key not in canonical_map:
                continue
            res = compute_hand_equity(canonical_map[key], exact=True)
            # win_rate + tie_rate + loss_rate == 1.0 (within rounding precision)
            total_prob = res["win_rate"] + res["tie_rate"] + res["loss_rate"]
            assert abs(total_prob - 1.0) <= 0.001

            # equity == win_rate + 0.5 * tie_rate
            expected_equity = res["win_rate"] + 0.5 * res["tie_rate"]
            assert abs(res["equity"] - expected_equity) <= 0.001

    def test_monte_carlo_convergence(self, canonical_map: dict) -> None:
        """Monte Carlo with N=5000 should converge to within 1.5% of exact equity."""
        qka = canonical_map["Q-K-A"]
        exact_res = compute_hand_equity(qka, exact=True)
        mc_res = compute_hand_equity(qka, exact=False, samples=5000, seed=42)

        assert abs(exact_res["equity"] - mc_res["equity"]) < 0.015
```

- **Invariants** are facts that must *always* hold (rates sum to 1; equity = win + ½ tie). Testing
  invariants catches whole families of bugs.
- Floats are compared with a **tolerance** (`abs(a - b) <= 0.001`), never with `==`, because rounding
  makes tiny differences.

> 💡 `"10-J-K"` is not a valid canonical ID (the real one is `"K-J-10"`), so `if key not in
> canonical_map: continue` silently skips it. A test that silently skips its own input is easy to miss.
> That's another symptom of the naming inconsistency from chapter 6.

📄 **File:** `backend/tests/test_generator.py` — *add to the end*

```python

    def test_generated_json_database_schema(self) -> None:
        """Verify the precomputed data/winrates.json conforms to the complete schema."""
        db_path = Path("data/winrates.json")
        if not db_path.exists():
            db_path = Path(__file__).resolve().parent.parent / "data" / "winrates.json"
        assert db_path.exists(), "data/winrates.json must exist"

        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 455, f"Expected 455 canonical hands, got {len(data)}"

        required_keys = {
            "equity", "win_rate", "tie_rate", "loss_rate",
            "category", "multiplicity", "samples"
        }

        for cid, profile in data.items():
            assert required_keys.issubset(profile.keys()), f"Missing keys in {cid}"
            assert 0.0 <= profile["equity"] <= 1.0
            assert profile["samples"] == 18424
            assert profile["category"] in {"SAP", "LIENG", "DI", "DIEM"}
            assert profile["multiplicity"] in {4, 24, 64}
```

- `Path(__file__).resolve().parent.parent` = "the folder two levels above this test file" =
  `backend/`. It's a fallback so the test also works when pytest is started from another folder.
- `assert condition, "message"`: the message is shown if the assertion fails.
- This test checks the **file on disk**, so it only passes after Step 7.7 (with `--exact`).

---

## ✅ Checkpoint

```bash
python -m pytest -q
```

Expected output (this takes a few seconds because of the exact enumerations):

```
............................                                             [100%]
28 passed in 3.50s
```

Commit, including the data file (remember the `!backend/data/winrates.json` rule in `.gitignore`):

```bash
git add . && git commit -m "feat: equity generator and precomputed winrates.json"
```

## Recap

- **Equity** = `(wins + ½ ties) / showdowns`. It's the "probability of winning" used by the EV maths.
- **Exact enumeration** checks all C(49,3) = 18,424 opponent hands; **Monte Carlo** samples randomly,
  with error ≈ `sqrt(p(1−p)/N)`.
- **`ProcessPoolExecutor`** spreads the 455 hand types over all CPU cores; `executor.map` keeps the order.
- The result is an ~83 KB JSON file that, in exact mode, is **byte-identical** on every machine.
- Pitfalls: global `random.seed`; hard-coded `18424`; Monte Carlo is the default but tests require `--exact`;
  and the big one: equity is measured against a **random** hand, not against the hands that would call.

**Next:** [08 — The database layer](08-database-layer.md)
