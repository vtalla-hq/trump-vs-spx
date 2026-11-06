import { el, fmtDate, fmtPct, pill } from '../format.js';

/** Card for the selected event: move, headline, said vs reality, source. */
export function renderDetail(box, r) {
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
  box.append(hd, sd);
}
