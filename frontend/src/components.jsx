import { useState } from 'react'
import { Activity, ArrowDownRight, ArrowUpRight, BarChart3, CheckCircle2, Info, ShieldCheck, TrendingUp } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { coveragePercent } from './data.js'

const number = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
const integer = new Intl.NumberFormat('en-GB')
const dateTime = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const axisDay = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', day: '2-digit', month: 'short' })
const axisHour = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const dayFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric' })

export function formatMW(value, signed = false) {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : `${signed && value > 0 ? '+' : ''}${number.format(value)}`
}

export function formatDay(isoDay) {
  return isoDay ? dayFormat.format(new Date(`${isoDay}T12:00:00Z`)) : '—'
}

export function formatTime(isoTime) {
  return isoTime ? `${dateTime.format(new Date(isoTime))} UK` : '—'
}

export function formatCount(value) { return integer.format(value) }

export function Skeleton({ className = '' }) { return <span className={`skeleton ${className}`} aria-hidden="true" /> }

export function SectionHeading({ eyebrow, title, description, right }) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{description && <p>{description}</p>}</div>{right && <div className="section-heading-right">{right}</div>}</div>
}

export function MetricCard({ icon: Icon, label, value, unit, detail, tone = 'teal', loading = false }) {
  return <article className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={18} aria-hidden="true" /></span></div>{loading ? <Skeleton className="skeleton-metric" /> : <div className="metric-value">{value}<span>{unit}</span></div>}<p>{detail}</p></article>
}

function PowerTooltip({ active, payload, mode }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  return <div className="chart-tooltip"><strong>{formatTime(row.start_time_utc)}</strong><span>Decision: {formatDay(row.decision_date)}</span>{mode === 'error' ? <div className="tooltip-row"><i className="legend-dot amber" />Signed error <b>{formatMW(row.signed_error_mw, true)} MW</b></div> : <><div className="tooltip-row"><i className="legend-dot navy" />FUELHH actual <b>{formatMW(row.actual_mw)} MW</b></div><div className="tooltip-row"><i className="legend-dot teal" />WINDFOR forecast <b>{formatMW(row.forecast_mw)} MW</b></div><small>Forecast published {formatTime(row.forecast_publish_time_utc)}</small></>}</div>
}

function EmptyChart() {
  return <div className="chart-empty"><BarChart3 size={28} aria-hidden="true" /><strong>No matched observations in this selection</strong><p>Try a wider decision-date range. Missing source values are excluded from charts.</p></div>
}

export function SourceChart({ rows, oneDay, mode, hourlyOnly }) {
  const error = mode === 'error'
  const title = error ? 'Forecast error over time' : 'Actual vs forecast generation'
  return <section className="panel chart-panel" aria-label={title}>
    <div className="panel-heading"><div className="panel-title-row"><span className="panel-icon">{error ? <TrendingUp size={18} aria-hidden="true" /> : <Activity size={18} aria-hidden="true" />}</span><div><h3>{title}</h3><p>{error ? 'Signed difference: selected forecast minus actual generation' : `FUELHH actual and selected WINDFOR forecast at exact ${hourlyOnly ? 'hourly' : 'UTC'} starts`}</p></div></div><span className="chart-tag">{error ? 'MW · SIGNED' : `MW · ${hourlyOnly ? 'HOURLY' : 'EXACT'} STARTS`}</span></div>
    {rows.length ? <div className={`chart-body ${error ? 'error-chart' : ''}`} role="img" aria-label={`${title}, ${rows.length} matched source observations`}><ResponsiveContainer width="100%" height="100%"><LineChart data={rows} margin={{ top: 12, right: 14, left: 2, bottom: 4 }}><CartesianGrid stroke="#e7eef1" strokeDasharray="4 5" vertical={false} /><XAxis dataKey="start_time_utc" tickFormatter={(value) => (oneDay ? axisHour : axisDay).format(new Date(value))} minTickGap={32} tickLine={false} axisLine={false} tick={{ fill: '#75899a', fontSize: 11 }} /><YAxis tickFormatter={(value) => `${Math.round(value / 1000)}k`} tickLine={false} axisLine={false} width={42} tick={{ fill: '#75899a', fontSize: 11 }} />{error && <ReferenceLine y={0} stroke="#8396a4" strokeDasharray="4 4" />}<Tooltip content={<PowerTooltip mode={mode} />} />{!error && <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />}{error ? <Line name="Signed error" type="monotone" dataKey="signed_error_mw" stroke="#e9935b" strokeWidth={2} dot={rows.length === 1 ? { r: 4 } : false} activeDot={{ r: 5 }} isAnimationActive={false} /> : <><Line name="FUELHH actual" type="monotone" dataKey="actual_mw" stroke="#183c57" strokeWidth={2.25} dot={rows.length === 1 ? { r: 4 } : false} activeDot={{ r: 5 }} isAnimationActive={false} /><Line name="WINDFOR forecast" type="monotone" dataKey="forecast_mw" stroke="#21a79d" strokeWidth={2.25} dot={rows.length === 1 ? { r: 4 } : false} activeDot={{ r: 5 }} isAnimationActive={false} /></>}</LineChart></ResponsiveContainer></div> : <EmptyChart />}
    <p className="chart-footnote">{error ? 'Above zero means overforecasting at that observed start; below zero means underforecasting.' : `Lines connect observed ${hourlyOnly ? 'hour-start' : 'exact-start'} pairs for readability. Missing intervals are not filled.`}</p>
  </section>
}

