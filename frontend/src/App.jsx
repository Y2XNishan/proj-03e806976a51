import { useEffect, useMemo, useState } from 'react'
import { Activity, AlertCircle, BarChart3, CalendarDays, Clock3, Database, ExternalLink, Info, RefreshCw, ShieldCheck, TrendingUp, Wind, CheckCircle2 } from 'lucide-react'
import { getAccuracy, getDashboard } from './api.js'
import { coveragePercent, filterIntervals, matchedIntervals, validDecisionRange } from './data.js'
import { CoveragePanel, formatCount, formatDay, formatMW, formatTime, Interpretation, LoadingDashboard, MetricCard, ObservationTable, SectionHeading, Skeleton, SourceChart } from './components.jsx'

export default function App() {
  const [reload, setReload] = useState(0)
  const [metricsRetry, setMetricsRetry] = useState(0)
  const [loadState, setLoadState] = useState({ phase: 'loading', error: '' })
  const [bundle, setBundle] = useState(null)
  const [draft, setDraft] = useState(null)
  const [applied, setApplied] = useState(null)
  const [metricResult, setMetricResult] = useState({ key: '', phase: 'loading', value: null, error: '' })

  useEffect(() => {
    const controller = new AbortController()
    setLoadState({ phase: 'loading', error: '' })
    setBundle(null)
    getDashboard(controller.signal).then((result) => {
      const range = { from: result.summary.first_decision_date, to: result.summary.last_decision_date }
      setBundle(result)
      setDraft(range)
      setApplied(range)
      setMetricResult({ key: `${range.from}:${range.to}`, phase: 'ready', value: result.accuracy, error: '' })
      setLoadState({ phase: 'ready', error: '' })
    }).catch((error) => {
      if (error.name !== 'AbortError') setLoadState({ phase: 'error', error: error.message })
    })
    return () => controller.abort()
  }, [reload])

  useEffect(() => {
    if (!bundle || !applied) return undefined
    const key = `${applied.from}:${applied.to}`
    const { summary } = bundle
    if (applied.from === summary.first_decision_date && applied.to === summary.last_decision_date) {
      setMetricResult({ key, phase: 'ready', value: bundle.accuracy, error: '' })
      return undefined
    }
    const controller = new AbortController()
    setMetricResult({ key, phase: 'loading', value: null, error: '' })
    getAccuracy(applied.from, applied.to, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setMetricResult({ key, phase: 'ready', value, error: '' })
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setMetricResult({ key, phase: 'error', value: null, error: error.message })
      })
    return () => controller.abort()
  }, [bundle, applied, metricsRetry])

  const summary = bundle?.summary
  const selected = useMemo(() => bundle && applied ? filterIntervals(bundle.timeseries.intervals, applied.from, applied.to) : [], [bundle, applied])
  const matched = useMemo(() => matchedIntervals(selected), [selected])
  const hourlyOnly = useMemo(() => {
    const forecasted = selected.filter((row) => row.forecast_mw !== null)
    return forecasted.length > 0 && forecasted.every((row) => new Date(row.start_time_utc).getUTCMinutes() === 0)
  }, [selected])
  const rangeKey = applied ? `${applied.from}:${applied.to}` : ''
  const accuracy = metricResult.key === rangeKey && metricResult.phase === 'ready' ? metricResult.value : null
  const metricsLoading = metricResult.key !== rangeKey || metricResult.phase === 'loading'
  const rangeValid = summary && draft && validDecisionRange(draft.from, draft.to, summary.first_decision_date, summary.last_decision_date)
  const oneDay = applied?.from === applied?.to

  function applyRange(event) {
    event.preventDefault()
    if (rangeValid) setApplied({ ...draft })
  }

  function resetRange() {
    if (!summary) return
    const full = { from: summary.first_decision_date, to: summary.last_decision_date }
    setDraft(full)
    setApplied(full)
  }

  return <div className="app-shell">
    <header className="topbar"><div className="topbar-inner">
      <a className="brand" href="#main" aria-label="WindScope Forecast Intelligence, skip to main content"><span className="brand-symbol"><Wind size={21} strokeWidth={2.2} aria-hidden="true" /></span><span>WindScope <small>ENERGY INTELLIGENCE</small></span></a>
      <div className="topbar-meta"><span className="market-label">UK ENERGY MARKET</span><span className={`status-pill ${loadState.phase}`}><span className="status-dot" />{loadState.phase === 'ready' ? 'Source snapshot ready' : loadState.phase === 'error' ? 'Data unavailable' : 'Connecting to data'}</span></div>
    </div></header>

    <main id="main" className="content">
      <div className="hero-grid"><div className="hero-copy"><div className="breadcrumb"><span>MARKET INTELLIGENCE</span><span className="breadcrumb-separator">/</span><span>WIND GENERATION</span></div><h1>Wind Forecast <span>Intelligence</span></h1><p>Historical day-ahead forecast performance for UK wind power purchasing decisions. Review what was known at each decision and how it compared with subsequent generation.</p><div className="hero-badges"><span><CalendarDays size={15} aria-hidden="true" />January 2026 decisions</span><span><ShieldCheck size={15} aria-hidden="true" />Publication-time screened</span></div></div>
        <aside className="hero-aside" aria-label="Analysis scope"><div className="hero-aside-icon"><Wind size={20} aria-hidden="true" /></div><span className="aside-eyebrow">ANALYSIS WINDOW</span><strong>{summary ? `${formatDay(summary.first_decision_date)} – ${formatDay(summary.last_decision_date)}` : 'January 2026'}</strong><p>Purchase-decision dates. Next-day delivery extends through {summary ? formatDay(summary.last_delivery_date) : '1 Feb 2026'}.</p><div className="aside-divider" /><small>Source: Elexon BMRS Insights</small></aside>
      </div>

      {loadState.phase === 'loading' && <LoadingDashboard />}
      {loadState.phase === 'error' && <section className="error-state panel" role="alert"><span className="error-icon"><AlertCircle size={24} aria-hidden="true" /></span><h2>Analysis data is unavailable</h2><p>{loadState.error}</p><p>Check the backend service and its Elexon cache, then retry.</p><button type="button" className="button-primary" onClick={() => setReload((value) => value + 1)}><RefreshCw size={16} aria-hidden="true" />Retry loading</button></section>}

      {loadState.phase === 'ready' && summary && applied && <>
        <section className="filter-card" aria-label="Purchase decision date range"><div className="filter-intro"><span className="filter-icon"><CalendarDays size={18} aria-hidden="true" /></span><div><strong>Decision date range</strong><p>Filter January purchase decisions; charts show delivery on the following day.</p></div></div><form className="filter-form" onSubmit={applyRange}><label>From decision<input type="date" min={summary.first_decision_date} max={summary.last_decision_date} value={draft?.from || ''} onChange={(event) => setDraft((current) => ({ ...current, from: event.target.value }))} required /></label><label>To decision<input type="date" min={summary.first_decision_date} max={summary.last_decision_date} value={draft?.to || ''} onChange={(event) => setDraft((current) => ({ ...current, to: event.target.value }))} required /></label><button type="submit" className="button-primary" disabled={!rangeValid}>Apply range</button><button type="button" className="button-text" onClick={resetRange}>Reset</button></form>{draft && !rangeValid && <p className="filter-error" role="alert">Choose an ordered range within {formatDay(summary.first_decision_date)}–{formatDay(summary.last_decision_date)}.</p>}</section>

        <section className="metrics-section" aria-label="Forecast accuracy key performance indicators"><SectionHeading eyebrow="PERFORMANCE SNAPSHOT" title="Forecast accuracy at a glance" description={`Decisions ${formatDay(applied.from)} – ${formatDay(applied.to)} · Metrics calculated by the API from matched intervals`} right={<span className="section-tag">{selected.length ? `${formatCount(selected.length)} delivery intervals` : 'No intervals'}</span>} />{metricResult.key === rangeKey && metricResult.phase === 'error' && <div className="inline-error" role="alert"><AlertCircle size={17} aria-hidden="true" /><span>{metricResult.error}</span><button type="button" onClick={() => setMetricsRetry((value) => value + 1)}>Retry metrics</button></div>}<div className="metrics-grid"><MetricCard icon={Activity} label="Mean Absolute Error" value={accuracy ? formatMW(accuracy.mae_mw) : '—'} unit="MW" detail="Average absolute difference at matched starts" loading={metricsLoading} /><MetricCard icon={BarChart3} label="Root Mean Square Error" value={accuracy ? formatMW(accuracy.rmse_mw) : '—'} unit="MW" detail="Places more weight on larger errors" tone="blue" loading={metricsLoading} /><MetricCard icon={TrendingUp} label="Mean Forecast Bias" value={accuracy ? formatMW(accuracy.bias_mw, true) : '—'} unit="MW" detail={accuracy?.bias_mw > 0 ? 'Positive means overforecasting' : accuracy?.bias_mw < 0 ? 'Negative means underforecasting' : 'Forecast minus actual, signed'} tone="amber" loading={metricsLoading} /><MetricCard icon={CheckCircle2} label="Matched Coverage" value={accuracy && selected.length ? `${formatMW(coveragePercent(accuracy.matched_intervals, selected.length))}%` : '—'} unit="" detail={accuracy ? `${formatCount(accuracy.matched_intervals)} of ${formatCount(selected.length)} intervals` : 'Exact-start, non-null pairs'} tone="blue" loading={metricsLoading} /></div></section>

        <section className="analysis-section" aria-label="Forecast and actual analysis"><SectionHeading eyebrow="SOURCE-BACKED ANALYSIS" title="Wind generation & forecast error" description="Only exact-start matched observations appear in the charts; all half-hours remain in coverage counts." />{selected.length === 0 && <div className="panel no-intervals"><Info size={21} aria-hidden="true" /><strong>No delivery intervals returned for this decision range.</strong><p>Try another January decision date or refresh the source cache.</p></div>}<div className="analysis-grid"><SourceChart rows={matched} oneDay={oneDay} hourlyOnly={hourlyOnly} />{accuracy ? <CoveragePanel accuracy={accuracy} expected={selected.length} warnings={summary.warnings} hourlyOnly={hourlyOnly} /> : <div className="panel panel-loading">{metricsLoading ? <><Skeleton className="skeleton-line wide" /><Skeleton className="skeleton-chart short" /></> : <p>Coverage metrics are unavailable. Retry above.</p>}</div>}</div><div className="analysis-grid lower-grid"><SourceChart rows={matched} oneDay={oneDay} hourlyOnly={hourlyOnly} mode="error" />{accuracy ? <Interpretation accuracy={accuracy} /> : <div className="panel panel-loading">{metricsLoading ? <><Skeleton className="skeleton-line wide" /><Skeleton className="skeleton-chart short" /></> : <p>Bias interpretation is unavailable until metrics load.</p>}</div>}</div><ObservationTable rows={selected} /></section>

        <section className="method-section" aria-label="How the forecast is selected"><SectionHeading eyebrow="AUDITABLE BY DESIGN" title="How the forecast is selected" description="A point-in-time view of the information available to a hypothetical day-ahead buyer." /><div className="method-grid"><article><span className="method-icon"><Clock3 size={20} aria-hidden="true" /></span><span className="step">01 / DECISION</span><h3>Assumed cutoff</h3><p>Each purchase decision is assumed at <strong>{summary.decision_cutoff_local} {summary.timezone}</strong>. The challenge does not specify an official trading cutoff; this setting is configurable in the backend.</p></article><article><span className="method-icon"><Database size={20} aria-hidden="true" /></span><span className="step">02 / HISTORY</span><h3>Published revisions</h3><p>WINDFOR revisions are filtered by publication time. For each delivery start, the latest revision published at or before that decision is selected.</p></article><article><span className="method-icon"><ShieldCheck size={20} aria-hidden="true" /></span><span className="step">03 / COMPARISON</span><h3>No look-ahead</h3><p>Later revisions are excluded. FUELHH WIND is joined on the exact UTC start, with no fill for absent half-hour forecast values.</p></article></div></section>

        <section className="about-panel panel" aria-labelledby="about-title"><div className="about-icon"><Info size={20} aria-hidden="true" /></div><div><h2 id="about-title">About this analysis</h2><p>MAE, RMSE and signed bias use non-null matched pairs only. A positive bias means the selected forecast is higher than observed wind generation on average. The forecast and outturn feeds may represent different wind-farm populations, so this is a diagnostic view rather than a complete procurement recommendation.</p><div className="source-links"><a href={summary.sources.actual} target="_blank" rel="noreferrer">FUELHH actual <ExternalLink size={13} aria-hidden="true" /></a><a href={summary.sources.forecast} target="_blank" rel="noreferrer">WINDFOR forecast <ExternalLink size={13} aria-hidden="true" /></a><span>Snapshot refreshed {formatTime(summary.refreshed_at)}</span></div></div></section>
      </>}
    </main>
    <footer className="footer"><div><strong>WindScope</strong><span>Wind Forecast Intelligence · UK energy market</span></div><span>Data: Elexon BMRS Insights · January 2026 purchase decisions</span></footer>
  </div>
}

