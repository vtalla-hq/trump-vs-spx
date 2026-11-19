import { el, fmtDate, fmtPct, fmtShort, toDate } from '../format.js';

const pc = (p) => (p == null ? '—' : `${Math.round(p * 100)}%`);
const range = (m) => (m && m.lo != null ? `${fmtPct(m.lo)} to ${fmtPct(m.hi)}` : '—');
const daysLeft = (d) => Math.round((toDate(d) - toDate(new Date().toISOString())) / 864e5);
const countdown = (d) => { const n = daysLeft(d); return n > 1 ? `in ${n} days` : n === 1 ? 'tomorrow' : n === 0 ? 'today' : `${-n}d overdue`; };
const link = (url, text) => { const a = el('a', null, text); a.href = url; a.target = '_blank'; a.rel = 'noopener'; return a; };

/** Top strip: one chip per pending deadline with a countdown and the model's p(walk-back). */
export function renderDeadlines(box, f) {
  box.replaceChildren();
  if (!f?.pending?.length) { box.hidden = true; return; }
  box.append(el('div', 'k', 'Upcoming deadlines'), ...f.pending.map((d) => {
    const c = el('div', 'chip');
    c.append(el('div', 'cd', countdown(d.deadline)), el('div', 'cw', `${d.target}: ${d.said}`),
      el('div', 'cp', `${fmtShort(d.deadline)} · walk-back ${pc(d.p_walkback)} (n=${d.n_train ?? 0})`));
    c.title = d.said;
    return c;
  }));
}

function row(cells) { const tr = el('tr'); tr.append(...cells.map((c) => (c instanceof Node ? (() => { const td = el('td'); td.append(c); return td; })() : el('td', 'n', c)))); return tr; }

/** The Forecasts section: pending forecasts, Brier scores, track record. The calibration plot is drawn separately. */
export function renderForecasts(f) {
  const bt = f.backtest, live = f.live;
  const verdict = document.getElementById('fc-verdict');
  verdict.textContent = bt.n
    ? `Backtest (walk-forward, n=${bt.n}): model Brier ${bt.brier.model.toFixed(3)} vs ${bt.brier.base.toFixed(3)} for the base rate. `
      + (bt.beats_base ? 'The model beats the base rate on this tiny sample.' : 'The model does NOT beat simply guessing the base rate. Treat its numbers as a demo, not an edge.')
    : 'Not enough resolved deadlines to backtest yet.';
  verdict.className = 'verdict ' + (bt.beats_base ? 'up' : 'down');

  document.getElementById('fc-pending').replaceChildren(...f.pending.map((d) => row([
    fmtShort(d.deadline), link(d.source_url, d.said), pc(d.p_walkback), pc(d.p_base),
    d.market ? link(d.market.venue === 'kalshi' ? `https://kalshi.com/markets/${d.market.id}` : `https://polymarket.com/market/${d.market.id}`,
      `${pc(d.market.p_walkback)} (${d.market.venue})`) : '—',
    range(d.move),
  ])));

  const sc = (v, n) => (v == null ? '—' : `${v.toFixed(3)} (n=${n})`);
  document.getElementById('fc-brier').replaceChildren(
    row(['Backtest, walk-forward', sc(bt.brier?.model, bt.n), sc(bt.brier?.base, bt.n), '—']),
    row(['Live ledger', sc(live.brier.model, live.n), sc(live.brier.base, live.n), sc(live.brier.market, live.n_market)]),
  );

  const t = live.track.length ? live.track.map((r) => ({ ...r, src: 'live' })) : bt.preds.map((r) => ({ ...r, src: 'backtest' }));
  document.getElementById('fc-track').replaceChildren(...t.map((r) => {
    const hit = (r.p >= 0.5) === Boolean(r.y);
    return row([fmtShort(r.date ?? r.announced), r.id, pc(r.p), pc(r.base), r.y ? 'walked back' : 'followed through',
      el('span', hit ? 'up' : 'down', hit ? 'hit' : 'miss'), r.src]);
  }));
  document.getElementById('fc-track-cap').textContent = live.track.length
    ? `${live.n} resolved live forecasts, each scored on its first logged prediction.`
    : `No logged forecast has resolved yet (${live.ledger_rows} ledger rows so far). Showing the walk-forward backtest instead.`;

  const cov = f.moves.coverage;
  document.getElementById('fc-meta').textContent = `Trained on ${f.n_resolved} resolved deadlines (base rate ${pc(f.base_rate)} walked back or extended). `
    + `Move ranges are 80% intervals from past days: the topic ranges covered ${pc(cov.hit_rate)} of ${cov.n} later moves (target 80%). `
    + `Model ${f.model_version}, data through ${fmtDate(f.last_price_date)}.`;
}
