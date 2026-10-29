"""Liêng Stealer - Flask REST API Backend.

Provides RESTful endpoints for range solving, single-hand valuation, and AI-assisted strategic
commentary via OpenRouter. ``create_app()`` builds an app with its own database, calling-range
model, advice thresholds and settings (dependency injection); the module-level ``app`` is the one
that ``gunicorn app:app`` and ``python app.py`` serve.

Every response uses one vocabulary (``bet_size``, ``showdown_equity``, ``advice`` …), and every
error is JSON: ``{"error": "<message>", "code": "<code>"}``.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any, Final

import requests
from flask import Blueprint, Flask, Response, current_app, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from src.advice import Action, AdviceThresholds, Reason, Recommendation, Rung, ladder
from src.calling_range import CallingRangeModel, OpponentModel
from src.db import HandStats, WinRateDB
from src.ev import (
    DEFAULT_BET_SIZE,
    DEFAULT_FOLD_EQUITY,
    DEFAULT_POT,
    calculate_break_even_fold_equity,
    final_pot,
)
from src.evaluator import Hand
from src.exceptions import InvalidCardError, InvalidGameParamsError, InvalidHandSizeError
from src.hands import TOTAL_COMBINATIONS
from src.paths import DEFAULT_DB_PATH
from src.range_finder import HandEVRecord, HandSolution, OpponentEquities, RangeFinder, category_breakdown
from src.sensitivity import Sensitivity, stress_test

API_VERSION: Final[str] = "3.0.0"
TOP_HANDS_LIMIT: Final[int] = 30
OPENROUTER_URL: Final[str] = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODEL_NAME: Final[str] = "rule-based-solver-engine (OPENROUTER_API_KEY not configured)"

# Request fields removed by the caller-range unification. They are rejected loudly for one release
# (with the conversion) rather than silently ignored, so a client can never keep sending a second,
# contradictory opponent assumption and receive numbers computed from a different one.
REMOVED_REQUEST_FIELDS: Final[dict[str, str]] = {
    "call_range_percent": (
        "call_range_percent was removed: it encoded the same opponent assumption as fold_equity. "
        "Send fold_equity = 1 - call_range_percent / 100 instead (e.g. 30 -> 0.7), or omit it and "
        "the calling range is derived from fold_equity."
    ),
}


# Settings and their defaults. create_app() reads each one from the environment when it is set,
# and an explicit ``config`` argument overrides both (tests use that).
DEFAULT_CONFIG: Final[dict[str, Any]] = {
    "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
    "ANALYZE_RATE_LIMIT": "10 per minute",
    "RATELIMIT_STORAGE_URI": "memory://",
    "RATELIMIT_ENABLED": True,
    # Number of reverse proxies in front of the app whose X-Forwarded-For header to trust (0 = none).
    # Behind a hosting proxy, set it to 1 so the rate limit counts each visitor, not the proxy.
    "PROXY_FIX_X_FOR": 0,
    "OPENROUTER_API_KEY": "",
    "OPENROUTER_MODEL": "meta-llama/llama-3.1-8b-instruct:free",
    "OPENROUTER_TIMEOUT": 15.0,
    # One ADVICE_* setting per policy threshold, so the nine numbers are defined in one place.
    **{f"ADVICE_{field.name.upper()}": field.default for field in fields(AdviceThresholds)},
}

Json = dict[str, Any]  # a JSON object as returned by the API


@dataclass(frozen=True)
class GameParams:
    """Validated game-state parameters shared by the solver endpoints.

    ``fold_equity`` is the single opponent assumption: under the RANGE model it also fixes the
    calling range (the opponent folds their weakest ``fold_equity`` share of the 22,100 hands).
    """
    pot: float
    bet_size: float
    fold_equity: float
    opponent_model: OpponentModel


@dataclass(frozen=True)
class Services:
    """Everything a request needs, built once per app and stored in ``app.extensions``."""
    db: WinRateDB
    calling_model: CallingRangeModel
    range_finder: RangeFinder
    advice_thresholds: AdviceThresholds


api = Blueprint("api", __name__)
analysis = Blueprint("analysis", __name__)  # separate so the rate limit applies to it alone


# --------------------------------------------------------------------------------------------
# Application factory
# --------------------------------------------------------------------------------------------
def create_app(
    *,
    db: WinRateDB | None = None,
    calling_model: CallingRangeModel | None = None,
    config: Mapping[str, Any] | None = None,
    thresholds: AdviceThresholds | None = None,
) -> Flask:
    """Build the Flask app and its services.

    Args:
        db: A loaded win-rate database. Defaults to loading backend/data/winrates.json.
        calling_model: The calling-range model. Defaults to building one (about 60 ms).
        config: Settings that override DEFAULT_CONFIG and the environment. ``TESTING=True``
            also turns the rate limiter off and ignores any OPENROUTER_API_KEY from the
            environment (so a test can never call the real service), unless the config sets
            ``RATELIMIT_ENABLED`` / ``OPENROUTER_API_KEY`` explicitly.
        thresholds: The advice policy's numbers. Defaults to ``ADVICE_*`` config, then to
            ``DEFAULT_THRESHOLDS``.

    Raises:
        DatabaseError: If the default database file is missing or invalid (fail fast at start-up).
        ValueError: If a numeric setting in the environment is not a number.
        InvalidGameParamsError: If the ``ADVICE_*`` settings break a threshold ordering (also a
            ValueError).
    """
    app = Flask(__name__)
    app.config.update(DEFAULT_CONFIG)
    app.config.update(_settings_from_env())
    overrides = dict(config or {})
    if overrides.get("TESTING"):
        overrides.setdefault("RATELIMIT_ENABLED", False)
        overrides.setdefault("OPENROUTER_API_KEY", "")
    app.config.update(overrides)

    if int(app.config["PROXY_FIX_X_FOR"]) > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=int(app.config["PROXY_FIX_X_FOR"]))  # type: ignore[method-assign]

    if db is None:
        db = WinRateDB(DEFAULT_DB_PATH)
    if calling_model is None:
        calling_model = CallingRangeModel()
    if thresholds is None:
        thresholds = _thresholds_from_config(app.config)
    app.extensions["lieng"] = Services(db, calling_model, RangeFinder(db, calling_model), thresholds)

    origins = [o.strip() for o in str(app.config["CORS_ORIGINS"]).split(",") if o.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}, r"/": {"origins": origins}, r"/health": {"origins": origins}})

    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
        enabled=bool(app.config["RATELIMIT_ENABLED"]),
        headers_enabled=True,  # Retry-After and X-RateLimit-* headers tell clients when to retry
    )
    limiter.limit(lambda: str(current_app.config["ANALYZE_RATE_LIMIT"]))(analysis)

    app.register_blueprint(api)
    app.register_blueprint(analysis)
    _register_error_handlers(app)
    return app


def _settings_from_env() -> dict[str, Any]:
    """Read every DEFAULT_CONFIG key that is set in the environment, converted to its type."""
    settings: dict[str, Any] = {}
    for key, default in DEFAULT_CONFIG.items():
        raw = os.environ.get(key)
        if raw is None:
            continue
        if isinstance(default, bool):
            settings[key] = raw.strip().lower() in {"1", "true", "yes", "on"}
        elif isinstance(default, int | float):
            try:
                settings[key] = type(default)(raw)
            except ValueError as err:
                raise ValueError(f"Environment variable {key} must be a number, got {raw!r}.") from err
        else:
            settings[key] = raw
    return settings


def _thresholds_from_config(config: Mapping[str, Any]) -> AdviceThresholds:
    """Build the advice thresholds from the resolved ``ADVICE_*`` settings.

    Raises:
        InvalidGameParamsError: If the settings break a threshold ordering (also a ValueError).
    """
    return AdviceThresholds(
        small_fraction=float(config["ADVICE_SMALL_FRACTION"]),
        large_fraction=float(config["ADVICE_LARGE_FRACTION"]),
        all_in_fraction=float(config["ADVICE_ALL_IN_FRACTION"]),
        min_edge_ratio=float(config["ADVICE_MIN_EDGE_RATIO"]),
        all_in_min_equity=float(config["ADVICE_ALL_IN_MIN_EQUITY"]),
        large_min_equity=float(config["ADVICE_LARGE_MIN_EQUITY"]),
        value_equity_floor=float(config["ADVICE_VALUE_EQUITY_FLOOR"]),
        bluff_equity_ceiling=float(config["ADVICE_BLUFF_EQUITY_CEILING"]),
        fold_step=float(config["ADVICE_FOLD_STEP"]),
    )


def _services() -> Services:
    services: Services = current_app.extensions["lieng"]
    return services


# --------------------------------------------------------------------------------------------
# Errors: one JSON shape everywhere
# --------------------------------------------------------------------------------------------
_HTTP_CODES: Final[dict[int, str]] = {
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    429: "rate_limited",
}


def _error(message: str, code: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message, "code": code}), status


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(InvalidGameParamsError)
    def handle_invalid_params(err: InvalidGameParamsError) -> tuple[Response, int]:
        return _error(str(err), "invalid_params", 400)

    @app.errorhandler(InvalidCardError)
    @app.errorhandler(InvalidHandSizeError)
    def handle_invalid_hand(err: Exception) -> tuple[Response, int]:
        return _error(str(err), "invalid_hand", 400)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException) -> tuple[Response, int]:
        status = err.code or 500
        message = err.description or err.name
        if status == 429:
            message = f"Too many analysis requests (limit: {message}). Wait a moment, then try again."
        return _error(message, _HTTP_CODES.get(status, "http_error"), status)

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception) -> tuple[Response, int]:
        # Log the details for the operator; never send internals to the client.
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)
        return _error("Internal server error.", "internal_error", 500)


# --------------------------------------------------------------------------------------------
# Request parsing
# --------------------------------------------------------------------------------------------
def _request_body() -> Json:
    """The JSON body as a dict. No body means "use the defaults"; anything else must be a JSON object."""
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data():
            raise InvalidGameParamsError("The request body must be valid JSON (Content-Type: application/json).")
        return {}
    if not isinstance(data, dict):
        raise InvalidGameParamsError("The request body must be a JSON object.")
    return data


def _number(data: Json, name: str, default: float, *aliases: str) -> float:
    """Read a finite number (int, float or numeric string), falling back to ``default``."""
    value: Any = default
    for key in (name, *aliases):
        if key in data:
            value = data[key]
            break
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise InvalidGameParamsError(f"{name} must be a number.")
    try:
        number = float(value)
    except ValueError as err:
        raise InvalidGameParamsError(f"{name} must be a number, got {value!r}.") from err
    if not math.isfinite(number):
        raise InvalidGameParamsError(f"{name} must be a finite number, got {value!r}.")
    return number


def _reject_removed_fields(data: Json) -> None:
    """Fail loudly on request fields this version no longer accepts, naming the replacement.

    Raises:
        InvalidGameParamsError: If the body carries a removed field (→ 400 invalid_params).
    """
    for field, replacement in REMOVED_REQUEST_FIELDS.items():
        if field in data:
            raise InvalidGameParamsError(replacement)


def _parse_game_params(data: Json) -> GameParams:
    """Parse and validate pot, bet size, fold equity, and opponent model from a request body.

    Missing fields take the documented defaults; ``bet`` is still accepted for ``bet_size``.
    ``fold_equity`` is the single opponent assumption — the calling range is derived from it.

    Raises:
        InvalidGameParamsError: If any parameter is not a valid value or out of bounds, or if the
            body carries a field removed by the caller-range unification.
    """
    _reject_removed_fields(data)
    pot = _number(data, "pot", DEFAULT_POT)
    bet_size = _number(data, "bet_size", DEFAULT_BET_SIZE, "bet")
    fold_equity = _number(data, "fold_equity", DEFAULT_FOLD_EQUITY)

    if pot <= 0 or bet_size <= 0:
        raise InvalidGameParamsError("Pot and bet_size must be strictly greater than zero.")
    if not (0.0 <= fold_equity <= 1.0):
        raise InvalidGameParamsError("Fold equity must be between 0.0 and 1.0.")

    try:
        opponent_model = OpponentModel(data.get("opponent_model", OpponentModel.RANDOM.value))
    except ValueError as err:
        choices = ", ".join(m.value for m in OpponentModel)
        raise InvalidGameParamsError(f"opponent_model must be one of: {choices}.") from err

    return GameParams(pot, bet_size, fold_equity, opponent_model)


def _parse_hand(data: Json, *, required: bool) -> Hand | None:
    """Parse the optional ``hand`` field ("As Kh Qd").

    Raises:
        InvalidGameParamsError: If the field is missing but required, or is not a string.
        InvalidCardError / InvalidHandSizeError: If the text is not a valid hand (→ invalid_hand).
    """
    value = data.get("hand")
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise InvalidGameParamsError("Field 'hand' is required.")
        return None
    if not isinstance(value, str):
        raise InvalidGameParamsError("Field 'hand' must be a string such as 'As Kh Qd'.")
    return Hand.from_str(value.strip())


# --------------------------------------------------------------------------------------------
# Computation shared by the endpoints
# --------------------------------------------------------------------------------------------
def _sensitivity_payload(sensitivity: Sensitivity) -> Json:
    """Project the assumption stress grid into the API vocabulary."""
    percentiles = [
        scenario.call_range_percent
        for scenario in sensitivity.scenarios
        if scenario.call_range_percent is not None
    ]
    return {
        "fold_equity_range": list(sensitivity.fold_equity_range),
        "call_range_percent_range": (
            [min(percentiles), max(percentiles)] if percentiles else None
        ),
        "central_equity_when_called": sensitivity.central_equity_when_called,
        "status": sensitivity.status.value,
        "scenarios": [
            {
                "fold_equity": scenario.fold_equity,
                "call_range_percent": scenario.call_range_percent,
                "equity_when_called": scenario.equity_when_called,
                "ev": scenario.ev,
            }
            for scenario in sensitivity.scenarios
        ],
    }


def _rung_payload(rung: Rung) -> Json:
    """One ladder row, with the blocker as a string so the UI can say why a size is refused."""
    return {
        "action": rung.action.value,
        "amount": rung.amount,
        "ev": rung.ev,
        "ev_ratio": rung.ev_ratio,
        "worst_ev_ratio": rung.worst_ev_ratio,
        "robust": rung.robust,
        "eligible": rung.eligible,
        "blocked_by": rung.blocked_by.value if rung.blocked_by is not None else None,
    }


def _advice_payload(advice: Recommendation) -> Json:
    """Project the recommendation into the API vocabulary."""
    return {
        "action": advice.action.value,
        "kind": advice.kind.value,
        "reason": advice.reason.value,
        "amount": advice.amount,
        "ev": advice.ev,
        "ev_ratio": advice.ev_ratio,
        "equity_when_called": advice.equity_when_called,
        "win_rate_defined": advice.win_rate_defined,
        "robust": advice.robust,
        "why": {
            "fold_component": advice.why.fold_component,
            "call_component": advice.why.call_component,
            "net": advice.why.net,
        },
        "ladder": [_rung_payload(rung) for rung in advice.ladder],
    }


def _sizing_payload(thresholds: AdviceThresholds, pot: float) -> Json:
    """The effective policy numbers, so the UI never hard-codes a threshold or a rung size."""
    return {
        "small_fraction": thresholds.small_fraction,
        "large_fraction": thresholds.large_fraction,
        "all_in_fraction": thresholds.all_in_fraction,
        "min_edge_ratio": thresholds.min_edge_ratio,
        "all_in_min_equity": thresholds.all_in_min_equity,
        "large_min_equity": thresholds.large_min_equity,
        "value_equity_floor": thresholds.value_equity_floor,
        "bluff_equity_ceiling": thresholds.bluff_equity_ceiling,
        "fold_step": thresholds.fold_step,
        "all_in_size": ladder(pot, thresholds)[2],
    }


def _hand_payload(
    solution: HandSolution,
    stats: HandStats,
    equities: OpponentEquities,
    sensitivity: Sensitivity | None,
    params: GameParams,
) -> Json:
    """The hand-evaluation fields, identical in /api/solve and /api/evaluate.

    ``showdown_equity``, ``ev`` and ``advice`` are the 455-class table row's stored values, so the
    verdict card and the table can never disagree. ``ev`` stays the EV at the caller's ``bet_size``;
    ``advice.ev`` is the EV of the size the policy recommends. ``call_range_percent`` is derived from
    ``fold_equity`` (null under the random model).

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


