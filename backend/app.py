"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for game-theoretic range solving, single-hand valuation,
and AI-powered strategic commentary via OpenRouter LLM.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

from src.db import WinRateDB
from src.evaluator import Hand
from src.exceptions import LiengError
from src.ev import calculate_break_even_fold_equity, evaluate_action
from src.hands import to_canonical
from src.range_finder import RangeFinder

app = Flask(__name__)
# Explicitly enable CORS for all origins on /api/*, /, and /health
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/": {"origins": "*"}, r"/health": {"origins": "*"}})

# Initialize WinRateDB at startup
DB_PATH = Path(__file__).resolve().parent / "data" / "winrates.json"
win_rate_db = WinRateDB()
if DB_PATH.is_file():
    win_rate_db.load(DB_PATH)
range_finder = RangeFinder(win_rate_db)


@app.route("/", methods=["GET"])
def root() -> Any:
    """Root endpoint providing service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/analyze"],
    }), 200


@app.route("/health", methods=["GET"])
def health_check() -> Any:
    """Health check endpoint returning system status and database stats."""
    return jsonify({
        "status": "healthy",
        "database_loaded": win_rate_db.is_loaded,
        "classes_loaded": len(win_rate_db),
        "version": "1.0.0",
    })


@app.route("/api/solve", methods=["POST"])
def solve_api() -> Any:
    """Calculate EV range and specific hand decision.

    Expected JSON body:
        pot (float): Dead pot size (> 0).
        bet_size (float): Hero raise / wager amount (> 0).
        fold_equity (float): Opponent fold probability in [0.0, 1.0].
        hand (str, optional): Player 3-card hand notation (e.g. 'As Kh Qd').
    """
    data = request.get_json(silent=True) or {}

    try:
        pot = float(data.get("pot", 100000.0))
        bet_size = float(data.get("bet_size", 50000.0))
        fold_equity = float(data.get("fold_equity", 0.35))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid numerical parameters for pot, bet_size, or fold_equity."}), 400

    if pot <= 0 or bet_size <= 0:
        return jsonify({"error": "Pot and bet_size must be strictly greater than zero."}), 400
    if not (0.0 <= fold_equity <= 1.0):
        return jsonify({"error": "Fold equity must be between 0.0 and 1.0."}), 400

    hand_input = data.get("hand")
    hand_eval_result = None

    if hand_input and isinstance(hand_input, str) and hand_input.strip():
        try:
            player_hand = Hand.from_str(hand_input.strip())
            stats = win_rate_db.get_by_cards(player_hand.cards)
            ev_res = evaluate_action(pot, bet_size, fold_equity, stats.equity)
            canonical = to_canonical(player_hand.cards)
            hand_eval_result = {
                "hand": str(player_hand),
                "score_name": str(player_hand.score),
                "category": stats.category.name,
                "category_name": stats.category.display_name,
                "canonical_id": canonical.canonical_id,
                "showdown_equity": stats.equity,
                "ev": ev_res.ev,
                "break_even_fold_equity": ev_res.break_even_fold_equity,
                "is_profitable": ev_res.is_profitable,
                "decision": "RAISE" if ev_res.is_profitable else "CHECK/FOLD",
            }
        except LiengError as err:
            return jsonify({"error": f"Invalid hand: {err}"}), 400

    # Solve full range
    records = range_finder.solve_range(pot, bet_size, fold_equity)
    profitable_records = [r for r in records if r.is_raise_profitable]
    coverage = range_finder.calculate_range_coverage(profitable_records)
    be_bluff = calculate_break_even_fold_equity(pot, bet_size, win_rate_when_called=0.0)

    # Format top profitable hands (top 30)
    top_hands = [
        {
            "canonical_id": r.canonical_id,
            "category": r.category.name,
            "equity": r.equity,
            "ev": r.ev,
            "multiplicity": r.multiplicity,
            "is_profitable": r.is_raise_profitable,
        }
        for r in records[:30]
    ]

    total_combos_in_range = sum(r.multiplicity for r in profitable_records)

    return jsonify({
        "summary": {
            "pot": pot,
            "bet_size": bet_size,
            "fold_equity": fold_equity,
            "final_pot": pot + 2.0 * bet_size,
            "pure_bluff_break_even_fold_equity": be_bluff,
            "total_canonical_classes": len(records),
            "profitable_classes": len(profitable_records),
            "total_combinations": 22100,
            "profitable_combinations": total_combos_in_range,
            "range_coverage_percent": coverage,
            "highest_ev_hand": records[0].canonical_id if records else None,
            "highest_ev_value": records[0].ev if records else None,
            "threshold_hand": profitable_records[-1].canonical_id if profitable_records else None,
            "threshold_ev_value": profitable_records[-1].ev if profitable_records else None,
        },
        "hand_evaluation": hand_eval_result,
        "top_hands": top_hands,
    })


@app.route("/api/analyze", methods=["POST"])
def analyze_api() -> Any:
    """Query OpenRouter LLM for strategic game-theoretic commentary."""
    data = request.get_json(silent=True) or {}

    pot = data.get("pot", 100000.0)
    bet_size = data.get("bet_size", 50000.0)
    fold_equity = data.get("fold_equity", 0.35)
    hand = data.get("hand", "None")
    hand_eval = data.get("hand_evaluation") or {}
    coverage = data.get("range_coverage_percent", 0.0)

    api_key = os.environ.get("OPENROUTER_API_KEY")

    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {pot:,.0f} VND\n"
        f"- Bet / Raise Size: {bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {float(fold_equity) * 100:.1f}%\n"
        f"- Total Range Coverage (Hands with EV > 0): {coverage}%\n"
    )

    if hand_eval:
        prompt += (
            f"- Hero's Hand: {hand_eval.get('hand')} ({hand_eval.get('score_name')})\n"
            f"- Showdown Equity: {float(hand_eval.get('showdown_equity', 0)) * 100:.1f}%\n"
            f"- Calculated EV: {float(hand_eval.get('ev', 0)):+,.0f} VND\n"
            f"- Solver Decision: {hand_eval.get('decision')}\n"
        )
    else:
        prompt += f"- Hero's Hand: {hand} (General Range Analysis)\n"

    prompt += (
        "\nProvide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Chiến thuật Bluff & Giá trị]: Hero có nên Tố (Raise)/Tất tay hay Check/Bỏ bài? Giải thích tâm lý đối thủ.\n"
        "3. [Lời khuyên GTO]: Nhận xét ngắn gọn về độ rủi ro và cách khai thác đối thủ."
    )

    if not api_key:
        # Fallback commentary when no OpenRouter API key is configured
        fallback_advice = (
            f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
            f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {float(fold_equity)*100:.1f}%, "
            f"ngưỡng hòa vốn cược hù (bluff) là {(bet_size / (pot + bet_size))*100:.1f}%. "
            f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có.\n\n"
            f"2. **Hành động Khuyến nghị:** "
        )
        if hand_eval:
            decision = hand_eval.get("decision", "EVALUATE")
            ev = hand_eval.get("ev", 0)
            fallback_advice += (
                f"Hero cầm **{hand_eval.get('hand')}** ({hand_eval.get('score_name')}) "
                f"với xác suất thắng đối đầu {float(hand_eval.get('showdown_equity', 0))*100:.1f}%. "
                f"Kỳ vọng thu nhập (EV) đạt **{ev:+,.0f} VND**. "
                f"Khuyến nghị tối ưu: **{decision}**.\n\n"
                f"3. **GTO Insight:** "
                + ("Bài có EV dương rõ rệt nhờ cả showdown equity lẫn fold equity. Tố lớn để tối đa hóa lợi nhuận." if ev > 0
                   else "EV âm. Showdown equity quá thấp và đối thủ ít bỏ bài. Không nên mạo hiểm, hãy Bỏ bài (Fold) hoặc Theo nhẹ nếu có thể.")
            )
        else:
            fallback_advice += (
                f"Với tần suất đối thủ bỏ bài {float(fold_equity)*100:.1f}%, hãy ưu tiên nâng cược với các nhóm bài Sáp, Liêng, Đĩ "
                f"và các tổ hợp điểm cao (> 7 điểm). Cẩn trọng cược hù khi đối thủ có xu hướng theo cược dính."
            )

        return jsonify({
            "advice": fallback_advice,
            "model": "rule-based-solver-engine (OPENROUTER_API_KEY not configured)",
        })

    # Call OpenRouter API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lieng-stealer",
        "X-Title": "Lieng Stealer Solver",
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [
            {"role": "system", "content": "You are a professional game theory analyst specializing in Vietnamese card games like Liêng."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if resp.status_code == 200:
            result_json = resp.json()
            advice = result_json["choices"][0]["message"]["content"]
            return jsonify({
                "advice": advice,
                "model": "meta-llama/llama-3.1-8b-instruct:free",
            })
        else:
            return jsonify({
                "error": f"OpenRouter API returned status {resp.status_code}: {resp.text}",
                "advice": f"Không thể lấy phân tích từ AI (Mã lỗi {resp.status_code}). Vui lòng kiểm tra OPENROUTER_API_KEY.",
            }), 502
    except requests.RequestException as err:
        return jsonify({
            "error": str(err),
            "advice": "Lỗi kết nối tới OpenRouter AI gateway.",
        }), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

