import { useState, useEffect, useEffectEvent, useRef } from 'react';
import './App.css';
import { STRINGS, LANGUAGES } from './i18n.js';
import { formatMoney, formatZones } from './format.js';

// Empty by default: requests go to /api on the page's own origin, which the Vite dev server
// proxies to Flask (vite.config.js). Set VITE_API_URL at build time when the API lives elsewhere.
const API_BASE = import.meta.env.VITE_API_URL ?? "";
const LANG_STORAGE_KEY = "lieng-scope-lang";

// Steppers move money fields by 10k and never go below 1k.
const AMOUNT_STEP = 10000;
const MIN_AMOUNT = 1000;

const POT_PRESETS = [50000, 100000, 200000, 500000];
const BET_PRESET_MULTIPLES = [0.33, 0.75, 1];
const HAND_PRESETS = [
  { cards: "As Kh Qd", labelKey: "presetLiengQKA" },
  { cards: "7s 7h 7d", labelKey: "presetSap7" },
  { cards: "Js Qh Kd", labelKey: "presetLiengJQK" },
  { cards: "9s 10h Kd", labelKey: "presetDiem9" },
  { cards: "2s 3h 5d", labelKey: "presetDiem0" },
];

// Backend category enum -> display label and i18n description key
const CATEGORY_LABELS = { SAP: "SÁP", LIENG: "LIÊNG", DI: "ĐĨ", DIEM: "ĐIỂM" };
const CATEGORY_DESC_KEYS = { SAP: "descSap", LIENG: "descLieng", DI: "descDi", DIEM: "descDiem" };

// Advice kind -> colour class. Colour names the kind of hand, never whether the advice is "good":
// a bluff is a legitimate play.
const KIND_CLASSES = {
  VALUE: "kind-value",
  THIN_VALUE: "kind-thin",
  BLUFF: "kind-bluff",
  NONE: "kind-none",
};

const percent = (value) => `${(value * 100).toFixed(1)}%`;
const wholePercent = (value) => `${Math.round(value * 100)}%`;
const signedMoney = (value, locale) => `${value > 0 ? "+" : ""}${formatMoney(value, locale)}`;

// The sentence that explains the recommendation. Every number is the response's own: a check's
// `ev` is 0 by definition, so its reasons quote the rung the ladder priced best.
function whyLine(t, advice, summary) {
  const { sizing, fold_equity: foldEquity, pot } = summary;
  const money = (value) => signedMoney(value, t.locale);
  const equity = advice.win_rate_defined ? percent(advice.equity_when_called) : t.winRateUndefined;
  const fold = wholePercent(foldEquity);
  const worstFold = wholePercent(Math.max(0, foldEquity - sizing.fold_step));
  const foldStep = Math.round(sizing.fold_step * 100);
  const best = advice.ladder.reduce((a, rung) => (rung.ev_ratio > a.ev_ratio ? rung : a));
  const small = advice.ladder[0];

  switch (advice.reason) {
    case "ALL_IN_VALUE":
      return t.whyAllInValue(equity, foldStep);
    case "LARGE_VALUE":
      return t.whyLargeValue(equity);
    case "LARGE_THIN":
      return t.whyLargeThin(equity);
    case "SMALL_VALUE":
      return t.whySmallValue(`${formatMoney(advice.amount, t.locale)} ${t.currency}`);
    case "SMALL_THIN":
      return t.whySmallThin(equity);
    case "SMALL_BLUFF":
      return t.whySmallBluff(money(advice.ev), equity);
    case "CHECK_NO_EDGE":
      return t.whyCheckNoEdge(fold);
    case "CHECK_EDGE_TOO_SMALL":
      return t.whyCheckEdgeTooSmall(
        money(best.ev),
        percent(best.ev_ratio),
        wholePercent(sizing.min_edge_ratio)
      );
    case "CHECK_ASSUMPTION_FRAGILE":
      return t.whyCheckFragile(money(small.ev), fold, money(small.worst_ev_ratio * pot), worstFold);
  }
}

function loadSavedLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return LANGUAGES.includes(saved) ? saved : "en";
  } catch {
    return "en";
  }
}

