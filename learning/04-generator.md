# Lesson 04 — The generator and `winrates.json`

> **Goal:** understand how `generator.py` plays every one of the 455 hand classes against every
> possible opponent hand, why that takes seconds and not a week, and what each field of the
> resulting `winrates.json` means.
> **Files:** [`backend/src/generator.py`](../backend/src/generator.py),
> [`backend/data/winrates.json`](../backend/data/winrates.json),
> [`backend/tests/test_generator.py`](../backend/tests/test_generator.py).
> **Time:** ~60 min. **Before this:** [03 — Canonical hands: 22,100 → 455](03-canonical-hands.md).

---

## Where this fits

```
 OFFLINE (you run this once, by hand)
 ────────────────────────────────────
 evaluator.py ──► hands.py ──► ┌────────────────────────────┐ ──► data/winrates.json
 who beats whom   455 classes  │ generator.py (this lesson) │     455 records, 82,694 bytes
                               └────────────────────────────┘           │
                                                                         ▼
 ONLINE (every request)                                   db.py (lesson 05) reads it
                                                          calling_range.py (lesson 06) checks itself against it
```

`generator.py` is the only module that does heavy work, and nothing in the running app imports it.
Only its test file does. You run it from the command line when the rules or the evaluator change.
It writes `data/winrates.json`, and from then on the app just reads that file. The file is
committed to git, so a fresh clone works without running the generator at all.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [generator.py:1-7](../backend/src/generator.py#L1-L7) | The docstring: exact enumeration and Monte Carlo, both supported. |
| 2 | [generator.py:32-106](../backend/src/generator.py#L32-L106) | `compute_hand_equity`: one hand class against its opponents. |
| 3 | [generator.py:118-122](../backend/src/generator.py#L118-L122) | `_worker_task`: a tiny wrapper that exists for the process pool. |
| 4 | [generator.py:125-177](../backend/src/generator.py#L125-L177), [:109-115](../backend/src/generator.py#L109-L115) | `generate_winrates_database`: 455 tasks, in parallel, then one JSON file, written atomically; `_file_mode` picks its permissions. |
| 5 | [generator.py:180-244](../backend/src/generator.py#L180-L244) | The command line: `--exact` / `--monte-carlo` (one or the other), `--samples`, `--output`, `--workers`. |
| 6 | [winrates.json](../backend/data/winrates.json) | Open it and read the first two records. Don't edit it by hand. |
| 7 | [test_generator.py](../backend/tests/test_generator.py) | 15 tests: exact values, invariants, the schema, the CLI defaults, five safety tests and three file-handling tests. |

---

## Walkthrough

### 1. What "equity" means here

Put your hand against `n` opponent hands and count the results:

```
win_rate  = wins   / n          tie_rate = ties / n          loss_rate = losses / n
equity    = (wins + 0.5 × ties) / n
```

A tie splits the pot, so it counts as half a win. **Equity** is the number the EV formula needs as
"how often do I win when called" (lesson 07). Here the opponent holds a *random* hand: any 3 of the
49 cards you don't hold, all equally likely. Lesson 06 replaces "random" with "the hands that would
actually call".

How many opponent hands are there? You hold 3 of the 52 cards, so the opponent picks 3 of the other
49: C(49, 3) = **18,424** hands. That number appears everywhere in this lesson and the next two. In
the code it is `OPPONENT_COMBINATIONS`, computed once in `hands.py` as `math.comb(52 - 3, 3)`
([hands.py:34](../backend/src/hands.py#L34), lesson 03).

### 2. One hand against every opponent: exact enumeration

📍 [`backend/src/generator.py:57-79`](../backend/src/generator.py#L57-L79)
```python
    hero_cards = get_representative_cards(canonical_hand.canonical_id)
    hero_score = canonical_hand.score

    # Construct the remaining 49-card deck
    hero_set = set(hero_cards)
    remaining_deck = [c for c in Deck.standard_52() if c not in hero_set]

    wins = 0
    ties = 0
    losses = 0

    if exact:
        # Full combinatorial enumeration: C(49, 3) = 18,424 opponent hands
        opponent_combinations = itertools.combinations(remaining_deck, 3)
        total_showdowns = OPPONENT_COMBINATIONS
        for opp_cards in opponent_combinations:
            opp_score = evaluate_hand(opp_cards)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
```

Read it in three steps:

1. **Pick concrete cards for the class.** `get_representative_cards("Q-K-A")` returns `Q♠ K♥ A♦`
   ([hands.py:136](../backend/src/hands.py#L136), lesson 03). `canonical_hand.score` is the
   `HandScore` computed once when the class was built.
2. **Build the 49-card deck the opponent draws from.** Cards are frozen dataclasses (lesson 01), so
   they hash and `c not in hero_set` is a fast set lookup.
3. **Walk every opponent hand.** `itertools.combinations(remaining_deck, 3)` yields each unordered
   3-card hand exactly once. `HandScore` defines `>` and `==` on its `score_tuple`
   ([evaluator.py:263-286](../backend/src/evaluator.py#L263-L286), lesson 02), so one comparison
   decides each showdown.

**Worked example: Q-K-A.** Counting by hand, without rounding:

| Result | Count | Why |
|--------|-------|-----|
| wins | 18,354 | everything that is not a Sáp and not another Q-K-A |
| ties | 27 | other Q-K-A hands: 3 queens × 3 kings × 3 aces left |
| losses | 43 | every Sáp: 10 untouched ranks × 4 combos + Q, K, A × 1 combo each |
| total | 18,424 | C(49, 3) |

`equity = (18,354 + 0.5 × 27) / 18,424 = 0.99693`, stored as **0.9969**. That is the number you
saw in lesson 07's worked example.

For the whole file the generator does 455 × 18,424 = **8,382,920** evaluations. One class takes
about 0.02 s on the machine this lesson was re-run on, and a full run with one worker took 10 s.
Before the evaluator's 455-entry score table (lesson 02) the same run took 57 s: almost all the
time is spent in `evaluate_hand`. Your timings will differ.

### 3. Why one representative per class is enough

The generator plays `Q♠ K♥ A♦` and writes the answer for all 64 Q-K-A hands. Why may it?

Take any other Q-K-A, say `Q♣ K♣ A♣`. Both hands take one queen, one king and one ace out of the
deck. So both leftover decks hold exactly the same number of cards of each rank: four of every
rank from 2 to J, and three each of Q, K and A. Pair the leftover cards up rank by rank (`Q♠` in one
deck with `Q♣` in the other, and so on). That pairing turns every opponent hand of one deck into an
opponent hand of the other with the **same ranks**. In Liêng, strength depends only on ranks
(AGENTS.md §3.1), so each pair of opponent hands has the same score. Same opponents, same scores,
same counts.

You don't have to trust the argument. I ran the same count for `Q♣ K♣ A♣`, all one suit:
`(18354, 27, 43)`, identical to `Q♠ K♥ A♦`. This is what makes the 22,100 → 455 reduction of
lesson 03 pay off here: 455 runs instead of 22,100, about 49 times less work.

### 4. The other branch: Monte Carlo

📍 [`backend/src/generator.py:80-91`](../backend/src/generator.py#L80-L91)
```python
    else:
        # Monte Carlo random sampling
        total_showdowns = samples
        for _ in range(samples):
            sampled = rng.sample(remaining_deck, 3)
            opp_score = evaluate_hand(sampled)
            if hero_score > opp_score:
                wins += 1
            elif hero_score == opp_score:
                ties += 1
            else:
                losses += 1
```

Instead of visiting all 18,424 opponents, Monte Carlo draws `samples` random ones and hopes they
are representative. `rng.sample(remaining_deck, 3)` picks 3 distinct cards. The same opponent can
come up twice across iterations, which is fine for an estimate.

How good is the estimate? Here is K-Q-3 (true equity 0.36) with `seed=7`:

| Samples | Estimate | Actual error | Predicted error √(p(1−p)/N) |
|---------|----------|--------------|-----------------------------|
| 100 | 0.405 | 0.045 | 0.048 |
| 1,000 | 0.3495 | 0.0105 | 0.0152 |
| 10,000 | 0.3598 | 0.0002 | 0.0048 |
| 18,424 exact | **0.36** | 0 | — |

The 10,000 row was lucky. The predicted error says a typical run is off by about 0.005. Note that
10,000 samples cost more than half of the exact count (18,424), and they give you only an estimate.
For Liêng the exact method is simply better. Monte Carlo stays in the code because it is the
technique you need when the full space is too big (5-card poker against several players, say).

The test pins a sanity bound instead of a value: Q-K-A with 5,000 samples and `seed=42` gives
0.9973, within 0.015 of the exact 0.9969
([test_generator.py:78-84](../backend/tests/test_generator.py#L78-L84)).

Where does `rng` come from? The top of the function:

📍 [`backend/src/generator.py:53-55`](../backend/src/generator.py#L53-L55)
```python
    if not exact and samples < 1:
        raise ValueError(f"Monte Carlo needs at least 1 sample, got {samples}.")
    rng = random.Random(seed)
```

`random.Random(seed)` is a **private** generator that belongs to this one call. Until October 2026
the function called `random.seed(seed)` instead, which reseeds Python's global generator, the one
every other module shares (weak spot 3). A private `Random(42)` produces exactly the same sequence
as `random.seed(42)` did, so every Monte Carlo number in this lesson stayed the same. The first two
lines reject `samples=0`, which would otherwise divide by zero further down.

### 5. The record: seven fields

📍 [`backend/src/generator.py:93-106`](../backend/src/generator.py#L93-L106)
```python
    win_rate = wins / total_showdowns
    tie_rate = ties / total_showdowns
    loss_rate = losses / total_showdowns
    equity = (wins + 0.5 * ties) / total_showdowns

    return {
        "equity": round(equity, 8),
        "win_rate": round(win_rate, 8),
        "tie_rate": round(tie_rate, 8),
        "loss_rate": round(loss_rate, 8),
        "category": canonical_hand.category.name,
        "multiplicity": canonical_hand.multiplicity,
        "samples": total_showdowns,
    }
```

| Field | Q-K-A | Meaning |
|-------|-------|---------|
| `equity` | 0.9969 | win + half the ties. The number the rest of the app uses. |
| `win_rate`, `tie_rate`, `loss_rate` | 0.9962, 0.0015, 0.0023 | the three counts divided by 18,424 |
| `category` | `"LIENG"` | the `HandCategory` **name** (`SAP`, `LIENG`, `DI`, `DIEM`), so `db.py` can turn it back into the enum |
| `multiplicity` | 64 | how many of the 22,100 real hands belong to the class (lesson 03) |
| `samples` | 18424 | how many showdowns were counted. 18,424 means "exact". |

**Tie rates come in exactly three sizes.** You can only tie a hand with the same rank multiset
(lesson 02: the score tuple holds all three ranks). So a tie needs the opponent to hold your three
ranks, drawn from what you left in the deck:

| Your class | Example | Opponent ways to copy your ranks | `tie_rate` |
|------------|---------|----------------------------------|------------|
| three distinct ranks | Q-K-A, K-Q-3 | 3 × 3 × 3 = **27** | 27 / 18,424 = 0.0015 |
| a pair | 5-2-2, K-K-Q | C(2,2) × 3 = **3** | 3 / 18,424 = 0.0002 |
| Sáp | A-A-A | C(1,3) = **0** | 0.0 |

Every one of the 455 records has one of those three tie rates.

**Rounding has a cost.** Each rate is rounded on its own, so the three do not always add up to 1.
In the real file, 151 of the 455 records sum to 1.0001. And `equity` is rounded from the raw counts,
so in 314 records it differs from `win_rate + 0.5 × tie_rate` by up to 0.0001. The tests allow
0.001 for both ([test_generator.py:70-76](../backend/tests/test_generator.py#L70-L76)), and the
database loader, which now checks both sums, allows 0.0002 ([db.py:20-21](../backend/src/db.py#L20-L21),
lesson 05).

### 6. All 455 classes, in parallel

📍 [`backend/src/generator.py:142-158`](../backend/src/generator.py#L142-L158)
```python
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
```

- **One task per class.** Each is a tuple `(hand, exact, samples, seed)`. In Monte Carlo mode the
  seed is the class's index, so a rerun gives the same numbers. In exact mode there is nothing
  random, so the seed is `None`.
- **Processes, not threads.** The work is pure Python arithmetic. Python threads take turns on one
  core (the GIL), so only separate processes run it truly in parallel. `ProcessPoolExecutor` starts
  `num_workers` copies of Python and hands each one tasks.
- **`executor.map` keeps the input order**, even when tasks finish out of order. So the dict, and
  the file, always list the classes in the same order.
- **One worker means no pool.** The `else` branch runs the same tasks in this process, which is
  easier to debug and is what you get with `--workers 1`.

Why does `_worker_task` exist at all, instead of passing `compute_hand_equity` with a `lambda`?

📍 [`backend/src/generator.py:118-122`](../backend/src/generator.py#L118-L122)
```python
def _worker_task(args: tuple[CanonicalHand, bool, int, int | None]) -> tuple[str, dict[str, Any]]:
    """Worker task wrapper for ProcessPoolExecutor."""
    canonical_hand, exact, samples, seed = args
    result = compute_hand_equity(canonical_hand, exact=exact, samples=samples, seed=seed)
    return canonical_hand.canonical_id, result
```

`executor.map` calls the function with **one** argument per task, so the wrapper unpacks the
tuple. And the function has to travel to another process, which means it has to be **pickled**
(see the concept box). A module-level function pickles as just its name, `src.generator._worker_task`
(45 bytes). A `lambda` fails with `PicklingError: Can't pickle <function <lambda> …>`. The wrapper
also returns the canonical ID next to the result, so the parent knows which record it got.

### 7. Writing the file

📍 [`backend/src/generator.py:160-177`](../backend/src/generator.py#L160-L177)
```python
    # Write to a temporary file in the same folder, then rename it over the target: readers see
    # either the old file or the complete new one, never a half-written file.
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=out_file.parent, suffix=".tmp", delete=False
    ) as tmp:
        try:
            json.dump(results, tmp, indent=2)
        except BaseException:
            tmp.close()
            os.unlink(tmp.name)
            raise
    # NamedTemporaryFile creates the file as owner-only (0600); give it normal permissions first.
    os.chmod(tmp.name, _file_mode(out_file))
    os.replace(tmp.name, out_file)

    return results
```

Opening the real file with `open(out_file, "w")`, as the code did until October 2026, empties it
first: if the process died during `json.dump`, the app would find a truncated file (weak spot 5).
Now the JSON goes to a randomly named `….tmp` file **in the same folder**, and `os.replace` renames
it over the target in one step. A rename within one file system is atomic, so a reader sees either
the old file or the complete new one. (`delete=False` keeps the temporary file after the `with`
closes it, so it can be renamed.)

Two details were added in `a9d9ce9` (weak spot 7). If `json.dump` fails half-way (a full disk, a
Ctrl-C), the `except BaseException` closes and deletes the temporary file and re-raises, so the
error still surfaces and no `….tmp` is left in `data/`. `BaseException` rather than `Exception` so
that a `KeyboardInterrupt` cleans up too. And because `NamedTemporaryFile` always creates its file
with mode `0600` (owner only), and `os.replace` keeps the mode of the file it moves, the code sets
the permissions before the rename:

📍 [`backend/src/generator.py:109-115`](../backend/src/generator.py#L109-L115)
```python
def _file_mode(path: Path) -> int:
    """Permissions for the written file: keep the old file's mode, or use 0644 minus the umask."""
    if path.exists():
        return path.stat().st_mode & 0o777
    umask = os.umask(0)
    os.umask(umask)
    return 0o644 & ~umask
```

Regenerating `data/winrates.json` keeps whatever mode it had. A brand-new file gets `0644`
(`rw-r--r--`) minus your **umask**, the per-process setting that says which permission bits new
files must *not* get; with the usual umask `002` or `022` that is `rw-r--r--`. Python can't read
the umask without setting it, hence the set-and-restore pair. `& 0o777` keeps only the permission
bits of `st_mode`, which also holds the file type.

Where is `out_file`? By default `DEFAULT_DB_PATH` from [paths.py](../backend/src/paths.py), the
absolute path `backend/data/winrates.json` worked out from the location of `paths.py` itself, not
from your current directory ([generator.py:128](../backend/src/generator.py#L128),
[:216](../backend/src/generator.py#L216)). Run the generator from anywhere and it writes where the
app reads.

`indent=2` makes the file readable and diff-friendly: 455 records, 82,694 bytes. The order is the
order of `generate_all_canonical_hands`, which is **multiset order, not strength order**. It starts
`"2-2-2", "3-2-2", "4-2-2", "5-2-2", "6-2-2"`. So `"5-2-2"` (9 points, equity 0.8591) sits right
next to `"6-2-2"` (0 points, 0.0038). The file ends with `"Q-K-A", "A-A-Q", "K-K-K", "A-K-K",
"A-A-K", "A-A-A"`. Never assume a position in this file means anything. Lesson 06 builds its own
strength order.

The exact run is deterministic. I regenerated it into a scratch path with the current code (one
worker, 10 s) and compared it with the committed file: `cmp` reported them **byte-for-byte
identical**. That one check proves that the rewritten evaluator, the canonical classes and the
generator still agree with the data the app serves.

### 8. The command line

📍 [`backend/src/generator.py:199-212`](../backend/src/generator.py#L199-L212)
```python
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--exact",
        dest="exact",
        action="store_true",
        default=True,
        help="Run exact combinatorial enumeration over all C(49, 3) = 18,424 hands (default).",
    )
    mode.add_argument(
        "--monte-carlo",
        dest="exact",
        action="store_false",
        help="Estimate equities from --samples random opponent hands instead of exact enumeration.",
    )
```

Both flags write to the same `dest="exact"`. Exact is the default, and `--monte-carlo` flips it to
`False`. Earlier versions defaulted to Monte Carlo and quietly produced a file that failed the
tests, so the safe choice became the default
([test_generator.py:114-120](../backend/tests/test_generator.py#L114-L120) pins that). `--exact`
on its own changes nothing, but it is now in a **mutually exclusive group**, so giving both flags is
an error instead of "the last one wins":

```
$ python -m src.generator --exact --monte-carlo
usage: generator.py [-h] [--samples SAMPLES] [--exact | --monte-carlo]
                    [--output OUTPUT] [--workers WORKERS]
generator.py: error: argument --monte-carlo: not allowed with argument --exact
```

`--samples` and `--workers` go through `_positive_int`
([generator.py:180-185](../backend/src/generator.py#L180-L185)), so `--samples 0` is also a usage
error (exit code 2): `argument --samples: must be at least 1, got 0`. Run it as
`python -m src.generator` from `backend/`: the `-m` form puts `backend/` on the import path, so
`from src.evaluator import …` works.

### 9. What the tests pin

| Test | Pins |
|------|------|
| [test_aaa_exact_equity :34](../backend/tests/test_generator.py#L34) | A-A-A: equity 1.0, no ties, `samples == 18424`, `"SAP"` |
| [test_equity_hierarchy_monotonicity :45](../backend/tests/test_generator.py#L45) | A-A-A > 2-2-2 > Q-K-A > A-2-3 > K-K-Q (Đĩ) |
| [test_rate_invariants :64](../backend/tests/test_generator.py#L64) | rates sum to 1 and equity = win + ½ tie, within 0.001 |
| [test_monte_carlo_convergence :78](../backend/tests/test_generator.py#L78) | 5,000 samples land within 0.015 of exact |
| [test_generated_json_database_schema :86](../backend/tests/test_generator.py#L86) | the committed file: 455 keys, 7 fields, `samples == 18424` everywhere |
| [:114](../backend/tests/test_generator.py#L114), [:117](../backend/tests/test_generator.py#L117) | exact by default, Monte Carlo only on request |
| [:124](../backend/tests/test_generator.py#L124), [:128](../backend/tests/test_generator.py#L128) | `--exact --monte-carlo` and `--samples 0` are usage errors |
| [:132](../backend/tests/test_generator.py#L132) | the default output is the absolute `DEFAULT_DB_PATH` |
| [:138](../backend/tests/test_generator.py#L138) | a seeded Monte Carlo run leaves the global `random` state alone |
| [:147](../backend/tests/test_generator.py#L147) | a real write (Monte Carlo, 5 samples, one worker) leaves one complete file and no `.tmp` |
| [:157](../backend/tests/test_generator.py#L157), [:168](../backend/tests/test_generator.py#L168) | a new file gets `0644` minus the umask; an existing `0640` file stays `0640` |
| [:177](../backend/tests/test_generator.py#L177) | a `json.dump` that raises leaves the old file untouched and no `.tmp` |

The schema test reads the real file, so it fails if someone commits a Monte Carlo file by mistake.
`test_rate_invariants` lists six hands, and since October 2026 it asserts that each is a real
canonical id instead of skipping unknown ones (weak spot 6).

---

## 💡 Concept: pickling and process pools

A worker process has its own memory. To send it a task, Python **pickles** the function and its
arguments into bytes, ships them through a pipe, and unpickles them on the other side.

- Data (tuples, frozen dataclasses, enums) pickles by value.
- Functions pickle **by name**: "module `src.generator`, attribute `_worker_task`". The worker
  imports that module and looks the name up. A `lambda` or a nested function has no importable
  name, so it cannot be sent.
- On Linux the default start method is `fork` (the worker starts as a copy of the parent). On
  Windows and macOS it is `spawn` (a fresh Python that re-imports your module). That is why
  [generator.py:243](../backend/src/generator.py#L243) has an `if __name__ == "__main__":` guard:
  without it, every spawned worker would start the generator again.

## 💡 Concept: how wrong is a Monte Carlo estimate?

Each sample is a coin flip that comes up "win" with probability `p`. After `N` flips, the typical
error of the average is the **standard error** `√(p(1 − p) / N)`. Two consequences:

- Quadrupling `N` only halves the error.
- Hands near 0 or 1 (A-A-A, 4-3-3) are estimated well, hands near 0.5 worst.

For K-Q-3 that is 0.048 at 100 samples and 0.0048 at 10,000, as in the table in section 4.

---

## Design decisions

- **Exact by default.** The space is small (18,424 opponents), so the true value costs about ten
  seconds of CPU, once. An estimate would add noise to every downstream number and break the
  exact cross-check in lesson 06.
- **One representative per class.** Suit symmetry makes it exact, not an approximation, and it
  cuts the work by about 49 times.
- **Precompute offline, commit the result.** Requests never wait for this. The cost is that the
  file can drift from the code if the rules change and nobody reruns the generator. The schema test
  and the `cmp` check are the guards.
- **JSON, not a binary format.** 83 KB, readable, diff-able, and loads in a few milliseconds.
- **Processes over threads.** It is CPU-bound Python, so only processes help. Tasks are big
  (18,424 evaluations each), so the cost of pickling them is negligible.
- **Write to a temporary file, then rename.** The app may be reading `winrates.json` at any moment
  (a restart, a test run); an atomic rename means it never sees half a file. The price is two
  details a plain `open(…, "w")` gets for free: the file's permissions and cleaning up on failure.

---

## ⚠️ Weak spots

Eight weak spots were listed here when the course was written. Commit `bba5e63` ("fix(core)",
October 2026) fixed six of them. Two small ones remain; the atomic write brought a new one, which
commit `a9d9ce9` fixed.

1. ✅ **Fixed: `--exact` did nothing, and the last flag won.** `--monte-carlo --exact` gave exact and
   `--exact --monte-carlo` gave Monte Carlo. Now both flags are in a mutually exclusive group
   ([generator.py:199-212](../backend/src/generator.py#L199-L212)), so giving both is a usage error.
   Pinned by `test_exact_and_monte_carlo_are_mutually_exclusive`
   ([test_generator.py:124-126](../backend/tests/test_generator.py#L124-L126)).
2. ✅ **Fixed: a hard-coded 18,424.** The count was typed out in the generator (and 22,100 in two
   other modules). Now it is `OPPONENT_COMBINATIONS` from `hands.py`
   ([generator.py:71](../backend/src/generator.py#L71)), computed with `math.comb` and pinned by
   [test_hands.py:127-131](../backend/tests/test_hands.py#L127-L131). Exercise 4 shows how far one
   wrong constant would reach.
3. ✅ **Fixed: global random state.** `random.seed(seed)` reseeded the generator every module shares,
   against AGENTS.md §2.2. Now each call has its own `random.Random(seed)`
   ([generator.py:55](../backend/src/generator.py#L55)). Pinned by
   `test_seeded_monte_carlo_leaves_global_random_untouched`
   ([test_generator.py:138-145](../backend/tests/test_generator.py#L138-L145)).
4. ✅ **Fixed: output relative to the current directory.** The default was the relative
   `"data/winrates.json"`, so running from another folder wrote a second file there while the app
   kept reading the old one. Now the default is the absolute `DEFAULT_DB_PATH`
   ([paths.py:8-9](../backend/src/paths.py#L8-L9)), shared with `db.py` and the CLI. Pinned by
   [test_generator.py:132-136](../backend/tests/test_generator.py#L132-L136).
5. ✅ **Fixed: a non-atomic write**, which truncated the real file before writing it. Now it writes a
   temporary file and renames it ([generator.py:160-175](../backend/src/generator.py#L160-L175)),
   pinned by [test_generator.py:147-153](../backend/tests/test_generator.py#L147-L153).
6. ✅ **Fixed: a test that silently skipped a hand.** `test_rate_invariants` listed `"10-J-K"`, which
   is not a canonical id (it is `"K-J-10"`), and `continue`d past it. Now it uses `"K-J-10"` and
   asserts every key exists ([test_generator.py:66-68](../backend/tests/test_generator.py#L66-L68)).
   Exercise 3 puts the typo back.
7. ✅ **Fixed: the new file was private to its owner, and a failed write left litter.**
   `NamedTemporaryFile` always creates its file with mode `0600`, and `os.replace` keeps that mode,
   so a regenerated `winrates.json` was `-rw-------` whatever your umask: on a server where the app
   runs as a different user than the one who regenerated the data, the app could no longer read it
   (and git, which records only the executable bit, wouldn't show the change). If `json.dump` failed
   half-way, the `….tmp` file stayed in `data/`. Now `os.chmod(tmp.name, _file_mode(out_file))`
   ([generator.py:174](../backend/src/generator.py#L174)) keeps the old file's mode, or gives a new
   file `0644` minus the umask ([:109-115](../backend/src/generator.py#L109-L115)), and the
   `except BaseException` around the dump deletes the temporary file
   ([:167-172](../backend/src/generator.py#L167-L172)). Pinned by `TestGeneratorFileHandling`
   ([test_generator.py:156-190](../backend/tests/test_generator.py#L156-L190)): delete the `chmod`
   line and `test_new_file_gets_normal_permissions` and `test_existing_file_keeps_its_permissions`
   both fail, the second with `assert (33152 & 511) == 416` (33152 is a regular file with mode
   `0600`, 416 is `0o640`);
   delete the `try`/`except` and `test_failed_write_leaves_the_old_file_and_no_temp_file` finds a
   `tmp….tmp` next to `winrates.json`. *Still open, and minor:* reading the umask means setting it to
   0 for an instant, which would race with another thread creating files (the generator has none at
   that point); and the cleanup covers only the dump, so a failing `chmod` or `os.replace` still
   leaves the `.tmp` behind.
8. **Rounded rates don't add up.** 151 records sum to 1.0001 (section 5). Harmless for the app,
   which only reads `equity`, and the database loader tolerates it, but surprising if you validate
   the file yourself. *Fix:* store the raw counts too, or round only `equity`.
9. **Small things.** The unused `Card` import is gone (`ruff` now checks for unused imports), but
   `Any` still appears in three signatures and one variable although AGENTS.md §2.1 asks for a
   justification. A `TypedDict` for the record would document the 7 fields in one place (exercise 6).
   And the
   `samples < 1` check raises a plain `ValueError` ([generator.py:53-54](../backend/src/generator.py#L53-L54)),
   not a `LiengError` (lesson 01).

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_generator.py -q
```

Expected output (the timing varies):

```
...............                                                          [100%]
15 passed in 0.46s
```

Peek at the file without dumping it:

```bash
python -c '
import json
d = json.load(open("data/winrates.json"))
print(len(d), list(d)[:5])
print(d["Q-K-A"])
'
```

Expected output:

```
455 ['2-2-2', '3-2-2', '4-2-2', '5-2-2', '6-2-2']
{'equity': 0.9969, 'win_rate': 0.9962, 'tie_rate': 0.0015, 'loss_rate': 0.0023, 'category': 'LIENG', 'multiplicity': 64, 'samples': 18424}
```

Watch Monte Carlo converge on K-Q-3:

```bash
python -c '
from src.hands import generate_all_canonical_hands
from src.generator import compute_hand_equity
kq3 = next(h for h in generate_all_canonical_hands() if h.canonical_id == "K-Q-3")
print("exact", compute_hand_equity(kq3)["equity"])
for n in (100, 1000, 10000):
    print(n, compute_hand_equity(kq3, exact=False, samples=n, seed=7)["equity"])
'
```

Expected output:

```
exact 0.36
100 0.405
1000 0.3495
10000 0.3598
```

Regenerate the whole database **into a scratch file** (never over `data/winrates.json`) and
compare it with the committed one. With one worker this took 10 s here; drop `--workers 1` to use
every core.

```bash
python -m src.generator --workers 1 --output /tmp/winrates_check.json && cmp /tmp/winrates_check.json data/winrates.json && echo IDENTICAL
```

Expected output:

```
Starting equity generation in Exact Combinatorial Enumeration across 1 workers...
Successfully generated database for 455 canonical hands -> /tmp/winrates_check.json
IDENTICAL
```

Then look at the permissions of the two files (weak spot 7):

```bash
ls -l data/winrates.json /tmp/winrates_check.json
```

```
-rw-rw-r-- 1 you you 82694 … data/winrates.json
-rw-r--r-- 1 you you 82694 … /tmp/winrates_check.json
```

The first line is whatever git gave the file when you cloned (it depends on your umask). The
second is a new file, so it gets `0644` minus the umask: `-rw-r--r--` with the usual `002` or
`022`, `-rw-------` only if your umask is `077`. Before `a9d9ce9` it was always `-rw-------`.
Regenerating over an existing file keeps that file's mode instead.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** How many of the 18,424 opponent hands beat 2-2-2, the weakest Sáp? What are its
`win_rate` and `loss_rate`?

<details><summary>Solution</summary>

Only a bigger Sáp beats it: 12 ranks (3 to A) × C(4,3) = 4 combos = **48**. Nothing ties (you hold
three of the four 2s). `win_rate = 18,376 / 18,424 = 0.9974`, `loss_rate = 48 / 18,424 = 0.0026`.
Check with `python -c 'import json; print(json.load(open("data/winrates.json"))["2-2-2"])'`.
</details>

**🟢 2. Predict.** What `tie_rate` does 9-9-4 get, and what does
`build_parser().parse_args(["--monte-carlo", "--exact"]).exact` do?

<details><summary>Solution</summary>

9-9-4 is a pair: the opponent needs both remaining 9s and one of three 4s, C(2,2) × 3 = 3 ties,
so `3 / 18,424 = 0.0002`. The parse doesn't return at all: the two flags are mutually exclusive, so
argparse prints `error: argument --exact: not allowed with argument --monte-carlo` and exits with
code 2 (`SystemExit`). Before October 2026 it returned `True`, because the last flag won. Check with
`python -c 'from src.generator import build_parser; print(build_parser().parse_args(["--monte-carlo", "--exact"]).exact)'; echo $?`.
</details>

**🟡 3. Put the skipped hand back.** In
[test_generator.py:66](../backend/tests/test_generator.py#L66) change `"K-J-10"` back to `"10-J-K"`,
the typo the test used to have. Predict what happens now, then run
`python -m pytest tests/test_generator.py -q`.

<details><summary>Solution</summary>

`1 failed, 14 passed`, with `AssertionError: 10-J-K is not a canonical ID` from
[test_generator.py:68](../backend/tests/test_generator.py#L68). Before the fix, the same typo was
skipped by an `if key not in canonical_map: continue`, and the test quietly checked five hands
while claiming six. A test that can silently do less than it says is worse than no test, because it
looks like coverage. Undo with `git checkout -- backend/tests/test_generator.py`.
</details>

**🟡 4. How far does one constant reach?** In [hands.py:34](../backend/src/hands.py#L34) change
`math.comb(52 - 3, 3)` to `math.comb(52, 3)`, a plausible slip. Predict which modules' tests fail and
what Q-K-A's record looks like, then run `python -m pytest -q` and `compute_hand_equity` on Q-K-A.

<details><summary>Solution</summary>

`5 failed, 167 passed`: the constant test in `test_hands.py`, three generator tests
(`test_aaa_exact_equity`, `test_rate_invariants`, `test_monte_carlo_convergence`) and the
calling-range test `test_card_removal_rows_sum_to_18424`, which compares against the same constant
re-exported by `calling_range.py`. Q-K-A becomes
`{'equity': 0.8311, 'win_rate': 0.8305, 'tie_rate': 0.0012, 'loss_rate': 0.0019, …, 'samples': 22100}`:
the loop still counts 18,424 showdowns, but divides by 22,100, so the rates no longer sum to 1. One
definition means one place to get wrong, and the tests that compare it with `math.comb(49, 3)`
catch it immediately. A divisor that cannot disagree with the loop is `wins + ties + losses`. Undo
with `git checkout -- backend/src/hands.py`.
</details>

**🟡 5. Undo the private generator.** In `compute_hand_equity`, replace
`rng = random.Random(seed)` ([generator.py:55](../backend/src/generator.py#L55)) with
`random.seed(seed)` and `rng.sample(…)` ([:84](../backend/src/generator.py#L84)) with
`random.sample(…)`. Predict which tests fail, then run `python -m pytest -q` and this probe:

```bash
python -c '
import random
from src.hands import generate_all_canonical_hands
from src.generator import compute_hand_equity
qka = next(h for h in generate_all_canonical_hands() if h.canonical_id == "Q-K-A")
random.seed(123); a = random.random()
random.seed(123); compute_hand_equity(qka, exact=False, samples=10, seed=1); b = random.random()
print(a == b)
'
```

<details><summary>Solution</summary>

`1 failed, 171 passed`: only `test_seeded_monte_carlo_leaves_global_random_untouched`, and the probe
prints `False` (with the real code it prints `True`). The Monte Carlo numbers themselves don't
change, because `random.Random(7)` and `random.seed(7)` produce the same sequence: the convergence
test still gets 0.9973. The bug is in what the function does to *other* code's random numbers.
Undo with `git checkout -- backend/src/generator.py`.
</details>

**🔴 6. Type the record (weak spot 9).** Replace the four `dict[str, Any]`s in `generator.py`
([:37](../backend/src/generator.py#L37), [:118](../backend/src/generator.py#L118),
[:130](../backend/src/generator.py#L130), [:150](../backend/src/generator.py#L150)) with a
`TypedDict` that lists the seven fields of a record, and drop the `Any` import. Add a test that a
computed record has exactly those fields. Then misspell one key in `compute_hand_equity`'s return
value (say `"winrate"`) and run `python -m mypy` before any test.

<details><summary>Solution</summary>

Below the imports:

```python
class EquityRecord(TypedDict):
    """One record of data/winrates.json: a class's results against all its opponents."""

    equity: float
    win_rate: float
    tie_rate: float
    loss_rate: float
    category: str
    multiplicity: int
    samples: int
```

with `from typing import TypedDict` instead of `Any`; then `compute_hand_equity` returns
`EquityRecord`, `_worker_task` returns `tuple[str, EquityRecord]`, and `generate_winrates_database`
and its `results` use `dict[str, EquityRecord]`. Nothing changes at run time: a `TypedDict` *is* a
plain `dict`, so `json.dump` writes the same bytes. The test, in `tests/test_generator.py` (import
`EquityRecord` next to `compute_hand_equity`):

```python
def test_records_have_exactly_the_typed_fields(canonical_map: dict) -> None:
    record = compute_hand_equity(canonical_map["Q-K-A"])
    assert set(record) == set(EquityRecord.__annotations__)
```

`173 passed`; `ruff check .` prints `All checks passed!` and mypy `Success: no issues found in 12
source files`. With the misspelt key, mypy fails before anything runs:

```
src/generator.py:110: error: Missing key "win_rate" for TypedDict "EquityRecord"  [typeddict-item]
src/generator.py:110: error: Extra key "winrate" for TypedDict "EquityRecord"  [typeddict-unknown-key]
```

(the line number is that of the `return {` once the class is added). With `dict[str, Any]` the same
typo passes mypy and is caught only by the schema test, and only after you regenerate the file. The
schema test could now use `EquityRecord.__annotations__` instead of its own copy of the field names,
so the seven names live in one place. Undo with
`git checkout -- backend/src/generator.py backend/tests/test_generator.py`.
</details>

---

## ❓ Quiz

1. Why is the number of opponent hands 18,424 and not 22,100?
2. Why is it enough to evaluate `Q♠ K♥ A♦` to know the equity of all 64 Q-K-A hands?
3. Why does the parallel version need `_worker_task` defined at module level?
4. A record has `tie_rate: 0.0002`. What kind of hand is it?
5. Why does the file list `"5-2-2"` right before `"6-2-2"`, and why must no code rely on file order?

<details><summary>Answers</summary>

1. You hold 3 of the 52 cards, so the opponent chooses 3 of the remaining 49: C(49, 3) = 18,424.
   22,100 = C(52, 3) counts all hands before anyone is dealt.
2. Strength depends only on ranks. Renaming suits maps one Q-K-A to any other and maps the leftover
   deck one-to-one onto the other leftover deck, so the win, tie and loss counts are identical.
3. The function must be pickled to reach the worker process, and functions pickle by importable
   name. A `lambda` or a nested function has no such name.
4. A pair (5-2-2, K-K-Q …): 3 ties / 18,424. Three distinct ranks give 0.0015, a Sáp 0.0.
5. The order comes from `combinations_with_replacement` over ranks (multiset order), not from hand
   strength. 5-2-2 is 9 points and 6-2-2 is 0 points, so position says nothing about strength.
</details>

---

## Recap

- The generator plays one representative of each of the 455 classes against all 18,424 opponent
  hands: 8,382,920 evaluations, about ten seconds on one core, run once, offline.
- Suit symmetry makes one representative exact, not an approximation.
- `equity = (wins + ½ ties) / 18,424`. Tie rates are 27, 3 or 0 out of 18,424, depending on the
  class shape.
- Monte Carlo is supported but worse here: 10,000 samples cost more than half the exact work and
  are still only accurate to about ±0.005.
- `ProcessPoolExecutor.map` runs tasks in parallel and keeps their order. Its function must be
  module-level, because it is pickled by name.
- `winrates.json` has 455 records with 7 fields, in multiset order. An exact rerun is byte-identical.
- Fixed: exclusive `--exact`/`--monte-carlo`, `OPPONENT_COMBINATIONS` instead of 18,424, a private
  `random.Random`, an absolute default output, an atomic write that keeps the file's permissions and
  cleans up after itself, a test that no longer skips a hand. Still open: rates that sum to 1.0001,
  and a few `Any`s.

**Next:** [05 — The win-rate database](05-win-rate-db.md)
