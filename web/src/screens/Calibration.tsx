import { Link } from 'react-router'
import { api, RUBRICS, STATIC, type AgreementReport, type Rubric } from '../api'
import { Empty, ErrorState, Loading, useLoad } from '../components'
import { kappaWord } from '../lib/kappa'

const RUBRIC_LABEL: Record<Rubric, string> = { factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments' }
const fmt2 = (v: number | null) => (v === null ? '–' : v.toFixed(2))
const pct0 = (v: number | null) => (v === null ? '–' : `${Math.round(v * 100)}%`)

function Matrix({ r }: { r: AgreementReport }) {
  return (
    <table className="matrix">
      <caption className="sr-only">Judge verdict against your label</caption>
      <thead>
        <tr>
          <td />
          <th scope="col">You: pass</th>
          <th scope="col">You: fail</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">Judge: pass</th>
          <td className="agree">{r.both_pass}</td>
          <td className="disagree">{r.judge_pass_human_fail}</td>
        </tr>
        <tr>
          <th scope="row">Judge: fail</th>
          <td className="disagree">{r.judge_fail_human_pass}</td>
          <td className="agree">{r.both_fail}</td>
        </tr>
      </tbody>
    </table>
  )
}

function RubricPanel({ rubric, r }: { rubric: Rubric; r?: AgreementReport }) {
  const head = <h2 id={`cal-${rubric}`}>{RUBRIC_LABEL[rubric]}</h2>
  if (!r || r.n === 0) {
    return (
      <section className="panel section" aria-labelledby={`cal-${rubric}`}>
        {head}
        <p className="muted">
          No comparable labels yet{r ? ` (${r.n_labels} labels, none on a judged scenario)` : ''}.
        </p>
        <p><Link to={`/label?rubric=${rubric}`}>Label 20 to get a first kappa</Link></p>
      </section>
    )
  }
  const oneClass = r.both_pass + r.judge_fail_human_pass === r.n || r.both_fail + r.judge_pass_human_fail === r.n
  return (
    <section className="panel section" aria-labelledby={`cal-${rubric}`}>
      {head}
      <div className="cal-figures">
        <div>
          <div className="big">{fmt2(r.kappa)}</div>
          <div className="small muted">Cohen’s kappa · {kappaWord(r.kappa)}</div>
        </div>
        <div>
          <div className="big">{pct0(r.raw_agreement)}</div>
          <div className="small muted">raw agreement on {r.n} labels</div>
        </div>
      </div>
      {oneClass && (
        <p className="small" style={{ color: 'var(--warning)' }}>
          All your labels are the same verdict, so kappa can’t measure agreement yet. Label some failing transcripts
          (the misinformed runs have plenty).
        </p>
      )}
      <Matrix r={r} />
      {r.disagreements.length > 0 && (
        <details>
          <summary>{r.disagreements.length} disagreements</summary>
          <ul className="small">
            {r.disagreements.map((d) => (
              <li key={`${d.run_id}/${d.sample_id}/${d.epoch}`}>
                <Link to={`/runs/${d.run_id}/results/${encodeURIComponent(d.sample_id)}?epoch=${d.epoch}&from=status%3D`} className="id">
                  {d.sample_id}
                </Link>{' '}
                <span className="muted">in {d.run_id.slice(0, 8)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export default function Calibration() {
  const { data, error, loading, reload } = useLoad(() => api.calibration(), [])
  const total = data ? Object.values(data).reduce((s, r) => s + (r?.n_labels ?? 0), 0) : 0
  return (
    <>
      <div className="page-head">
        <h1>Calibration</h1>
        <p className="lead">
          How often the judge agrees with your labels, per rubric. Kappa corrects raw agreement for chance: above 0.6
          is substantial.{data && ` ${total} labels so far.`}
        </p>
      </div>
      {loading && <Loading label="Loading calibration" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && total === 0 && (
        <Empty>
          {STATIC ? (
            <p>
              Not measured yet. A 102-item blind batch, mixed pass and fail across all three bots, is built and waiting
              for human labels. Until then the judge&rsquo;s verdicts are unvalidated.
            </p>
          ) : (
            <>
              <p>No labels yet.</p>
              <Link className="btn btn-primary" to="/label">Start labeling</Link>
            </>
          )}
        </Empty>
      )}
      {data && total > 0 && (
        <div className="cal-grid">
          {RUBRICS.map((rb) => <RubricPanel key={rb} rubric={rb} r={data[rb]} />)}
        </div>
      )}
    </>
  )
}