def _action_counts(records: Sequence[HandEVRecord]) -> Json:
    """How many canonical classes each action covers, in ladder order."""
    counts: Json = {action.value: 0 for action in Action}
    for record in records:
        counts[record.advice.action.value] += 1
    return counts


def _solve(services: Services, params: GameParams) -> tuple[OpponentEquities, list[HandEVRecord], Json]:
    """Score all 455 classes from one equity source; return it, the records, and the summary."""

    equities = services.range_finder.equities(params.fold_equity, params.opponent_model)
    records = services.range_finder.solve_range(
        params.pot, params.bet_size, equities, services.advice_thresholds
    )
    profitable = [r for r in records if r.is_raise_profitable]
    betting = [r for r in records if r.advice.action is not Action.CHECK]
    summary: Json = {
        "pot": params.pot,
        "bet_size": params.bet_size,
        "fold_equity": params.fold_equity,
        "opponent_model": params.opponent_model.value,
        "call_range_percent": equities.calling_percentile,
        "final_pot": final_pot(params.pot, params.bet_size),
        "pure_bluff_break_even_fold_equity": calculate_break_even_fold_equity(params.pot, params.bet_size, 0.0),
        "total_canonical_classes": len(records),
        "profitable_classes": len(profitable),
        "total_combinations": TOTAL_COMBINATIONS,
        "profitable_combinations": sum(r.multiplicity for r in profitable),
        "range_coverage_percent": services.range_finder.calculate_range_coverage(profitable),
        "action_counts": _action_counts(records),
        "bet_recommended_percent": round(
            sum(r.multiplicity for r in betting) / TOTAL_COMBINATIONS * 100.0, 2
        ),
        "bet_ladder": list(ladder(params.pot, services.advice_thresholds)),
        "sizing": _sizing_payload(services.advice_thresholds, params.pot),
        "highest_ev_hand": records[0].canonical_id if records else None,
        "highest_ev_value": records[0].ev if records else None,
        "threshold_hand": profitable[-1].canonical_id if profitable else None,
        "threshold_ev_value": profitable[-1].ev if profitable else None,
        "category_breakdown": [
            {
                "category": row.category.name,
                "classes": row.classes,
                "combos": row.combos,
                "profitable_combos": row.profitable_combos,
            }
            for row in category_breakdown(records)
        ],
    }
    return equities, records, summary


