import * as d3 from 'd3';
import { colorFor, el, fmtDate, fmtPct, normTag, tagLabel, tagOrder } from '../format.js';
import { extremes, summary, tagCounts } from '../stats.js';

const set = (id, text) => { const n = document.getElementById(id); if (n) n.textContent = text; };

/** Big follow-through score, the 1-block-per-event bar, and the stat row. */
export function renderScorecard(events, onSelect) {
  const s = summary(events);
  const { worst, best } = extremes(events);
  set('n-followed', s.followed);
  set('n-events', s.events);
  set('n-events2', s.events);
  set('n-broke', s.broke);
  set('worst', fmtPct(worst.pct));
  set('best', fmtPct(best.pct));
  set('avg', d3.format('.1f')(s.avgAbs) + '%');
  document.getElementById('worst').title = fmtDate(worst.date);
  document.getElementById('best').title = fmtDate(best.date);

  const rank = (t) => tagOrder.indexOf(normTag(t));
  const blocks = document.getElementById('blocks');
  blocks.replaceChildren(...[...events]
    .sort((a, b) => rank(a.tag) - rank(b.tag) || (a.date < b.date ? -1 : 1))
    .map((r) => {
      const b = el('i');
      b.style.background = colorFor(r.tag);
      b.title = `${fmtDate(r.date)}: ${r.headline}`;
      b.addEventListener('click', () => onSelect(r.id));
      return b;
    }));

  const legend = document.getElementById('block-legend');
  legend.replaceChildren(...tagCounts(events)
    .sort((a, b) => tagOrder.indexOf(a.tag) - tagOrder.indexOf(b.tag))
    .map((r) => {
      const sw = el('i'); sw.style.background = colorFor(r.tag);
      const span = el('span');
      span.append(sw, el('b', null, r.n), document.createTextNode(' ' + (tagLabel[r.tag] || r.tag)));
      return span;
    }));

  document.querySelectorAll('.legend i').forEach((i) => { i.style.background = colorFor(i.dataset.tag); });
}
