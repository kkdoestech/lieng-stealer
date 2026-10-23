# Lesson 07 — Expected value: the maths behind "raise or not"

> **Goal:** understand every line of `ev.py`: the EV formula, the break-even fold rate, and why the
> code scans for *zones* of fold rates instead of trusting a single threshold.
> **Files:** [`backend/src/ev.py`](../backend/src/ev.py), [`backend/tests/test_ev.py`](../backend/tests/test_ev.py),
> and the two places that call it in [`backend/app.py`](../backend/app.py#L81-L115).
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
| 2 | [ev.py:14-24](../backend/src/ev.py#L14-L24) | `EVResult`: everything one calculation produces. |
| 3 | [ev.py:27-64](../backend/src/ev.py#L27-L64) | `calculate_ev`: input checks, then three lines of maths. |
| 4 | [ev.py:67-106](../backend/src/ev.py#L67-L106) | `calculate_break_even_fold_equity`: the formula solved for `f`. |
| 5 | [ev.py:109-133](../backend/src/ev.py#L109-L133) | `is_profitable` and `evaluate_action`, which bundle the above. |
| 6 | [ev.py:136-179](../backend/src/ev.py#L136-L179) | `profitable_fold_zones`: a scan over 101 fold rates. |
| 7 | [app.py:81-115](../backend/app.py#L81-L115) | How the API feeds `ev.py` and turns zones into two JSON fields. |
| 8 | [test_ev.py](../backend/tests/test_ev.py) | 13 tests that pin the boundary cases and the K-Q-3 zones. |

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
  AGENTS.md §5.1 writes the general `P + B + C_opp`; the code fixes `C_opp = B`.

### 2. `calculate_ev`: three lines of maths behind four guards

📍 [`backend/src/ev.py:51-64`](../backend/src/ev.py#L51-L64)
```python
    if pot <= 0:
        raise ValueError(f"Pot must be strictly positive, got {pot}.")
    if bet_size <= 0:
        raise ValueError(f"Bet size must be strictly positive, got {bet_size}.")
    if not (0.0 <= fold_equity <= 1.0):
        raise ValueError(f"Fold equity must be between 0.0 and 1.0, got {fold_equity}.")
    if not (0.0 <= win_rate_when_called <= 1.0):
        raise ValueError(f"Win rate when called must be between 0.0 and 1.0, got {win_rate_when_called}.")

    final_pot = pot + 2.0 * bet_size
    showdown_value = (win_rate_when_called * final_pot) - bet_size

    ev = (fold_equity * pot) + (1.0 - fold_equity) * showdown_value
    return round(ev, 4)
```

The guards raise the built-in `ValueError`, not one of the project's `LiengError` types
(lesson 01). The API never reaches them, because `_parse_game_params` in `app.py` rejects bad
input first. Tests and the CLI can reach them.

**Worked example.** This is the default hand in the web UI, Q-K-A, with pot 100,000, bet 50,000,
the opponent folding 35% of the time, and equity 0.9969 against a random hand (from
`winrates.json`, lesson 04):

| Step | Value |
|------|-------|
| `final_pot` = 100,000 + 2 × 50,000 | 200,000 |
| `showdown_value` = 0.9969 × 200,000 − 50,000 | 149,380 |
| fold part = 0.35 × 100,000 | 35,000 |
| showdown part = 0.65 × 149,380 | 97,097 |
| **EV** | **+132,097** |

The UI shows +131,876 for the same hand. The UI defaults to the *range* opponent model, which
gives Q-K-A slightly less equity (0.9952) because the hands that call are stronger (lesson 06).

### 3. Three numbers you can check in your head

| Situation | EV | Pinned by |
|-----------|----|-----------|
| Opponent always folds, `f = 1` | `P` (any `w`) | [test_ev.py:29](../backend/tests/test_ev.py#L29) |
| Never folds, you always win, `f = 0`, `w = 1` | `P + B` | [test_ev.py:36](../backend/tests/test_ev.py#L36) |
| Never folds, you always lose, `f = 0`, `w = 0` | `−B` | [test_ev.py:44](../backend/tests/test_ev.py#L44) |

There is a fourth one hiding in the formula. When `f = 0`, raising pays only if
`w > B / (P + 2B)`. With the default sizes that is `50,000 / 200,000 = 0.25`. These are the
**pot odds**: you need to win more than a quarter of showdowns to profit from a bet nobody folds to.

### 4. Break-even: the same formula, solved for `f`

Set `EV = 0` and solve for `f`. Write `S` for the showdown value:

```
f · P + (1 − f) · S = 0   →   f = −S / (P − S)
```

📍 [`backend/src/ev.py:94-106`](../backend/src/ev.py#L94-L106)
```python
    final_pot = pot + 2.0 * bet_size
    showdown_value = (win_rate_when_called * final_pot) - bet_size

    # If showdown value is already non-negative, zero fold equity is needed
    if showdown_value >= 0.0:
        return 0.0

    denominator = pot - showdown_value
    if denominator <= 0.0:
        return 0.0

    req_fe = -showdown_value / denominator
    return round(min(1.0, max(0.0, req_fe)), 4)
```

- If `S ≥ 0`, you profit even when called, so you need no folds at all: the function returns 0.0.
- Otherwise the answer is `−S / (P − S)`. For a **pure bluff** (`w = 0`, so `S = −B`) this
  simplifies to `B / (P + B)`. A half-pot bet needs `50,000 / 150,000 = 33.3%` folds. A pot-sized
  bet needs 50%.

**Worked example: the junk hand.** 5-3-2 has 0 points and wins only 0.24% of showdowns
(`w = 0.0024`). Then `S = 0.0024 × 200,000 − 50,000 = −49,520`, and
`f = 49,520 / 149,520 = 0.3312`. At the default 35% folds, raising this hand is +2,812 VND:
a profitable bluff, but only just.

### 5. When more folds *cost* you money

You might expect "the more they fold, the better". The test docstring at
[test_ev.py:9](../backend/tests/test_ev.py#L9) even says so. It is wrong for strong hands. The
slope of EV in `f` is `P − S`:

- **Weak hand** (`S < P`): the slope is positive, so folds help. Every fold hands you a pot you
  would probably have lost.
- **Strong hand** (`S > P`): the slope is negative, so folds hurt. A fold costs you a showdown you
  would probably have won.

Q-K-A against a random hand, at the default sizes:

| f | 0 | 0.35 | 1 |
|---|---|------|---|
| EV | 149,380 | 132,097 | 100,000 |

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

📍 [`backend/src/ev.py:162-179`](../backend/src/ev.py#L162-L179)
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
- `is_profitable` is a strict `ev > 0` ([ev.py:109-111](../backend/src/ev.py#L109-L111)), so the
  exact break-even point is never "in". That is why the bluff zone starts at 0.51, not 0.50.

> **Bet size changes the picture.** With the UI's default half-pot bet (`B = 50,000`), K-Q-3 is
> +EV at *every* fold rate: zones `[(0.0, 1.0)]`. At f = 0.35 it is +3,904 rather than −27,894. A
> smaller bet is cheaper to bluff with, since the break-even drops from 50% to 33.3%.

### 7. How the API uses all of this

📍 [`backend/app.py:88-97`](../backend/app.py#L88-L97)
```python
def _evaluate_hand(
    canonical_id: str,
    random_equity: float,
    params: GameParams,
) -> tuple[EVResult, list[tuple[float, float]]]:
    """Return the EV result and the profitable fold-frequency zones."""
    equity_at = _equity_function(canonical_id, random_equity, params.opponent_model)
    ev_res = evaluate_action(params.pot, params.bet_size, params.fold_equity, equity_at(params.fold_equity))
    zones = profitable_fold_zones(params.pot, params.bet_size, equity_at)
    return ev_res, zones
```

`_equity_function` ([app.py:81-85](../backend/app.py#L81-L85)) returns either
`lambda f: calling_model.equity(canonical_id, f)` (range model) or `lambda f: random_equity`
(random model). The same `equity_at` is used once for your actual fold rate, and 101 times for
the zones.

The zones then become two separate JSON fields:

📍 [`backend/app.py:100-115`](../backend/app.py#L100-L115)
```python
def _break_even_fields(
    ev_res: EVResult,
    zones: list[tuple[float, float]],
    model: OpponentModel,
) -> dict[str, float | None]:
    """Describe when raising pays off, with one unambiguous meaning per field.

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under
        RANGE, EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    return {
        "break_even_fold_equity": ev_res.break_even_fold_equity if model is OpponentModel.RANDOM else None,
        "profitable_from_fold_equity": zones[-1][0],
    }
```

For the junk hand 5-3-2 under the random model, the API answers with
`break_even_fold_equity: 0.3312` (exact) and `profitable_from_fold_equity: 0.34` (the grid point).
For K-Q-3 under the range model, `break_even_fold_equity` is `null` and the zones are
`[[0.0, 0.08], [0.51, 1.0]]`. The web UI draws those zones as the green stretches of the
"where raising pays" bar (lesson 13).

`zones[-1]` is safe only because the last zone always ends at `f = 1`: there the EV equals the pot,
which is positive.

### 8. The other caller: the range finder

[range_finder.py:80-87](../backend/src/range_finder.py#L80-L87) calls `calculate_ev` once for each of
the 455 hand classes on every request, then sorts by EV (lesson 08). On the machine this course
was written on, one `calculate_ev` call takes about 0.6 µs, so all 455 cost well under a
millisecond. The zone scan for one hand under the range model took about 0.26 ms, because it asks
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
([test_ev.py:121-128](../backend/tests/test_ev.py#L121-L128)).

## 💡 Concept: `@dataclass(frozen=True)` for results

`EVResult` ([ev.py:14-24](../backend/src/ev.py#L14-L24)) is a frozen dataclass: Python writes
`__init__`, `__repr__` and `__eq__` for you, and assigning to a field afterwards raises
`FrozenInstanceError`. A result that cannot change after it is built can be passed around freely.
This is the AGENTS.md rule "immutable data models" in practice.

---

## Design decisions

- **Pure functions.** No I/O, no globals, no randomness. Every function is a plain mapping from
  numbers to numbers, so the 13 tests need no fixtures and run in under a tenth of a second.
- **Rounding to 4 decimals.** Results are stable in JSON and easy to compare in tests
  (`ev == 72000.0`). The cost is that EV is not exactly 0 at the break-even point (see weak spots).
- **Scan instead of solve.** Under the range model `w(f)` comes from another module and is only
  piecewise smooth. Scanning 101 points is simple, and it is fast enough for every request. The
  cost is a 1% resolution, which README lists as a known limitation.
- **The caller chooses the equity source.** `ev.py` imports nothing from the project, and the
  opponent model is decided in `app.py`, `cli.py` and `range_finder.py`.
- **One betting round, fixed call.** The opponent either folds or calls exactly `B`. There are no
  re-raises or later rounds. This keeps the maths to one line, and it is the model's biggest
  simplification.

---

## ⚠️ Weak spots

1. **A guard that can never trigger.** [ev.py:101-103](../backend/src/ev.py#L101-L103): we only get
   there when `S < 0`, and then `P − S > P > 0`. The `denominator <= 0` branch is dead code. *Fix:*
   delete it, or turn it into an `assert`.
2. **`P + 2B` written in three places.** [ev.py:60](../backend/src/ev.py#L60),
   [:94](../backend/src/ev.py#L94) and [:123](../backend/src/ev.py#L123). It appears more often
   across the backend (`app.py`, `cli.py`). If the call model ever changes (say a call of
   `C_opp ≠ B`), every copy has to change together. *Fix:* one `final_pot(pot, bet)` helper.
3. **A test docstring that states something false.**
   [test_ev.py:9](../backend/tests/test_ev.py#L9) and [:62-63](../backend/tests/test_ev.py#L62-L63)
   say more fold equity always increases EV. The test only checks `w = 0.5`, where it happens to be
   true. Section 5 shows the opposite for strong hands. *Fix:* correct the docstring and add a
   `w = 1` test (exercise 6).
4. **Rounding at the break-even point.** For 5-3-2, EV at `f = 0.3312` is +1.024 rather than 0.
   `test_break_even_fold_equity` therefore allows up to ±5 VND
   ([test_ev.py:86](../backend/tests/test_ev.py#L86)). That is harmless, but worth knowing before
   you write an `== 0` test.
5. **A field that is sometimes meaningless.** `EVResult.break_even_fold_equity` is always
   computed from the current `w`. Under the range model, `w` itself depends on `f`, so the number
   does not mean "break-even". The API hides it (`None`), and so does the CLI ("n/a (range
   model)", [cli.py:136-138](../backend/src/cli.py#L136-L138)). The dataclass still carries it.
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
.............                                                            [100%]
13 passed in 0.09s
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

**🟡 4. Delete the dead guard.** Remove [ev.py:101-103](../backend/src/ev.py#L101-L103) and run
`python -m pytest -q`. Before you run it: will anything fail? Write down the one-line proof.

<details><summary>Solution</summary>

All 93 tests still pass. Proof: we reach line 101 only when `S < 0`, so
`P − S = P + |S| > 0` because `P > 0` was already checked at line 87.
</details>

**🟡 5. Change the grid.** In [app.py:96](../backend/app.py#L96), pass `steps=1000` to
`profitable_fold_zones`. Which tests fail, and what do they tell you about the API contract?

<details><summary>Solution</summary>

K-Q-3's zones become `[(0.0, 0.08), (0.501, 1.0)]`, and 5-3-2's start moves from 0.34 to the first
point above 0.3312. The three assertions that pin grid values fail:
[test_api.py:120](../backend/tests/test_api.py#L120), [:155](../backend/tests/test_api.py#L155)
and [:162](../backend/tests/test_api.py#L162). The 1% resolution is effectively part of the public
API: the UI and the tests both assume it. Changing it is an API change, not an internal tweak.
</details>

**🔴 6. Fix the false claim.** Correct the docstring at [test_ev.py:9](../backend/tests/test_ev.py#L9),
and add a test that shows EV *decreasing* in `f` for an unbeatable hand.

<details><summary>Solution sketch</summary>

```python
def test_folds_hurt_unbeatable_hands(self) -> None:
    """With w = 1 the slope P − S is negative: every fold gives up a won showdown."""
    evs = [calculate_ev(100000.0, 50000.0, f, 1.0) for f in (0.0, 0.5, 1.0)]
    assert evs == [150000.0, 125000.0, 100000.0]
```
</details>

**🔴 7. Generalise the call size.** AGENTS.md §5.1 allows the opponent's call `C_opp` to differ
from `B`. Add an optional `call_amount: float | None = None` parameter to `calculate_ev`
(`None` means "= bet_size"), keep every existing test green, and add two tests of your own.
Which other modules would have to change for the UI to use it?

<details><summary>Hints</summary>

`final_pot = pot + bet_size + call_amount`. In the showdown part you still pay `bet_size`. To
reach the UI it has to go through `calculate_break_even_fold_equity`, `evaluate_action`,
`profitable_fold_zones`, `app.py` (`_parse_game_params` and the copies of `P + 2B`) and the
frontend. This is the cost of weak spot 2.
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
  calls exactly `B`.
- The boundary values `P`, `P + B` and `−B`, and the pot odds `B / (P + 2B)`, are worth knowing by
  heart. The tests pin the first three.
- Break-even is the same formula solved for `f`. A pure bluff needs `B / (P + B)` folds.
- Folds help weak hands and hurt strong ones (slope `P − S`).
- Under the range model EV is not monotonic in `f`. `profitable_fold_zones` scans 101 points and
  can return two zones (K-Q-3).
- `ev.py` is pure and model-agnostic. The caller passes `equity_at`, and the API turns the result
  into `break_even_fold_equity` (exact, random model only) and `profitable_from_fold_equity` (grid).

**Next:** [08 — The range finder](08-range-finder.md)