def _evaluate_hand(
    services: Services,
    hand: Hand,
    params: GameParams,
    equities: OpponentEquities,
    records: Sequence[HandEVRecord],
) -> tuple[HandSolution, Sensitivity]:
    """Answer one hand from the table and stress its assumption grid."""
    solution = services.range_finder.hand_solution(hand, records, equities, params.pot, params.bet_size)
    sensitivity = stress_test(
        equities,
        services.calling_model,
        solution.record.canonical_id,
        params.pot,
        params.bet_size,
    )
    return solution, sensitivity


def _top_hands_payload(records: Sequence[HandEVRecord]) -> list[Json]:
    """The best hands by EV, in the same shape for /api/solve and /api/range."""
    return [
        {
            "canonical_id": r.canonical_id,
            "category": r.category.name,
            "showdown_equity": r.equity,
            "ev": r.ev,
            "multiplicity": r.multiplicity,
            "action": r.advice.action.value,
            "kind": r.advice.kind.value,
            "amount": r.advice.amount,
        }
        for r in records[:TOP_HANDS_LIMIT]
    ]


# --------------------------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------------------------
@api.get("/")
def root() -> Response:
    """Service metadata."""
    return jsonify({
        "service": "Lieng Stealer API",
        "status": "online",
        "endpoints": ["/health", "/api/solve", "/api/evaluate", "/api/range", "/api/analyze"],
    })