export function ObservationTable({ rows }) {
  const [open, setOpen] = useState(false)
  return <details className="observation-panel panel" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary><span><strong>Inspect interval records</strong><small>Accessible source values, including missing forecast intervals</small></span><span className="section-tag">{integer.format(rows.length)} intervals</span></summary>
    {open && <div className="table-scroll"><table><caption>Selected purchase decisions and their next-day delivery intervals. Missing means no eligible source value; zero is a measured value.</caption><thead><tr><th scope="col">Decision</th><th scope="col">Delivery start (UK)</th><th scope="col">Forecast published (UK)</th><th scope="col">Actual MW</th><th scope="col">Forecast MW</th><th scope="col">Error MW</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.decision_date}-${row.start_time_utc}`}><td>{formatDay(row.decision_date)}</td><td>{formatTime(row.start_time_utc)}</td><td>{row.forecast_publish_time_utc ? formatTime(row.forecast_publish_time_utc) : 'Missing'}</td><td>{row.actual_mw === null ? 'Missing' : formatMW(row.actual_mw)}</td><td>{row.forecast_mw === null ? 'Missing' : formatMW(row.forecast_mw)}</td><td>{row.signed_error_mw === null ? '—' : formatMW(row.signed_error_mw, true)}</td></tr>)}</tbody></table></div>}
  </details>
}

export function CoveragePanel({ accuracy, expected, warnings, hourlyOnly }) {
  const percentage = coveragePercent(accuracy.matched_intervals, expected)
  return <section className="panel insight-panel" aria-labelledby="coverage-title"><div className="panel-title-row"><span className="panel-icon"><CheckCircle2 size={18} aria-hidden="true" /></span><div><h3 id="coverage-title">Coverage & data quality</h3><p>Exact-start source matching</p></div></div><div className="coverage-number">{percentage === null ? '—' : `${number.format(percentage)}%`}<small>matched coverage</small></div><div className="coverage-track" role="progressbar" aria-label="Matched interval coverage" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage ?? 0}><span style={{ width: `${percentage ?? 0}%` }} /></div><div className="coverage-rows"><div><span><i className="legend-dot teal" />Matched intervals</span><strong>{integer.format(accuracy.matched_intervals)}</strong></div><div><span><i className="legend-dot pale" />Missing forecast</span><strong>{integer.format(accuracy.missing_forecast_intervals)}</strong></div><div><span><i className="legend-dot gray" />Missing actual</span><strong>{integer.format(accuracy.missing_actual_intervals)}</strong></div></div><div className="quality-callout"><Info size={17} aria-hidden="true" /><p>{hourlyOnly ? 'WINDFOR targets in this selection start hourly; FUELHH reports half-hour averages. ' : 'WINDFOR and FUELHH are joined only at exact UTC starts. '}Unmatched half-hours are missing forecasts, not zero wind output.</p></div>{warnings?.length > 0 && <details className="warnings"><summary>Source and coverage notes ({warnings.length})</summary><ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></details>}</section>
}

export function Interpretation({ accuracy }) {
  const bias = accuracy.bias_mw
  const positive = bias !== null && bias > 0
  const negative = bias !== null && bias < 0
  return <section className="panel interpretation-panel" aria-labelledby="interpret-title"><div className="panel-title-row"><span className="panel-icon amber-icon">{positive ? <ArrowUpRight size={18} aria-hidden="true" /> : negative ? <ArrowDownRight size={18} aria-hidden="true" /> : <Info size={18} aria-hidden="true" />}</span><div><h3 id="interpret-title">Purchasing interpretation</h3><p>What signed bias suggests</p></div></div><p className="interpret-lead">{positive ? 'The selected forecast exceeded actual wind output on average at matched starts.' : negative ? 'Actual wind output exceeded the selected forecast on average at matched starts.' : bias === null ? 'There are no matched intervals to interpret in this selection.' : 'The matched sample has no average directional error.'}</p><p>{positive ? 'A buyer relying on that forecast could need additional replacement power relative to the forecasted wind position.' : negative ? 'A buyer could need less replacement power than the wind forecast alone implied.' : 'Use the matched sample and coverage before drawing a purchasing conclusion.'}</p><div className="interpret-caveat"><ShieldCheck size={16} aria-hidden="true" /><span>Actual procurement also depends on demand, contracts, other generation, prices and portfolio position. These wind feeds may cover different asset populations.</span></div></section>
}

export function LoadingDashboard() {
  return <div role="status" aria-label="Loading source-backed analysis"><div className="filter-card loading-filter"><Skeleton className="skeleton-line wide" /><Skeleton className="skeleton-line" /></div><div className="metrics-grid">{[0, 1, 2, 3].map((key) => <MetricCard key={key} icon={Activity} label="Loading metric" detail="Loading source-backed result" loading />)}</div><div className="loading-panel panel"><Skeleton className="skeleton-line wide" /><Skeleton className="skeleton-chart" /></div></div>
}
