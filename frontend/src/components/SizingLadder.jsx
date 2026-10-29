import { rungView, toneClass } from '../verdict.js';

// The sizing sticky note: three pasted receipt rows. The EV column is monospace and right-aligned so
// the numbers align row to row; the chosen row is the only one with a neon spine.
export default function SizingLadder({ advice, summary, t }) {
  const tone = toneClass(advice);
  const { sizing } = summary;

  return (
    <section className={`ladder-card sticky ${tone}`}>
      <span className="tape tape-left" aria-hidden="true" />
      <span className="tape tape-right" aria-hidden="true" />

      <div className="card-head">
        <span className="title">{t.sizesTag}</span>
        <span className="meta">{t.currency}</span>
      </div>

      <ol className="ladder">
        {advice.ladder.map((rung) => {
          const view = rungView(t, rung, advice.action);
          const rowClass = [
            'ladder-rung',
            view.chosen ? 'chosen' : '',
            view.blocked ? 'rung-blocked' : '',
          ]
            .filter(Boolean)
            .join(' ');
          return (
            <li key={rung.action} className={rowClass}>
              <span className="ladder-head">
                <span className="ladder-mark" aria-hidden="true">
                  {view.mark}
                </span>
                <span className="ladder-label">{t.actionLabel[rung.action]}</span>
              </span>
              <span className="ladder-amount">{view.amount}</span>
              <span className="ladder-ev">{view.evText}</span>
              {view.stateText && <span className="ladder-state">{view.stateText}</span>}
            </li>
          );
        })}
      </ol>

      <p className="ladder-note">
        {t.thresholdNote(
          Math.round(sizing.min_edge_ratio * 100),
          Math.round(sizing.fold_step * 100)
        )}
      </p>
    </section>
  );
}
