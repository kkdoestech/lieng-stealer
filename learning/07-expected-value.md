# Lesson 07 — Expected value: the maths behind "which size"

> **Goal:** understand every line of `ev.py`: the EV formula, the break-even fold rate, why the code
> scans for *zones* of fold rates instead of trusting a single threshold, and how `advice.py` turns
> those numbers into one of three bet sizes.
> **Files:** [`backend/src/ev.py`](../backend/src/ev.py), [`backend/tests/test_ev.py`](../backend/tests/test_ev.py),
> [`backend/src/advice.py`](../backend/src/advice.py), [`backend/tests/test_advice.py`](../backend/tests/test_advice.py),
> and the code that calls them in [`backend/app.py`](../backend/app.py#L427-L542).
> **Time:** ~70 min. **Before this:** [06 — The calling range](06-calling-range.md).

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
  range_finder.py          advice.py                app.py / cli.py
  (455 × calculate_ev)     (EV → one of three sizes) (your hand + report)
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
| 8 | [advice.py:259-316](../backend/src/advice.py#L259-L316) | `recommend`: the three rung amounts, their EV in the centre cell and in the worst stress cell, and the walk down. |
| 9 | [advice.py:366-389](../backend/src/advice.py#L366-L389) | `_blocker`: why one rung is refused, in the order the policy checks it. |
| 10 | [app.py:427-469](../backend/app.py#L427-L469) | How the API turns a solution into JSON: the zones, the two break-even fields and the advice object. |
| 11 | [test_ev.py](../backend/tests/test_ev.py) | 19 tests that pin the boundary cases, the K-Q-3 zones and the strong-hand slope. |
| 12 | [test_advice.py](../backend/tests/test_advice.py) | 32 tests that pin the ladder, the floor, the band edges and the bluff cap from literal numbers. |

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

📍 [`backend/src/ev.py:35-37`](../backend/src/ev.py#L35-L37)
```python
def final_pot(pot: float, bet_size: float) -> float:
    """Pot after Hero bets and the opponent calls the same amount: P + 2B (AGENTS.md: C_opp = B)."""
    return pot + 2.0 * bet_size
```

Every function in `ev.py` calls `final_pot()`, and so do the API's range summary
([app.py:359](../backend/app.py#L359)) and the CLI report ([cli.py:102](../backend/src/cli.py#L102)).
If the call model ever changes, this is the line to change.

### 2. `calculate_ev`: two lines of maths behind four guards

📍 [`backend/src/ev.py:67-81`](../backend/src/ev.py#L67-L81)
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
    return ev
```

The guards raise `InvalidGameParamsError`, the project's error for bad numbers (lesson 01). It
derives from both `LiengError` and the built-in `ValueError`
([exceptions.py:25-26](../backend/src/exceptions.py#L25-L26)), so code that catches either one
works. The API rarely reaches these guards, because `_parse_game_params`
([app.py:256-279](../backend/app.py#L256-L279)) rejects bad input first with the same error type,
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

The default request uses the *range* opponent model, which gives Q-K-A slightly less equity (0.9952)
because the hands that call are stronger (lesson 06), so the API and the CLI answer +131,876 for the
same hand. The table above is the uniform model, which `"opponent_model": "random"` still selects.

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

📍 [`backend/src/ev.py:118-126`](../backend/src/ev.py#L118-L126)
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

📍 [`backend/src/ev.py:182-199`](../backend/src/ev.py#L182-L199)
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

📍 [`backend/app.py:520-535`](../backend/app.py#L520-L535)
```python
def _evaluate_hand(
    services: Services,
    hand: Hand,
    params: GameParams,
    equities: OpponentEquities,
    records: Sequence[HandEVRecord],
) -> tuple[HandSolution, Sensitivity]:
    solution = services.range_finder.hand_solution(hand, records, equities, params.pot, params.bet_size)
    sensitivity = stress_test(
        equities,
        services.calling_model,
        solution.record.canonical_id,
        params.pot,
        params.bet_size,
    )
    return solution, sensitivity
```

`_evaluate_hand` above is the whole bridge from the table to JSON. The `equity_at` function that
`profitable_fold_zones` scans comes from `RangeFinder._equity_scan`
([range_finder.py:270-278](../backend/src/range_finder.py#L270-L278)): under the range model it is
`lambda f: model.equity(canonical_id, f)`, under the random model a constant. The same source answers
your own fold rate once, through `hand_solution`, and the three advice cells through `stress_test`.
`services` is the app's own database, calling-range model and thresholds (lesson 10).

`_hand_payload` then turns a `HandSolution` into the JSON that both `/api/solve` and `/api/evaluate`
send. The zones become two separate fields, and the advice rides along:

📍 [`backend/app.py:424-465`](../backend/app.py#L424-L465)
```python
def _hand_payload(
    solution: HandSolution,
    stats: HandStats,
    equities: OpponentEquities,
    sensitivity: Sensitivity | None,
    params: GameParams,
) -> Json:
    """The hand-evaluation fields, identical in /api/solve and /api/evaluate.

    ``showdown_equity``, ``ev`` and ``advice`` come from the 455-class table row. ``ev`` stays the EV
    at the caller's ``bet_size``; ``advice.ev`` is the EV of the size the policy recommends.
    ``call_range_percent`` is derived from ``fold_equity`` (null under the random model).

    break_even_fold_equity: exact fold frequency where EV = 0 (random model only; under RANGE,
        EV is not monotonic in fold equity, so no single break-even point exists).
    profitable_from_fold_equity: first 1%-grid fold frequency from which raising stays +EV.
        The last zone always ends at 1.0, because EV there equals the pot.
    """
    record = solution.record
    is_random = equities.opponent_model is OpponentModel.RANDOM
    return {
        "hand": str(solution.hand),
        "score_name": str(solution.hand.score),
        "category": stats.category.name,
        "category_name": stats.category.display_name,
        "canonical_id": record.canonical_id,
        "showdown_equity": record.equity,
        "equity_vs_random": stats.equity,
        "random_hand_equity": stats.equity,
        "call_range_percent": equities.calling_percentile,
        "sensitivity": _sensitivity_payload(sensitivity) if sensitivity is not None else None,
        "ev": record.ev,
        "break_even_fold_equity": (
            calculate_break_even_fold_equity(params.pot, params.bet_size, record.equity)
            if is_random
            else None
        ),
        "profitable_from_fold_equity": solution.zones[-1][0],
        "profitable_fold_zones": [[start, end] for start, end in solution.zones],
        "is_profitable": record.is_raise_profitable,
        "advice": _advice_payload(record.advice),
    }
```

- `showdown_equity` is the `w` that went into the EV (it depends on the opponent model), while
  `equity_vs_random` is always the database number. Under the random model they are equal.
- `break_even_fold_equity` comes straight from `EVResult`, but only under the random model.
- `profitable_from_fold_equity` is the start of the *last* zone.
- `ev` is the EV at the `bet_size` the caller sent, and `advice.ev` is the EV of the size the policy
  recommends. Send `bet_size = 50000` with a hand worth shoving and the two differ: 132,101 against
  164,402 in the README example.
- `advice` is the record's own `Recommendation`, projected by `_advice_payload`
  ([app.py:390-408](../backend/app.py#L390-L408)). The card and the table row cannot disagree, because
  they are the same object. Until 3.0.0 this block also sent `decision` (`"RAISE"` / `"CHECK/FOLD"`) and
  `recommended_action` (`"BET"` / `"NO BET"`). Both are gone: a boolean verdict cannot say how much to
  bet.

For the junk hand 5-3-2 under the random model, the API answers with
`break_even_fold_equity: 0.3312` (exact) and `profitable_from_fold_equity: 0.34` (the grid point).
For K-Q-3 under the range model, `break_even_fold_equity` is `null` and the zones are
`[[0.0, 0.08], [0.51, 1.0]]`. The web page draws those zones as the green stretches of the
"where raising pays" bar (lesson 13).

`result.zones[-1]` is safe only because the last zone always ends at `f = 1`: there the EV equals
the pot, which is positive.

`ev.py` has one more caller in the API. `_solve` puts `final_pot()` and the pure-bluff break-even
`calculate_break_even_fold_equity(pot, bet_size, 0.0)` into every range summary
([app.py:495-496](../backend/app.py#L495-L496)): at the default sizes, `final_pot: 200000.0` and
`pure_bluff_break_even_fold_equity: 0.3333`.

### 8. From EV to a size: `advice.py`

EV answers "does this wager make money". It does not answer "which wager". `advice.py` is the module
that compares three sizes and returns one frozen answer, and it is pure in the same way `ev.py` is: it
imports `calculate_ev` and the error type, and nothing else.

The ladder comes from the pot alone: `round(pot * 0.33, 2)`, `round(pot * 0.75, 2)` and
`round(pot * 1.00, 2)`. A pot of 100,000 gives 33,000, 75,000 and 100,000. There is no stack input, so
the whole pot is the price ceiling of the model. The `bet_size` you send still decides the reported
`ev` and the zone scan; it never moves the ladder.

Three rules turn those numbers into an answer.

1. **Label the hand from its win rate when called.** `VALUE` at 0.55 and above, `THIN_VALUE` from 0.45,
   `BLUFF` below 0.45. The label never gates value sizing; it only decides the sentence and the cap.
2. **Start at the biggest rung the win rate allows** and walk down: all in at 0.85 and above, the large
   rung above 0.50, the small rung otherwise. A tie at exactly 0.50 starts small.
3. **Take the first rung that clears the floor in both cells.** A rung is eligible when its EV is at
   least 5% of the pot in the centre cell *and* in the worst of the stress cells at your fold rate
   minus and plus 0.10. The all-in rung also has to be a `VALUE` hand and has to beat the large rung's
   EV. A bluff is capped at the small rung. No eligible rung, and the answer is `CHECK`.

📍 [`backend/src/advice.py:283-315`](../backend/src/advice.py#L283-L315)
```python
    amounts = ladder(pot, thresholds)
    central = tuple(calculate_ev(pot, amount, centre.fold_equity, centre.equity_when_called) for amount in amounts)
    worst = tuple(
        min(calculate_ev(pot, amount, cell.fold_equity, cell.equity_when_called) for cell in cells)
        for amount in amounts
    )
    ev_ratios = tuple(ev / pot for ev in central)
    worst_ratios = tuple(ev / pot for ev in worst)

    kind = _kind(centre.equity_when_called, thresholds)
    start = _start_rung(centre.equity_when_called, thresholds)
    blockers = tuple(
        _blocker(index, start, kind, central, ev_ratios, worst_ratios, thresholds) for index in range(3)
    )
    rungs = tuple(
        Rung(
            action=action,
            amount=amounts[index],
            ev=central[index],
            ev_ratio=ev_ratios[index],
            worst_ev_ratio=worst_ratios[index],
            robust=worst_ratios[index] >= 0.0,
            eligible=blockers[index] is None,
            blocked_by=blockers[index],
        )
        for index, action in enumerate(_RUNG_ACTIONS)
    )
    built: tuple[Rung, Rung, Rung] = (rungs[0], rungs[1], rungs[2])
    # A fold rate of 1.0 leaves the calling range empty, and the range model reports equity 0.0
    # there; a random caller keeps its real equity at the same fold rate, so only that case reads 0.
    win_rate_defined = not (centre.fold_equity >= 1.0 and centre.equity_when_called == 0.0)

    chosen = next((index for index in range(start, -1, -1) if blockers[index] is None), None)
```

`_blocker` ([advice.py:366-389](../backend/src/advice.py#L366-L389)) is where the rules live, in one
order: `EV_BELOW_FLOOR` first, then `BLUFF_TOO_SMALL_ONLY` for any rung above small on a bluff, then
`NEEDS_BIGGER_EDGE` for a rung above the one the win rate allows, then the all-in extras. `chosen` is
the walk down that list, and a rejected rung still reports why, so the UI can show the whole ladder.

**Why a fixed fold rate makes sizing a policy, not an argmax.** The policy is handed one fold rate per
cell, and the same rate is used for all three rungs. That is a deliberate simplification: real players
fold more to a bet of 75,000 than to one of 33,000, and modelling that would need an elasticity curve
the tool does not have. Without elasticity, EV rises with the size whenever your hand wins at showdown,
so "pick the rung with the highest EV" would shove nearly every strong hand and never bluff. The floor
plus the worst cell, the 85% gate and the bluff cap are what replace the missing elasticity, and they
are why the answer is a rule you can read off the response rather than the top of a sorted list.

`win_rate_defined` is one more idea worth knowing: a fold rate of 1.0 empties the calling range, and
the range model then reports equity 0.0 for every class. That 0 is not a real win rate, so it travels
as a flag and the caller says nobody calls instead of printing 0%.

### 9. The other caller: the range finder

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
- **A policy, not an argmax.** `advice.py` could have returned `max(ladder, key=ev)`. It returns an
  ordered walk instead, because the fold rate is one number for every size: with no elasticity, the
  highest-EV rung is almost always the biggest one. The floor, the worst cell, the 85% gate and the
  bluff cap cost a little EV on paper and buy an answer that survives a wrong estimate.

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
   model)", [cli.py:168-171](../backend/src/cli.py#L168-L171)). The dataclass still carries it
   (exercise 6).
6. **Modelling limits, not bugs.** One betting round, a fixed call size, one fold rate that applies to
   all three rungs, and `f` is a number you guess. The output is exactly as good as that guess.

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

**🟢 3. Predict.** At `P = 100,000`, `B = 50,000`, `f = 0`, a hand has exactly `w = 0.25`. What are
`is_profitable` and `advice`? They disagree, and that is the lesson.

<details><summary>Solution</summary>

`EV = 0.25 × 200,000 − 50,000 = 0.0`, and `is_profitable` is a strict `> 0`, so `is_profitable` is
`false`. The advice looks at 33,000 instead, where `EV = 0.25 × 166,000 − 33,000 = 8,500`, which is
8.5% of the pot, so it answers `SMALL_BET`, `BLUFF`, `SMALL_BLUFF`. The large and all-in rungs lose money
in the centre cell. "Worth raising" is always "worth raising *this much*":

```bash
python -c "from src.advice import FoldCell, recommend; r = recommend(100000.0, FoldCell(0.0, 0.25), [FoldCell(0.0, 0.25), FoldCell(0.1, 0.25)]); print(r.action, r.kind, r.reason, r.amount, r.ev)"
```

prints `SMALL_BET BLUFF SMALL_BLUFF 33000.0 8500.0`.
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

**🟡 5. Change the grid.** In [range_finder.py:266](../backend/src/range_finder.py#L266), pass
`steps=1000` to `profitable_fold_zones`. Which tests fail, and what do they tell you about the API
contract?

<details><summary>Solution</summary>

K-Q-3's zones become `[(0.0, 0.08), (0.501, 1.0)]`, and 5-3-2's start moves from 0.34 to 0.332. The
assertions that pin grid values fail: `test_solve_range_model_prices_medium_hand`
([test_api.py:500](../backend/tests/test_api.py#L500)) and the 5-3-2 break-even test
([test_api.py:527](../backend/tests/test_api.py#L527)). The 1% resolution is effectively part of the
public API: the page and the tests both assume it. Changing it is an API change, not an internal tweak.
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
6. A hand wins 60% when called and the opponent folds 35% of the time, pot 100,000. Which rung does the
   walk start at, and what happens to the all-in rung?
7. Why may a bluff never use the large rung, even when that rung clears the 5% floor?

<details><summary>Answers</summary>

1. If everyone folds there is no showdown: you take the dead pot, and the `(1 − f)` term is 0.
2. You put in `B`, and the opponent calls with `B`. The code assumes the call matches the bet.
3. One. `w` is constant, so EV is a straight line in `f`. A line crosses zero at most once, so the
   +EV part is a single interval (or empty, or everything).
4. Under the range model `w` depends on `f`, so EV can go up, down and up again (K-Q-3). A single
   break-even number would be misleading, so the API returns `null` and sends the zones instead.
5. Two reasons together: the scan only tests grid points 0.00, 0.01, …, 1.00, and
   `is_profitable` is a strict `> 0`, so EV = 0 at 0.50 does not count.
6. At the large rung, because 0.60 is above 0.50 and below 0.85. The all-in rung is refused with
   `blocked_by: "NEEDS_BIGGER_EDGE"` however good its EV looks: the walk may not start above the rung
   the win rate allows.
7. The label forbids it, not a number. With one fold rate for every size, a big bluff looks good on
   paper, and that is precisely the elasticity the model cannot see. So the cap is written as a rule
   over `Kind`, which no EV number can override.
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
- `advice.py` adds the size. Three rungs from the pot (33%, 75%, 100%), a 5% floor in the centre cell
  and in the worst ±10-point cell, an 85% gate on the all-in rung, and the value/thin/bluff bands. It
  is a policy rather than a max over EV because one fold rate for every size has no elasticity.

**Next:** [08 — The range finder](08-range-finder.md)
