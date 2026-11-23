// Blind labeling: this screen only talks to /label-queue and /labels, never to judge output.
import { useEffect, useReducer } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, RUBRICS, type QueueItem, type Rubric } from '../api'
import { Citation, Empty, ErrorState, Loading, Transcript, useLoad } from '../components'
import { initialLabelState, labelReducer, type LabelState } from '../lib/labelReducer'

const RUBRIC_LABEL: Record<Rubric, string> = { factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments' }

export default function Label() {
  const [params, setParams] = useSearchParams()
  const rubric = (RUBRICS as string[]).includes(params.get('rubric') ?? '') ? (params.get('rubric') as Rubric) : 'factual'
  const run = params.get('run') ?? ''
  const batch = params.get('batch') ?? ''
  const runs = useLoad(() => api.runs(), [])
  const batches = useLoad(() => api.batches(), [])
  const queue = useLoad(
    () => (batch ? api.labelQueue({ batch, limit: 200 }) : api.labelQueue({ rubric, run: run || undefined, limit: 200 })),
    [rubric, run, batch],
  )
  const [state, dispatch] = useReducer(
    labelReducer<QueueItem>,
    initialLabelState as LabelState<QueueItem>,
  )
  // Clear the queue the moment the filters change, so nothing from the old rubric can be labeled.
  useEffect(() => {
    dispatch({ type: 'reset' })
  }, [rubric, run, batch])

  useEffect(() => {
    if (queue.data) dispatch({ type: 'loaded', items: queue.data })
  }, [queue.data])

  // Post each pending label exactly once; the confirmation names the label it confirms.
  useEffect(() => {
    const p = state.pending
    if (!p) return
    api.postLabel(p).then(
      () => dispatch({ type: 'saved', key: p }),
      (e) => dispatch({ type: 'failed', key: p, message: e?.detail ?? String(e) }),
    )
  }, [state.pending])

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

  const ready = !!queue.data && !queue.loading && !queue.error
  // The queue is fetched in pages of 200; fetch the next page when this one runs out.
  const exhausted = ready && state.items.length === 200 && state.index >= state.items.length
  useEffect(() => {
    if (exhausted) queue.reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exhausted])

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v) p.set(k, v)
    else p.delete(k)
    setParams(p, { replace: true })
  }

  const item = ready ? state.items[state.index] : undefined
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
        {!!batches.data?.length && (
          <label className="field">
            Batch
            <select value={batch} onChange={(e) => set('batch', e.target.value)}>
              <option value="">No batch (pick rubric and run)</option>
              {batches.data.map((b) => (
                <option key={b.name} value={b.name}>{b.name} · {b.labeled} of {b.n} labeled</option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          Rubric
          <select value={rubric} disabled={!!batch} onChange={(e) => set('rubric', e.target.value)}>
            {RUBRICS.map((r) => <option key={r} value={r}>{RUBRIC_LABEL[r]}</option>)}
          </select>
        </label>
        <label className="field">
          Run
          <select value={run} disabled={!!batch} onChange={(e) => set('run', e.target.value)}>
            <option value="">All runs (mixed)</option>
            {runs.data?.map((r) => (
              <option key={r.id} value={r.id}>Run {r.id.slice(0, 8)} · {r.pack} pack</option>
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
      {ready && !item && (
        <Empty>
          <p>{batch ? `Batch ${batch} is fully labeled.` : `Nothing left to label for ${RUBRIC_LABEL[rubric]}${run ? ' in this run' : ''}.`}</p>
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
            {batch && (
              <p className="small" aria-live="polite">
                Judging this one on <strong>{RUBRIC_LABEL[item.rubric]}</strong> (the rubric changes between items in a batch)
              </p>
            )}
            <div className="label-actions" role="group" aria-label="Your verdict">
              <button className="btn btn-primary" aria-disabled={saving} onClick={() => !saving && dispatch({ type: 'key', pass: true })}>
                Pass <kbd>Y</kbd>
              </button>
              <button className="btn btn-fail" aria-disabled={saving} onClick={() => !saving && dispatch({ type: 'key', pass: false })}>
                Fail <kbd>N</kbd>
              </button>
              <button className="btn" aria-disabled={saving} onClick={() => !saving && dispatch({ type: 'skip' })}>
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
              <h2 id="rub-h">Rubric: {RUBRIC_LABEL[item.rubric]}</h2>
              <div className="rubric-text">{item.rubric_text.replace(/^## Rubric: [^\n]*\n/, '')}</div>
            </section>
            {item.key_facts.length > 0 && item.rubric === 'disclosure' && (
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
