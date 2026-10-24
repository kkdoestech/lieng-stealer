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
    assert data["endpoints"] == ["/health", "/api/solve", "/api/analyze"]


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


def test_solve_category_breakdown_matches_canonical_combinations(client):
    response = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 1.0,
    })
    assert response.status_code == 200

    data = response.get_json()
    breakdown = {
        item["category"]: item
        for item in data["summary"]["category_breakdown"]
    }
    expected = {
        "SAP": (13, 52),
        "LIENG": (12, 768),
        "DI": (6, 144),
        "DIEM": (424, 21136),
    }
    assert {
        category: (item["total_classes"], item["total_combinations"])
        for category, item in breakdown.items()
    } == expected
    assert sum(item["total_combinations"] for item in breakdown.values()) == 22100
    assert sum(item["profitable_combinations"] for item in breakdown.values()) == 22100


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
    assert data["hand_evaluation"]["decision"] == "BET"
    assert data["hand_evaluation"]["canonical_id"] == "Q-K-A"
    assert data["hand_evaluation"]["ev"] > 0
    assert data["hand_evaluation"]["call_range_percent"] == 30.0
    assert data["hand_evaluation"]["showdown_equity"] < data["hand_evaluation"]["random_hand_equity"]


def test_weak_hand_uses_calling_range_and_reports_sensitivity(client):
    response = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "fold_equity": 0.35,
        "call_range_percent": 30,
        "hand": "2s 3h 5d",
    })

    assert response.status_code == 200
    hand_eval = response.get_json()["hand_evaluation"]
    assert hand_eval["showdown_equity"] == 0.0
    assert hand_eval["random_hand_equity"] > hand_eval["showdown_equity"]
    assert hand_eval["ev"] == pytest.approx(2500.0)
    assert hand_eval["decision"] == "BET"
    assert hand_eval["sensitivity"]["status"] == "ASSUMPTION_SENSITIVE"
    assert len(hand_eval["sensitivity"]["scenarios"]) == 9
    assert {scenario["ev"] > 0 for scenario in hand_eval["sensitivity"]["scenarios"]} == {False, True}


def test_solve_rejects_invalid_call_range(client):
    response = client.post("/api/solve", json={
        "pot": 100000,
        "bet_size": 50000,
        "call_range_percent": 0,
        "hand": "2s 3h 5d",
    })

    assert response.status_code == 400
    assert "Call range percent" in response.get_json()["error"]


def test_evaluate_negative_ev_reports_no_bet_not_fold(client):
    response = client.post("/api/evaluate", json={
        "pot": 100000,
        "bet": 50000,
        "fold_equity": 0.05,
        "hand": "2s 3h 5d",
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["recommended_action"] == "NO BET"
    assert data["is_profitable"] is False


def test_solve_endpoint_invalid_inputs(client):
    res = client.post("/api/solve", json={"pot": -100, "bet_size": 50})
    assert res.status_code == 400

    res2 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "fold_equity": 2.5})
    assert res2.status_code == 400

    res3 = client.post("/api/solve", json={"pot": 100, "bet_size": 50, "hand": "InvalidHand"})
    assert res3.status_code == 400


@pytest.mark.parametrize("endpoint", ["/api/solve", "/api/evaluate", "/api/range"])
@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "-Infinity"])
def test_math_endpoints_reject_non_finite_inputs(client, endpoint, invalid):
    response = client.post(endpoint, json={
        "pot": invalid,
        "bet_size": 50,
        "fold_equity": 0.5,
        "hand": "As Kh Qd",
    })
    assert response.status_code == 400
    assert "finite" in response.get_json()["error"]


def test_analyze_endpoint(client):
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
            "decision": "BET",
        },
        "range_coverage_percent": 100.0,
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "advice" in data
    assert len(data["advice"]) > 0
