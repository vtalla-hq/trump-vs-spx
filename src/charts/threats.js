import * as d3 from 'd3';
import { fmtPct, fmtDate, toDate } from '../format.js';
import { svgFor, makeTip } from './common.js';

/** S&P 500 move on the first trading day after each new tariff threat. */
export function drawThreats(box, rows, onSelect) {
  const H = 200, mt = 22, mb = 34;
  const { svg, W } = svgFor(box, H);
  const x = d3.scalePoint(rows.map((r) => r.id), [48, W - 48]);
  const y = d3.scaleLinear([d3.min(rows, (r) => r.pct) * 1.15, 0], [H - mb, mt]);
  const red = '#dc2626';

  svg.append('line').attr('x1', 0).attr('x2', W).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--axis)');
  svg.append('path').datum(rows).attr('d', d3.line().x((r) => x(r.id)).y((r) => y(r.pct)))
    .attr('fill', 'none').attr('stroke', red).attr('stroke-width', 2).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');

  const tip = makeTip(box);
  svg.selectAll('circle').data(rows).join('circle')
    .attr('cx', (r) => x(r.id)).attr('cy', (r) => y(r.pct)).attr('r', 5).attr('fill', red).style('cursor', 'pointer')
    .on('mousemove', (ev, r) => tip.show(ev, [['d', fmtDate(r.date)], ['', r.headline]]))
    .on('mouseleave', tip.hide)
    .on('click', (ev, r) => onSelect(r.id));
  svg.selectAll('text.v').data(rows).join('text').attr('class', 'v')
    .attr('x', (r) => x(r.id)).attr('y', (r) => y(r.pct) + 18).attr('text-anchor', 'middle').style('fill', '#111').text((r) => fmtPct(r.pct));
  svg.selectAll('text.l').data(rows).join('text').attr('class', 'l')
    .attr('x', (r) => x(r.id)).attr('y', H - 6).attr('text-anchor', 'middle').text((r) => d3.utcFormat("%b '%y")(toDate(r.date)));
}
