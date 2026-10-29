// Pure presentation helpers for the scrapbook verdict surface. No React, no side effects: every
// function takes the frozen solve response (plus the copy table) and returns display text. Keeping
// them here means the card components stay dumb and the rules can be unit-tested without a DOM.

import { formatMoney, percent, signedMoney, wholePercent } from './format.js';

// Kind -> tone class. A check is gray regardless of the kind it carries, because the check card
// never renders a kind stamp (App.test.jsx pins that a CHECK card must not contain "Bluff").
const TONE_BY_KIND = {
  VALUE: 'tone-value',
  THIN_VALUE: 'tone-thin',
  BLUFF: 'tone-bluff',
};

/**
 * The paper tint for one recommendation.
 *
 * @param {{ action: string, kind: string }} advice - A `Recommendation` from /api/solve.
 * @returns {string} One of tone-value | tone-thin | tone-bluff | tone-check.
 */
export function toneClass(advice) {
  if (advice.action === 'CHECK') return 'tone-check';
  return TONE_BY_KIND[advice.kind] ?? 'tone-check';
}

/**
 * The kind word rendered inside the neon stamp, or null when the action is a check.
 *
 * @param {object} t - The active language copy table.
 * @param {{ action: string, kind: string }} advice - A `Recommendation`.
 * @returns {string | null} "Value", "Thin value", "Bluff", or null for CHECK.
 */
export function stampLabel(t, advice) {
  if (advice.action === 'CHECK') return null;
  return t.kindLabel[advice.kind] ?? null;
}

/**
 * The sentence that explains the recommendation, built from the response's own numbers.
 *
 * @param {object} t - Copy table.
 * @param {object} advice - A `Recommendation`.
 * @param {object} summary - The solve summary (pot, fold equity, sizing thresholds).
 * @returns {string} One sentence.
 */
export function whyLine(t, advice, summary) {
  const { sizing, fold_equity: foldEquity, pot } = summary;
  const money = (value) => signedMoney(value, t.locale);
  const equity = advice.win_rate_defined ? percent(advice.equity_when_called) : t.winRateUndefined;
  const fold = wholePercent(foldEquity);
  const worstFold = wholePercent(Math.max(0, foldEquity - sizing.fold_step));
  const foldStep = Math.round(sizing.fold_step * 100);
  const best = advice.ladder.reduce((a, rung) => (rung.ev_ratio > a.ev_ratio ? rung : a));
  const small = advice.ladder[0];

  switch (advice.reason) {
    case 'ALL_IN_VALUE':
      return t.whyAllInValue(equity, foldStep);
    case 'LARGE_VALUE':
      return t.whyLargeValue(equity);
    case 'LARGE_THIN':
      return t.whyLargeThin(equity);
    case 'SMALL_VALUE':
      return t.whySmallValue(`${formatMoney(advice.amount, t.locale)} ${t.currency}`);
    case 'SMALL_THIN':
      return t.whySmallThin(equity);
    case 'SMALL_BLUFF':
      return t.whySmallBluff(money(advice.ev), equity);
    case 'CHECK_NO_EDGE':
      return t.whyCheckNoEdge(fold);
    case 'CHECK_EDGE_TOO_SMALL':
      return t.whyCheckEdgeTooSmall(money(best.ev), percent(best.ev_ratio), wholePercent(sizing.min_edge_ratio));
    case 'CHECK_ASSUMPTION_FRAGILE':
      return t.whyCheckFragile(money(small.ev), fold, money(small.worst_ev_ratio * pot), worstFold);
    default:
      return '';
  }
}

/**
 * The opponent assumption the solver used, stated with the response's model and fold rate.
 *
 * @param {object} t - Copy table.
 * @param {object} summary - The solve summary.
 * @returns {string} One sentence.
 */
export function assumptionLine(t, summary) {
  const foldPct = Math.round(summary.fold_equity * 100);
  return summary.opponent_model === 'range'
    ? t.modelAssumptionRange(foldPct)
    : t.modelAssumptionRandom(foldPct);
}

/**
 * One ladder rung, mapped to the five strings the receipt row paints.
 *
 * @param {object} t - Copy table.
 * @param {object} rung - A `Rung` from `advice.ladder`.
 * @param {string} chosenAction - `advice.action`, to mark the chosen row.
 * @returns {{ mark: string, chosen: boolean, blocked: boolean, amount: string, evText: string,
 *   stateText: string }} Display values. `stateText` is empty for an eligible rung that simply
 *   was not the answer — the design forbids adding a derived delta number.
 */
export function rungView(t, rung, chosenAction) {
  const chosen = rung.action === chosenAction;
  const blocked = !rung.eligible;
  const stateText = chosen ? t.chosenTag : blocked ? (t.blocked[rung.blocked_by] ?? '') : '';
  return {
    mark: blocked ? '○' : '●',
    chosen,
    blocked,
    amount: formatMoney(rung.amount, t.locale),
    evText: `${t.evTag} ${signedMoney(rung.ev, t.locale)}`,
    stateText,
  };
}
