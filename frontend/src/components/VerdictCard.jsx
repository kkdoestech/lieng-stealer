import { percent, signedMoney } from '../format.js';
import { stampLabel, toneClass, whyLine } from '../verdict.js';

// A hand-drawn squiggle under the action verb. Pure decoration: no text, hidden from AT.
function Squiggle() {
  return (
    <svg className="squiggle" viewBox="0 0 200 12" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <path
        d="M2 8 Q 20 1 38 8 T 74 8 T 110 8 T 146 8 T 182 8"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

// The verdict is one pinned polaroid: the loudest note on the board. It owns the action verb, the
// EV, the win rate and the why sentence; every test-pinned string lives in its own text node.
export default function VerdictCard({ advice, handEval, summary, t }) {
  const tone = toneClass(advice);
  const stamp = stampLabel(t, advice);
  const demoted = advice.action === 'CHECK';
  const winRate = advice.win_rate_defined
    ? percent(advice.equity_when_called)
    : t.winRateUndefined;
  const yourSize =
    handEval.ev !== advice.ev
      ? t.evAtYourBetSize(`${signedMoney(handEval.ev, t.locale)} ${t.currency}`)
      : null;

  return (
    <section className={`verdict-card polaroid ${tone}`}>
      <span className="tape tape-top" aria-hidden="true" />
      {stamp && <span className="kind-stamp">{stamp}</span>}

      <div className="kicker">{t.recommendedAction}</div>
      <h2 className="verb">{t.actionLabel[advice.action]}</h2>
      <Squiggle />

      <div className="figs">
        <div className="fig">
          <div className="kicker">{t.expectedValueTag}</div>
          <div className={`ev${demoted ? ' ev-demoted' : ''}`}>
            {signedMoney(advice.ev, t.locale)}
            <span className="unit">{t.currency}</span>
          </div>
          <div className="caption">{t.evAtRecommendedSize}</div>
          {yourSize && <div className="caption">{yourSize}</div>}
        </div>

        {/* Legacy `.hud-card` class is a test hook: App.test.jsx finds the "Showdown equity" label
            inside it. The figure itself now belongs to the verdict, not to a separate HUD grid. */}
        <div className="fig fig-right hud-card">
          <div className="kicker">{t.showdownEquity}</div>
          <div className={advice.win_rate_defined ? 'rate' : 'rate rate-phrase'}>{winRate}</div>
        </div>
      </div>

      <p className="why">{whyLine(t, advice, summary)}</p>

      <div className="chin">
        {handEval.hand} · {handEval.canonical_id} · {handEval.score_name}
      </div>
    </section>
  );
}