@api.get("/health")
def health_check() -> Response:
    """System status and database stats."""
    db = _services().db
    return jsonify({
        "status": "healthy",
        "database_loaded": db.is_loaded,
        "classes_loaded": len(db),
        "version": API_VERSION,
    })


def _hand_fields(
    services: Services,
    hand: Hand,
    params: GameParams,
    equities: OpponentEquities,
    records: Sequence[HandEVRecord],
) -> tuple[Json, HandSolution]:
    """The hand payload plus the domain solution it was projected from."""
    solution, sensitivity = _evaluate_hand(services, hand, params, equities, records)
    stats = services.db.get(solution.record.canonical_id)
    return _hand_payload(solution, stats, equities, sensitivity, params), solution


@api.post("/api/solve")
def solve_api() -> Response:
    """Rank all 455 hands and, if ``hand`` is given, evaluate that hand too.

    JSON body (all optional): pot (> 0), bet_size (> 0), fold_equity in [0, 1],
    opponent_model ('random' default, or 'range'), hand (e.g. 'As Kh Qd'). A blank or missing
    hand is legal: the answer is then the range itself.
    """
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=False)

    equities, records, summary = _solve(services, params)
    hand_evaluation = _hand_fields(services, hand, params, equities, records)[0] if hand else None
    return jsonify({
        "summary": summary,
        "hand_evaluation": hand_evaluation,
        "top_hands": _top_hands_payload(records),
    })


