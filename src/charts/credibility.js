import * as d3 from 'd3';
import { colorFor, fmtDate, toDate } from '../format.js';
import { svgFor, leftAxis, styleAxis, makeTip } from './common.js';

/** Running "kept his word" % with a dashed 50% line. */
export function drawCredibility(box, rows, onSelect) {
  const H = 200, mt = 14, mb = 26, mr = 46;
  const { svg, W } = svgFor(box, H);
  const data = rows.map((r) => ({ ...r, t: toDate(r.date) }));
  const y = d3.scaleLinear([0, 1], [H - mb, mt]);
  const ml = leftAxis(svg, y, W, mr, 4, d3.format('.0%'));
  const x = d3.scaleUtc(d3.extent(data, (r) => r.t), [ml + 6, W - mr]);
  const gx = svg.append('g').attr('transform', `translate(0,${H - mb})`)
    .call(d3.axisBottom(x).ticks(W < 520 ? d3.utcMonth.every(6) : Math.max(2, Math.floor(W / 120))).tickFormat(d3.utcFormat("%b '%y")).tickSize(0).tickPadding(8));
  styleAxis(gx);

  svg.append('line').attr('x1', ml).attr('x2', W - mr).attr('y1', y(0.5)).attr('y2', y(0.5))
    .attr('stroke', 'var(--axis)').attr('stroke-dasharray', '4 4');
  svg.append('path').datum(data).attr('d', d3.line().x((r) => x(r.t)).y((r) => y(r.rate)))
    .attr('fill', 'none').attr('stroke', '#111').attr('stroke-width', 2).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');

  const tip = makeTip(box);
  svg.selectAll('circle').data(data).join('circle')
    .attr('cx', (r) => x(r.t)).attr('cy', (r) => y(r.rate)).attr('r', 4)
    .attr('fill', (r) => colorFor(r.tag)).attr('stroke', '#fff').attr('stroke-width', 1.5).style('cursor', 'pointer')
    .on('mousemove', (ev, r) => tip.show(ev, [['d', fmtDate(r.date)], ['', r.headline], ['', `${r.kept} of ${r.total} kept · ${d3.format('.0%')(r.rate)}`]]))
    .on('mouseleave', tip.hide)
    .on('click', (ev, r) => onSelect(r.id));

  const last = data[data.length - 1];
  svg.append('text').attr('x', x(last.t) + 8).attr('y', y(last.rate) + 4)
    .style('fill', '#111').style('font-weight', 600).text(d3.format('.0%')(last.rate));
}
