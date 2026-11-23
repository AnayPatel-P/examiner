// Typed client for the Examiner API (src/examiner/api/app.py). Shapes mirror the FastAPI responses.

export type Verdict = 0 | 1 | null
export type Rubric = 'factual' | 'disclosure' | 'commitments'
export const RUBRICS: Rubric[] = ['factual', 'disclosure', 'commitments']
export type Check = 'overall' | 'fact' | 'judge' | Rubric
export const CHECKS: Check[] = ['overall', 'fact', 'judge', ...RUBRICS]

export interface Cell {
  passed: number
  n: number
  rate: number | null
}

export interface RunSummary {
  id: string
  target: string
  variant: string
  pack: string
  started_at: string
  judge_version: string | null
  cost_usd: number | null
  target_cost_usd: number | null
  wall_seconds: number | null
  n: number
  errors: number
  overall: Cell
  fact: Cell
  judge: Cell
}

export type ScorecardArea = Record<Check, Cell> & { errors: number }
export type Scorecard = Record<string, ScorecardArea>

export interface ResultRow {
  sample_id: string
  epoch: number
  area: string
  overall: Verdict
  fact_pass: Verdict
  judge_pass: Verdict
  rubrics: Partial<Record<Rubric, Verdict>>
  citation: string | null
  error: string | null
}

export interface RunOps {
  n: number
  judge_cost_usd: number | null
  target_cost_usd: number | null
  total_cost_usd: number | null
  cost_per_scenario_usd: number | null
  wall_seconds: number | null
  latency_p50_s: number | null
  latency_p95_s: number | null
  latency_mean_s: number | null
}

export interface TaxonomyRow {
  section: string
  section_title: string
  n: number
  failed: number
}
export interface Taxonomy {
  scored_scenarios: number
  failed_scenarios: number
  modes: Record<string, number>
  sections: TaxonomyRow[]
  clauses: (TaxonomyRow & { citation: string; modes: Record<string, number>; failing: string[] })[]
}

export interface Fact {
  id: string
  any_of: string[]
  note?: string
}

export interface CitationText {
  cite: string
  display: string
  text: string | null
}

export interface ResultDetail {
  run_id: string
  sample_id: string
  epoch: number
  area: string
  overall: Verdict
  fact_pass: Verdict
  judge_pass: Verdict
  error: string | null
  transcript: string | null
  fact_detail: { missing?: string[]; forbidden?: string[]; citation?: string } | null
  scenario: {
    persona: string
    turns: string[]
    must_say: Fact[]
    must_not_say: Fact[]
    source_note: string
    seed_id: string | null
  } | null
  scores: { rubric: Rubric; passed: Verdict; rationale: string | null; judge_version: string | null }[]
  citations: CitationText[]
}

export interface QueueItem {
  run_id: string
  sample_id: string
  epoch: number
  rubric: Rubric
  transcript: string
  citations: CitationText[]
  source_note: string
  key_facts: string[][]
  rubric_text: string
}

export interface LabelBatch {
  name: string
  n: number
  labeled: number
}

export interface LabelIn {
  run_id: string
  sample_id: string
  epoch: number
  rubric: Rubric
  human_pass: boolean
}

export interface AgreementReport {
  n: number
  n_labels: number
  raw_agreement: number | null
  kappa: number | null
  both_pass: number
  judge_pass_human_fail: number
  judge_fail_human_pass: number
  both_fail: number
  disagreements: { run_id: string; sample_id: string; epoch: number }[]
}
export type Calibration = Partial<Record<Rubric, AgreementReport>>

export type DiffCategory =
  | 'fixed' | 'broke' | 'still_fail' | 'still_pass' | 'unscored' | 'only_a' | 'only_b'
export const DIFF_CATEGORIES: DiffCategory[] = [
  'broke', 'fixed', 'still_fail', 'unscored', 'only_a', 'only_b', 'still_pass',
]
export interface DiffItem {
  sample_id: string
  epoch: number
  a: Verdict
  b: Verdict
}
export type Diff = Record<DiffCategory, DiffItem[]> & {
  check: Check
  a: RunSummary
  b: RunSummary
  counts: Record<DiffCategory, number>
}

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

const BASE = '/api'

