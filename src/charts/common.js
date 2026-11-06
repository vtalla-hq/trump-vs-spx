import * as d3 from 'd3';
import { el } from '../format.js';

export function svgFor(box, H) {
  box.replaceChildren();
  const W = Math.max(280, box.clientWidth);
  const svg = d3.select(box).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).style('display', 'block');
  return { svg, W };
}

export function styleAxis(g) {
  g.attr('font-size', null).attr('font-family', null);
  g.select('.domain').remove();
}

/** Left axis whose width is measured from its widest label. */
export function leftAxis(svg, y, W, mr, ticks, fmt) {
  const g = svg.append('g').call(d3.axisLeft(y).ticks(ticks).tickFormat(fmt));
  styleAxis(g);
  let ml = 0;
  g.selectAll('text').each(function () { ml = Math.max(ml, this.getComputedTextLength()); });
  ml += 12;
  g.attr('transform', `translate(${ml},0)`);
  g.selectAll('.tick line').attr('x2', W - ml - mr).attr('stroke', 'var(--grid)');
  return ml;
}

export function makeTip(box) {
  const tip = el('div', 'tip');
  tip.style.display = 'none';
  box.appendChild(tip);
  return {
    show(ev, lines) {
      tip.replaceChildren(...lines.map(([cls, t]) => el('div', cls, t)));
      tip.style.display = 'block';
      const b = box.getBoundingClientRect();
      let x = ev.clientX - b.left + 12;
      const y = Math.max(0, ev.clientY - b.top - tip.offsetHeight - 10);
      if (x + tip.offsetWidth > b.width) x = Math.max(0, ev.clientX - b.left - tip.offsetWidth - 12);
      tip.style.left = x + 'px';
      tip.style.top = y + 'px';
    },
    hide() { tip.style.display = 'none'; },
  };
}