@api.post("/api/evaluate")
def evaluate_api() -> Response:
    """Evaluate a single 3-card hand (``hand`` required) against the game parameters."""
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=True)
    assert hand is not None  # required=True never returns None

    equities, records, _summary = _solve(services, params)
    return jsonify({
        "pot": params.pot,
        "bet_size": params.bet_size,
        "fold_equity": params.fold_equity,
        "opponent_model": params.opponent_model.value,
        **_hand_fields(services, hand, params, equities, records)[0],
    })


@api.post("/api/range")
def range_api() -> Response:
    """The range summary and the best hands, without a specific hand."""
    services = _services()
    params = _parse_game_params(_request_body())
    equities, records, summary = _solve(services, params)
    return jsonify({**summary, "top_hands": _top_hands_payload(records)})


@analysis.post("/api/analyze")
def analyze_api() -> Response | tuple[Response, int]:
    """Strategic commentary for the same inputs as /api/solve.

    The server recomputes every number itself; only validated values (numbers and the parsed
    hand) reach the prompt. Without OPENROUTER_API_KEY a rule-based answer is returned instead.
    """
    services = _services()
    data = _request_body()
    params = _parse_game_params(data)
    hand = _parse_hand(data, required=False)

    equities, records, summary = _solve(services, params)
    coverage = float(summary["range_coverage_percent"])
    solution: HandSolution | None = None
    sensitivity: Sensitivity | None = None
    if hand is not None:
        solution, sensitivity = _evaluate_hand(services, hand, params, equities, records)

    api_key = str(current_app.config["OPENROUTER_API_KEY"])
    if not api_key:
        return jsonify({
            "advice": _fallback_advice(params, summary, solution, equities),
            "model": FALLBACK_MODEL_NAME,
        })

    model = str(current_app.config["OPENROUTER_MODEL"])
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/lieng-stealer",
                "X-Title": "Lieng Stealer Solver",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a professional game theory analyst specializing in Vietnamese card games like Liêng."},
                    {"role": "user", "content": _build_prompt(params, coverage, solution, sensitivity, equities)},
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=float(current_app.config["OPENROUTER_TIMEOUT"]),
        )
    except requests.RequestException:
        current_app.logger.exception("OpenRouter request failed")
        return _error("Could not reach the AI analysis service.", "upstream_error", 502)

    if resp.status_code != 200:
        current_app.logger.warning("OpenRouter returned %s: %.500s", resp.status_code, resp.text)
        return _error(f"The AI analysis service returned status {resp.status_code}.", "upstream_error", 502)
    try:
        advice = resp.json()["choices"][0]["message"]["content"]
        if not isinstance(advice, str):
            raise TypeError("content is not a string")
    except (ValueError, KeyError, IndexError, TypeError):
        current_app.logger.exception("Unexpected OpenRouter response: %.500s", resp.text)
        return _error("The AI analysis service sent an unexpected response.", "upstream_error", 502)
    return jsonify({"advice": advice, "model": model})


