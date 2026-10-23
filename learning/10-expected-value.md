# 09 — Expected Value

> **Goal:** turn "should I raise?" into a formula, derive it step by step, and implement it as pure functions.
> **You will build:** `backend/src/ev.py` and `backend/tests/test_ev.py` (9 tests).
> **Time:** ~1.5 hours.
> **Prerequisites:** [08](08-database-layer.md). Re-read chapter 1, Part 3.

---

## The big picture

So far we can answer "how often does this hand win at showdown?" (equity). But a player wants to know
**"do I make money if I raise?"** That also depends on the pot, the bet size and how often the opponent
folds. The EV formula combines all four numbers into one answer.

```
 pot P ─────────┐
 bet size B ────┤
 fold equity f ─┼──► calculate_ev() ──► EV (VND)  ──► EV > 0 ?  ──► RAISE  /  CHECK-FOLD
 equity e ──────┘         ▲
 (from WinRateDB)         │
                 calculate_break_even_fold_equity() ──► "you need the opponent to fold at least X%"
```

`ev.py` is **pure maths**: no files, no printing, no global state. `AGENTS.md` requires this, and it
makes the module trivial to test: same inputs → same output, always.

---

## Concepts you need: deriving the formula

We'll use these symbols throughout:

| Symbol | Meaning | Example |
|--------|---------|---------|
| `P` | pot before our bet ("dead money") | 100,000 |
| `B` | our bet / raise | 50,000 |
| `f` | probability the opponent folds (fold equity) | 0.35 |
| `e` | our equity if called, `P(Win \| Call)` | 0.9969 for Q-K-A |

**Expected value** = Σ (probability of outcome × profit of outcome). We measure profit **from the moment
we decide**, so money already in the pot counts as something we can *win*, not something we "own".

### The outcome tree

```
                               we bet B
                                  │
              ┌───────────────────┴────────────────────┐
         FOLD (prob f)                            CALL (prob 1 − f)
         profit: +P                         opponent adds B → final pot = P + 2B
                                  ┌───────────────────┴───────────────────┐
                            we WIN (prob e)                         we LOSE (prob 1 − e)
                            profit: (P + 2B) − B = P + B            profit: −B
```

- **Fold:** we take the pot, `+P`. Our bet comes back to us, so it costs nothing.
- **Call, we win:** we collect the whole final pot `P + 2B`, but `B` of it was our own money, so our
  profit is `P + B`.
- **Call, we lose:** we lose our bet, `−B`.

### Putting it together

The expected profit **given that the opponent calls** (the "showdown value", `S`):

```
S = e × (P + B) + (1 − e) × (−B)
  = e×P + e×B − B + e×B
  = e × (P + 2B) − B
  = e × FinalPot − B
```

Then weight the two branches:

```
EV = f × P  +  (1 − f) × S
EV = f × P  +  (1 − f) × [ e × (P + 2B) − B ]
```

That's exactly the formula in `AGENTS.md` §5.1 (with the opponent's call `C_opp = B`).

**Decision rule:** raise **if and only if `EV > 0`**.

### Worked example (from chapter 1)

`P = 100,000`, `B = 50,000`, `f = 0.35`, `e = 0.9969`:

```
FinalPot = 100,000 + 2 × 50,000          = 200,000
S        = 0.9969 × 200,000 − 50,000     = 149,380
EV       = 0.35 × 100,000 + 0.65 × 149,380
         = 35,000 + 97,097               = +132,097  → RAISE
```

### Break-even fold equity

**How often must the opponent fold for a bet to break even?** Set `EV = 0` and solve for `f`:

```
f × P + (1 − f) × S = 0
f × P + S − f × S   = 0
f × (P − S)         = −S
f                   = −S / (P − S)
```

- If `S ≥ 0` (we profit even when called), we need **no** folds at all: the answer is 0.
- A **pure bluff** (`e = 0`, so `S = −B`): `f = B / (P + B)`. With `P = 100k`, `B = 50k`:
  **50k / 150k = 33.3%**. If the opponent folds more often than that, betting with *any* hand
  makes money.

