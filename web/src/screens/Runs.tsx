import { useNavigate, Link } from 'react-router'
import { api, type RunSummary } from '../api'
import { Empty, ErrorState, Loading, Rate, TableWrap, useLoad } from '../components'
import { money, pct, secs, variantLabel, when } from '../format'

function latest(runs: RunSummary[], variant: string, pack = 'v1') {
  return runs.find((r) => r.variant === variant && r.pack === pack)
}

export default function Runs() {
  const { data, error, loading, reload } = useLoad(() => api.runs(), [])
  const nav = useNavigate()
  const naive = data && latest(data, 'naive')
  const guarded = data && latest(data, 'guarded')

  return (
    <>
      <div className="page-head">
        <h1>Runs</h1>
        {naive && guarded ? (
          <p className="lead">
            On the v1 pack, the guarded bot passes <strong>{pct(guarded.overall)}</strong> of scenarios overall; the naive
            bot passes <strong>{pct(naive.overall)}</strong>.{' '}
            <Link to={`/diff?a=${naive.id}&b=${guarded.id}`}>See what changed</Link>
          </p>
        ) : (
          <p className="lead">Each run sends every scenario in a pack to the bot and grades the replies.</p>
        )}
      </div>
      {loading && <Loading label="Loading runs" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <Empty>
          <p>No runs yet.</p>
          <p className="small">
            Start the bot, then run <code>uv run examiner run --pack v1</code>.
          </p>
        </Empty>
      )}
      {data && data.length > 0 && (
        <TableWrap label="Runs table, scrolls sideways">
          <table>
            <caption className="sr-only">All runs, newest first</caption>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Started</th>
                <th scope="col">Overall</th>
                <th scope="col">Fact check</th>
                <th scope="col">Judge</th>
                <th scope="col" className="num">Cost</th>
                <th scope="col" className="num">Time</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} className="link-row" onClick={() => nav(`/runs/${r.id}`)}>
                  <td>
                    <Link to={`/runs/${r.id}`} onClick={(e) => e.stopPropagation()}>
                      {variantLabel(r.variant)} · {r.pack}
                    </Link>
                    <div className="small muted">
                      <span className="id">{r.id}</span>
                      {r.errors > 0 && ` · ${r.errors} errors`}
                    </div>
                  </td>
                  <td className="muted">{when(r.started_at)}</td>
                  <td><Rate cell={r.overall} label="Overall" /></td>
                  <td><Rate cell={r.fact} label="Fact check" /></td>
                  <td><Rate cell={r.judge} label="Judge" /></td>
                  <td className="num">
                    {money((r.cost_usd ?? 0) + (r.target_cost_usd ?? 0))}
                    <div className="small muted">judge {money(r.cost_usd)}</div>
                  </td>
                  <td className="num">{secs(r.wall_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </>
  )
}
