import * as d3 from 'd3';
import { normTag } from './format.js';

const PROMISE_TAGS = ['Followed through', 'Walked back', "Didn't check out"];

/** Worst and best event days by S&P 500 % move. */
export function extremes(events) {
  const s = [...events].sort((a, b) => a.pct - b.pct);
  return { worst: s[0], best: s[s.length - 1] };
}

/** How many events fall under each outcome. */
export function tagCounts(events) {
  return [...d3.rollup(events, (v) => v.length, (r) => normTag(r.tag))].map(([tag, n]) => ({ tag, n }));
}

/** First trading day after each new tariff threat. */
export const threatDays = (events) => events.filter((r) => r.threat_day);

/** Headline totals. "Broke" = walked back or a false claim. */
export function summary(events) {
  return {
    events: events.length,
    followed: events.filter((r) => r.tag === 'Followed through').length,
    broke: events.filter((r) => r.tag === 'Walked back' || r.tag === "Didn't check out").length,
    avgAbs: d3.mean(events, (r) => Math.abs(r.pct)),
  };
}

/** Running follow-through rate, counting only real promises. */
export function credibility(events) {
  let kept = 0, total = 0;
  return events
    .filter((r) => PROMISE_TAGS.includes(r.tag))
    .map((r) => {
      total++;
      if (r.tag === 'Followed through') kept++;
      return { ...r, kept, total, rate: kept / total };
    });
}
