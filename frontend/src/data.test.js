import test from 'node:test'
import assert from 'node:assert/strict'
import { coveragePercent, filterIntervals, matchedIntervals, validDecisionRange } from './data.js'

test('range is constrained to January decision dates and ordered', () => {
  assert.equal(validDecisionRange('2026-01-01', '2026-01-31', '2026-01-01', '2026-01-31'), true)
  assert.equal(validDecisionRange('2026-01-31', '2026-01-01', '2026-01-01', '2026-01-31'), false)
  assert.equal(validDecisionRange('2026-01-01', '2026-02-01', '2026-01-01', '2026-01-31'), false)
})

test('decision filter keeps February delivery from January 31 and sorts ISO instants', () => {
  const rows = [
    { decision_date: '2026-01-31', start_time_utc: '2026-02-01T01:00:00Z' },
    { decision_date: '2026-01-30', start_time_utc: '2026-01-31T00:00:00Z' },
    { decision_date: '2026-01-31', start_time_utc: '2026-02-01T00:00:00Z' },
  ]
  assert.deepEqual(filterIntervals(rows, '2026-01-31', '2026-01-31').map((row) => row.start_time_utc),
    ['2026-02-01T00:00:00Z', '2026-02-01T01:00:00Z'])
})

test('missing forecast is distinct from zero generation', () => {
  const rows = [
    { forecast_mw: 0, actual_mw: 20, signed_error_mw: -20 },
    { forecast_mw: null, actual_mw: 20, signed_error_mw: null },
  ]
  assert.equal(matchedIntervals(rows).length, 1)
  assert.equal(coveragePercent(1, 2), 50)
  assert.equal(coveragePercent(0, 0), null)
})
