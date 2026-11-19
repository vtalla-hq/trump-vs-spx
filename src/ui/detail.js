import { el, fmtDate, fmtPct, pill } from '../format.js';

/** Card for the selected event: move, headline, said vs reality, source. */
export function renderDetail(box, r, st) {
  box.replaceChildren();
  if (!r) return;
  const dir = r.pct > 0 ? 'up' : r.pct < 0 ? 'down' : '';
  const hd = el('div', 'dh');
  hd.append(el('div', 'mv ' + dir, fmtPct(r.pct)), el('div', 'hl', r.headline), el('div', 'dt', fmtDate(r.date)), pill(r.tag));

  const link = el('a', null, `${r.source} ↗`);
  link.href = r.url; link.target = '_blank'; link.rel = 'noopener';
  const src = el('div'); src.append(link);

  const sd = el('div', 'sd');
  sd.append(el('div', 'l', 'Said'), el('div', null, r.said), el('div', 'l', 'Reality'), el('div', null, r.did),
    el('div', 'l', 'Also'), el('div', null, r.context), el('div', 'l', 'Source'), src);
  if (st) {
    const c = st.spx.car, f = (v) => (v == null ? '—' : fmtPct(v));
    sd.append(el('div', 'l', 'Abnormal'), el('div', null,
      `AR ${f(st.spx.ar)} (${st.spx.sar.toFixed(1)}σ) · CAR[0,+1] ${f(c['0,1'])} · CAR[0,+5] ${f(c['0,5'])} · VIX ${st.vix_chg > 0 ? '+' : ''}${st.vix_chg.toFixed(1)} · 10Y ${st.tnx_bps > 0 ? '+' : ''}${st.tnx_bps.toFixed(0)}bp`));
  }
  box.append(hd, sd);
}
