"""Unit tests for Flask API endpoints in backend/app.py."""

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.get_json()
    assert data["service"] == "Lieng Stealer API"
    assert data["status"] == "online"
    assert data["endpoints"] == ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"]


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["classes_loaded"] == 455


def test_solve_endpoint_general(client):
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "summary" in data
    assert data["summary"]["range_coverage_percent"] == 100.0
    assert len(data["top_hands"]) > 0


def test_solve_endpoint_with_hand(client):
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
    }
    res = client.post("/api/solve", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["hand_evaluation"] is not None
    assert data["hand_evaluation"]["decision"] == "RAISE"
    assert data["hand_evaluation"]["canonical_id"] == "Q-K-A"
    assert data["hand_evaluation"]["ev"] > 0


def test_solve_endpoint_invalid_inputs(client):
    res = client.post("/api/solve", json={"pot": -100, "bet_size": 50})
    assert res.status_code == 400

    res2 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "fold_equity": 2.5})
    assert res2.status_code == 400

    res3 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "hand": "InvalidHand"})
    assert res3.status_code == 400


def test_analyze_endpoint(client, monkeypatch):
    # Force the offline fallback: a test must never call the real OpenRouter API
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    payload = {
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "hand": "As Kh Qd",
        "hand_evaluation": {
            "hand": "As Kh Qd",
            "score_name": "Liêng Q-K-A",
            "showdown_equity": 0.9969,
            "ev": 132097.0,
            "decision": "RAISE",
        },
        "range_coverage_percent": 100.0,
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "advice" in data
    assert len(data["advice"]) > 0



def test_solve_default_model_is_random_hand(client):
    """Omitting opponent_model keeps the original random-hand equity for existing clients."""
    res = client.post("/api/solve", json={"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d"})
    data = res.get_json()
    hand_eval = data["hand_evaluation"]
    assert data["summary"]["opponent_model"] == "random"
    assert hand_eval["showdown_equity"] == hand_eval["equity_vs_random"]
    assert hand_eval["decision"] == "RAISE"
    assert hand_eval["profitable_fold_zones"] == [[0.0, 1.0]]


def test_solve_range_model_flips_medium_hand(client):
    """An opponent who folds their weakest 35% leaves 3 points almost drawing dead when called."""
    payload = {"pot": 100000, "bet_size": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    data = client.post("/api/solve", json=payload).get_json()
    hand_eval = data["hand_evaluation"]
    assert data["summary"]["opponent_model"] == "range"
    assert hand_eval["equity_vs_random"] == 0.36
    assert hand_eval["showdown_equity"] < 0.02
    assert hand_eval["decision"] == "CHECK/FOLD"
    assert len(hand_eval["profitable_fold_zones"]) == 2
    # EV is not monotonic in fold equity here, so there is no single break-even point
    assert hand_eval["break_even_fold_equity"] is None
    assert hand_eval["profitable_from_fold_equity"] == 0.51


def test_solve_invalid_opponent_model(client):
    res = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "opponent_model": "psychic"})
    assert res.status_code == 400
    assert "opponent_model" in res.get_json()["error"]


def test_solve_category_breakdown(client):
    data = client.post("/api/solve", json={"pot": 100000, "bet_size": 50000, "fold_equity": 0.0}).get_json()
    breakdown = {row["category"]: row for row in data["summary"]["category_breakdown"]}
    assert [row["category"] for row in data["summary"]["category_breakdown"]] == ["SAP", "LIENG", "DI", "DIEM"]
    assert {cat: row["combos"] for cat, row in breakdown.items()} == {"SAP": 52, "LIENG": 768, "DI": 144, "DIEM": 21136}
    assert {cat: row["classes"] for cat, row in breakdown.items()} == {"SAP": 13, "LIENG": 12, "DI": 6, "DIEM": 424}
    assert sum(row["profitable_combos"] for row in breakdown.values()) == data["summary"]["profitable_combinations"]


def test_evaluate_and_range_accept_opponent_model(client):
    payload = {"pot": 100000, "bet": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    evaluated = client.post("/api/evaluate", json=payload).get_json()
    assert evaluated["recommended_action"] == "CHECK/FOLD"
    assert evaluated["opponent_model"] == "range"

    random_range = client.post("/api/range", json={**payload, "opponent_model": "random"}).get_json()
    calling_range = client.post("/api/range", json=payload).get_json()
    assert calling_range["range_coverage_percent"] < random_range["range_coverage_percent"]


def test_break_even_fields_random_model(client):
    """Random model: the exact closed-form break-even, plus the 1%-grid point where raising stays +EV."""
    payload = {"pot": 100000, "bet_size": 50000, "fold_equity": 0.05, "hand": "2s 3h 5d"}
    hand_eval = client.post("/api/solve", json=payload).get_json()["hand_evaluation"]
    # S = 0.0024 * 200k - 50k = -49,520  ->  f = 49,520 / 149,520 = 0.3312; first +EV grid point is 0.34
    assert hand_eval["break_even_fold_equity"] == 0.3312
    assert hand_eval["profitable_from_fold_equity"] == 0.34


def test_evaluate_reports_both_break_even_fields(client):
    payload = {"pot": 100000, "bet": 100000, "fold_equity": 0.35, "hand": "Ks Qh 3d", "opponent_model": "range"}
    evaluated = client.post("/api/evaluate", json=payload).get_json()
    assert evaluated["break_even_fold_equity"] is None
    assert evaluated["profitable_from_fold_equity"] == 0.51


def test_analyze_rejects_non_numeric_pot(client):
    res = client.post("/api/analyze", json={"pot": "abc"})
    assert res.status_code == 400
    assert "pot" in res.get_json()["error"]


def test_analyze_rejects_unknown_opponent_model(client):
    res = client.post("/api/analyze", json={"pot": 100000, "bet_size": 50000, "opponent_model": "psychic"})
    assert res.status_code == 400


@pytest.mark.parametrize("hand_evaluation", [{"ev": "lots", "showdown_equity": 0.5}, ["not", "a", "dict"]])
def test_analyze_rejects_malformed_hand_evaluation(client, hand_evaluation):
    res = client.post("/api/analyze", json={"pot": 100000, "bet_size": 50000, "hand_evaluation": hand_evaluation})
    assert res.status_code == 400
    assert "hand_evaluation" in res.get_json()["error"]
