import { Link, useParams, useSearchParams, useNavigate } from 'react-router'
import { api, CHECKS, RUBRICS, type Check, type Scorecard } from '../api'
import { Chip, Empty, ErrorState, Loading, Rate, TableWrap, useLoad } from '../components'
import { money, pct, secs, variantLabel, when } from '../format'

const CHECK_LABEL: Record<Check, string> = {
  overall: 'Overall', fact: 'Fact check', judge: 'Judge (all rubrics)',
  factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments',
}
const AREA_LABEL: Record<string, string> = { fees: 'Fees', reg_e: 'Reg E', all: 'All scenarios', unknown: 'Unknown' }

function ScorecardTable({ card }: { card: Scorecard }) {
  return (
    <TableWrap label="Scorecard">
      <table>
        <caption className="sr-only">Pass rate by area and check</caption>
        <thead>
          <tr>
            <th scope="col">Area</th>
            {CHECKS.map((c) => (
              <th key={c} scope="col">{CHECK_LABEL[c]}</th>
            ))}
            <th scope="col" className="num">Errors</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(card).map(([area, row]) => (
            <tr key={area} className={area === 'all' ? 'total' : undefined}>
              <th scope="row" className="row-head">
                {AREA_LABEL[area] ?? area}
              </th>
              {CHECKS.map((c) => (
                <td key={c}><Rate cell={row[c]} label={`${AREA_LABEL[area] ?? area} ${CHECK_LABEL[c]}`} /></td>
              ))}
              <td className="num">{row.errors}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  )
}

const STATUSES = [
  { v: '', label: 'All' },
  { v: 'fail', label: 'Failed' },
  { v: 'pass', label: 'Passed' },
  { v: 'error', label: 'Errors' },
]

export default function RunPage() {
  const { runId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'fail'
  const area = params.get('area') ?? ''
  const nav = useNavigate()
  const run = useLoad(() => api.run(runId), [runId])
  const results = useLoad(() => api.results(runId, { status, area }), [runId, status, area])

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    if (k === 'status' && !v) p.set('status', '')
    setParams(p, { replace: true })
  }

  if (run.loading) return <Loading label="Loading run" />
  if (run.error) return <ErrorState error={run.error} onRetry={run.reload} />
  if (!run.data) return null
  const { run: r, scorecard } = run.data
  const areas = Object.keys(scorecard).filter((a) => a !== 'all')
  const qs = params.toString()

  return (
    <>
      <div className="page-head">
        <div className="crumbs"><Link to="/">Runs</Link><span aria-hidden="true">/</span><span className="id">{r.id}</span></div>
        <h1>
          {variantLabel(r.variant)} · {r.pack} pack · {pct(r.overall)} overall
        </h1>
        <p className="lead">
          {r.overall.passed} of {r.overall.n} judged scenarios passed both the fact check and every rubric.
          {r.errors > 0 && ` ${r.errors} scenarios errored and are not counted.`}
        </p>
        <p className="small muted">
          {when(r.started_at)} · judge {money(r.cost_usd)} · bot {money(r.target_cost_usd)} · {secs(r.wall_seconds)} ·{' '}
          {r.judge_version ?? 'no judge version'}
        </p>
      </div>

      <section className="section" aria-labelledby="scorecard-h">
        <h2 id="scorecard-h">Scorecard</h2>
        <ScorecardTable card={scorecard} />
      </section>

      <section className="section" aria-labelledby="results-h">
        <div className="section-head">
          <h2 id="results-h">Scenarios</h2>
          <div className="controls">
            <div className="segmented" role="group" aria-label="Filter by verdict">
              {STATUSES.map((s) => (
                <button key={s.v} aria-pressed={status === s.v} onClick={() => set('status', s.v)}>
                  {s.label}
                </button>
              ))}
            </div>
            <label className="field">
              Area
              <select value={area} onChange={(e) => set('area', e.target.value)}>
                <option value="">All areas</option>
                {areas.map((a) => (
                  <option key={a} value={a}>{AREA_LABEL[a] ?? a}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {results.loading && <Loading label="Loading scenarios" />}
        {results.error && <ErrorState error={results.error} onRetry={results.reload} />}
        {results.data && results.data.length === 0 && (
          <Empty>
            <p>No scenarios match this filter.</p>
            <button className="btn" onClick={() => setParams(new URLSearchParams({ status: '' }), { replace: true })}>
              Show all scenarios
            </button>
          </Empty>
        )}
        {results.data && results.data.length > 0 && (
          <TableWrap label="Scenarios">
            <table>
              <caption className="sr-only">Scenarios in this run</caption>
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col">Overall</th>
                  <th scope="col">Fact</th>
                  {RUBRICS.map((rb) => (
                    <th key={rb} scope="col">{CHECK_LABEL[rb]}</th>
                  ))}
                  <th scope="col">Rule cited</th>
                </tr>
              </thead>
              <tbody>
                {results.data.map((row) => {
                  const href = `/runs/${runId}/results/${encodeURIComponent(row.sample_id)}?epoch=${row.epoch}${qs ? `&from=${encodeURIComponent(qs)}` : ''}`
                  return (
                    <tr key={`${row.sample_id}-${row.epoch}`} className="link-row" onClick={() => nav(href)}>
                      <td>
                        <Link to={href} onClick={(e) => e.stopPropagation()} className="id">{row.sample_id}</Link>
                        {row.epoch > 1 && <span className="small muted"> · epoch {row.epoch}</span>}
                      </td>
                      <td><Chip v={row.overall} error={row.error} /></td>
                      <td><Chip v={row.fact_pass} error={row.error} /></td>
                      {RUBRICS.map((rb) => (
                        <td key={rb}><Chip v={row.rubrics[rb] ?? null} error={row.error} /></td>
                      ))}
                      <td className="small" style={{ overflowWrap: 'anywhere' }}>{row.error ?? row.citation}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </TableWrap>
        )}
        {results.data && results.data.length > 0 && (
          <p className="small muted">{results.data.length} scenarios shown</p>
        )}
      </section>
    </>
  )
}
