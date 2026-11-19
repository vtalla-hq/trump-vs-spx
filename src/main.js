import './style.css';
import { drawTimeline } from './charts/timeline.js';
import { drawCredibility } from './charts/credibility.js';
import { drawThreats } from './charts/threats.js';
import { renderScorecard } from './ui/scorecard.js';
import { renderDetail, renderCalibration } from './ui/detail.js';
import { renderEvents, renderKobeissi, renderAR, renderBacktest } from './ui/tables.js';
import { drawPermutation, drawSectorStrip, drawCalibration } from './charts/numbers.js';
import { credibility, threatDays } from './stats.js';
import { el, fmtPct } from './format.js';
import { renderDeadlines, renderForecasts } from './ui/forecast.js';

const $ = (id) => document.getElementById(id);
const state = { events: [], auto: [], spx: [], kob: [], study: null, cal: null, fc: null, selected: null };
const handRows = () => state.study.events.filter((r) => !r.auto);
const studyFor = (id) => state.study.events.find((r) => r.id === id);

async function load(name) {
  const res = await fetch(`/data/${name}.json`);
  if (!res.ok) throw new Error(`${name}: ${res.status}`);
  return res.json();
}
const loadOpt = (name, fallback) => load(name).catch(() => fallback);

function select(id, scroll = false) {
  state.selected = id;
  renderSelected();
  if (scroll) $('detail').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function current() {
  return [...state.events, ...state.auto].find((r) => r.id === state.selected)
    || [...state.events].sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct))[0];
}

function renderSelected() {
  const r = current();
  renderDetail($('detail'), r, studyFor(r.id));
  drawTimeline($('timeline'), state.spx, [...state.events, ...state.auto], state.selected, select);
  renderEvents($('events-table'), state.events, state.selected, select);
  renderAR($('ar-table'), handRows(), state.events, state.selected, select);
}

function renderCharts() {
  drawTimeline($('timeline'), state.spx, [...state.events, ...state.auto], state.selected, select);
  drawCredibility($('cred'), credibility(state.events), select);
  drawThreats($('decay'), threatDays(state.events), select);
  drawPermutation($('perm'), state.study.permutation.overall);
  drawSectorStrip($('sectors'), handRows(), Object.keys(state.study.events[0].sectors), select);
  if (state.fc) drawCalibration($('fc-cal'), state.fc.live.calibration.length ? state.fc.live.calibration : state.fc.backtest.calibration);
}

function renderNumbers() {
  const { permutation: p, backtest: bt } = state.study;
  const fmtP = (v) => (v <= 1 / p.draws ? `< ${(1 / p.draws).toFixed(4)}` : v.toFixed(4));
  $('perm-cap').textContent = `Event days (n=${p.overall.n}): mean |AR| ${p.overall.event_mean_abs_ar.toFixed(2)}% vs ${p.overall.null_mean_abs_ar.toFixed(2)}% on ${p.draws.toLocaleString()} random draws of ${p.overall.n} non-event days. p ${fmtP(p.overall.p_value)}. By topic: `
    + Object.entries(p.by_topic).map(([t, v]) => `${t} (n=${v.n}) p ${fmtP(v.p_value)}`).join(' · ') + '.';
  $('bt-cap').textContent = `${bt.rule} ${bt.caveat} Sharpe ${bt.sharpe_annualized?.toFixed(1) ?? '—'} (annualized, n=${bt.n}).`;
  renderBacktest($('bt-table'), bt, state.events, select);
  $('ar-n').textContent = handRows().length;
  renderCalibration($('cal'), state.cal);
}

function renderKpis() {
  const { permutation: { overall: o, draws }, backtest: bt } = state.study;
  const tile = (v, of, k, n) => {
    const t = el('div', 'kpi'), val = el('div', 'v', v);
    if (of) val.append(el('span', 'of', ` ${of}`));
    t.append(val, el('div', 'k', k), el('div', 'n', n));
    return t;
  };
  const tiles = [
    tile(`${o.event_mean_abs_ar.toFixed(2)}%`, `vs ${o.null_mean_abs_ar.toFixed(2)}%`, 'Mean |abnormal return|, event days vs random days',
      `n=${o.n} · p ${o.p_value <= 1 / draws ? '< 0.001' : o.p_value.toFixed(3)}`),
    tile(`${Math.round(bt.hit_rate * bt.n)}/${bt.n}`, `${fmtPct(bt.avg_ret)} avg`, '"TACO" trades that made money',
      `n=${bt.n} · ${fmtPct(bt.avg_baseline)} avg SPX baseline`),
  ];
  const f = state.fc;
  if (f) tiles.push(
    tile(`${Math.round(f.base_rate * 100)}%`, null, 'Past deadlines he walked back or extended', `n=${f.n_resolved}`),
    tile(f.backtest.brier.model.toFixed(3), `vs ${f.backtest.brier.base.toFixed(3)}`,
      `Forecast Brier vs base rate: ${f.backtest.beats_base ? 'beats it' : 'does not beat it'}`, `n=${f.backtest.n} · lower is better`),
  );
  $('kpis').replaceChildren(...tiles);
}

async function init() {
  try {
    const [events, daily, kob, study, auto, cal] = await Promise.all([load('events'), load('daily'), load('kobeissi'), load('study'),
      loadOpt('auto_events', []), loadOpt('calibration', null)]);
    state.fc = await loadOpt('forecast', null);
    const hand = new Set(events.map((r) => r.date));
    state.auto = auto.filter((r) => !hand.has(r.date) && r.pct != null);
    state.cal = cal;
    state.events = events.map((r) => ({ ...r, pct: Number(r.pct) })).sort((a, b) => (a.date < b.date ? -1 : 1));
    state.spx = daily.filter((r) => r.date >= '2025-01-01');
    state.kob = kob;
    state.study = study;
  } catch (err) {
    $('detail').textContent = `Couldn't load data (${err.message}).`;
    return;
  }
  renderScorecard(state.events, select);
  renderKobeissi($('kob-table'), state.kob, select);
  renderNumbers();
  renderKpis();
  renderDeadlines($('deadlines'), state.fc);
  if (state.fc) renderForecasts(state.fc);
  renderSelected();
  renderCharts();

  let raf;
  new ResizeObserver(() => { cancelAnimationFrame(raf); raf = requestAnimationFrame(renderCharts); }).observe(document.querySelector('.tp'));
}

init();
