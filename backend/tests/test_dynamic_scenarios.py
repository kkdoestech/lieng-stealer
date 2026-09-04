"""Comprehensive Dynamic Scenario Verification Suite for Liêng Stealer.

Verifies that the engine and API are completely dynamic and mathematically
rigorous across 5 diverse game scenarios:
1. Monster Hand Value Raise (Liêng Q-K-A)
2. Junk Hand against Calling Station (Forced Fold with 0 points)
3. Mathematical Pure Bluff (0 points flips to Raise under high fold equity)
4. Range Coverage Sensitivity Sweep across fold equities
5. API Schema, Endpoint Variations & Dynamic Response Verification
"""

import sys
from pathlib import Path
import pytest

# Ensure UTF-8 encoding on Windows terminal output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app
from src.db import WinRateDB
from src.range_finder import RangeFinder

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "winrates.json"


@pytest.fixture(scope="module")
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="module")
def solver():
    db = WinRateDB(DB_PATH)
    return RangeFinder(db)


def test_scenario_1_monster_hand_value_raise(client):
    """Scenario 1: Monster Hand Value Raise (Liêng Q-K-A).
    Pot=100k, Bet=50k, FoldEquity=0.20, Hand='As Kh Qd'
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.20,
        "hand": "As Kh Qd",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST be "RAISE"
    assert hand_eval["decision"] == "RAISE"
    # 2. Showdown Equity MUST be > 99%
    assert hand_eval["showdown_equity"] > 0.99
    # 3. EV MUST be positive (> +100,000)
    assert hand_eval["ev"] > 100000.0
    # 4. Break-Even Fold Equity MUST be 0.0% (profitable even if opponent never folds)
    assert hand_eval["break_even_fold_equity"] == 0.0

    print("\n[Scenario 1: Monster Value Raise]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Showdown Equity: {hand_eval['showdown_equity'] * 100:.2f}%")
    print(f"  Net EV: +{hand_eval['ev']:,.0f} VND")
    print(f"  Break-Even FE: {hand_eval['break_even_fold_equity'] * 100:.1f}%")
    print(f"  Decision: {hand_eval['decision']} -> PASS")


def test_scenario_2_junk_hand_calling_station(client):
    """Scenario 2: Junk Hand against Calling Station (Forced Fold).
    Pot=100k, Bet=50k, FoldEquity=0.05, Hand='2s 3h 5d' (0 pts Bù)
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.05,
        "hand": "2s 3h 5d",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST be "CHECK/FOLD"
    assert "FOLD" in hand_eval["decision"]
    # 2. Showdown Equity MUST be < 1% (0.24%)
    assert hand_eval["showdown_equity"] < 0.01
    # 3. EV MUST be negative (close to -42,000)
    assert hand_eval["ev"] < 0.0
    assert abs(hand_eval["ev"] - (-42044.0)) < 100.0
    # 4. Break-Even Fold Equity MUST be > 30% (unprofitable because 0.05 < 0.33)
    assert hand_eval["break_even_fold_equity"] > 0.30

    print("\n[Scenario 2: Junk Hand Forced Fold]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Showdown Equity: {hand_eval['showdown_equity'] * 100:.2f}%")
    print(f"  Net EV: {hand_eval['ev']:,.0f} VND")
    print(f"  Break-Even FE: {hand_eval['break_even_fold_equity'] * 100:.2f}%")
    print(f"  Decision: {hand_eval['decision']} -> PASS")


