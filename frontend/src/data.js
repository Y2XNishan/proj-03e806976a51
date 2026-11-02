export function validDecisionRange(from, to, first, last) {
  return Boolean(from && to && first && last && first <= from && from <= to && to <= last)
}

export function filterIntervals(intervals, from, to) {
  return intervals
    .filter((row) => from <= row.decision_date && row.decision_date <= to)
    .sort((a, b) => Date.parse(a.start_time_utc) - Date.parse(b.start_time_utc))
}

export function matchedIntervals(intervals) {
  return intervals.filter((row) => Number.isFinite(row.forecast_mw)
    && Number.isFinite(row.actual_mw) && Number.isFinite(row.signed_error_mw))
}

export function coveragePercent(matched, expected) {
  return expected > 0 ? (matched / expected) * 100 : null
}
