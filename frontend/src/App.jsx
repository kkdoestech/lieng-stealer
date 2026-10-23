import { useState, useEffect } from 'react';
import './App.css';
import { STRINGS, LANGUAGES } from './i18n.js';
import { formatMoney, formatZones } from './format.js';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";
const LANG_STORAGE_KEY = "lieng-scope-lang";

// Backend category enum -> display label and i18n description key
const CATEGORY_LABELS = { SAP: "SÁP", LIENG: "LIÊNG", DI: "ĐĨ", DIEM: "ĐIỂM" };
const CATEGORY_DESC_KEYS = { SAP: "descSap", LIENG: "descLieng", DI: "descDi", DIEM: "descDiem" };

function loadSavedLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return LANGUAGES.includes(saved) ? saved : "en";
  } catch {
    return "en";
  }
}

export default function App() {
  const [lang, setLang] = useState(loadSavedLang);
  const t = STRINGS[lang];

  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);
  const [opponentModel, setOpponentModel] = useState("range");

  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [solveData, setSolveData] = useState(null);
  // { text } from the server, or { key, detail } for a client-side notice translated at render
  const [aiAdvice, setAiAdvice] = useState(null);
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  // { key, detail } translated at render, or null
  const [solveError, setSolveError] = useState(null);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_STORAGE_KEY, lang);
    } catch {
      // Storage unavailable (e.g. private mode): the choice just won't persist.
    }
  }, [lang]);

  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setSolveError(null);

    try {
      // 1. Call solve endpoint
      const solveRes = await fetch(`${API_BASE}/api/solve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pot: Number(pot),
          bet_size: Number(betSize),
          fold_equity: Number(foldEquity),
          hand: hand.trim(),
          opponent_model: opponentModel,
        }),
      });

      if (!solveRes.ok) {
        // The solver is up but rejected the input (e.g. duplicate cards)
        const errJson = await solveRes.json().catch(() => ({}));
        setSolveError({ key: "invalidInput", detail: errJson.error || `HTTP ${solveRes.status}` });
        setIsLoading(false);
        setIsAiLoading(false);
        return;
      }

      const solveJson = await solveRes.json();
      setSolveData(solveJson);
      setIsLoading(false);

      // 2. Call analyze endpoint for strategic AI telemetry
      try {
        const analyzeRes = await fetch(`${API_BASE}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pot: Number(pot),
            bet_size: Number(betSize),
            fold_equity: Number(foldEquity),
            hand: hand.trim(),
            opponent_model: opponentModel,
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });

        if (analyzeRes.ok) {
          const analyzeJson = await analyzeRes.json();
          setAiAdvice(analyzeJson.advice ? { text: analyzeJson.advice } : { key: "aiNoAdvice" });
        } else {
          setAiAdvice({ key: "aiUnreachable" });
        }
      } catch (aiErr) {
        setAiAdvice({ key: "aiTransportFault", detail: aiErr.message });
      } finally {
        setIsAiLoading(false);
      }
    } catch {
      setSolveError({ key: "solverOffline" });
      setIsLoading(false);
      setIsAiLoading(false);
    }
  };

  // Run initial solve on mount
  useEffect(() => {
    handleSolve();
  }, []);

  const handEval = solveData?.hand_evaluation;
  const summary = solveData?.summary;
  const isRaise = handEval?.decision === "RAISE";

  const zones = handEval?.profitable_fold_zones;

  // Category Matrix Statistics (computed by the solver per category)
  const categoryMatrix = (summary?.category_breakdown || []).map((row) => ({
    ...row,
    pct: ((row.profitable_combos / row.combos) * 100).toFixed(1),
  }));

  return (
    <div className="terminal-container">
      {/* Tactical Header & Telemetry Status */}
      <header className="terminal-header">
        <div className="brand-group">
          <h1 className="terminal-title">
            <span className="brand-white">LIÊNG</span> <span className="brand-green">SCOPE</span>
          </h1>
          <p className="terminal-subtitle">{t.subtitle}</p>
        </div>

        <div className="header-actions">
          <div className="telemetry-status-tag">
            <span className="radar-beacon"></span>
            <span className="telemetry-status-text">{t.liveSolver}</span>
            <span className="telemetry-separator">/</span>
            <span className="telemetry-classes">{t.classesLoaded}</span>
          </div>

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

      {/* Main Tactical Grid */}
      <main className="terminal-grid">
        {/* Left Column: Control Telemetry */}
        <section className="terminal-card control-panel">
          <div className="panel-header">
            <span className="panel-tag">{t.controlsTag}</span>
            <span className="panel-id">SEC-01</span>
          </div>

          <div className="form-group">
            <label className="form-label">{t.potLabel}</label>
            <div className="input-wrapper">
              <input
                type="number"
                className="input-field"
                value={pot}
                onChange={(e) => setPot(Number(e.target.value))}
                step="10000"
                min="1000"
              />
            </div>
            <div className="preset-chips">
              {[50000, 100000, 200000, 500000].map((v) => (
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
            <label className="form-label">{t.betLabel}</label>
            <div className="input-wrapper">
              <input
                type="number"
                className="input-field"
                value={betSize}
                onChange={(e) => setBetSize(Number(e.target.value))}
                step="10000"
                min="1000"
              />
            </div>
            <div className="preset-chips">
              <button
                type="button"
                className={`preset-chip ${betSize === Math.round(pot * 0.5) ? "active" : ""}`}
                onClick={() => setBetSize(Math.round(pot * 0.5))}
              >
                0.5x Pot
              </button>
              <button
                type="button"
                className={`preset-chip ${betSize === pot ? "active" : ""}`}
                onClick={() => setBetSize(pot)}
              >
                1.0x Pot
              </button>
              <button
                type="button"
                className={`preset-chip ${betSize === pot * 2 ? "active" : ""}`}
                onClick={() => setBetSize(pot * 2)}
              >
                2.0x Pot
              </button>
            </div>
          </div>

          <div className="form-group">
            <div className="slider-label-row">
              <label className="form-label">{t.foldLabel}</label>
              <span className="slider-value-badge">{Math.round(foldEquity * 100)}%</span>
            </div>
            <input
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
            <label className="form-label">{t.handLabel}</label>
            <div className="input-wrapper">
              <input
                type="text"
                className="input-field mono-bold"
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                placeholder={t.handPlaceholder}
              />
            </div>
            <div className="preset-chips">
              <button
                type="button"
                className={`preset-chip ${hand === "As Kh Qd" ? "active" : ""}`}
                onClick={() => setHand("As Kh Qd")}
              >
                Liêng Q-K-A
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "7s 7h 7d" ? "active" : ""}`}
                onClick={() => setHand("7s 7h 7d")}
              >
                Sáp 7
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "Js Qh Kd" ? "active" : ""}`}
                onClick={() => setHand("Js Qh Kd")}
              >
                Liêng J-Q-K
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "9s 10h Kd" ? "active" : ""}`}
                onClick={() => setHand("9s 10h Kd")}
              >
                9 Điểm
              </button>
              <button
                type="button"
                className={`preset-chip ${hand === "2s 3h 5d" ? "active" : ""}`}
                onClick={() => setHand("2s 3h 5d")}
              >
                0 Điểm (Bù)
              </button>
            </div>
          </div>

          <button
            type="button"
            className="tactical-btn"
            onClick={handleSolve}
            disabled={isLoading}
          >
            {isLoading ? t.solveBusy : t.solveIdle}
          </button>

          {solveError && (
            <div className="terminal-alert">
              <span className="alert-marker">!</span>
              <span>{t[solveError.key](solveError.detail)}</span>
            </div>
          )}

          {/* Engine Specs Sub-Card */}
          <div className="specs-subcard">
            <div className="spec-row">
              <span className="spec-label">{t.specArchitecture}</span>
              <span className="spec-val">{t.specArchitectureVal}</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">{t.specSpace}</span>
              <span className="spec-val">{t.specSpaceVal}</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">{t.specQuery}</span>
              <span className="spec-val">{t.specQueryVal}</span>
            </div>
          </div>
        </section>

        {/* Right Column: Strategic HUD & Matrix */}
        <section className="results-container">
          {/* Verdict Banner */}
          {handEval && (
            <div className={`verdict-banner ${isRaise ? "verdict-raise" : "verdict-fold"}`}>
              <div className="verdict-col-left">
                <span className="verdict-label">{t.recommendedAction}</span>
                <h2 className="verdict-title">
                  {isRaise ? t.actionRaise : t.actionFold}
                </h2>
                <div className="verdict-meta">
                  <span className="holding-tag">{handEval.hand}</span>
                  <span className="holding-sep">•</span>
                  <span className="holding-class">[{handEval.canonical_id}]</span>
                  <span className="holding-sep">•</span>
                  <span className="holding-score">{handEval.score_name.toUpperCase()}</span>
                </div>
              </div>

              <div className="verdict-col-right">
                <span className="verdict-label">{t.expectedValueTag}</span>
                <div className="verdict-ev">
                  {handEval.ev > 0 ? "+" : ""}{formatMoney(handEval.ev, t.locale)} <span className="ev-currency">VND</span>
                </div>
                <div className="verdict-breakeven">
                  {t.profitableWhen} <span className="mono-green">{formatZones(zones)}</span>
                </div>
              </div>
            </div>
          )}

          {/* 4-Card Metrics HUD */}
          <div className="hud-metrics-grid">
            <div className="hud-card">
              <div className="hud-label">{t.rangeCoverage}</div>
              <div className="hud-value green-glow">
                {summary?.range_coverage_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="hud-subtext">
                {summary?.profitable_combinations?.toLocaleString(t.locale) || "0"} {t.combosOfTotal}
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.showdownEquity}</div>
              <div className="hud-value white-metric">
                {handEval ? `${(handEval.showdown_equity * 100).toFixed(1)}%` : t.notAvailable}
              </div>
              <div className="hud-subtext">
                {handEval && summary.opponent_model === "range"
                  ? `${t.vsCallingRange(Math.round((1 - summary.fold_equity) * 100))} · ${t.vsRandomShort(
                      `${(handEval.equity_vs_random * 100).toFixed(1)}%`
                    )}`
                  : t.showdownEquitySub}
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.expectedValue}</div>
              <div className={`hud-value ${handEval?.ev > 0 ? "green-metric" : "dim-metric"}`}>
                {handEval ? `${handEval.ev > 0 ? "+" : ""}${formatMoney(handEval.ev, t.locale)}` : "0"}
              </div>
              <div className="hud-subtext">{t.expectedValueSub}</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">{t.bluffThreshold}</div>
              <div className="hud-value amber-metric">
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : t.notAvailable}
              </div>
              <div className="hud-subtext">{t.bluffThresholdSub}</div>
            </div>
          </div>

          {/* Range Breakdown Matrix Table */}
          <div className="terminal-card table-panel">
            <div className="panel-header">
              <span className="panel-tag">{t.matrixTag}</span>
              <span className="panel-id">{t.matrixId}</span>
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
                  {categoryMatrix.map((cat) => (
                    <tr key={cat.category}>
                      <td>
                        <span className={`cat-pill cat-${cat.category}`}>{CATEGORY_LABELS[cat.category]}</span>
                      </td>
                      <td className="desc-cell">{t[CATEGORY_DESC_KEYS[cat.category]]}</td>
                      <td className="mono-num">{cat.classes}</td>
                      <td className="mono-num">{cat.combos.toLocaleString(t.locale)}</td>
                      <td className="mono-num">{cat.profitable_combos.toLocaleString(t.locale)}</td>
                      <td className="mono-num highlight-val">{cat.pct}%</td>
                      <td>
                        <span
                          className={`status-chip ${
                            Number(cat.pct) === 100
                              ? "chip-full"
                              : Number(cat.pct) > 0
                              ? "chip-partial"
                              : "chip-zero"
                          }`}
                        >
                          {Number(cat.pct) === 100
                            ? t.statusFull
                            : Number(cat.pct) > 0
                            ? t.statusPartial
                            : t.statusZero}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top Canonical Holdings Table */}
          {solveData?.top_hands && (
            <div className="terminal-card table-panel">
              <div className="panel-header">
                <span className="panel-tag">{t.topHandsTag}</span>
                <span className="panel-id">{t.topHandsId}</span>
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
                        <td>
                          <span className={`cat-pill cat-${item.category}`}>{CATEGORY_LABELS[item.category]}</span>
                        </td>
                        <td className="mono-num">{(item.equity * 100).toFixed(1)}%</td>
                        <td className={`mono-num bold-num ${item.ev > 0 ? "positive-ev" : "negative-ev"}`}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev, t.locale)} VND
                        </td>
                        <td className="dim-cell">{item.multiplicity} {t.combosSuffix}</td>
                        <td>
                          <span className={`action-badge ${item.is_profitable ? "act-raise" : "act-fold"}`}>
                            {item.is_profitable ? t.raise : t.fold}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Collapsible Mathematical Telemetry Notes Drawer */}
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
                  <span className="drawer-sub">OPENROUTER / LLAMA 3.1 8B INSTRUCT</span>
                </div>

                {isAiLoading ? (
                  <div className="telemetry-loading">
                    <span className="radar-spinner"></span>
                    <span>{t.notesLoading}</span>
                  </div>
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
