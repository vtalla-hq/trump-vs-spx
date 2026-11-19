import * as d3 from 'd3';
import { fmtDate, fmtShort } from '../format.js';
import { svgFor, leftAxis, styleAxis, makeTip } from './common.js';

/** Null distribution of mean |AR| over random non-event days, with the event-day mean marked. */
export function drawPermutation(box, p) {
  const H = 200, mt = 22, mb = 26, mr = 12;
  const { svg, W } = svgFor(box, H);
  const { edges, counts } = p.hist;
  const bins = counts.map((c, i) => ({ x0: edges[i], x1: edges[i + 1], c }));
  const y = d3.scaleLinear([0, d3.max(counts)], [H - mb, mt]);
  const ml = leftAxis(svg, y, W, mr, 3, d3.format('~s'));
  const x = d3.scaleLinear([edges[0], Math.max(edges[edges.length - 1], p.event_mean_abs_ar) * 1.05], [ml, W - mr]);
  const gx = svg.append('g').attr('transform', `translate(0,${H - mb})`)
    .call(d3.axisBottom(x).ticks(Math.max(3, Math.floor(W / 90))).tickFormat((v) => v + '%').tickSize(0).tickPadding(8));
  styleAxis(gx);
  svg.selectAll('rect').data(bins).join('rect')
    .attr('x', (b) => x(b.x0)).attr('width', (b) => Math.max(0, x(b.x1) - x(b.x0) - 1))
    .attr('y', (b) => y(b.c)).attr('height', (b) => y(0) - y(b.c)).attr('fill', '#d4d4d4');
  const xe = x(p.event_mean_abs_ar);
  svg.append('line').attr('x1', xe).attr('x2', xe).attr('y1', mt - 6).attr('y2', H - mb).attr('stroke', '#dc2626').attr('stroke-width', 2);
  svg.append('text').attr('x', xe - 4).attr('y', mt - 10).attr('text-anchor', 'end').style('fill', '#dc2626').style('font-weight', 600)
    .text(`event days ${p.event_mean_abs_ar.toFixed(2)}%`);
}

/** Day-0 market-model AR per sector ETF (rows) for every event (columns). */
export function drawSectorStrip(box, rows, sectors, onSelect) {
  const cell = 16, ml = 44, mt = 4, mb = 22;
  const H = mt + sectors.length * cell + mb;
  const { svg, W } = svgFor(box, H);
  const x = d3.scaleBand(rows.map((r) => r.id), [ml, W - 4]).padding(0.08);
  const lim = d3.max(rows, (r) => d3.max(sectors, (s) => Math.abs(r.sectors[s].ar))) || 1;
  const color = d3.scaleDiverging([-lim, 0, lim], (t) => d3.interpolateRdBu(t));
  const tip = makeTip(box);
  sectors.forEach((s, k) => {
    svg.append('text').attr('x', ml - 6).attr('y', mt + k * cell + cell / 2 + 4).attr('text-anchor', 'end').text(s);
    svg.append('g').selectAll('rect').data(rows).join('rect')
      .attr('x', (r) => x(r.id)).attr('width', x.bandwidth()).attr('y', mt + k * cell + 1).attr('height', cell - 2).attr('rx', 2)
      .attr('fill', (r) => color(r.sectors[s].ar)).style('cursor', 'pointer')
      .on('mousemove', (ev, r) => tip.show(ev, [['d', fmtDate(r.date)], ['', `${s} AR ${r.sectors[s].ar.toFixed(2)}% · β ${r.sectors[s].beta.toFixed(2)}`]]))
      .on('mouseleave', tip.hide)
      .on('click', (ev, r) => onSelect(r.id));
  });
  const every = Math.ceil(rows.length / Math.max(2, Math.floor((W - ml) / 60)));
  svg.selectAll('text.d').data(rows.filter((r, i) => i % every === 0)).join('text').attr('class', 'd')
    .attr('x', (r) => x(r.id)).attr('y', H - 6).text((r) => fmtShort(r.date));
}
