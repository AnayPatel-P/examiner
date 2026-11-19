// Blind labeling: this screen only talks to /label-queue and /labels, never to judge output.
import { useEffect, useReducer, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, RUBRICS, type QueueItem, type Rubric } from '../api'
import { Citation, Empty, ErrorState, Loading, Transcript, useLoad } from '../components'
import { initialLabelState, labelReducer, type LabelState } from '../lib/labelReducer'

const RUBRIC_LABEL: Record<Rubric, string> = { factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments' }

export default function Label() {
  const [params, setParams] = useSearchParams()
  const rubric = (RUBRICS as string[]).includes(params.get('rubric') ?? '') ? (params.get('rubric') as Rubric) : 'factual'
  const run = params.get('run') ?? ''
  const runs = useLoad(() => api.runs(), [])
  const queue = useLoad(() => api.labelQueue({ rubric, run: run || undefined, limit: 200 }), [rubric, run])
  const [state, dispatch] = useReducer(
    labelReducer<QueueItem>,
    initialLabelState as LabelState<QueueItem>,
  )
  const pending = useRef(false)

  useEffect(() => {
    if (queue.data) dispatch({ type: 'loaded', items: queue.data })
  }, [queue.data])

  // Save whenever the reducer has a pending label.
  useEffect(() => {
    if (!state.pending || pending.current) return
    pending.current = true
    api
      .postLabel({ ...state.pending, rubric })
      .then(() => dispatch({ type: 'saved' }), (e) => dispatch({ type: 'failed', message: e.detail ?? String(e) }))
      .finally(() => {
        pending.current = false
      })
  }, [state.pending, rubric])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return
      if ((e.target as HTMLElement).closest('input, select, textarea')) return
      const k = e.key.toLowerCase()
      if (k === 'y') dispatch({ type: 'key', pass: true })
      else if (k === 'n') dispatch({ type: 'key', pass: false })
      else if (k === 's') dispatch({ type: 'skip' })
      else if (k === 'u') dispatch({ type: 'undo' })
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  const item = state.items[state.index]
  const saving = state.status === 'saving'

  return (
    <>
      <div className="page-head">
        <h1>Label</h1>
        <p className="lead">
          Read the conversation and decide, against the rubric below, whether the bot passes. The judge’s verdict is
          hidden until you’ve labeled; your labels measure how far it can be trusted.
        </p>
      </div>

      <div className="controls">
        <label className="field">
          Rubric
          <select value={rubric} onChange={(e) => set('rubric', e.target.value)}>
            {RUBRICS.map((r) => <option key={r} value={r}>{RUBRIC_LABEL[r]}</option>)}
          </select>
        </label>
        <label className="field">
          Run
          <select value={run} onChange={(e) => set('run', e.target.value)}>
            <option value="">All runs (mixed)</option>
            {runs.data?.map((r) => (
              <option key={r.id} value={r.id}>{r.variant} · {r.pack} · {r.id.slice(0, 8)}</option>
            ))}
          </select>
        </label>
        <p className="small muted label-progress" aria-live="polite">
          {state.history.length} labeled this session
          {queue.data && ` · ${Math.max(state.items.length - state.index, 0)} left in this queue`}
        </p>
      </div>

      {queue.loading && <Loading label="Loading the labeling queue" />}
      {queue.error && <ErrorState error={queue.error} onRetry={queue.reload} />}
      {queue.data && !item && (
        <Empty>
          <p>Nothing left to label for {RUBRIC_LABEL[rubric]}{run ? ' in this run' : ''}.</p>
          <p className="small"><Link to="/calibration">See how the judge agrees with your labels</Link></p>
        </Empty>
      )}

      {item && (
        <div className="label-grid">
          <section className="panel section" aria-labelledby="lt-h">
            <div className="section-head">
              <h2 id="lt-h">Conversation</h2>
              <span className="small muted id">{item.sample_id}</span>
            </div>
            <Transcript text={item.transcript} />
            <div className="label-actions" role="group" aria-label="Your verdict">
              <button className="btn btn-primary" disabled={saving} onClick={() => dispatch({ type: 'key', pass: true })}>
                Pass <kbd>Y</kbd>
              </button>
              <button className="btn btn-fail" disabled={saving} onClick={() => dispatch({ type: 'key', pass: false })}>
                Fail <kbd>N</kbd>
              </button>
              <button className="btn" disabled={saving} onClick={() => dispatch({ type: 'skip' })}>
                Skip <kbd>S</kbd>
              </button>
              <button className="btn btn-quiet" disabled={saving || state.history.length === 0} onClick={() => dispatch({ type: 'undo' })}>
                Undo <kbd>U</kbd>
              </button>
            </div>
            {saving && <p className="small muted" role="status">Saving…</p>}
            {state.error && <p className="small" role="alert" style={{ color: 'var(--fail)' }}>Not saved: {state.error}. Press the key again to retry.</p>}
          </section>

          <div className="finding-side">
            <section className="panel section" aria-labelledby="rub-h">
              <h2 id="rub-h">Rubric: {RUBRIC_LABEL[rubric]}</h2>
              <div className="rubric-text">{item.rubric_text.replace(/^## Rubric: [^\n]*\n/, '')}</div>
            </section>
            {item.key_facts.length > 0 && rubric === 'disclosure' && (
              <section className="panel section" aria-labelledby="kf-h">
                <h2 id="kf-h">Key facts the reply must state</h2>
                <ul className="small">
                  {item.key_facts.map((f, i) => <li key={i}>{f.join(' or ')}</li>)}
                </ul>
              </section>
            )}
            <section className="panel section" aria-labelledby="lr-h">
              <h2 id="lr-h">Rules cited</h2>
              {item.citations.map((c) => <Citation key={c.cite} c={c} />)}
              {item.source_note && <p className="small"><span className="muted">In plain English: </span>{item.source_note}</p>}
            </section>
          </div>
        </div>
      )}
    </>
  )
}