def _model_line(params: GameParams, equities: OpponentEquities) -> str:
    if params.opponent_model is OpponentModel.RANGE:
        percentile = equities.calling_percentile
        assert percentile is not None  # RANGE always has a calling range
        return f"folds their weakest hands (calls only with the top {percentile:.1f}%)"
    return "folds at random, regardless of hand strength"


def _advice_line(advice: Recommendation) -> str:
    """The recommendation as one English line, for the prompt and the offline answer."""
    return (
        f"{advice.action.value} ({advice.kind.value}) for {advice.amount:,.0f} VND, "
        f"worth {advice.ev:+,.0f} VND at your fold assumption"
    )


def _build_prompt(
    params: GameParams,
    coverage: float,
    solution: HandSolution | None,
    sensitivity: Sensitivity | None,
    equities: OpponentEquities,
) -> str:
    """The LLM prompt, built only from server-computed values."""
    prompt = (
        f"You are a World-Class Game Theory Expert and High-Stakes Vietnamese Liêng Solver.\n"
        f"Analyze this decision spot with precision and strategic depth in Vietnamese:\n\n"
        f"- Current Pot: {params.pot:,.0f} VND\n"
        f"- Bet / Raise Size: {params.bet_size:,.0f} VND\n"
        f"- Opponent Fold Equity: {params.fold_equity * 100:.1f}%\n"
        f"- Opponent Model: {_model_line(params, equities)}\n"
        f"- Random-opponent range coverage (hands with EV > 0): {coverage}%\n"
    )
    if solution is not None:
        record = solution.record
        advice = record.advice
        chosen_worst = (
            advice.ladder[0].worst_ev_ratio
            if advice.action is Action.CHECK
            else next(rung.worst_ev_ratio for rung in advice.ladder if rung.action is advice.action)
        )
        prompt += (
            f"- Hero's Hand: {solution.hand} ({solution.hand.score})\n"
            f"- Showdown Equity: {record.equity * 100:.1f}%\n"
            f"- Calculated EV at {params.bet_size:,.0f} VND: {record.ev:+,.0f} VND\n"
            f"- Solver Advice: {_advice_line(advice)}; reason {advice.reason.value}\n"
            f"- Why: {advice.why.fold_component:+,.0f} VND comes from folds, "
            f"{advice.why.call_component:+,.0f} VND from the showdown when called\n"
            f"- Assumption stress: the recommended bet earns at worst {chosen_worst * 100:.1f}% "
            f"of the pot one fold step away\n"
        )
        percentile = equities.calling_percentile
        if percentile is not None:
            prompt += (
                f"- Caller range: strongest {percentile:.1f}% of legal hands\n"
                f"- Assumption sensitivity: {sensitivity.status.value if sensitivity is not None else 'unavailable'}\n"
            )
    else:
        prompt += "- Hero's Hand: None (General Range Analysis)\n"
    return prompt + (
        "\nProvide a structured breakdown:\n"
        "1. [Quyết định Toán học & EV]: Phân tích EV, Fold Equity và ngưỡng hòa vốn.\n"
        "2. [Chiến thuật Bluff & Giá trị]: Hero có nên Tố (Raise)/Tất tay hay Check/Bỏ bài? Giải thích tâm lý đối thủ.\n"
        "3. [Lời khuyên chiến thuật]: Nhận xét ngắn gọn về độ rủi ro và cách khai thác đối thủ."
    )