The bigger you bet, the more folds a bluff needs:

| Bet `B` (pot 100k) | Bluff break-even `B/(P+B)` | Equity needed if `f = 0`: `B/(P+2B)` |
|----|----|----|
| 25,000 (¼ pot) | 20.0% | 16.7% |
| 50,000 (½ pot) | 33.3% | 25.0% |
| 100,000 (1× pot) | 50.0% | 33.3% |
| 200,000 (2× pot) | 66.7% | 40.0% |

The last column is the classic **pot odds**: when the opponent never folds, we need `e × (P + 2B) > B`,
i.e. `e > B / (P + 2B)`.

### How EV moves (a feel for the formula)

EV in VND, for `P = 100k`, `B = 50k`:

| Hand (equity `e`) | f = 0 | f = 0.20 | f = 0.35 | f = 0.50 | f = 1.0 |
|-------------------|------:|------:|------:|------:|------:|
| `5-3-2` junk (0.0024) | −49,520 | −19,616 | **+2,812** | +25,240 | +100,000 |
| weak (0.20) | −10,000 | +12,000 | +28,500 | +45,000 | +100,000 |
| coin flip (0.50) | +50,000 | +60,000 | +67,500 | +75,000 | +100,000 |
| `Q-K-A` (0.9969) | +149,380 | +139,504 | +132,097 | +124,690 | +100,000 |

Two lessons hide in this table:

1. **Junk hands live on fold equity.** `5-3-2` flips from losing to winning around `f = 0.33`.
2. **Monster hands want to be called.** Q-K-A's EV *drops* as `f` rises: a fold only wins `P`, while a
   call wins about `P + B`. At `f = 1.0` every hand earns exactly `P`, because nobody ever sees a showdown.

---

## Step 9.1 — Docstring, imports and the result object

📄 **File:** `backend/src/ev.py` — *create this file*

```python
"""Liêng Stealer - Expected Value (EV) Decision Engine.

Implements pure mathematical game-theoretic calculations for pot odds,
fold equity, showdown value, and break-even thresholds in Liêng:
EV = [P(Fold) * Pot] + [1 - P(Fold)] * [(P(Win|Call) * FinalPot) - BetSize]
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EVResult:
    """Immutable result object encapsulating a complete EV calculation."""
    ev: float
    pot: float
    bet_size: float
    fold_equity: float
    win_rate_when_called: float
    final_pot: float
    break_even_fold_equity: float
    is_profitable: bool
```

`EVResult` bundles **inputs and outputs together**, so whoever displays the result (the CLI, the API)
has everything in one object and can't mix up numbers from different calculations.

---

## Step 9.2 — `calculate_ev`

📄 **File:** `backend/src/ev.py` — *add to the end*

```python


def calculate_ev(
    pot: float,
    bet_size: float,
    fold_equity: float,
    win_rate_when_called: float,
) -> float:
    """Calculate the Expected Value (EV) of a Raise or All-in action.

    Formula:
        EV = [P(Fold) * Pot] + [1 - P(Fold)] * [(P(Win|Call) * FinalPot) - BetSize]
        where FinalPot = Pot + 2 * BetSize.

    Args:
        pot: Current dead money in the pot (must be > 0).
        bet_size: The player's wager / raise amount (must be > 0).
        fold_equity: Opponent's probability of folding, in [0.0, 1.0].
        win_rate_when_called: Hero's equity if opponent calls, in [0.0, 1.0].

    Returns:
        The expected value in units matching pot/bet currency.

    Raises:
        ValueError: If any parameter violates physical/probability bounds.
    """
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

**How it works**

- **Guard clauses first.** A negative pot or a probability of 1.5 is physically meaningless. We
  refuse it immediately with a clear message instead of returning a nonsense number.
- `0.0 <= x <= 1.0` is a chained comparison (both conditions must be true).
- The three maths lines are the derivation above, one line per idea: `FinalPot`, `S`, `EV`.
- `round(ev, 4)` keeps results tidy (and stable across tiny floating-point differences).

> 💡 **Error type.** These checks raise the built-in `ValueError`, not a `LiengError`. That's a reasonable
> choice for "bad numeric argument", but it means the API must validate numbers **before** calling
> (which it does, in chapter 12). Otherwise a bad pot would crash with a 500 error instead of a
> friendly 400.

---

## Step 9.3 — `calculate_break_even_fold_equity`

📄 **File:** `backend/src/ev.py` — *add to the end*

```python


