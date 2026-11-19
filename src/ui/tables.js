import { el, fmtPct, fmtShort, pill } from '../format.js';

export function renderEvents(tbody, events, selected, onSelect) {
  tbody.replaceChildren(...events.map((r) => {
    const tr = el('tr', r.id === selected ? 'sel' : null);
    const dir = r.pct > 0 ? 'up' : r.pct < 0 ? 'down' : '';
    const outcome = el('td', 'hide-sm'); outcome.append(pill(r.tag));
    tr.append(el('td', 'n', fmtShort(r.date)), el('td', 'n ' + dir, fmtPct(r.pct)), el('td', null, r.headline), outcome);
    tr.addEventListener('click', () => onSelect(r.id, true));
    return tr;
  }));
}

export function renderKobeissi(tbody, posts, onSelect) {
  tbody.replaceChildren(...posts.map((r) => {
    const tr = el('tr');
    const a = el('a', null, '↗'); a.href = r.url; a.target = '_blank'; a.rel = 'noopener';
    const link = el('td'); link.append(a);
    tr.append(el('td', 'n', fmtShort(r.date)), el('td', null, r.post), link);
    tr.addEventListener('click', (ev) => { if (ev.target.tagName !== 'A') onSelect(r.event_id, true); });
    return tr;
  }));
}

const pct = (v) => (v == null ? '—' : fmtPct(v));
const dirOf = (v) => (v > 0 ? 'up' : v < 0 ? 'down' : '');

/** One row per event: SPX AR, standardized AR, CARs, VIX and 10Y moves. */
export function renderAR(tbody, rows, events, selected, onSelect) {
  const byId = Object.fromEntries(events.map((e) => [e.id, e]));
  tbody.replaceChildren(...rows.map((r) => {
    const tr = el('tr', r.id === selected ? 'sel' : null);
    const s = r.spx;
    tr.append(el('td', 'n', fmtShort(r.date)), el('td', null, byId[r.id]?.headline ?? r.id),
      el('td', 'n ' + dirOf(s.ar), pct(s.ar)), el('td', 'n', s.sar.toFixed(1)),
      el('td', 'n hide-sm ' + dirOf(s.car['0,1']), pct(s.car['0,1'])), el('td', 'n hide-sm ' + dirOf(s.car['0,5']), pct(s.car['0,5'])),
      el('td', 'n hide-sm', (r.vix_chg > 0 ? '+' : '') + r.vix_chg.toFixed(1)), el('td', 'n hide-sm', (r.tnx_bps > 0 ? '+' : '') + r.tnx_bps.toFixed(0)));
    tr.addEventListener('click', () => onSelect(r.id, true));
    return tr;
  }));
}

/** TACO trades plus a summary row. */
export function renderBacktest(tbody, bt, events, onSelect) {
  const byId = Object.fromEntries(events.map((e) => [e.id, e]));
  const rows = bt.trades.map((t) => {
    const tr = el('tr');
    tr.append(el('td', 'n', fmtShort(t.entry)), el('td', null, byId[t.id]?.headline ?? t.id),
      el('td', 'n', `${t.hold_days}d${t.walkback ? '' : '*'}`), el('td', 'n ' + dirOf(t.ret), pct(t.ret)),
      el('td', 'n hide-sm', pct(t.baseline)), el('td', 'n ' + dirOf(t.excess), pct(t.excess)));
    tr.addEventListener('click', () => onSelect(t.id, true));
    return tr;
  });
  const sum = el('tr');
  sum.append(el('td', 'n', `n=${bt.n}`), el('td', null, `Hit rate ${Math.round(bt.hit_rate * 100)}%`), el('td', 'n', `${bt.avg_hold_days.toFixed(1)}d`),
    el('td', 'n ' + dirOf(bt.avg_ret), pct(bt.avg_ret)), el('td', 'n hide-sm', pct(bt.avg_baseline)), el('td', 'n', pct(bt.avg_ret - bt.avg_baseline)));
  sum.style.fontWeight = 600;
  tbody.replaceChildren(...rows, sum);
}