// Map a failed /api/solve response to the message shown under the button ({ key, detail }).
// The API answers every error with { error, code }. A response without a code did not come from
// Flask (e.g. the dev proxy's 502, or a 404 from the wrong server), so the solver isn't reachable.
function solveErrorFor(body) {
  if (!body.code) return { key: "solverOffline" };
  if (body.code === "invalid_hand") return { key: "invalidHand", detail: body.error };
  if (body.code === "invalid_params") return { key: "invalidParams", detail: body.error };
  return { key: "serverError" };
}

// One solve + analysis round trip. It holds no state: it reports each step through the callbacks
// and stops calling them as soon as `signal` is aborted (a newer run started, or the page unmounted).
async function fetchSolveAndAnalysis(body, signal, { onSolved, onSolveFailed, onAnalysis }) {
  const post = (path) =>
    fetch(`${API_BASE}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body, signal });

  let solveJson;
  try {
    const solveRes = await post("/api/solve");
    if (signal.aborted) return;
    if (!solveRes.ok) {
      const errorBody = await solveRes.json().catch(() => ({}));
      if (!signal.aborted) onSolveFailed(solveErrorFor(errorBody));
      return;
    }
    try {
      solveJson = await solveRes.json();
    } catch {
      if (!signal.aborted) onSolveFailed({ key: "badResponse" });
      return;
    }
  } catch {
    if (!signal.aborted) onSolveFailed({ key: "solverOffline" });
    return;
  }
  if (signal.aborted) return;
  onSolved(solveJson);

  // The server recomputes everything for the analysis from the same inputs.
  let advice;
  try {
    const analyzeRes = await post("/api/analyze");
    if (signal.aborted) return;
    if (analyzeRes.ok) {
      const analyzeJson = await analyzeRes.json();
      advice = analyzeJson.advice ? { text: analyzeJson.advice, model: analyzeJson.model } : { key: "aiNoAdvice" };
    } else {
      advice = { key: analyzeRes.status === 429 ? "aiRateLimited" : "aiUnreachable" };
    }
  } catch (aiErr) {
    advice = { key: "aiTransportFault", detail: aiErr.message };
  }
  if (!signal.aborted) onAnalysis(advice);
}

function Stepper({ id, label, value, onChange }) {
  return (
    <div className="input-wrapper stepper">
      <button
        type="button"
        className="stepper-btn"
        aria-label={`${label} −${AMOUNT_STEP / 1000}k`}
        onClick={() => onChange(Math.max(MIN_AMOUNT, value - AMOUNT_STEP))}
      >
        −
      </button>
      <input
        id={id}
        type="number"
        className="input-field"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        step={AMOUNT_STEP}
        min={MIN_AMOUNT}
      />
      <button
        type="button"
        className="stepper-btn"
        aria-label={`${label} +${AMOUNT_STEP / 1000}k`}
        onClick={() => onChange(value + AMOUNT_STEP)}
      >
        +
      </button>
    </div>
  );
}

export default function App() {
  const [lang, setLang] = useState(loadSavedLang);
  const t = STRINGS[lang];

  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);
  const [opponentModel, setOpponentModel] = useState("range");

  // Both start true: the first solve begins as soon as the page mounts.
  const [isLoading, setIsLoading] = useState(true);
  const [isAiLoading, setIsAiLoading] = useState(true);
  const [solveData, setSolveData] = useState(null);
  // { text, model } from the server, or { key, detail } for a client-side notice translated at render
  const [aiAdvice, setAiAdvice] = useState(null);
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  // { key, detail } translated at render, or null
  const [solveError, setSolveError] = useState(null);
  // The AbortController of the run in progress, so a newer run can cancel it
  const currentRun = useRef(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      // Storage unavailable (e.g. private mode): the choice just won't persist.
    }
  }, [lang]);

  // Start one run with the current inputs; every state change happens in a callback, after the
  // matching response has arrived. The API takes one opponent assumption: fold_equity. The
  // calling range the UI shows next to it is derived from that same number, never sent.
  const runSolve = (controller) => {
    const body = JSON.stringify({
      pot: Number(pot),
      bet_size: Number(betSize),
      fold_equity: Number(foldEquity),
      hand: hand.trim(),
      opponent_model: opponentModel,
    });
    fetchSolveAndAnalysis(body, controller.signal, {
      onSolved: (data) => {
        setSolveError(null);
        setSolveData(data);
        setIsLoading(false);
      },
      onSolveFailed: (error) => {
        // Clear the old results: they belong to different inputs than the ones on screen now.
        setSolveError(error);
        setSolveData(null);
        setAiAdvice(null);
        setIsLoading(false);
        setIsAiLoading(false);
      },
      onAnalysis: (advice) => {
        setAiAdvice(advice);
        setIsAiLoading(false);
      },
    });
  };

  // Start a run from a click: cancel any run still in flight, then show the loading state.
  const startSolve = () => {
    currentRun.current?.abort();
    const controller = new AbortController();
    currentRun.current = controller;
    setIsLoading(true);
    setIsAiLoading(true);
    setSolveError(null);
    runSolve(controller);
  };

  // The first run on mount. It reads the current inputs without making them effect dependencies.
  const startFirstRun = useEffectEvent((controller) => {
    currentRun.current = controller;
    runSolve(controller);
  });

  useEffect(() => {
    const controller = new AbortController();
    startFirstRun(controller);
    // In development StrictMode mounts twice; aborting here cancels the first, duplicate request.
    return () => controller.abort();
  }, []);

  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const advice = handEval?.advice;
  const actionCounts = summary?.action_counts;

  const zones = handEval?.profitable_fold_zones;

  // The API's single opponent assumption is fold_equity; the calling range is derived from it, so
  // the second slider only displays the value that fold rate implies.
  const callingRangePercent = Math.round((1 - foldEquity) * 100);

  // Category Matrix Statistics (computed by the solver per category)
  const categoryMatrix = (summary?.category_breakdown || []).map((row) => ({
    ...row,
    pct: ((row.profitable_combos / row.combos) * 100).toFixed(1),
  }));

  return (
    <div className="terminal-container">
      <header className="terminal-header">
        <div>
          <h1 className="terminal-title">LIÊNG SCOPE</h1>
          <p className="terminal-subtitle">{t.subtitle}</p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="lang-toggle"
            onClick={() => setLang((cur) => (cur === "en" ? "vi" : "en"))}
            aria-label={t.langToggleLabel}
            title={t.langToggleLabel}
          >
            {LANGUAGES.map((code) => (
              <span key={code} className={`lang-option ${lang === code ? "active" : ""}`}>
                {code.toUpperCase()}
              </span>
            ))}
          </button>
        </div>
      </header>

      <main className="terminal-grid">
        {/* Left column: inputs */}
        <section className="control-panel">
          <div className="panel-header">
            <h2 className="panel-tag">{t.controlsTag}</h2>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="pot-input">{t.potLabel}</label>
            <Stepper id="pot-input" label={t.potLabel} value={pot} onChange={setPot} />
            <div className="preset-chips">
              {POT_PRESETS.map((v) => (
                <button
                  key={v}
                  type="button"
                  className={`preset-chip ${pot === v ? "active" : ""}`}
                  onClick={() => setPot(v)}
                >
                  {v / 1000}k
                </button>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="bet-input">{t.betLabel}</label>
            <Stepper id="bet-input" label={t.betLabel} value={betSize} onChange={setBetSize} />
            <div className="preset-chips">
              {BET_PRESET_MULTIPLES.map((multiple) => {
                const amount = Math.round(pot * multiple);
                return (
                  <button
                    key={multiple}
                    type="button"
                    className={`preset-chip ${betSize === amount ? "active" : ""}`}
                    onClick={() => setBetSize(amount)}
                  >
                    {t.betPresetLabel(multiple.toLocaleString(t.locale, { minimumFractionDigits: 1 }))}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="form-group">
            <div className="slider-label-row">
              <label className="form-label" htmlFor="fold-input">{t.foldLabel}</label>
              <span className="slider-value-badge">{Math.round(foldEquity * 100)}%</span>
            </div>
            <input
              id="fold-input"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={foldEquity}
              onChange={(e) => setFoldEquity(parseFloat(e.target.value))}
              className="radar-slider"
            />
            <div className="slider-calibrations">
              <span>{t.foldMin}</span>
              <span>50%</span>
              <span>{t.foldMax}</span>
            </div>

            <div className="model-row">
              <span className="form-label model-label">{t.opponentFolds}</span>
              <div className="preset-chips model-chips" role="group" aria-label={t.opponentFolds}>
                {["range", "random"].map((model) => (
                  <button
                    key={model}
                    type="button"
                    className={`preset-chip ${opponentModel === model ? "active" : ""}`}
                    aria-pressed={opponentModel === model}
                    onClick={() => setOpponentModel(model)}
                  >
                    {model === "range" ? t.modelRange : t.modelRandom}
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <div className="slider-label-row">
                <label className="form-label" htmlFor="call-range-input">{t.callRangeLabel}</label>
                <span className="slider-value-badge">{callingRangePercent}%</span>
              </div>
              <input
                id="call-range-input"
                type="range"
                min="0"
                max="100"
                step="1"
                value={callingRangePercent}
                onChange={(e) => setFoldEquity(1 - Number(e.target.value) / 100)}
                className="radar-slider"
              />
              <div className="slider-calibrations">
                <span>0%</span>
                <span>{t.callRangeSub}</span>
                <span>100%</span>
              </div>
            </div>

            {zones && (
              <div className="profit-map">
                <span className="profit-map-label">{t.profitMap}</span>
                <div className="profit-map-bar">
                  {zones.map(([start, end]) => (
                    <span
                      key={start}
                      className="profit-zone"
                      style={{ left: `${Math.min(start, 0.99) * 100}%`, width: `${Math.max(end - start, 0.01) * 100}%` }}
                    />
                  ))}
                  <span className="profit-marker" style={{ left: `${foldEquity * 100}%` }} />
                </div>
              </div>
            )}
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="hand-input">{t.handLabel}</label>
            <div className="input-wrapper">
              <input
                id="hand-input"
                type="text"
                className="input-field"
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                placeholder={t.handPlaceholder}
              />
            </div>
            <div className="preset-chips">
              {HAND_PRESETS.map(({ cards, labelKey }) => (
                <button
                  key={cards}
                  type="button"
                  className={`preset-chip ${hand === cards ? "active" : ""}`}
                  onClick={() => setHand(cards)}
                >
                  {t[labelKey]}
                </button>
              ))}
            </div>
          </div>

          <button
            type="button"
            className="tactical-btn"
            onClick={startSolve}
            disabled={isLoading}
          >
            {isLoading ? t.solveBusy : t.solveIdle}
          </button>

          {solveError && (
            <div className="terminal-alert" role="alert">
              {t[solveError.key](solveError.detail)}
            </div>
          )}

          {/* Engine specs footnote */}
          <div className="specs-subcard">
            <div className="spec-row">
              <span>{t.specArchitecture}</span>
              <span className="spec-val">{t.specArchitectureVal}</span>
            </div>
            <div className="spec-row">
              <span>{t.specSpace}</span>
              <span className="spec-val">{t.specSpaceVal}</span>
            </div>
            <div className="spec-row">
              <span>{t.specQuery}</span>
              <span className="spec-val">{t.specQueryVal}</span>
            </div>
          </div>
        </section>

        {/* Right column: results */}
        <section className="results-container">
          {/* Verdict: what to do, how much, why, and why not the bigger bet */}
          {advice && (
            <div className={`verdict-card ${KIND_CLASSES[advice.kind]}`}>
              <div className="verdict-banner">
                <div>
                  <span className="verdict-label">{t.recommendedAction}</span>
                  <div className="verdict-title-row">
                    <h2 className="verdict-title">{t.actionLabel[advice.action]}</h2>
                    {advice.action !== "CHECK" && (
                      <span className="kind-chip">{t.kindLabel[advice.kind]}</span>
                    )}
                  </div>
                  <div className="verdict-meta">
                    <span className="holding-tag">{handEval.hand}</span>
                    <span className="holding-sep">·</span>
                    <span>{handEval.canonical_id}</span>
                    <span className="holding-sep">·</span>
                    <span className="holding-score">{handEval.score_name}</span>
                  </div>
                </div>

                <div className="verdict-col-right">
                  <span className="verdict-label">{t.expectedValueTag}</span>
                  <div className="verdict-ev">
                    {signedMoney(advice.ev, t.locale)} <span className="ev-currency">{t.currency}</span>
                  </div>
                  <div className="verdict-breakeven">{t.evAtRecommendedSize}</div>
                  {handEval.ev !== advice.ev && (
                    <div className="verdict-breakeven">
                      {t.evAtYourBetSize(`${signedMoney(handEval.ev, t.locale)} ${t.currency}`)}
                    </div>
                  )}
                  {zones && (
                    <div className="verdict-breakeven">
                      {t.profitableWhen} <span className="mono-green">{formatZones(zones)}</span>
                    </div>
                  )}
                  {handEval.sensitivity && (
                    <div className="verdict-breakeven">
                      {t.assumptionSensitivity(handEval.sensitivity.status)}
                    </div>
                  )}
                </div>
              </div>

              <p className="verdict-why">{whyLine(t, advice, summary)}</p>

              <div className="ladder-strip">
                {advice.ladder.map((rung) => (
                  <div
                    key={rung.action}
                    className={`ladder-rung${rung.action === advice.action ? " chosen" : ""}${
                      rung.eligible ? "" : " rung-blocked"
                    }`}
                  >
                    <div className="ladder-head">
                      <span className="ladder-mark">{rung.eligible ? "✓" : "✗"}</span>
                      <span className="ladder-label">{t.actionLabel[rung.action]}</span>
                    </div>
                    <div className="ladder-amount">
                      {formatMoney(rung.amount, t.locale)}{" "}
                      <span className="ev-currency">{t.currency}</span>
                    </div>
                    <div className="ladder-ev">
                      {t.evTag} {signedMoney(rung.ev, t.locale)}
                    </div>
                    {!rung.eligible && <div className="ladder-blocked">{t.blocked[rung.blocked_by]}</div>}
                  </div>
                ))}
              </div>

              <p className="ladder-note">
                {t.thresholdNote(
                  Math.round(summary.sizing.min_edge_ratio * 100),
                  Math.round(summary.sizing.fold_step * 100)
                )}
              </p>
            </div>
          )}

          {/* No hand entered: the range tables below still answer the question */}
          {solveData && !handEval && (
            <div className="verdict-banner verdict-empty" role="status">
              <div>
                <span className="verdict-label">{t.recommendedAction}</span>
                <h2 className="verdict-title">{t.noHandTitle}</h2>
                <div className="verdict-meta">{t.noHandBody}</div>
                {actionCounts && (
                  <p className="verdict-why">
                    {t.actionCountsLine(
                      actionCounts.ALL_IN,
                      actionCounts.LARGE_BET,
                      actionCounts.SMALL_BET,
                      actionCounts.CHECK
                    )}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Summary figures */}
          <div className="hud-metrics-grid">
            <div className="hud-card">
              <div>{t.betRecommended}</div>
              <div className="hud-value">
                {summary?.bet_recommended_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="hud-subtext">{t.combosWorthBet}</div>
            </div>

            <div className="hud-card">
              <div>{t.showdownEquity}</div>
              <div className={`hud-value ${advice?.win_rate_defined === false ? "hud-phrase" : ""}`}>
                {advice?.win_rate_defined === false
                  ? t.winRateUndefined
                  : handEval
                    ? percent(handEval.showdown_equity)
                    : t.notAvailable}
              </div>
              <div className="hud-subtext">
                {handEval && handEval.call_range_percent != null
                  ? `${t.vsCallingRange(Math.round(handEval.call_range_percent))} · ${t.vsRandomShort(
                      percent(handEval.equity_vs_random)
                    )}`
                  : handEval
                    ? t.showdownEquitySub
                    : t.notAvailable}
              </div>
            </div>

            <div className="hud-card">
              <div>{t.expectedValue}</div>
              <div className={`hud-value ${advice?.ev > 0 ? "green-metric" : ""}`}>
                {advice ? signedMoney(advice.ev, t.locale) : "0"}
              </div>
              <div className="hud-subtext">{t.evAtRecommendedSize}</div>
            </div>

            <div className="hud-card">
              <div>{t.bluffThreshold}</div>
              <div className="hud-value">
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : t.notAvailable}
              </div>
              <div className="hud-subtext">{t.bluffThresholdSub}</div>
            </div>
          </div>

          {/* Coverage by category */}
          <div>
            <div className="panel-header">
              <h2 className="panel-tag">{t.matrixTag}</h2>
            </div>

            <div className="table-wrapper">
              <table className="tactical-table">
                <thead>
                  <tr>
                    <th>{t.colCategory}</th>
                    <th>{t.colDescription}</th>
                    <th>{t.colClasses}</th>
                    <th>{t.colCombos}</th>
                    <th>{t.colProfitable}</th>
                    <th>{t.colCoverage}</th>
                    <th>{t.colStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryMatrix.map((cat) => {
                    const pct = Number(cat.pct);
                    return (
                      <tr key={cat.category}>
                        <td>{CATEGORY_LABELS[cat.category]}</td>
                        <td className="desc-cell">{t[CATEGORY_DESC_KEYS[cat.category]]}</td>
                        <td className="mono-num">{cat.classes}</td>
                        <td className="mono-num">{cat.combos.toLocaleString(t.locale)}</td>
                        <td className="mono-num">{cat.profitable_combos.toLocaleString(t.locale)}</td>
                        <td className="mono-num">{cat.pct}%</td>
                        <td className={pct === 100 ? "chip-full" : pct > 0 ? "" : "chip-zero"}>
                          {pct === 100 ? t.statusFull : pct > 0 ? t.statusPartial : t.statusZero}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Most profitable hands */}
          {solveData?.top_hands && (
            <div>
              <div className="panel-header">
                <h2 className="panel-tag">{t.topHandsTag}</h2>
              </div>

              <div className="table-wrapper">
                <table className="tactical-table">
                  <thead>
                    <tr>
                      <th>{t.colCanonicalId}</th>
                      <th>{t.colCategory}</th>
                      <th>{t.colEquity}</th>
                      <th>{t.colEv}</th>
                      <th>{t.colMultiplicity}</th>
                      <th>{t.colAction}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solveData.top_hands.slice(0, 10).map((item) => (
                      <tr key={item.canonical_id}>
                        <td className="mono-canonical">{item.canonical_id}</td>
                        <td>{CATEGORY_LABELS[item.category]}</td>
                        <td className="mono-num">{(item.showdown_equity * 100).toFixed(1)}%</td>
                        <td className={`mono-num bold-num ${item.ev > 0 ? "positive-ev" : "negative-ev"}`}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev, t.locale)} {t.currency}
                        </td>
                        <td className="dim-cell">{item.multiplicity} {t.combosSuffix}</td>
                        <td className={KIND_CLASSES[item.kind]}>
                          {t.actionLabel[item.action]} · {t.kindLabel[item.kind]}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Analysis notes (collapsed by default) */}
          <div className="notes-drawer-container">
            <button
              type="button"
              className="drawer-toggle-btn"
              onClick={() => setIsNotesOpen(!isNotesOpen)}
            >
              <span>{isNotesOpen ? t.notesCollapse : t.notesExpand}</span>
              <span className="drawer-indicator">{isNotesOpen ? "▲" : "▼"}</span>
            </button>

            {isNotesOpen && (
              <div className="drawer-content">
                <div className="drawer-header">
                  <span className="drawer-title">{t.notesTitle}</span>
                  {aiAdvice?.model && <span className="drawer-sub">{aiAdvice.model}</span>}
                </div>

                {isAiLoading ? (
                  <div className="telemetry-loading">{t.notesLoading}</div>
                ) : (
                  <div className="telemetry-body">
                    {!aiAdvice ? t.notesEmpty : aiAdvice.text ?? t[aiAdvice.key](aiAdvice.detail)}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
