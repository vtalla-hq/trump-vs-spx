import * as d3 from 'd3';
import { colorFor, fmtDate, fmtPct, toDate } from '../format.js';
import { svgFor, leftAxis, styleAxis, makeTip } from './common.js';

/** S&P 500 monthly line with a dot per event, sized by that day's move. */
export function drawTimeline(box, spx, events, selected, onSelect) {
  const narrow = box.clientWidth < 520;
  const H = narrow ? 260 : 340, mb = 24, mt = 14, mr = narrow ? 22 : 30;
  const { svg, W } = svgFor(box, H);
  const pts = spx.map((r) => ({ t: d3.utcDay.offset(toDate(r.month), 14), v: r.avg_close }));
  const evs = events.map((r) => ({ ...r, t: toDate(r.date) }));

  const y = d3.scaleLinear(d3.extent(pts, (p) => p.v), [H - mb, mt]).nice();
  const ml = leftAxis(svg, y, W, mr, 5, d3.format(','));
  const x = d3.scaleUtc([d3.min([pts[0].t, ...evs.map((d) => d.t)]), pts[pts.length - 1].t], [ml, W - mr]);
  const gx = svg.append('g').attr('transform', `translate(0,${H - mb})`)
    .call(d3.axisBottom(x).ticks(narrow ? d3.utcMonth.every(6) : Math.max(3, Math.floor(W / 110))).tickFormat(d3.utcFormat("%b '%y")).tickSize(0).tickPadding(8));
  styleAxis(gx);

  const yAt = (t) => {
    const i = d3.bisector((p) => p.t).left(pts, t);
    if (i <= 0) return pts[0].v;
    if (i >= pts.length) return pts[pts.length - 1].v;
    const a = pts[i - 1], b = pts[i];
    return a.v + ((t - a.t) / (b.t - a.t)) * (b.v - a.v);
  };

  const grad = svg.append('defs').append('linearGradient').attr('id', 'area-fade').attr('x1', 0).attr('x2', 0).attr('y1', 0).attr('y2', 1);
  [[0, 0.14], [0.5, 0.05], [1, 0]].forEach(([o, a]) => grad.append('stop').attr('offset', o).attr('stop-color', '#111').attr('stop-opacity', a));
  svg.append('path').datum(pts).attr('d', d3.area().x((p) => x(p.t)).y0(H - mb).y1((p) => y(p.v))).attr('fill', 'url(#area-fade)');
  svg.append('path').datum(pts).attr('d', d3.line().x((p) => x(p.t)).y((p) => y(p.v)))
    .attr('fill', 'none').attr('stroke', '#111').attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');

  const r = d3.scaleSqrt([0, d3.max(evs, (d) => Math.abs(d.pct)) || 1], [4, 13]);
  const tip = makeTip(box);
  svg.append('g').selectAll('circle')
    .data(evs.sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)))
    .join('circle')
    .attr('cx', (d) => x(d.t)).attr('cy', (d) => y(yAt(d.t))).attr('r', (d) => r(Math.abs(d.pct)))
    .attr('fill', (d) => colorFor(d.tag)).attr('fill-opacity', (d) => (selected && selected !== d.id ? 0.35 : 0.9))
    .attr('stroke', (d) => (d.id === selected ? '#111' : '#fff')).attr('stroke-width', (d) => (d.id === selected ? 2.5 : 1.5))
    .style('cursor', 'pointer')
    .on('mousemove', (ev, d) => tip.show(ev, [['d', fmtDate(d.date)], ['', `${fmtPct(d.pct)}  ${d.headline}`]]))
    .on('mouseleave', tip.hide)
    .on('click', (ev, d) => onSelect(d.id));
}