def calculate_break_even_fold_equity(
    pot: float,
    bet_size: float,
    win_rate_when_called: float,
) -> float:
    """Calculate minimum fold equity required for an action to achieve EV >= 0.

    Solving for f in:
        f * Pot + (1 - f) * ShowdownValue = 0
        f * (Pot - ShowdownValue) = -ShowdownValue
        f = -ShowdownValue / (Pot - ShowdownValue)

    Args:
        pot: Current pot (must be > 0).
        bet_size: Hero bet amount (must be > 0).
        win_rate_when_called: Equity when called, in [0.0, 1.0].

    Returns:
        Required fold equity in [0.0, 1.0]. Returns 0.0 if already profitable.
    """
    if pot <= 0:
        raise ValueError(f"Pot must be strictly positive, got {pot}.")
    if bet_size <= 0:
        raise ValueError(f"Bet size must be strictly positive, got {bet_size}.")
    if not (0.0 <= win_rate_when_called <= 1.0):
        raise ValueError(f"Win rate when called must be between 0.0 and 1.0, got {win_rate_when_called}.")

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

**How it works**

- The docstring contains the algebra, so the code can be checked against it line by line.
- `min(1.0, max(0.0, x))` **clamps** `x` into `[0, 1]`. A probability can't be outside that range.
- Example: `e = 0.20` → `S = 0.2 × 200,000 − 50,000 = −10,000` → `f = 10,000 / (100,000 + 10,000) =
  0.0909`. So the opponent must fold at least 9.1% of the time.

> 💡 **Dead code.** When we reach `denominator = pot - showdown_value`, we already know `S < 0` and
> `pot > 0`, so `pot − S` is always **positive**. The `if denominator <= 0.0` branch can never run. It's
> harmless defensive code, but a test-coverage tool would report it as never executed. Spotting
> impossible branches by reasoning is a useful skill.

> 💡 **DRY.** `final_pot = pot + 2.0 * bet_size` and the showdown-value line appear in both
> functions (and `pot + 2.0 * bet_size` again in `evaluate_action`, the CLI and the API). A tiny helper,
> `def _showdown_value(pot, bet, eq) -> float`, would give the formula a single home.

---

## Step 9.4 — `is_profitable` and `evaluate_action`

📄 **File:** `backend/src/ev.py` — *add to the end*

```python


def is_profitable(ev: float) -> bool:
    """Return True if Expected Value is strictly positive."""
    return ev > 0.0


def evaluate_action(
    pot: float,
    bet_size: float,
    fold_equity: float,
    win_rate_when_called: float,
) -> EVResult:
    """Perform complete financial evaluation and return an EVResult instance."""
    ev = calculate_ev(pot, bet_size, fold_equity, win_rate_when_called)
    be_fe = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called)
    final_pot = pot + 2.0 * bet_size
    return EVResult(
        ev=ev,
        pot=pot,
        bet_size=bet_size,
        fold_equity=fold_equity,
        win_rate_when_called=win_rate_when_called,
        final_pot=final_pot,
        break_even_fold_equity=be_fe,
        is_profitable=is_profitable(ev),
    )
```

**How it works**

- `is_profitable` names the decision rule. `EV == 0` exactly is **not** profitable (strict `>`).
  Giving a one-line rule its own function means the rule is written down in exactly one place.
- `evaluate_action` is a **facade**: one convenient call that runs the others and packs everything into
  an `EVResult`. The CLI and the API use it for single-hand decisions.

🧪 **Mini-check** (the junk-hand bluff from chapter 1)