# One sentence per reason code, in Vietnamese, interpolated from the advice's own fields.
_REASON_TEXT: Final[dict[Reason, str]] = {
    Reason.CHECK_NO_EDGE: "Mọi mức cược đều lỗ ở giả định bỏ bài này, nên không cược là tối ưu.",
    Reason.CHECK_EDGE_TOO_SMALL: "Cược chỉ lãi {edge:.1f}% pot, dưới mức {min_edge:.0f}% cần có, nên không cược.",
    Reason.CHECK_ASSUMPTION_FRAGILE: (
        "Cược nhỏ có vẻ có lãi nhưng chỉ khi đối thủ bỏ bài đúng như dự đoán; "
        "ở ô xấu nhất chỉ còn {worst:.1f}% pot."
    ),
    Reason.SMALL_BLUFF: (
        "Cược hù nhỏ: lãi {edge:.1f}% pot nhưng tỷ lệ thắng chỉ {equity:.1f}%, nên chỉ cược mức nhỏ nhất."
    ),
    Reason.SMALL_THIN: "Gần cân kèo khi bị theo ({equity:.1f}%), nên giữ pot nhỏ: lãi {edge:.1f}% pot.",
    Reason.SMALL_VALUE: (
        "Bài mạnh ({equity:.1f}% khi bị theo) nhưng cược lớn hơn sẽ hết lãi nếu bị theo chặt hơn; "
        "cược nhỏ lãi {edge:.1f}% pot."
    ),
    Reason.LARGE_THIN: "Cược lớn với giá trị mỏng, chỉ nhỉnh hơn khi bị theo ({equity:.1f}%): lãi {edge:.1f}% pot.",
    Reason.LARGE_VALUE: (
        "Cược lớn: khi bị theo vẫn mạnh hơn ({equity:.1f}%), lãi {edge:.1f}% pot, nhưng chưa đủ để tất tay."
    ),
    Reason.ALL_IN_VALUE: (
        "Tất tay: thắng {equity:.1f}% khi bị theo, lãi {edge:.1f}% pot ngay cả khi đối thủ bỏ ít hơn 10%."
    ),
}