function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the Examiner API. Start it with `uv run examiner serve`.')
  }
  const body = await res.json().catch(() => null)
  // Behind the Vite proxy a stopped API shows up as a bodiless 5xx, not a network error.
  if (res.status >= 502 || (res.status === 500 && body === null)) {
    throw new ApiError(0, 'Cannot reach the Examiner API. Start it with `uv run examiner serve`.')
  }
  if (res.ok && body === null) throw new ApiError(res.status, 'The API returned an empty or non-JSON response.')
  if (!res.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail)
  }
  return body as T
}

const enc = encodeURIComponent

const liveApi = {
  runs: () => request<RunSummary[]>('/runs'),
  run: (id: string) => request<{ run: RunSummary; scorecard: Scorecard; ops: RunOps }>(`/runs/${enc(id)}`),
  taxonomy: (id: string) => request<Taxonomy>(`/runs/${enc(id)}/taxonomy`),
  results: (id: string, f: { area?: string; status?: string } = {}) =>
    request<ResultRow[]>(`/runs/${enc(id)}/results${query(f)}`),
  result: (id: string, sample: string, epoch = 1) =>
    request<ResultDetail>(`/runs/${enc(id)}/results/${enc(sample)}${query({ epoch })}`),
  labelQueue: (p: { rubric?: Rubric; run?: string; batch?: string; limit?: number }) =>
    request<QueueItem[]>(`/label-queue${query(p)}`),
  batches: () => request<LabelBatch[]>('/batches'),
  postLabel: (body: LabelIn) =>
    request<LabelIn>('/labels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  labels: (p: { rubric?: Rubric; run?: string } = {}) =>
    request<(LabelIn & { created_at: string })[]>(`/labels${query(p)}`),
  calibration: () => request<Calibration>('/calibration'),
  diff: (a: string, b: string, check: Check = 'overall') => request<Diff>(`/diff${query({ a, b, check })}`),
}

// Static mode (GitHub Pages): read the JSON snapshot written by `examiner export`.
// Filtering that the API does server-side happens here instead. Labeling is local-only.
export const STATIC = import.meta.env.VITE_STATIC === '1'

const cache = new Map<string, Promise<unknown>>()
function snapshot<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const url = `${import.meta.env.BASE_URL}data/${path}`
    cache.set(
      path,
      fetch(url).then(
        (r) => {
          if (!r.ok) throw new ApiError(r.status, r.status === 404 ? 'Not in this snapshot.' : `Request failed (${r.status})`)
          return r.json()
        },
        () => {
          throw new ApiError(0, 'Cannot load the scorecard snapshot.')
        },
      ),
    )
  }
  return cache.get(path) as Promise<T>
}

const localOnly = () => Promise.reject(new ApiError(0, 'Labeling runs in the local app, not this public snapshot.'))

export const staticApi: typeof liveApi = {
  runs: () => snapshot<RunSummary[]>('runs.json'),
  run: (id) => snapshot(`runs/${id}.json`),
  taxonomy: (id) => snapshot<Taxonomy>(`runs/${id}/taxonomy.json`),
  results: async (id, f = {}) => {
    const rows = await snapshot<ResultRow[]>(`runs/${id}/results.json`)
    return rows.filter(
      (r) =>
        (!f.area || r.area === f.area) &&
        (!f.status ||
          (f.status === 'error' ? !!r.error : f.status === 'pass' ? r.overall === 1 : f.status === 'fail' ? r.overall === 0 : true)),
    )
  },
  result: async (id, sample, epoch = 1) => {
    const all = await snapshot<Record<string, ResultDetail>>(`runs/${id}/details.json`)
    const d = all[`${sample}/${epoch}`]
    if (!d) throw new ApiError(404, `no result ${sample} epoch ${epoch} in run ${id}`)
    return d
  },
  labelQueue: localOnly,
  batches: () => Promise.resolve([]),
  postLabel: localOnly,
  labels: () => Promise.resolve([]),
  calibration: () => snapshot<Calibration>('calibration.json'),
  diff: async (a, b, check = 'overall') => {
    const all = await snapshot<Record<Check, Diff>>(`diff/${a}__${b}.json`)
    return all[check]
  },
}

export const api = STATIC ? staticApi : liveApi
