import './style.css';
import { drawTimeline } from './charts/timeline.js';
import { drawCredibility } from './charts/credibility.js';
import { drawThreats } from './charts/threats.js';
import { renderScorecard } from './ui/scorecard.js';
import { renderDetail } from './ui/detail.js';
import { renderEvents, renderKobeissi } from './ui/tables.js';
import { credibility, threatDays } from './stats.js';

const $ = (id) => document.getElementById(id);
const state = { events: [], spx: [], kob: [], selected: null };

async function load(name) {
  const res = await fetch(`/data/${name}.json`);
  if (!res.ok) throw new Error(`${name}: ${res.status}`);
  return res.json();
}

function select(id, scroll = false) {
  state.selected = id;
  renderSelected();
  if (scroll) $('detail').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function current() {
  return state.events.find((r) => r.id === state.selected)
    || [...state.events].sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
}

function renderSelected() {
  renderDetail($('detail'), current());
  drawTimeline($('timeline'), state.spx, state.events, state.selected, select);
  renderEvents($('events-table'), state.events, state.selected, select);
}

function renderCharts() {
  drawTimeline($('timeline'), state.spx, state.events, state.selected, select);
  drawCredibility($('cred'), credibility(state.events), select);
  drawThreats($('decay'), threatDays(state.events), select);
}

async function init() {
  try {
    const [events, spx, kob] = await Promise.all([load('events'), load('spx_monthly'), load('kobeissi')]);
    state.events = events.map((r) => ({ ...r, pct: Number(r.pct) })).sort((a, b) => (a.date < b.date ? -1 : 1));
    state.spx = spx.map((r) => ({ ...r, avg_close: Number(r.avg_close) }));
    state.kob = kob;
  } catch (err) {
    $('detail').textContent = `Couldn't load data (${err.message}).`;
    return;
  }
  renderScorecard(state.events, select);
  renderKobeissi($('kob-table'), state.kob, select);
  renderDetail($('detail'), current());
  renderEvents($('events-table'), state.events, state.selected, select);
  renderCharts();

  let raf;
  new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(renderCharts); }).observe(document.querySelector('.tp'));
}

init();
