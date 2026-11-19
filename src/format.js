import * as d3 from 'd3';

export const fmtPct = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + d3.format('.2~f')(Math.abs(v)) + '%';
export const toDate = (s) => new Date(String(s).slice(0, 10) + 'T00:00:00Z');
export const fmtDate = (s) => d3.utcFormat('%b %-d, %Y')(toDate(s));
export const fmtShort = (s) => d3.utcFormat("%b %-d '%y")(toDate(s));

export const tagColor = {
  // Promises get the three hues (validated on the dark surface); non-promises share one neutral.
  'Followed through': '#199e70',
  'Walked back': '#9085e9',
  "Didn't check out": '#e66767',
  'Rhetoric': '#7d7f8a',
  'False report': '#7d7f8a',
  'Report / rumor': '#7d7f8a',
  'Overruled': '#7d7f8a',
};
export const tagOrder = ['Followed through', 'Walked back', "Didn't check out", 'Rhetoric', 'False report', 'Overruled'];
export const tagLabel = {
  'Followed through': 'Did it',
  'Walked back': 'Walked back',
  'Rhetoric': 'Just talk',
  "Didn't check out": 'False claim',
  'False report': 'Fake news / rumor',
  'Report / rumor': 'Fake news / rumor',
  'Overruled': 'Court',
};
export const colorFor = (tag) => tagColor[tag] || '#7d7f8a';
export const normTag = (t) => (t === 'Report / rumor' ? 'False report' : t);

export function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

export function pill(tag) {
  const p = el('span', 'pill', tagLabel[tag] || tag);
  p.style.color = colorFor(tag);
  p.style.background = colorFor(tag) + '17';
  return p;
}
