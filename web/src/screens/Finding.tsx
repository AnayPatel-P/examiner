import { useEffect } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { api, RUBRICS, type ResultDetail } from '../api'
import { Chip, Citation, ErrorState, Loading, Transcript, useLoad } from '../components'

const RUBRIC_LABEL = { factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments' } as const

/** The one line a reader needs first: why this scenario failed. */
export function findingLead(d: ResultDetail): string {
  if (d.error) return `The bot could not be reached: ${d.error}`
  const failed = d.scores.find((s) => s.passed === 0)
  if (failed?.rationale) return failed.rationale
  const fd = d.fact_detail
  if (d.fact_pass === 0 && fd) {
    const parts = []
    if (fd.forbidden?.length) parts.push(`said something it must not (${fd.forbidden.join(', ')})`)
    if (fd.missing?.length) parts.push(`left out a required fact (${fd.missing.join(', ')})`)
    if (parts.length) return `The fact check failed: the reply ${parts.join(' and ')}. The judge passed it.`
  }
  if (d.overall === 1) return 'Passed: the reply stated the required facts and broke no cited rule.'
  return 'Not fully judged: one or more checks have no verdict.'
}

function factName(id: string, d: ResultDetail): string {
  const f = [...(d.scenario?.must_say ?? []), ...(d.scenario?.must_not_say ?? [])].find((x) => x.id === id)
  return f ? `“${f.any_of.join('” or “')}”` : id
}

export default function Finding() {
  const { runId = '', sampleId = '' } = useParams()
  const [params] = useSearchParams()
  const epoch = Number(params.get('epoch') ?? '1') || 1
  const from = params.get('from') ?? 'status=fail'
  const nav = useNavigate()
  const detail = useLoad(() => api.result(runId, sampleId, epoch), [runId, sampleId, epoch])
  const fromParams = new URLSearchParams(from)
  const list = useLoad(
    () => api.results(runId, { status: fromParams.get('status') ?? '', area: fromParams.get('area') ?? '' }),
    [runId, from],
  )

  const idx = list.data?.findIndex((r) => r.sample_id === sampleId && r.epoch === epoch) ?? -1
  const prev = idx > 0 ? list.data![idx - 1] : null
  const next = idx >= 0 && list.data && idx < list.data.length - 1 ? list.data[idx + 1] : null
  const hrefFor = (r: { sample_id: string; epoch: number }) =>
    `/runs/${runId}/results/${encodeURIComponent(r.sample_id)}?epoch=${r.epoch}&from=${encodeURIComponent(from)}`

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target as HTMLElement).closest('input, select, textarea')) return
      if (e.key === 'j' && next) nav(hrefFor(next))
      if (e.key === 'k' && prev) nav(hrefFor(prev))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (detail.loading) return <Loading label="Loading scenario" />
  if (detail.error) return <ErrorState error={detail.error} onRetry={detail.reload} />
  const d = detail.data
  if (!d) return null
  const fd = d.fact_detail

  return (
    <>
      <div className="page-head">
        <div className="crumbs">
          <Link to="/">Runs</Link><span aria-hidden="true">/</span>
          <Link to={`/runs/${runId}?${from}`} className="id">{runId}</Link><span aria-hidden="true">/</span>
          <span className="id">{d.sample_id}</span>
        </div>
        <h1 className="finding-title">
          <span className="id">{d.sample_id}</span> <Chip v={d.overall} error={d.error} label="Overall" />
        </h1>
        <p className="finding-lead">{findingLead(d)}</p>
        <div className="finding-nav">
          {prev ? <Link className="btn" to={hrefFor(prev)}>← Previous <kbd>K</kbd></Link> : <span />}
          {list.data && idx >= 0 && <span className="small muted">{idx + 1} of {list.data.length} in this list</span>}
          {next ? <Link className="btn" to={hrefFor(next)}>Next <kbd>J</kbd> →</Link> : <span />}
        </div>
      </div>

      <div className="finding-grid">
        <section className="panel section" aria-labelledby="t-h">
          <h2 id="t-h">Conversation</h2>
          {d.scenario && <p className="small muted">Customer: {d.scenario.persona}</p>}
          <Transcript text={d.transcript} />
        </section>

        <div className="finding-side">
          <section className="panel section" aria-labelledby="v-h">
            <h2 id="v-h">Verdicts</h2>
            <dl className="verdicts">
              <dt>Fact check</dt>
              <dd>
                <Chip v={d.fact_pass} error={d.error} />
                {fd?.missing?.length ? <p className="small">Missing: {fd.missing.map((m) => factName(m, d)).join('; ')}</p> : null}
                {fd?.forbidden?.length ? <p className="small">Said: {fd.forbidden.map((m) => factName(m, d)).join('; ')}</p> : null}
              </dd>
              {RUBRICS.map((rb) => {
                const s = d.scores.find((x) => x.rubric === rb)
                return (
                  <div key={rb} className="verdict-row">
                    <dt>{RUBRIC_LABEL[rb]}</dt>
                    <dd>
                      {s ? <Chip v={s.passed} /> : <span className="small muted">Not scored for this scenario</span>}
                      {s?.rationale && <p className="small rationale">{s.rationale}</p>}
                      {s?.judge_version && <p className="small muted">{s.judge_version}</p>}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </section>

          <section className="panel section" aria-labelledby="r-h">
            <h2 id="r-h">Rules cited</h2>
            {d.citations.length === 0 && <p className="muted">No citations (the scenario is missing from its pack).</p>}
            {d.citations.map((c) => <Citation key={c.cite} c={c} />)}
            {d.scenario?.source_note && (
              <p className="small"><span className="muted">In plain English: </span>{d.scenario.source_note}</p>
            )}
          </section>
        </div>
      </div>
    </>
  )
}
