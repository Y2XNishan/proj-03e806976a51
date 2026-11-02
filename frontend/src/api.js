/** @typedef {{matched_intervals:number, missing_actual_intervals:number, missing_forecast_intervals:number, mae_mw:number|null, rmse_mw:number|null, bias_mw:number|null}} AccuracyResponse */
/** @typedef {{first_decision_date:string, last_decision_date:string, first_delivery_date:string, last_delivery_date:string, decision_cutoff_local:string, timezone:string, expected_intervals:number, refreshed_at:string, source_rows:Record<string, number>, sources:{actual:string,forecast:string}, accuracy:AccuracyResponse, warnings:string[]}} SummaryResponse */
/** @typedef {{decision_date:string, decision_cutoff_utc:string, start_time_utc:string, forecast_publish_time_utc:string|null, forecast_mw:number|null, actual_mw:number|null, signed_error_mw:number|null}} IntervalResponse */
/** @typedef {{decision_cutoff_local:string, timezone:string, refreshed_at:string, sources:{actual:string,forecast:string}, warnings:string[], intervals:IntervalResponse[]}} TimeseriesResponse */

const base = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '')

async function get(path, signal) {
  let response
  try {
    response = await fetch(`${base}${path}`, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new Error('Cannot reach the analysis API. Check that the backend is running and try again.')
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed with HTTP ${response.status}`
    throw new Error(detail)
  }
  return response.json()
}

export async function getDashboard(signal) {
  const [summary, timeseries, accuracy] = await Promise.all([
    get('/summary', signal), get('/timeseries', signal), get('/accuracy', signal),
  ])
  if (!summary?.first_decision_date || !summary?.last_decision_date || !Array.isArray(timeseries?.intervals)
      || typeof accuracy?.matched_intervals !== 'number') {
    throw new Error('The analysis API returned an unexpected response. Please refresh the page.')
  }
  if (summary.refreshed_at !== timeseries.refreshed_at
      || summary.expected_intervals !== timeseries.intervals.length
      || summary.accuracy?.matched_intervals !== accuracy.matched_intervals) {
    throw new Error('The source snapshot changed during loading. Retry to get a consistent analysis.')
  }
  return { summary, timeseries, accuracy }
}

export function getAccuracy(from, to, signal) {
  const query = new URLSearchParams({ decision_date_from: from, decision_date_to: to })
  return get(`/accuracy?${query}`, signal).then((body) => {
    if (typeof body?.matched_intervals !== 'number' || typeof body?.missing_forecast_intervals !== 'number') {
      throw new Error('The filtered accuracy response was incomplete. Please retry.')
    }
    return body
  })
}
