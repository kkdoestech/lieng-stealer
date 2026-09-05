import { useState, useEffect } from 'react';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000";

function formatMoney(num) {
  if (num === undefined || num === null) return "0";
  return new Intl.NumberFormat("vi-VN").format(Math.round(num));
}

export default function App() {
  const [pot, setPot] = useState(100000);
  const [betSize, setBetSize] = useState(50000);
  const [hand, setHand] = useState("As Kh Qd");
  const [foldEquity, setFoldEquity] = useState(0.35);

  const [isLoading, setIsLoading] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [solveData, setSolveData] = useState(null);
  const [aiAdvice, setAiAdvice] = useState("");
  const [isNotesOpen, setIsNotesOpen] = useState(false);
  const [error, setError] = useState("");

  const handleSolve = async () => {
    setIsLoading(true);
    setIsAiLoading(true);
    setError("");

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
        }),
      });

      if (!solveRes.ok) {
        const errJson = await solveRes.json();
        throw new Error(errJson.error || `Server responded with ${solveRes.status}`);
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
            hand_evaluation: solveJson.hand_evaluation,
            range_coverage_percent: solveJson.summary?.range_coverage_percent,
          }),
        });

        if (analyzeRes.ok) {
          const analyzeJson = await analyzeRes.json();
          setAiAdvice(analyzeJson.advice || "No telemetry analysis generated.");
        } else {
          setAiAdvice("AI telemetry gateway unreachable.");
        }
      } catch (aiErr) {
        setAiAdvice(`Telemetry transmission fault: ${aiErr.message}`);
      } finally {
        setIsAiLoading(false);
      }
    } catch (err) {
      setError("LOCAL SOLVER DAEMON OFFLINE. VERIFY BACKEND RUNNING ON PORT 5000.");
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

  // Category Matrix Statistics
  const totalProfitableCombos = summary?.profitable_combinations || 0;
  const sapProfitable = Math.min(52, Math.max(0, totalProfitableCombos));
  const liengProfitable = Math.min(768, Math.max(0, totalProfitableCombos - 52));
  const diProfitable = Math.min(288, Math.max(0, totalProfitableCombos - 820));
  const diemProfitable = Math.min(20992, Math.max(0, totalProfitableCombos - 1108));

  const categoryMatrix = [
    {
      name: "SÁP",
      desc: "Three of a Kind",
      classes: 13,
      combos: 52,
      profitable: sapProfitable,
      pct: ((sapProfitable / 52) * 100).toFixed(1),
      tier: "TIER 1 (NUTS)",
    },
    {
      name: "LIÊNG",
      desc: "Straight Sequence",
      classes: 12,
      combos: 768,
      profitable: liengProfitable,
      pct: ((liengProfitable / 768) * 100).toFixed(1),
      tier: "TIER 2 (STRONG)",
    },
    {
      name: "ĐĨ",
      desc: "Three Face Cards",
      classes: 6,
      combos: 288,
      profitable: diProfitable,
      pct: ((diProfitable / 288) * 100).toFixed(1),
      tier: "TIER 3 (MEDIUM)",
    },
    {
      name: "ĐIỂM",
      desc: "Points Modulo 10",
      classes: 424,
      combos: 20992,
      profitable: diemProfitable,
      pct: ((diemProfitable / 20992) * 100).toFixed(1),
      tier: "TIER 4 (MARGINAL)",
    },
  ];

  return (
    <div className="terminal-container">
      {/* Tactical Header & Telemetry Status */}
      <header className="terminal-header">
        <div className="brand-group">
          <h1 className="terminal-title">
            <span className="brand-white">LIÊNG</span> <span className="brand-green">SCOPE</span>
          </h1>
          <p className="terminal-subtitle">GTO SOLVER & COMBINATORIAL ENGINE</p>
        </div>

        <div className="telemetry-status-tag">
          <span className="radar-beacon"></span>
          <span className="telemetry-status-text">LIVE SOLVER</span>
          <span className="telemetry-separator">/</span>
          <span className="telemetry-classes">455 CLASSES LOADED</span>
        </div>
      </header>

      {/* Main Tactical Grid */}
      <main className="terminal-grid">
        {/* Left Column: Control Telemetry */}
        <section className="terminal-card control-panel">
          <div className="panel-header">
            <span className="panel-tag">// TELEMETRY CONTROLS</span>
            <span className="panel-id">SEC-01</span>
          </div>

          <div className="form-group">
            <label className="form-label">CURRENT POT (VND)</label>
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
            <label className="form-label">BET / RAISE SIZING</label>
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
              <label className="form-label">OPPONENT FOLD FREQUENCY</label>
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
              <span>0% (CALLING STATION)</span>
              <span>50%</span>
              <span>100% (EXTREME FOLD)</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">PLAYER HAND (3 CARDS)</label>
            <div className="input-wrapper">
              <input
                type="text"
                className="input-field mono-bold"
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                placeholder="e.g. As Kh Qd"
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
            {isLoading ? "[ COMPUTING RANGE... ]" : "[ EXECUTE SOLVER ]"}
          </button>

          {error && (
            <div className="terminal-alert">
              <span className="alert-marker">!</span>
              <span>{error}</span>
            </div>
          )}

          {/* Engine Specs Sub-Card */}
          <div className="specs-subcard">
            <div className="spec-row">
              <span className="spec-label">SOLVER ARCHITECTURE</span>
              <span className="spec-val">MONTE CARLO / CANONICAL</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">COMBINATORIAL SPACE</span>
              <span className="spec-val">22,100 COMBOS (455 CLS)</span>
            </div>
            <div className="spec-row">
              <span className="spec-label">ONLINE QUERY COMPLEXITY</span>
              <span className="spec-val">O(1) CACHED LOOKUP</span>
            </div>
          </div>
        </section>

        {/* Right Column: Strategic HUD & Matrix */}
        <section className="results-container">
          {/* Verdict Banner */}
          {handEval && (
            <div className={`verdict-banner ${isRaise ? "verdict-raise" : "verdict-fold"}`}>
              <div className="verdict-col-left">
                <span className="verdict-label">// RECOMMENDED ACTION</span>
                <h2 className="verdict-title">
                  {isRaise ? "ACTION: RAISE / ALL-IN" : "ACTION: CHECK / FOLD"}
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
                <span className="verdict-label">// EXPECTED VALUE</span>
                <div className="verdict-ev">
                  {handEval.ev > 0 ? "+" : ""}{formatMoney(handEval.ev)} <span className="ev-currency">VND</span>
                </div>
                <div className="verdict-breakeven">
                  BREAK-EVEN FOLD EQ: <span className="mono-green">{Math.round(handEval.break_even_fold_equity * 100)}%</span>
                </div>
              </div>
            </div>
          )}

          {/* 4-Card Metrics HUD */}
          <div className="hud-metrics-grid">
            <div className="hud-card">
              <div className="hud-label">RANGE COVERAGE</div>
              <div className="hud-value green-glow">
                {summary?.range_coverage_percent?.toFixed(1) || "0.0"}%
              </div>
              <div className="hud-subtext">
                {summary?.profitable_combinations?.toLocaleString() || "0"} / 22,100 COMBOS
              </div>
            </div>

            <div className="hud-card">
              <div className="hud-label">SHOWDOWN EQUITY</div>
              <div className="hud-value white-metric">
                {handEval ? `${(handEval.showdown_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="hud-subtext">VS UNKNOWN 49-CARD SPECTRUM</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">EXPECTED VALUE</div>
              <div className={`hud-value ${handEval?.ev > 0 ? "green-metric" : "dim-metric"}`}>
                {handEval ? `${handEval.ev > 0 ? "+" : ""}${formatMoney(handEval.ev)}` : "0"}
              </div>
              <div className="hud-subtext">NET VND GAIN PER DECISION</div>
            </div>

            <div className="hud-card">
              <div className="hud-label">PURE BLUFF THRESHOLD</div>
              <div className="hud-value amber-metric">
                {summary ? `${(summary.pure_bluff_break_even_fold_equity * 100).toFixed(1)}%` : "N/A"}
              </div>
              <div className="hud-subtext">MIN FOLD EQ FOR 0-PT AIR</div>
            </div>
          </div>

          {/* Range Breakdown Matrix Table */}
          <div className="terminal-card table-panel">
            <div className="panel-header">
              <span className="panel-tag">// CATEGORY COVERAGE MATRIX</span>
              <span className="panel-id">4 CORE HIERARCHIES</span>
            </div>

            <div className="table-wrapper">
              <table className="tactical-table">
                <thead>
                  <tr>
                    <th>CATEGORY</th>
                    <th>DESCRIPTION</th>
                    <th>CLASSES</th>
                    <th>COMBOS</th>
                    <th>PROFITABLE</th>
                    <th>COVERAGE</th>
                    <th>RADAR STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryMatrix.map((cat) => (
                    <tr key={cat.name}>
                      <td>
                        <span className={`cat-pill cat-${cat.name}`}>{cat.name}</span>
                      </td>
                      <td className="desc-cell">{cat.desc}</td>
                      <td className="mono-num">{cat.classes}</td>
                      <td className="mono-num">{cat.combos.toLocaleString()}</td>
                      <td className="mono-num">{cat.profitable.toLocaleString()}</td>
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
                            ? "100% PUSH"
                            : Number(cat.pct) > 0
                            ? "PARTIAL"
                            : "FOLD"}
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
                <span className="panel-tag">// TOP PROFITABLE HOLDINGS</span>
                <span className="panel-id">SAMPLE EQUIVALENCE CLASSES</span>
              </div>

              <div className="table-wrapper">
                <table className="tactical-table">
                  <thead>
                    <tr>
                      <th>CANONICAL ID</th>
                      <th>CATEGORY</th>
                      <th>SHOWDOWN EQUITY</th>
                      <th>EXPECTED VALUE (EV)</th>
                      <th>MULTIPLICITY</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {solveData.top_hands.slice(0, 10).map((item) => (
                      <tr key={item.canonical_id}>
                        <td className="mono-canonical">{item.canonical_id}</td>
                        <td>
                          <span className={`cat-pill cat-${item.category}`}>{item.category}</span>
                        </td>
                        <td className="mono-num">{(item.equity * 100).toFixed(1)}%</td>
                        <td className={`mono-num bold-num ${item.ev > 0 ? "positive-ev" : "negative-ev"}`}>
                          {item.ev > 0 ? "+" : ""}{formatMoney(item.ev)} VND
                        </td>
                        <td className="dim-cell">{item.multiplicity} combos</td>
                        <td>
                          <span className={`action-badge ${item.is_profitable ? "act-raise" : "act-fold"}`}>
                            {item.is_profitable ? "RAISE" : "FOLD"}
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
              <span>{isNotesOpen ? "[ − COLLAPSE TELEMETRY NOTES ]" : "[ + MATHEMATICAL TELEMETRY NOTES ]"}</span>
              <span className="drawer-indicator">{isNotesOpen ? "▲" : "▼"}</span>
            </button>

            {isNotesOpen && (
              <div className="drawer-content">
                <div className="drawer-header">
                  <span className="drawer-title">// GAME-THEORETIC TELEMETRY ADVISORY</span>
                  <span className="drawer-sub">OPENROUTER / LLAMA 3.1 8B INSTRUCT</span>
                </div>

                {isAiLoading ? (
                  <div className="telemetry-loading">
                    <span className="radar-spinner"></span>
                    <span>&gt; TRANSMITTING GAME-THEORETIC TELEMETRY QUERY...</span>
                  </div>
                ) : (
                  <div className="telemetry-body">
                    {aiAdvice || "No active telemetry payload recorded for this game state."}
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
