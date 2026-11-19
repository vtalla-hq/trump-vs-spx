import { el, fmtDate, fmtPct, pill } from '../format.js';

/** Card for the selected event: move, headline, said vs reality, source. */
export function renderDetail(box, r, st) {
  box.replaceChildren();
  if (!r) return;
  const dir = r.pct > 0 ? 'up' : r.pct < 0 ? 'down' : '';
  const hd = el('div', 'dh');
  hd.append(el('div', 'mv ' + dir, fmtPct(r.pct)), el('div', 'hl', r.headline), el('div', 'dt', fmtDate(r.date)), pill(r.tag));
  if (r.auto) hd.append(el('span', 'pill auto', `auto · ${Math.round(r.confidence * 100)}% conf.`));

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

/** "How reliable is the auto-tagger": blind LLM labels vs the hand-labeled events. */
export function renderCalibration(box, c) {
  box.replaceChildren();
  if (!c || !c.tag) { box.append(el('p', 'note', 'No calibration run yet.')); return; }
  const f = (m) => `${Math.round(m.accuracy * 100)}% agree, κ ${m.kappa.toFixed(2)}`;
  const sd = el('div', 'sd');
  sd.append(el('div', 'l', 'Model'), el('div', null, c.model),
    el('div', 'l', 'Outcome'), el('div', null, `${f(c.tag)} (n=${c.tag.n})`),
    el('div', 'l', 'Topic'), el('div', null, `${f(c.topic)} (n=${c.topic.n})`),
    el('div', 'l', 'Coverage'), el('div', null, `${c.n_valid} of ${c.n_gold} hand-labeled days scraped and tagged (${Object.entries(c.text_sources || {}).map(([k, v]) => `${v} ${k}`).join(', ')}); ${c.n_rejected} rejected by the schema.`));
  const t = el('table', 'cm'), head = el('tr');
  head.append(el('th', null, 'hand ↓ / LLM →'), ...c.tag.labels.map((l) => el('th', null, l)));
  t.append(head, ...c.tag.labels.map((l, i) => {
    const tr = el('tr'); tr.append(el('td', null, l), ...c.tag.confusion[i].map((v, j) => el('td', i === j ? 'n diag' : 'n', v || '')));
    return tr;
  }));
  const wrap = el('div', 'list'); wrap.append(t);
  box.append(sd, wrap, el('p', 'note', 'Outcome tags need hindsight (was it walked back later?) that a same-day story lacks, so expect more misses there than on topic.'));
}
