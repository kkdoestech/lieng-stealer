# Lesson 07 — Expected value: the maths behind "raise or not"

> **Goal:** understand every line of `ev.py`: the EV formula, the break-even fold rate, and why the
> code scans for *zones* of fold rates instead of trusting a single threshold.
> **Files:** [`backend/src/ev.py`](../backend/src/ev.py), [`backend/tests/test_ev.py`](../backend/tests/test_ev.py),
> and the code that calls it in [`backend/app.py`](../backend/app.py#L282-L327).
> **Time:** ~60 min. **Before this:** [06 — The calling range](06-calling-range.md).

---

## Where this fits

```
  equity when called (w)                     the bet
  ├─ vs a random hand: db.py (lesson 05)     pot P, bet B,
  └─ vs the calling range: calling_range.py  opponent fold rate f
       (lesson 06)                                 │
                └────────────────┬─────────────────┘
                                 ▼
                     ┌──────────────────────┐
                     │  ev.py  (this lesson)│  pure functions, no I/O
                     └──────────────────────┘
                                 │
        ┌────────────────────────┼─────────────────────────┐
        ▼                        ▼                         ▼
  range_finder.py          app.py _evaluate_hand      cli.py
  (455 × calculate_ev)     (your hand + profit zones)  (terminal report)
```

Every other module answers "how strong is this hand?". `ev.py` is the only place that turns that
answer into money. It takes four numbers and returns an expected profit in VND. It never reads a
file, never looks at a card and never prints, which is why it is the easiest module to test and
the best one to understand first in full.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [ev.py:1-6](../backend/src/ev.py#L1-L6) | The formula, written once in the module docstring. |
| 2 | [ev.py:15-18](../backend/src/ev.py#L15-L18) | The default pot, bet and fold rate that the CLI and the API share. |
| 3 | [ev.py:21-36](../backend/src/ev.py#L21-L36) | `EVResult`: everything one calculation produces, and `final_pot()`: the one place that writes `P + 2B`. |
| 4 | [ev.py:39-78](../backend/src/ev.py#L39-L78) | `calculate_ev`: input checks, then two lines of maths. |
| 5 | [ev.py:81-121](../backend/src/ev.py#L81-L121) | `calculate_break_even_fold_equity`: the formula solved for `f`. |
| 6 | [ev.py:124-147](../backend/src/ev.py#L124-L147) | `is_profitable` and `evaluate_action`, which bundle the above. |
| 7 | [ev.py:150-194](../backend/src/ev.py#L150-L194) | `profitable_fold_zones`: a scan over 101 fold rates. |
| 8 | [app.py:282-327](../backend/app.py#L282-L327) | How the API feeds `ev.py` (`_equity_function`, `_evaluate_hand`) and turns zones into two JSON fields (`_hand_payload`). |
| 9 | [test_ev.py](../backend/tests/test_ev.py) | 15 tests that pin the boundary cases, the K-Q-3 zones and the strong-hand slope. |

---

## Walkthrough

### 1. The decision as a tree

When you raise by `B` into a pot of `P`, one of three things happens:

```
                 you raise B
                     │
        ┌────────────┴─────────────┐
   opponent folds (f)        opponent calls (1 − f)
   you win P                 cards are shown; final pot = P + 2B
                              ┌──────────┴──────────┐
                         you win (w)            you lose (1 − w)
                         + (P + B)              − B
```

The **expected value** is the average result if you could make this exact decision many times:

```
EV = f · P  +  (1 − f) · [ w · (P + 2B) − B ]
     ─────     ───────────────────────────────
     fold part          showdown part
```

The showdown part is the bracket: you collect the final pot `w` of the time, and you always paid
`B` to get there. That is the same as `w · (P + B) − (1 − w) · B`, which is how the tree reads.

Two choices are built into this formula. Both matter later:

- **The baseline is "give up" = 0.** EV is profit compared with *not* raising and losing the pot.
  That is why winning the dead pot `P` counts as profit.
- **The opponent calls exactly `B`.** There is no re-raise, so the final pot is always `P + 2B`.
  AGENTS.md §5.1 writes the general `P + B + C_opp`; the code fixes `C_opp = B`, in one helper:

📍 [`backend/src/ev.py:34-36`](../backend/src/ev.py#L34-L36)
```python
def final_pot(pot: float, bet_size: float) -> float:
    """Pot after Hero bets and the opponent calls the same amount: P + 2B (AGENTS.md: C_opp = B)."""
    return pot + 2.0 * bet_size
```

Every function in `ev.py` calls `final_pot()`, and so do the API's range summary
([app.py:339](../backend/app.py#L339)) and the CLI report ([cli.py:100](../backend/src/cli.py#L100)).
If the call model ever changes, this is the line to change.

### 2. `calculate_ev`: two lines of maths behind four guards

📍 [`backend/src/ev.py:64-78`](../backend/src/ev.py#L64-L78)
```python
    if pot <= 0:
        raise InvalidGameParamsError(f"Pot must be strictly positive, got {pot}.")
    if bet_size <= 0:
        raise InvalidGameParamsError(f"Bet size must be strictly positive, got {bet_size}.")
    if not (0.0 <= fold_equity <= 1.0):
        raise InvalidGameParamsError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
    if not (0.0 <= win_rate_when_called <= 1.0):
        raise InvalidGameParamsError(
            f"Win rate when called must be between 0.0 and 1.0, got {win_rate_when_called}."
        )

    showdown_value = (win_rate_when_called * final_pot(pot, bet_size)) - bet_size

    ev = (fold_equity * pot) + (1.0 - fold_equity) * showdown_value
    return round(ev, 4)
```

The guards raise `InvalidGameParamsError`, the project's error for bad numbers (lesson 01). It
derives from both `LiengError` and the built-in `ValueError`
([exceptions.py:25-26](../backend/src/exceptions.py#L25-L26)), so code that catches either one
works. The API rarely reaches these guards, because `_parse_game_params`
([app.py:236-259](../backend/app.py#L236-L259)) rejects bad input first with the same error type,
which the API turns into a `400 invalid_params` answer (lesson 10). Tests and the CLI can reach them.

**Worked example.** This is the default hand in the web UI, Q-K-A, with pot 100,000, bet 50,000,
the opponent folding 35% of the time, and equity 0.9969 against a random hand (from
`winrates.json`, lesson 04). The three game numbers are also `DEFAULT_POT`, `DEFAULT_BET_SIZE` and
`DEFAULT_FOLD_EQUITY` ([ev.py:15-18](../backend/src/ev.py#L15-L18)), which the API and the CLI use
when you leave a value out:

| Step | Value |
|------|-------|
| `final_pot(100,000, 50,000)` = 100,000 + 2 × 50,000 | 200,000 |
| `showdown_value` = 0.9969 × 200,000 − 50,000 | 149,380 |
| fold part = 0.35 × 100,000 | 35,000 |
| showdown part = 0.65 × 149,380 | 97,097 |
| **EV** | **+132,097** |

The UI shows +131,876 for the same hand. The UI defaults to the *range* opponent model, which
gives Q-K-A slightly less equity (0.9952) because the hands that call are stronger (lesson 06).

### 3. Three numbers you can check in your head

| Situation | EV | Pinned by |
|-----------|----|-----------|
| Opponent always folds, `f = 1` | `P` (any `w`) | [test_ev.py:30](../backend/tests/test_ev.py#L30) |
| Never folds, you always win, `f = 0`, `w = 1` | `P + B` | [test_ev.py:37](../backend/tests/test_ev.py#L37) |
| Never folds, you always lose, `f = 0`, `w = 0` | `−B` | [test_ev.py:45](../backend/tests/test_ev.py#L45) |

There is a fourth one hiding in the formula. When `f = 0`, raising pays only if
`w > B / (P + 2B)`. With the default sizes that is `50,000 / 200,000 = 0.25`. These are the
**pot odds**: you need to win more than a quarter of showdowns to profit from a bet nobody folds to.

### 4. Break-even: the same formula, solved for `f`

Set `EV = 0` and solve for `f`. Write `S` for the showdown value:

```
f · P + (1 − f) · S = 0   →   f = −S / (P − S)
```

📍 [`backend/src/ev.py:113-121`](../backend/src/ev.py#L113-L121)
```python
    showdown_value = (win_rate_when_called * final_pot(pot, bet_size)) - bet_size

    # If showdown value is already non-negative, zero fold equity is needed
    if showdown_value >= 0.0:
        return 0.0

    # Here showdown_value < 0 and pot > 0, so the denominator pot - showdown_value is positive.
    req_fe = -showdown_value / (pot - showdown_value)
    return round(min(1.0, max(0.0, req_fe)), 4)
```

- If `S ≥ 0`, you profit even when called, so you need no folds at all: the function returns 0.0.
- Otherwise the answer is `−S / (P − S)`. The comment on line 119 is the proof that the division is
  safe: `S < 0` and `P > 0`, so `P − S > 0`. (An older version guarded it with an
  `if denominator <= 0` branch that could never run; see weak spot 1.)
- For a **pure bluff** (`w = 0`, so `S = −B`) this
  simplifies to `B / (P + B)`. A half-pot bet needs `50,000 / 150,000 = 33.3%` folds. A pot-sized
  bet needs 50%.

**Worked example: the junk hand.** 5-3-2 has 0 points and wins only 0.24% of showdowns
(`w = 0.0024`). Then `S = 0.0024 × 200,000 − 50,000 = −49,520`, and
`f = 49,520 / 149,520 = 0.3312`. At the default 35% folds, raising this hand is +2,812 VND:
a profitable bluff, but only just.

### 5. When more folds *cost* you money

You might expect "the more they fold, the better". The test file used to say exactly that in its
docstring. It is wrong for strong hands, and the docstring now says so
([test_ev.py:9-10](../backend/tests/test_ev.py#L9-L10)). The slope of EV in `f` is `P − S`:

- **Weak hand** (`S < P`): the slope is positive, so folds help. Every fold hands you a pot you
  would probably have lost.
- **Strong hand** (`S > P`): the slope is negative, so folds hurt. A fold costs you a showdown you
  would probably have won.

Q-K-A against a random hand, at the default sizes:

| f | 0 | 0.35 | 1 |
|---|---|------|---|
| EV | 149,380 | 132,097 | 100,000 |

`TestStrongHands.test_folds_hurt_unbeatable_hands`
([test_ev.py:149-152](../backend/tests/test_ev.py#L149-L152)) pins the extreme case, `w = 1`:
the EV falls from 150,000 to 125,000 to 100,000 as `f` goes 0 → 0.5 → 1.

That is why "how often will they fold?" matters for every hand, not only for bluffs.

### 6. `profitable_fold_zones`: why one threshold is not enough

Under the **random** opponent model `w` is a constant, so EV is a straight line in `f` and one
break-even number describes everything. Under the **range** model (lesson 06) the opponent folds
their *weakest* hands. As `f` rises, the hands that still call get stronger, and your `w` falls.
EV is no longer a straight line.

Take K-Q-3 (3 points) with a pot-sized bet (`P = B = 100,000`). Each `w` comes from
`CallingRangeModel.equity("K-Q-3", f)`:

| f | 0.00 | 0.05 | 0.08 | 0.09 | 0.10 | 0.20 | 0.35 | 0.50 | 0.51 | 1.00 |
|---|------|------|------|------|------|------|------|------|------|------|
| w | 0.3600 | 0.3238 | 0.3047 | 0.2960 | 0.2883 | 0.1976 | 0.0108 | 0 | 0 | 0 |
| EV | +8,000 | +2,283 | +97.2 | −1,192 | −2,159 | −12,576 | −27,894 | 0 | +2,000 | +100,000 |

There are two profitable stretches: against loose callers (f ≤ 8%) the hand wins enough
showdowns, and above 50% it is a pure bluff that folds alone pay for. In between it loses. No single
threshold can say that, so the code scans:

📍 [`backend/src/ev.py:177-194`](../backend/src/ev.py#L177-L194)
```python
    if steps < 1:
        raise ValueError(f"Steps must be at least 1, got {steps}.")

    zones: list[tuple[float, float]] = []
    start: float | None = None
    last = 0.0
    for i in range(steps + 1):
        f = i / steps
        if is_profitable(calculate_ev(pot, bet_size, f, equity_at(f))):
            if start is None:
                start = f
            last = f
        elif start is not None:
            zones.append((start, last))
            start = None
    if start is not None:
        zones.append((start, last))
    return zones
```

- `equity_at` is a **function**, not a number. The caller decides where `w` comes from (see the
  concept box below). `ev.py` stays independent of both opponent models.
- With `steps = 100` it tests 101 fold rates, 0.00 to 1.00, and records each run of +EV points as
  a closed `(start, end)` pair. For K-Q-3 above: `[(0.0, 0.08), (0.51, 1.0)]`.
- `is_profitable` is a strict `ev > 0` ([ev.py:124-126](../backend/src/ev.py#L124-L126)), so the
  exact break-even point is never "in". That is why the bluff zone starts at 0.51, not 0.50.

> **Bet size changes the picture.** With the UI's default half-pot bet (`B = 50,000`), K-Q-3 is
> +EV at *every* fold rate: zones `[(0.0, 1.0)]`. At f = 0.35 it is +3,904 rather than −27,894. A
> smaller bet is cheaper to bluff with, since the break-even drops from 50% to 33.3%.

### 7. How the API uses all of this

📍 [`backend/app.py:291-298`](../backend/app.py#L291-L298)
```python
def _evaluate_hand(services: Services, hand: Hand, params: GameParams) -> HandResult:
    """Evaluate one hand: EV at the given fold rate and the zones where raising is +EV."""
    canonical = to_canonical(hand.cards)
    stats = services.db.get(canonical.canonical_id)
    equity_at = _equity_function(services, canonical.canonical_id, stats.equity, params.opponent_model)
    ev_res = evaluate_action(params.pot, params.bet_size, params.fold_equity, equity_at(params.fold_equity))
    zones = profitable_fold_zones(params.pot, params.bet_size, equity_at)
    return HandResult(hand, canonical, stats, ev_res, zones)
```

`_equity_function` ([app.py:282-288](../backend/app.py#L282-L288)) returns either
`lambda f: services.calling_model.equity(canonical_id, f)` (range model) or
`lambda f: random_equity` (random model). The same `equity_at` is used once for your actual fold
rate, and 101 times for the zones. Everything lands in one frozen `HandResult`
([app.py:82-89](../backend/app.py#L82-L89)): the hand, its class, its database row, the `EVResult`
and the zones. `services` is the app's own database and calling-range model (lesson 10).

`_hand_payload` then turns a `HandResult` into the JSON that both `/api/solve` and `/api/evaluate`
send. The zones become two separate fields:

📍 [`backend/app.py:305-327`](../backend/app.py#L305-L327)
```python
def _hand_payload(result: HandResult, model: OpponentModel) -> Json:
    """The hand-evaluation fields, identical in /api/solve and /api/evaluate.

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under RANGE,
        EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    return {
        "hand": str(result.hand),
        "score_name": str(result.hand.score),
        "category": result.stats.category.name,
        "category_name": result.stats.category.display_name,
        "canonical_id": result.canonical.canonical_id,
        "showdown_equity": result.ev.win_rate_when_called,
        "equity_vs_random": result.stats.equity,
        "ev": result.ev.ev,
        "break_even_fold_equity": result.ev.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": result.zones[-1][0],
        "profitable_fold_zones": [[start, end] for start, end in result.zones],
        "is_profitable": result.ev.is_profitable,
        "decision": _decision(result.ev.is_profitable),
    }
```

- `showdown_equity` is the `w` that went into the EV (it depends on the opponent model), while
  `equity_vs_random` is always the database number. Under the random model they are equal.
- `break_even_fold_equity` comes straight from `EVResult`, but only under the random model.
- `profitable_from_fold_equity` is the start of the *last* zone.
- `decision` is `"RAISE"` when `is_profitable`, otherwise `"CHECK/FOLD"`
  ([app.py:301-302](../backend/app.py#L301-L302)).

For the junk hand 5-3-2 under the random model, the API answers with
`break_even_fold_equity: 0.3312` (exact) and `profitable_from_fold_equity: 0.34` (the grid point).
For K-Q-3 under the range model, `break_even_fold_equity` is `null` and the zones are
`[[0.0, 0.08], [0.51, 1.0]]`. The web UI draws those zones as the green stretches of the
"where raising pays" bar (lesson 13).

`result.zones[-1]` is safe only because the last zone always ends at `f = 1`: there the EV equals
the pot, which is positive.

`ev.py` has one more caller in the API. `_solve_range` puts `final_pot()` and the pure-bluff
break-even `calculate_break_even_fold_equity(pot, bet_size, 0.0)` into every range summary
([app.py:339-340](../backend/app.py#L339-L340)): at the default sizes, `final_pot: 200000.0` and
`pure_bluff_break_even_fold_equity: 0.3333`.

### 8. The other caller: the range finder

[range_finder.py:84-91](../backend/src/range_finder.py#L84-L91) calls `calculate_ev` once for each of
the 455 hand classes on every request, then sorts by EV (lesson 08). On the machine this course
was written on, one `calculate_ev` call takes about 0.5 µs, so all 455 cost well under a
millisecond. The zone scan for one hand under the range model took about 0.2 ms, because it asks
the calling-range model for 101 equities.

---

## 💡 Concept: passing a function as an argument

`profitable_fold_zones` takes `equity_at: Callable[[float], float]`, meaning "something you can
call with a float that returns a float". A `lambda` is the shortest way to make one:

```python
equity_at = lambda f: 0.36            # constant: random model
equity_at = lambda f: model.equity("K-Q-3", f)   # changes with f: range model
equity_at(0.35)                       # call it like any function
```

This keeps `ev.py` free of any knowledge about opponent models. The tests use it too:
`lambda f: 0.0` is a perfect pure bluff, and `lambda f: 1.0` is an unbeatable hand
([test_ev.py:122-129](../backend/tests/test_ev.py#L122-L129)).

## 💡 Concept: `@dataclass(frozen=True)` for results

`EVResult` ([ev.py:21-31](../backend/src/ev.py#L21-L31)) is a frozen dataclass: Python writes
`__init__`, `__repr__` and `__eq__` for you, and assigning to a field afterwards raises
`FrozenInstanceError`. A result that cannot change after it is built can be passed around freely.
This is the AGENTS.md rule "immutable data models" in practice.

---

## Design decisions

- **Pure functions.** No I/O, no globals, no randomness. Every function is a plain mapping from
  numbers to numbers, so the 15 tests need no fixtures and run in under a tenth of a second.
- **Rounding to 4 decimals.** Results are stable in JSON and easy to compare in tests
  (`ev == 72000.0`). The cost is that EV is not exactly 0 at the break-even point (see weak spots).
- **Scan instead of solve.** Under the range model `w(f)` comes from another module and is only
  piecewise smooth. Scanning 101 points is simple, and it is fast enough for every request. The
  cost is a 1% resolution, which README lists as a known limitation.
- **The caller chooses the equity source.** The only project module `ev.py` imports is
  `exceptions.py`. It knows nothing about cards or opponent models: those are decided in `app.py`,
  `cli.py` and `range_finder.py`.
- **One helper for the call model.** `final_pot()` is the single place that says "the opponent
  calls exactly `B`". The defaults live next to it, so the CLI and the API cannot drift apart.
- **One betting round, fixed call.** The opponent either folds or calls exactly `B`. There are no
  re-raises or later rounds. This keeps the maths to one line, and it is the model's biggest
  simplification.

---

## ⚠️ Weak spots

1. ✅ **Fixed: a guard that could never trigger.** `calculate_break_even_fold_equity` used to end
   with `if denominator <= 0: return 0.0`. It was reached only when `S < 0`, and then
   `P − S > P > 0`, so the branch was dead code. It is gone; the one-line proof is now a comment
   ([ev.py:119-120](../backend/src/ev.py#L119-L120)). Unreachable code has no behaviour to pin, so
   there is no new test: the break-even tests
   ([test_ev.py:76-96](../backend/tests/test_ev.py#L76-L96)) pass unchanged, which is the point.
2. ✅ **Fixed: `P + 2B` written in three places.** `calculate_ev`, `calculate_break_even_fold_equity`
   and `evaluate_action` each wrote `pot + 2.0 * bet_size`, and `app.py` and `cli.py` had their own
   copies. Now every one of them calls `final_pot()` ([ev.py:34-36](../backend/src/ev.py#L34-L36)).
   Pinned by `test_final_pot_is_pot_plus_two_bets`
   ([test_ev.py:154-157](../backend/tests/test_ev.py#L154-L157)), and by every boundary test that
   depends on the final pot (exercise 4 breaks it on purpose).
3. ✅ **Fixed: a test docstring that stated something false.** The module docstring said that more
   fold equity always increases EV; the test only checked `w = 0.5`, where it happens to be true.
   The docstrings now limit the claim to hands whose showdown value is below the pot
   ([test_ev.py:9-10](../backend/tests/test_ev.py#L9-L10), [:64](../backend/tests/test_ev.py#L64)),
   and `test_folds_hurt_unbeatable_hands`
   ([test_ev.py:149-152](../backend/tests/test_ev.py#L149-L152)) pins the opposite case.
4. **Rounding at the break-even point.** For 5-3-2, EV at `f = 0.3312` is +1.024 rather than 0.
   `test_break_even_fold_equity` therefore allows up to ±5 VND
   ([test_ev.py:87](../backend/tests/test_ev.py#L87)). That is harmless, but worth knowing before
   you write an `== 0` test.
5. **A field that is sometimes meaningless.** `EVResult.break_even_fold_equity` is always
   computed from the current `w`. Under the range model, `w` itself depends on `f`, so the number
   does not mean "break-even". The API hides it (`None`), and so does the CLI ("n/a (range
   model)", [cli.py:166-169](../backend/src/cli.py#L166-L169)). The dataclass still carries it
   (exercise 6).
6. **Modelling limits, not bugs.** One betting round, a fixed call size, and `f` is a number you
   guess. The output is exactly as good as that guess.

---

## 🧪 Try it

Run from `backend/` with the virtual environment active (see [COURSE.md](COURSE.md#setup)).

```bash
python -m pytest tests/test_ev.py -q
```

Expected output (the timing varies):

```
...............                                                          [100%]
15 passed in 0.09s
```

Reproduce the K-Q-3 table and its zones:

```bash
python -c '
from src.ev import calculate_ev, profitable_fold_zones
from src.calling_range import CallingRangeModel
m = CallingRangeModel()
for f in (0.0, 0.08, 0.09, 0.35, 0.51):
    print(f, calculate_ev(100000, 100000, f, m.equity("K-Q-3", f)))
print(profitable_fold_zones(100000.0, 100000.0, lambda f: m.equity("K-Q-3", f)))
'
```

Expected output:

```
0.0 8000.0
0.08 97.2
0.09 -1192.0
0.35 -27894.0
0.51 2000.0
[(0.0, 0.08), (0.51, 1.0)]
```

See both break-even fields through the real API, without starting a server:

```bash
python -c '
from app import app
c = app.test_client()
r = c.post("/api/solve", json={"pot": 100000, "bet_size": 50000, "fold_equity": 0.35,
                               "hand": "2s 3h 5d", "opponent_model": "random"}).get_json()
e = r["hand_evaluation"]
print(e["ev"], e["break_even_fold_equity"], e["profitable_from_fold_equity"], e["profitable_fold_zones"])
'
```

Expected output:

```
2812.0 0.3312 0.34 [[0.34, 1.0]]
```

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** Pot 200,000, bet 100,000, the opponent folds half the time, and your equity when
called is 0.4. What is the EV? Work it out on paper, then check with `calculate_ev`.

<details><summary>Solution</summary>

`final_pot = 400,000`; `S = 0.4 × 400,000 − 100,000 = 60,000`;
`EV = 0.5 × 200,000 + 0.5 × 60,000 = 130,000`.
`python -c "from src.ev import calculate_ev; print(calculate_ev(200000, 100000, 0.5, 0.4))"`
prints `130000.0`.
</details>

**🟢 2. Predict.** You shove all-in for three times the pot with pure air (`w = 0`). How often must
the opponent fold for that to break even?

<details><summary>Solution</summary>

`B / (P + B) = 3P / 4P = 0.75`.
`calculate_break_even_fold_equity(100000, 300000, 0.0)` returns `0.75`. Big bluffs need many folds.
</details>

**🟢 3. Predict.** At `P = 100,000`, `B = 50,000`, `f = 0`, a hand has exactly `w = 0.25`. What
does the UI recommend, and why?

<details><summary>Solution</summary>

`EV = 0.25 × 200,000 − 50,000 = 0.0`. `is_profitable` is a strict `> 0`, so the decision is
CHECK/FOLD. A hand exactly at its pot odds is not worth raising.
</details>

**🟡 4. Break the helper on purpose.** Weak spot 2 was fixed by moving `P + 2B` into `final_pot()`.
Make the classic mistake of forgetting the call: change [ev.py:36](../backend/src/ev.py#L36) to
`return pot + bet_size`. Before you run `python -m pytest tests/test_ev.py -q`, predict which of the
15 tests fail and which still pass.

<details><summary>Solution</summary>

Six fail, nine pass:

```
FAILED tests/test_ev.py::TestEVEngine::test_boundary_zero_fold_nuts - assert ...
FAILED tests/test_ev.py::TestEVEngine::test_bluff_profitability - assert 7150...
FAILED tests/test_ev.py::TestEVEngine::test_evaluate_action_helper - assert 1...
FAILED tests/test_ev.py::TestProfitableFoldZones::test_medium_hand_has_two_zones_against_calling_range
FAILED tests/test_ev.py::TestStrongHands::test_folds_hurt_unbeatable_hands - ...
FAILED tests/test_ev.py::TestStrongHands::test_final_pot_is_pot_plus_two_bets
6 failed, 9 passed in 0.17s
```

The survivors are the cases where the final pot drops out of the formula: `f = 1` (no showdown),
`w = 0` (you collect nothing, so `S = −B` whatever the pot), the validation tests, and the two
break-even tests (the threshold moves, but EV is still about 0 there, and `w = 0.8` still profits
at showdown). Because
all three functions share the helper, one wrong line breaks EV, `EVResult.final_pot` and the zones
together. Before the fix, the same typo in one copy would have broken only one of them. Undo it
with `git checkout -- backend/src/ev.py`.
</details>

**🟡 5. Change the grid.** In [app.py:297](../backend/app.py#L297), pass `steps=1000` to
`profitable_fold_zones`. Which tests fail, and what do they tell you about the API contract?

<details><summary>Solution</summary>

K-Q-3's zones become `[(0.0, 0.08), (0.501, 1.0)]`, and 5-3-2's start moves from 0.34 to the first
point above 0.3312. The three assertions that pin grid values fail:
[test_api.py:136](../backend/tests/test_api.py#L136), [:160](../backend/tests/test_api.py#L160)
and [:205](../backend/tests/test_api.py#L205). The 1% resolution is effectively part of the public
API: the UI and the tests both assume it. Changing it is an API change, not an internal tweak.
</details>

**🔴 6. Close weak spot 5.** `EVResult.break_even_fold_equity` is meaningless under the range
model, and two callers have to remember to hide it. Make the dataclass say so itself: give
`evaluate_action` a keyword argument `equity_depends_on_fold: bool = False`, store
`break_even_fold_equity: float | None`, and set it to `None` when the flag is true. Update the
callers in `app.py` and `cli.py`, keep every test green, and add one test of your own.

<details><summary>Solution sketch</summary>

```python
def evaluate_action(pot, bet_size, fold_equity, win_rate_when_called, *,
                    equity_depends_on_fold: bool = False) -> EVResult:
    ev = calculate_ev(pot, bet_size, fold_equity, win_rate_when_called)
    be_fe = None if equity_depends_on_fold else calculate_break_even_fold_equity(
        pot, bet_size, win_rate_when_called)
    ...
```

In `_evaluate_hand`, pass `equity_depends_on_fold=params.opponent_model is OpponentModel.RANGE`;
then `_hand_payload` can send `result.ev.break_even_fold_equity` as it is, without the `if model`
test. In `cli.py`, pass `calling_model is not None` and print "n/a (range model)" when the field is
`None`. `mypy` will point at every place that formats the field as a number. A test:

```python
def test_no_break_even_when_equity_depends_on_fold(self) -> None:
    res = evaluate_action(100000.0, 50000.0, 0.35, 0.3, equity_depends_on_fold=True)
    assert res.break_even_fold_equity is None
```
</details>

**🔴 7. Generalise the call size.** AGENTS.md §5.1 allows the opponent's call `C_opp` to differ
from `B`. Add an optional `call_amount: float | None = None` parameter to `calculate_ev`
(`None` means "= bet_size"), keep every existing test green, and add two tests of your own.
Which other modules would have to change for the UI to use it?

<details><summary>Hints</summary>

`final_pot(pot, bet_size, call_amount)` returns `pot + bet_size + call_amount`. In the showdown part
you still pay `bet_size`. Because of the fix for weak spot 2, the pot side is one helper instead of
a copy in every module. The new value still has to travel: through `calculate_break_even_fold_equity`,
`evaluate_action` and `profitable_fold_zones`, `range_finder.py`, `app.py` (`GameParams`,
`_parse_game_params`, `_solve_range`), `cli.py` and the frontend. One helper fixes the formula,
but it does not shorten that path.
</details>

---

## ❓ Quiz

1. Why is EV exactly `P` when `f = 1`, whatever your hand?
2. Why is the final pot `P + 2B` rather than `P + B`?
3. Under the random model, how many profitable zones can a hand have at most? Why?
4. Why does `/api/solve` return `break_even_fold_equity: null` under the range model?
5. A pure bluff with a pot-sized bet breaks even at exactly 50% folds. Why does
   `profitable_from_fold_equity` say 0.51?

<details><summary>Answers</summary>

1. If everyone folds there is no showdown: you take the dead pot, and the `(1 − f)` term is 0.
2. You put in `B`, and the opponent calls with `B`. The code assumes the call matches the bet.
3. One. `w` is constant, so EV is a straight line in `f`. A line crosses zero at most once, so the
   +EV part is a single interval (or empty, or everything).
4. Under the range model `w` depends on `f`, so EV can go up, down and up again (K-Q-3). A single
   break-even number would be misleading, so the API returns `null` and sends the zones instead.
5. Two reasons together: the scan only tests grid points 0.00, 0.01, …, 1.00, and
   `is_profitable` is a strict `> 0`, so EV = 0 at 0.50 does not count.
</details>

---

## Recap

- `EV = f·P + (1 − f)·[w·(P + 2B) − B]`, measured against giving up. The code assumes the opponent
  calls exactly `B`, and says so in one place: `final_pot()`.
- The boundary values `P`, `P + B` and `−B`, and the pot odds `B / (P + 2B)`, are worth knowing by
  heart. The tests pin the first three.
- Break-even is the same formula solved for `f`. A pure bluff needs `B / (P + B)` folds.
- Folds help weak hands and hurt strong ones (slope `P − S`).
- Under the range model EV is not monotonic in `f`. `profitable_fold_zones` scans 101 points and
  can return two zones (K-Q-3).
- `ev.py` is pure and model-agnostic. The caller passes `equity_at`, and the API turns the result
  into `break_even_fold_equity` (exact, random model only) and `profitable_from_fold_equity` (grid).

**Next:** [08 — The range finder](08-range-finder.md)