```bash
python -c "
from src.ev import evaluate_action, calculate_ev
print(evaluate_action(100000, 50000, 0.35, 0.0024))
print(calculate_ev(100000, 50000, 0.05, 0.0024), calculate_ev(100000, 50000, 0.50, 0.0024))
"
```

Expected output:

```
EVResult(ev=2812.0, pot=100000, bet_size=50000, fold_equity=0.35, win_rate_when_called=0.0024, final_pot=200000.0, break_even_fold_equity=0.3312, is_profitable=True)
-42044.0 25240.0
```

The junk hand needs 33.12% folds (slightly less than 33.33%, because its 0.24% equity helps a little).
At 35% it's barely profitable; at 5% it loses 42,044 per hand; at 50% it wins 25,240.

> ⚠️ **Pitfall: what the model leaves out.** This formula describes a single betting round:
> the opponent can only fold or call, never re-raise; there are exactly two players; and the fold
> probability `f` is a number **you guess**. It also uses the equity against a *random* hand (see the
> chapter 7 pitfall), although the hands that call are usually stronger than random. Every model
> simplifies; what matters is knowing **which** simplifications you made. Chapter 17 lists ideas to relax them.

---

## Step 9.5 — The tests

📄 **File:** `backend/tests/test_ev.py` — *create this file*

```python
"""Unit tests for the Expected Value (EV) Decision Engine.

Verifies:
- Mathematical boundary conditions:
    P(Fold) = 1.0 => EV = Pot
    P(Fold) = 0.0, P(Win) = 1.0 => EV = Pot + Bet
    P(Fold) = 0.0, P(Win) = 0.0 => EV = -Bet
- Mathematical bluffing: junk hand (win_rate = 0.05) has EV > 0 when fold_equity = 0.8
- Strict monotonicity with respect to fold equity and win rate
- Break-even fold equity calculation correctness
- Parameter bound validations and error handling
"""

import pytest

from src.ev import (
    calculate_break_even_fold_equity,
    calculate_ev,
    evaluate_action,
    is_profitable,
)


class TestEVEngine:
    """Test suite for mathematical EV calculations."""

    def test_boundary_all_fold(self) -> None:
        """When opponent folds 100% of the time, EV must equal the dead pot."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=1.0, win_rate_when_called=0.0)
        assert ev == pot

    def test_boundary_zero_fold_nuts(self) -> None:
        """When opponent never folds and hero wins 100%, EV = Pot + Bet."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.0, win_rate_when_called=1.0)
        # FinalPot = 100k + 100k = 200k; Payoff = 200k - 50k = 150k = pot + bet
        assert ev == pot + bet

    def test_boundary_zero_fold_zero_equity(self) -> None:
        """When opponent never folds and hero has zero equity, EV = -Bet."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.0, win_rate_when_called=0.0)
        assert ev == -bet
```

**Boundary tests** check the extreme inputs where the right answer is obvious: always fold → `P`;
always call and always win → `P + B`; always call and always lose → `−B`. If a formula fails at the
edges, it's certainly wrong in the middle.

📄 **File:** `backend/tests/test_ev.py` — *add to the end*

```python

    def test_bluff_profitability(self) -> None:
        """A junk hand (5% win rate when called) must yield positive EV if fold equity is 80%."""
        pot = 100000.0
        bet = 50000.0
        ev = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.80, win_rate_when_called=0.05)
        # Fold component: 0.8 * 100k = 80k
        # Call component: 0.2 * (0.05 * 200k - 50k) = 0.2 * (10k - 50k) = -8k
        # Net EV = 80k - 8k = 72k > 0
        assert ev == 72000.0
        assert is_profitable(ev) is True

    def test_monotonicity(self) -> None:
        """Increasing fold equity or win rate must strictly increase EV."""
        pot = 100000.0
        bet = 50000.0

        ev_fe_low = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.2, win_rate_when_called=0.5)
        ev_fe_high = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.6, win_rate_when_called=0.5)
        assert ev_fe_high > ev_fe_low

        ev_win_low = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.4, win_rate_when_called=0.3)
        ev_win_high = calculate_ev(pot=pot, bet_size=bet, fold_equity=0.4, win_rate_when_called=0.7)
        assert ev_win_high > ev_win_low
```