def test_scenario_3_pure_bluff_flip(client):
    """Scenario 3: Mathematical Pure Bluff (Junk Hand with High Fold Equity).
    Pot=100k, Bet=50k, FoldEquity=0.50, Hand='2s 3h 5d' (0 pts Bù)
    """
    payload = {
        "pot": 100000.0,
        "bet_size": 50000.0,
        "fold_equity": 0.50,
        "hand": "2s 3h 5d",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()

    hand_eval = data["hand_evaluation"]
    assert hand_eval is not None

    # Invariants:
    # 1. Recommendation MUST flip to "RAISE" despite holding 0 points
    assert hand_eval["decision"] == "RAISE"
    # 2. EV MUST become positive (> +20,000) solely due to fold equity exceeding 33.3%
    assert hand_eval["ev"] > 20000.0
    assert abs(hand_eval["ev"] - 25240.0) < 100.0
    assert hand_eval["is_profitable"] is True

    print("\n[Scenario 3: Mathematical Pure Bluff]")
    print(f"  Hand: {hand_eval['hand']} ({hand_eval['canonical_id']})")
    print(f"  Opponent Fold Equity: 50.0% (Threshold: {data['summary']['pure_bluff_break_even_fold_equity'] * 100:.1f}%)")
    print(f"  Net EV: +{hand_eval['ev']:,.0f} VND")
    print(f"  Decision: {hand_eval['decision']} (Flipped from Fold to Raise) -> PASS")


def test_scenario_4_range_coverage_sensitivity(solver):
    """Scenario 4: Range Coverage Sensitivity Sweep.
    Sweep fold equities: f = 0.00, 0.15, 0.30, 0.40
    """
    pot = 100000.0
    bet = 50000.0

    cov_00 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.00))
    cov_15 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.15))
    cov_30 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.30))
    cov_40 = solver.calculate_range_coverage(solver.get_profitable_range(pot, bet, 0.40))

    # Invariants:
    # 1. Coverage MUST strictly increase as f increases
    assert cov_00 < cov_15 < cov_30 < cov_40
    # 2. Coverage at f = 0.40 MUST equal 100.0% (pure bluff threshold is 33.3%)
    assert cov_40 == 100.0
    # 3. Coverage at f = 0.00 is restricted (< 80% under pot odds, and strict >50% equity hands < 50%)
    assert cov_00 < 80.0
    # Verify pure favorite hands (>50% equity) are < 50% of total hand space
    db = WinRateDB(DB_PATH)
    combos_above_50 = sum(s.multiplicity for s in db.all_items().values() if s.equity > 0.50)
    assert (combos_above_50 / 22100.0) * 100.0 < 50.0

    print("\n[Scenario 4: Range Coverage Sensitivity Sweep]")
    print(f"  f = 0.00 (Calling Station): {cov_00:.2f}% coverage")
    print(f"  f = 0.15 (Tight Caller):   {cov_15:.2f}% coverage")
    print(f"  f = 0.30 (Average Player): {cov_30:.2f}% coverage")
    print(f"  f = 0.40 (Folding Player): {cov_40:.2f}% coverage")
    print("  Monotonicity: cov(0.0) < cov(0.15) < cov(0.30) < cov(0.40) == 100.0% -> PASS")


def test_scenario_5_api_schema_and_endpoints(client):
    """Scenario 5: API Schema & Endpoints Check.
    Test with and without hand, and verify dynamic variance with parameter changes.
    """
    # 1. Request with hand
    res_with_hand = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
    })
    assert res_with_hand.status_code == 200
    data_with_hand = res_with_hand.get_json()
    assert data_with_hand["hand_evaluation"] is not None
    assert "summary" in data_with_hand
    assert "top_hands" in data_with_hand

    # 2. Request without hand
    res_no_hand = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
    })
    assert res_no_hand.status_code == 200
    data_no_hand = res_no_hand.get_json()
    assert data_no_hand["hand_evaluation"] is None
    assert data_no_hand["summary"]["range_coverage_percent"] == 100.0

    # 3. Dynamic verification: Changing pot/bet changes EV and thresholds
    res_diff_params = client.post("/api/solve", json={
        "pot": 200000,
        "bet_size": 100000,
        "fold_equity": 0.10,
        "hand": "As Kh Qd",
    })
    data_diff = res_diff_params.get_json()
    assert data_diff["summary"]["pot"] == 200000
    assert data_diff["summary"]["final_pot"] == 400000
    assert data_diff["hand_evaluation"]["ev"] != data_with_hand["hand_evaluation"]["ev"]

    # 4. Service root metadata
    root_res = client.get("/")
    assert root_res.status_code == 200
    root_json = root_res.get_json()
    assert root_json["service"] == "Lieng Stealer API"
    assert root_json["status"] == "online"

    print("\n[Scenario 5: API Schema & Dynamic Verification]")
    print("  POST /api/solve with hand: OK")
    print("  POST /api/solve without hand: OK")
    print("  Dynamic EV scaling with Pot/Bet changes: OK")
    print("  GET / service metadata: OK -> PASS")

