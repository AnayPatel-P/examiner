import { Link, useParams, useSearchParams, useNavigate } from 'react-router'
import { api, CHECKS, RUBRICS, type Check, type Scorecard, type Taxonomy } from '../api'
import { Chip, Empty, ErrorState, Loading, Rate, TableWrap, useLoad } from '../components'
import { money, pct, secs, variantLabel, when } from '../format'

const CHECK_LABEL: Record<Check, string> = {
  overall: 'Overall', fact: 'Fact check', judge: 'Judge (all rubrics)',
  factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments',
}
const AREA_LABEL: Record<string, string> = { fees: 'Fees', reg_e: 'Reg E', all: 'All scenarios', unknown: 'Unknown' }

function ScorecardTable({ card }: { card: Scorecard }) {
  return (
    <TableWrap label="Scorecard table, scrolls sideways">
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

const MODE_LABEL: Record<string, string> = {
  fact_missing: 'left out a required fact',
  fact_forbidden: 'said a forbidden fact',
  factual: 'factual rubric',
  disclosure: 'disclosure rubric',
  commitments: 'commitments rubric',
}

function WhereItFails({ tax }: { tax: Taxonomy }) {
  const failing = tax.sections.filter((s) => s.failed > 0)
  if (tax.failed_scenarios === 0) return <p className="small muted">No scored scenario failed in this run.</p>
  const modes = Object.entries(tax.modes).sort((a, b) => b[1] - a[1])
  return (
    <>
      <p className="small">
        {tax.failed_scenarios} of {tax.scored_scenarios} scored scenarios failed. How:{' '}
        {modes.map(([m, n], i) => (
          <span key={m}>{i > 0 && ' · '}{MODE_LABEL[m] ?? m} {n}</span>
        ))}
        . A scenario can fail more than one way.
      </p>
      <TableWrap label="Failures by rule, scrolls sideways">
        <table>
          <caption className="sr-only">Failures by Reg E section and fee schedule</caption>
          <thead>
            <tr>
              <th scope="col">Rule</th>
              <th scope="col">Section</th>
              <th scope="col" className="num">Failed</th>
              <th scope="col">Worst clauses</th>
            </tr>
          </thead>
          <tbody>
            {failing.map((s) => {
              const worst = tax.clauses.filter((c) => c.section === s.section && c.failed > 0).slice(0, 3)
              return (
                <tr key={s.section}>
                  <th scope="row" className="row-head">{s.section === 'fee schedule' ? 'Fee schedule' : `12 CFR ${s.section}`}</th>
                  <td>{s.section_title || 'Meridian fees'}</td>
                  <td className="num">{s.failed} of {s.n}</td>
                  <td className="small">
                    {worst.map((c) => `${c.citation.replace('12 CFR ', '').replace('fee:', '')} (${c.failed}/${c.n})`).join(', ')}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </TableWrap>
    </>
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
  const tax = useLoad(() => api.taxonomy(runId), [runId])

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
  const { run: r, scorecard, ops } = run.data
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
        {ops && (ops.latency_p50_s !== null || ops.cost_per_scenario_usd !== null) && (
          <p className="small muted">
            {ops.cost_per_scenario_usd !== null && `$${ops.cost_per_scenario_usd.toFixed(3)} per scenario`}
            {ops.latency_p50_s !== null &&
              ` · bot latency p50 ${ops.latency_p50_s.toFixed(1)} s, p95 ${ops.latency_p95_s?.toFixed(1)} s per conversation`}
          </p>
        )}
      </div>

      <section className="section" aria-labelledby="scorecard-h">
        <h2 id="scorecard-h">Scorecard</h2>
        <ScorecardTable card={scorecard} />
      </section>

      <section className="section" aria-labelledby="fails-h">
        <h2 id="fails-h">Where it fails</h2>
        {tax.loading && <Loading label="Loading failure breakdown" />}
        {tax.error && <ErrorState error={tax.error} onRetry={tax.reload} />}
        {tax.data && <WhereItFails tax={tax.data} />}
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
          <TableWrap label="Scenarios table, scrolls sideways">
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