> 💡 The docstring says "increasing fold equity … must strictly increase EV", but our table shows that's
> **not always true**: for Q-K-A, more folds means *less* EV. The test passes because it uses `e = 0.5`,
> where `S = 50,000 < P = 100,000`. In general, EV grows with `f` only when `S < P`. The test is correct;
> its docstring over-generalises. Writing a test makes you state a claim precisely, so read claims
> carefully.

📄 **File:** `backend/tests/test_ev.py` — *add to the end*

```python

    def test_break_even_fold_equity(self) -> None:
        """At break-even fold equity, calculated EV must be approximately zero."""
        pot = 100000.0
        bet = 50000.0
        win_rate = 0.20

        be_fe = calculate_break_even_fold_equity(pot, bet, win_rate)
        assert 0.0 <= be_fe <= 1.0

        ev_at_be = calculate_ev(pot, bet, be_fe, win_rate)
        # 4 decimal places on be_fe introduces at most ~0.005% rounding delta on a 100k pot
        assert abs(ev_at_be) <= 5.0
        assert abs(ev_at_be) / pot < 0.0001

    def test_break_even_for_profitable_showdown(self) -> None:
        """If showdown alone is profitable, break-even fold equity is 0.0."""
        pot = 100000.0
        bet = 50000.0
        # Final pot = 200k. Win rate = 80% => Showdown value = 160k - 50k = 110k > 0
        be_fe = calculate_break_even_fold_equity(pot, bet, 0.80)
        assert be_fe == 0.0
```

`test_break_even_fold_equity` is a **round-trip test** again: compute the break-even `f`, plug it back
into `calculate_ev`, and expect ≈ 0. (It's −1.0 VND because `f` was rounded to 0.0909.)

📄 **File:** `backend/tests/test_ev.py` — *add to the end*

```python

    def test_parameter_validations(self) -> None:
        """Verify invalid parameter values raise ValueError."""
        with pytest.raises(ValueError):
            calculate_ev(pot=-10.0, bet_size=50.0, fold_equity=0.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=0.0, fold_equity=0.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=50.0, fold_equity=1.5, win_rate_when_called=0.5)
        with pytest.raises(ValueError):
            calculate_ev(pot=100.0, bet_size=50.0, fold_equity=0.5, win_rate_when_called=-0.1)

    def test_evaluate_action_helper(self) -> None:
        """Verify evaluate_action returns complete EVResult object."""
        res = evaluate_action(pot=100000.0, bet_size=50000.0, fold_equity=0.40, win_rate_when_called=0.60)
        assert res.pot == 100000.0
        assert res.bet_size == 50000.0
        assert res.final_pot == 200000.0
        assert res.is_profitable is True
        assert res.ev > 0.0
```

---

## ✅ Checkpoint

```bash
python -m pytest tests/test_ev.py -v
```

Expected: **9 passed**. Then the whole suite:

```bash
python -m pytest -q
```

```
...........................................                              [100%]
43 passed in 3.70s
```

Commit:

```bash
git add . && git commit -m "feat: EV engine with break-even fold equity"
```

## Recap

- `EV = f·P + (1 − f)·[e·(P + 2B) − B]`, derived from a three-outcome tree (fold / call-win / call-lose).
- **Raise iff EV > 0.** Break-even fold equity is `−S / (P − S)`, which for a pure bluff is `B / (P + B)`.
- Junk hands depend on fold equity; monster hands prefer being called (their EV falls as `f` rises).
- `ev.py` is pure: guard clauses, three lines of maths, rounding, and a facade (`evaluate_action`) that returns an `EVResult`.
- Pitfalls: model limits (one street, no re-raise, guessed `f`, random-hand equity); a little dead code and repetition.

**Next:** [10 — The range finder](11-range-finder.md)
