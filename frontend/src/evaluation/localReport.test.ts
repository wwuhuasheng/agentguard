import { describe, expect, it } from 'vitest'
import { LOCAL_REPLAY_SOURCE, parseLocalReplayReport } from './localReport'

const valid = {
  schema_version: 1,
  source: LOCAL_REPLAY_SOURCE,
  generated_at_utc: '2026-11-21T02:00:00+00:00',
  code_revision: 'a'.repeat(40),
  working_tree_dirty: true,
  policy_sha256: 'b'.repeat(64),
  dataset_sha256: 'c'.repeat(64),
  total: 2,
  passed: 1,
  failed: 1,
  by_provenance: { SYNTHETIC_DEMO: 1, SYNTHETIC_ATTACK: 0, REAL_DEIDENTIFIED: 1 },
  results: [
    {
      id: 'LOCAL-01', category: 'normal', provenance: 'SYNTHETIC_DEMO', passed: true,
      actual: {
        status: 'COMPLETED', approval_tools: [],
        side_effects: { calendar_events: 1, notifications: 1, files_changed: false },
      },
    },
    { id: 'LOCAL-02', category: 'approval', provenance: 'REAL_DEIDENTIFIED', passed: false, error: 'HTTPError' },
  ],
}

describe('local replay report import', () => {
  it('reads actual local results while retaining failed cases in the denominator', () => {
    const report = parseLocalReplayReport(JSON.stringify(valid))
    expect([report.total, report.passed, report.failed]).toEqual([2, 1, 1])
    expect(report.rows[0]!.sideEffects).toContain('通知 1')
    expect(report.rows[1]!.status).toBe('运行失败')
    expect(report.byProvenance.REAL_DEIDENTIFIED).toBe(1)
  })

  it('rejects a forged summary or a report without the local-only source marker', () => {
    expect(() => parseLocalReplayReport(JSON.stringify({ ...valid, passed: 2 }))).toThrow('汇总')
    expect(() => parseLocalReplayReport(JSON.stringify({ ...valid, source: 'AGENTARTS' }))).toThrow('本地案例')
  })

  it('rejects a forged provenance summary', () => {
    const forged = { ...valid, by_provenance: { ...valid.by_provenance, REAL_DEIDENTIFIED: 2 } }
    expect(() => parseLocalReplayReport(JSON.stringify(forged))).toThrow('来源汇总')
  })

  it('rejects duplicate case IDs', () => {
    const duplicate = { ...valid, results: [valid.results[0], { ...valid.results[1], id: 'LOCAL-01' }] }
    expect(() => parseLocalReplayReport(JSON.stringify(duplicate))).toThrow('重复编号')
  })
})