def _fallback_advice(
    params: GameParams,
    summary: Json,
    solution: HandSolution | None,
    equities: OpponentEquities,
) -> str:
    """Rule-based commentary (Vietnamese) used when no OpenRouter key is configured.

    Every number the solver decided is quoted from the payload, so the offline answer and the card
    say the same thing.
    """
    pot, bet_size, fold_equity = params.pot, params.bet_size, params.fold_equity
    coverage = summary["range_coverage_percent"]
    counts = summary["action_counts"]
    bluff_break_even = calculate_break_even_fold_equity(pot, bet_size, 0.0)
    advice = (
        f"**[Phân Tích Chiến Thuật Hệ Thống (Offline Solver)]**\n\n"
        f"1. **Quyết định Toán học:** Với Pot = {pot:,.0f}, Cược = {bet_size:,.0f}, và Fold Equity = {fold_equity*100:.1f}%, "
        f"ngưỡng hòa vốn cược hù (bluff) là {bluff_break_even*100:.1f}%. "
        f"Khoảng bài có lãi (EV > 0) chiếm **{coverage}%** toàn bộ thế bài có thể có. "
        f"Khuyến nghị cược cho {summary['bet_recommended_percent']}% thế bài: "
        f"tất tay {counts['ALL_IN']} nhóm, cược lớn {counts['LARGE_BET']}, cược nhỏ {counts['SMALL_BET']}, "
        f"không cược {counts['CHECK']}. "
        + ("Giả định đối thủ bỏ những bài yếu nhất, nên khi bị theo, Hero đối đầu với nhóm bài mạnh hơn.\n\n"
           if params.opponent_model is OpponentModel.RANGE
           else "Giả định đối thủ bỏ bài ngẫu nhiên, không phụ thuộc độ mạnh của bài.\n\n")
        + "2. **Hành động Khuyến nghị:** "
    )
    if solution is None:
        return advice + (
            f"Với tần suất đối thủ bỏ bài {fold_equity*100:.1f}%, chỉ nên tất tay với nhóm bài thắng "
            f"ít nhất 85% khi bị theo; cược lớn cần thắng trên 50%; các nhóm còn lại chỉ cược nhỏ hoặc không cược."
        )
    record = solution.record
    advice_rec = record.advice
    percentile = equities.calling_percentile
    caller_model = (
        f" Equity is versus the strongest {percentile:.1f}% of legal hands."
        if percentile is not None
        else ""
    )
    ladder_text = "; ".join(
        f"{rung.action.value} {rung.amount:,.0f} = {rung.ev:+,.0f}"
        + ("" if rung.eligible else f" (loại: {rung.blocked_by.value if rung.blocked_by else 'n/a'})")
        for rung in advice_rec.ladder
    )
    return advice + (
        f"Hero cầm **{solution.hand}** ({solution.hand.score}) "
        f"với xác suất thắng đối đầu {record.equity*100:.1f}%.{caller_model} "
        f"Khuyến nghị tối ưu: **{advice_rec.action.value}** ({advice_rec.kind.value}) "
        f"cược **{advice_rec.amount:,.0f} VND**, kỳ vọng **{advice_rec.ev:+,.0f} VND** "
        f"(gồm {advice_rec.why.fold_component:+,.0f} từ fold equity và "
        f"{advice_rec.why.call_component:+,.0f} từ showdown). "
        f"Thang cược: {ladder_text}.\n\n"
        f"3. **Nhận định chiến thuật:** {_reason_sentence(advice_rec, summary)}"
    )


def _reason_sentence(advice: Recommendation, summary: Json) -> str:
    """One Vietnamese sentence for the reason code, from the advice's numbers and the policy."""
    # A check's own ev_ratio is zero, so its reasons quote the best rung the ladder priced.
    edge = advice.ev_ratio if advice.action is not Action.CHECK else max(rung.ev_ratio for rung in advice.ladder)
    return _REASON_TEXT[advice.reason].format(
        edge=edge * 100.0,
        worst=advice.ladder[0].worst_ev_ratio * 100.0,
        ev=advice.ev,
        equity=advice.equity_when_called * 100.0,
        min_edge=summary["sizing"]["min_edge_ratio"] * 100.0,
    )


app = create_app()


if __name__ == "__main__":
    # Listen on this machine only unless HOST says otherwise (e.g. HOST=0.0.0.0 to share on a LAN).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False)
