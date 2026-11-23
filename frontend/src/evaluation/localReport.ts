export const LOCAL_REPLAY_SOURCE = 'LOCAL_REPLAY_NOT_AGENTARTS_EVALUATION'

export type CaseProvenance = 'SYNTHETIC_DEMO' | 'SYNTHETIC_ATTACK' | 'REAL_DEIDENTIFIED'
const provenanceValues: CaseProvenance[] = ['SYNTHETIC_DEMO', 'SYNTHETIC_ATTACK', 'REAL_DEIDENTIFIED']

export interface LocalReplayRow {
  id: string
  category: string
  provenance: CaseProvenance
  passed: boolean
  status: string
  approvalTools: string[]
  sideEffects: string
  error: string | null
}

export interface LocalReplayReport {
  generatedAt: string
  codeRevision: string
  workingTreeDirty: boolean
  policyHash: string
  datasetHash: string
  total: number
  passed: number
  failed: number
  byProvenance: Record<CaseProvenance, number>
  rows: LocalReplayRow[]
}

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function shortText(value: unknown, limit = 100): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= limit
}

export function parseLocalReplayReport(text: string): LocalReplayReport {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    throw new Error('文件不是有效 JSON。')
  }
  if (!object(raw) || raw.source !== LOCAL_REPLAY_SOURCE || raw.schema_version !== 1 ||
      !Array.isArray(raw.results)) {
    throw new Error('这不是本地案例回放器生成的报告。')
  }
  if (!shortText(raw.generated_at_utc, 60) || !shortText(raw.code_revision, 64) ||
      typeof raw.working_tree_dirty !== 'boolean' ||
      typeof raw.policy_sha256 !== 'string' ||
      !/^[0-9a-f]{64}$/.test(raw.policy_sha256) ||
      typeof raw.dataset_sha256 !== 'string' ||
      !/^[0-9a-f]{64}$/.test(raw.dataset_sha256)) {
    throw new Error('报告缺少可复核的版本信息。')
  }
  if (raw.results.length < 1 || raw.results.length > 500) {
    throw new Error('报告应包含 1–500 条结果。')
  }
  const ids = new Set<string>()
  const rows = raw.results.map((value: unknown): LocalReplayRow => {
    if (!object(value) || !shortText(value.id) || !shortText(value.category) ||
        typeof value.passed !== 'boolean' || ids.has(value.id) ||
        !provenanceValues.includes(value.provenance as CaseProvenance)) {
      throw new Error('报告存在重复编号或无效结果。')
    }
    ids.add(value.id)
    const actual = value.actual
    if (value.passed && !object(actual)) throw new Error('通过的案例缺少实际结果。')
    let status = '运行失败'
    let approvalTools: string[] = []
    let sideEffects = '无结果'
    if (object(actual)) {
      if (!shortText(actual.status) || !Array.isArray(actual.approval_tools) ||
          !actual.approval_tools.every((item: unknown) => shortText(item, 60)) ||
          !object(actual.side_effects)) {
        throw new Error('报告的实际结果格式不正确。')
      }
      const effects = actual.side_effects
      if (typeof effects.calendar_events !== 'number' ||
          !Number.isSafeInteger(effects.calendar_events) || effects.calendar_events < 0 ||
          typeof effects.notifications !== 'number' ||
          !Number.isSafeInteger(effects.notifications) || effects.notifications < 0 ||
          typeof effects.files_changed !== 'boolean') {
        throw new Error('报告的模拟副作用格式不正确。')
      }
      status = actual.status
      approvalTools = actual.approval_tools as string[]
      sideEffects = `日历 ${effects.calendar_events} · 通知 ${effects.notifications} · 文件${effects.files_changed ? '已变更' : '未变更'}`
    }
    return {
      id: value.id,
      category: value.category,
      provenance: value.provenance as CaseProvenance,
      passed: value.passed,
      status,
      approvalTools,
      sideEffects,
      error: shortText(value.error, 100) ? value.error : null,
    }
  })
  const passed = rows.filter((row) => row.passed).length
  if (raw.total !== rows.length || raw.passed !== passed ||
      raw.failed !== rows.length - passed) {
    throw new Error('报告汇总与逐例结果不一致。')
  }
  const byProvenance = Object.fromEntries(
    provenanceValues.map((name) => [name, rows.filter((row) => row.provenance === name).length]),
  ) as Record<CaseProvenance, number>
  if (!object(raw.by_provenance) || provenanceValues.some(
    (name) => raw.by_provenance && (raw.by_provenance as Record<string, unknown>)[name] !== byProvenance[name],
  )) {
    throw new Error('报告来源汇总与逐例结果不一致。')
  }
  return {
    generatedAt: raw.generated_at_utc,
    codeRevision: raw.code_revision,
    workingTreeDirty: raw.working_tree_dirty,
    policyHash: raw.policy_sha256,
    datasetHash: raw.dataset_sha256,
    total: rows.length, passed, failed: rows.length - passed, byProvenance, rows,
  }
}
