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
