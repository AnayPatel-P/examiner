import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, CHECKS, DIFF_CATEGORIES, type Check, type Diff, type DiffCategory, type RunSummary } from '../api'
import { Chip, ErrorState, Loading, Transcript, useLoad } from '../components'
import { pct, variantLabel } from '../format'
import { stripModel, tickTone, type Tick, type TickTone } from '../lib/strip'

const CAT_LABEL: Record<DiffCategory, string> = {
  fixed: 'Fixed', broke: 'Broke', still_fail: 'Still failing', still_pass: 'Still passing',
  unscored: 'Not judged in one run', only_a: 'Only in A', only_b: 'Only in B',
}
const CHECK_LABEL: Record<Check, string> = {
  overall: 'Overall', fact: 'Fact check', judge: 'Judge', factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments',
}

const TONE_WORD: Record<TickTone, string> = { pass: 'pass', fail: 'fail', unjudged: 'not judged', absent: 'not in run' }

function runLabel(r: RunSummary) {
  return `${variantLabel(r.variant)} · ${r.pack} · ${r.id.slice(0, 8)}`
}

const played = new Set<string>()
const sameTick = (x: Tick | null, y: Tick) => !!x && x.sample_id === y.sample_id && x.epoch === y.epoch

/** The signature: B's ticks turn from A's verdict to their own in one left-to-right wave, once per comparison.
 *  Mounted with key = comparison, so the "before" state is in place on the first paint (no flash). */
function Strips({ diff, ticks, onPick, picked, waveKey }: {
  diff: Diff; ticks: Tick[]; onPick: (t: Tick) => void; picked: Tick | null; waveKey: string
}) {
  const [phase, setPhase] = useState<'before' | 'after'>(() =>
    played.has(waveKey) || window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'after' : 'before',
  )
  useEffect(() => {
    if (phase === 'after') return
    let inner = 0
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => {
        played.add(waveKey)
        setPhase('after')
      })
    })
    return () => {
      cancelAnimationFrame(outer)
      cancelAnimationFrame(inner)
    }
  }, [phase, waveKey])
  const step = Math.min(2, 300 / Math.max(ticks.length, 1))

  // Roving tab stop: one Tab into the strip, arrows move, Enter or Space opens.
  const pickedIdx = Math.max(0, ticks.findIndex((t) => sameTick(picked, t)))
  const [focusIdx, setFocusIdx] = useState(pickedIdx)
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const move = (to: number) => {
    const i = Math.max(0, Math.min(ticks.length - 1, to))
    setFocusIdx(i)
    refs.current[i]?.focus()
  }
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const keys: Record<string, number> = {
      ArrowRight: focusIdx + 1, ArrowLeft: focusIdx - 1, Home: 0, End: ticks.length - 1,
      PageDown: focusIdx + 10, PageUp: focusIdx - 10,
    }
    if (e.key in keys) {
      e.preventDefault()
      move(keys[e.key])
    }
  }

  return (
    <div className="strips">
      <div className="strip-row" aria-hidden="true">
        <div className="strip-label">
          <strong>A</strong> {runLabel(diff.a)}<span className="muted"> · {pct(diff.a.overall)} overall</span>
        </div>
        <div className="strip">
          {ticks.map((t) => (
            <span key={`${t.sample_id}-${t.epoch}`} className={`tick ${tickTone(t, 'a')}`} onClick={() => onPick(t)} />
          ))}
        </div>
      </div>
      <div className="strip-row">
        <div className="strip-label" id="strip-b-label">
          <strong>B</strong> {runLabel(diff.b)}<span className="muted"> · {pct(diff.b.overall)} overall</span>
        </div>
        <div className="strip" role="toolbar" aria-labelledby="strip-b-label" aria-describedby="strip-help" onKeyDown={onKeyDown}>
          {ticks.map((t, i) => {
            const before = phase === 'before'
            const tone = before ? tickTone(t, 'a') : tickTone(t, 'b')
            const marked = !before && t.category === 'broke'
            return (
              <button
                key={`${t.sample_id}-${t.epoch}`}
                ref={(el) => {
                  refs.current[i] = el
                }}
                className={`tick ${tone}${marked ? ` ring ${t.category}` : ''}${sameTick(picked, t) ? ' picked' : ''}`}
                style={{ transitionDelay: before ? '0ms' : `${i * step}ms` }}
                tabIndex={i === focusIdx ? 0 : -1}
                aria-pressed={sameTick(picked, t)}
                aria-label={`${t.sample_id}: ${CAT_LABEL[t.category]}. A ${TONE_WORD[tickTone(t, 'a')]}, B ${TONE_WORD[tickTone(t, 'b')]}`}
                onFocus={() => setFocusIdx(i)}
                onClick={() => onPick(t)}
              />
            )
          })}
        </div>
      </div>
      <p className="small muted strip-key">
        <span className="tick pass static" aria-hidden="true" /> pass
        <span className="tick fail static" aria-hidden="true" /> fail
        <span className="tick unjudged static" aria-hidden="true" /> not judged
        <span className="tick absent static" aria-hidden="true" /> not in this run
        <span className="tick fail static ring" aria-hidden="true" /> broke
      </p>
      <p className="small muted" id="strip-help">Each tick is one scenario. Arrow keys move along run B; Enter compares the two transcripts.</p>
    </div>
  )
}

function SideBySide({ diff, t }: { diff: Diff; t: Tick }) {
  const a = useLoad(() => (t.a === null && t.category === 'only_b' ? Promise.resolve(null) : api.result(diff.a.id, t.sample_id, t.epoch)), [diff.a.id, t.sample_id, t.epoch])
  const b = useLoad(() => (t.category === 'only_a' ? Promise.resolve(null) : api.result(diff.b.id, t.sample_id, t.epoch)), [diff.b.id, t.sample_id, t.epoch])
  const col = (side: 'a' | 'b', s: typeof a) => (
    <section className="panel section" aria-label={`Run ${side.toUpperCase()}`}>
      <div className="section-head">
        <h3>{side.toUpperCase()} · {variantLabel(diff[side].variant)}</h3>
        <Chip v={t[side]} error={s.data?.error} />
      </div>
      {s.loading && <Loading />}
      {s.error && <ErrorState error={s.error} />}
      {s.data === null && !s.loading && !s.error && <p className="muted">Not in this run.</p>}
      {s.data && (
        <>
          <Transcript text={s.data.transcript} />
          <Link className="small" to={`/runs/${diff[side].id}/results/${encodeURIComponent(t.sample_id)}?epoch=${t.epoch}&from=status%3D`}>
            Open the full finding
          </Link>
        </>
      )}
    </section>
  )
  return (
    <section className="section" aria-labelledby="cmp-h">
      <h2 id="cmp-h" tabIndex={-1}><span className="id">{t.sample_id}</span> · {CAT_LABEL[t.category]}</h2>
      <div className="compare-grid">
        {col('a', a)}
        {col('b', b)}
      </div>
    </section>
  )
}

export default function DiffPage() {
  const [params, setParams] = useSearchParams()
  const runs = useLoad(() => api.runs(), [])
  const check = ((CHECKS as string[]).includes(params.get('check') ?? '') ? params.get('check') : 'overall') as Check
  const pick = (variant: string) => runs.data?.find((r) => r.variant === variant && r.pack === 'v1')?.id
  const b = params.get('b') ?? pick('guarded') ?? runs.data?.[0]?.id ?? ''
  const a = params.get('a') ?? pick('naive') ?? runs.data?.find((r) => r.id !== b)?.id ?? ''
  const diff = useLoad(() => (a && b ? api.diff(a, b, check) : Promise.resolve(null)), [a, b, check])
  const [picked, setPickedState] = useState<Tick | null>(null)
  useEffect(() => setPickedState(null), [a, b, check])
  const ticks = useMemo(() => (diff.data ? stripModel(diff.data) : []), [diff.data])
  const setPicked = (t: Tick) => {
    setPickedState(t)
    requestAnimationFrame(() => document.getElementById('cmp-h')?.focus())
  }

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    p.set('a', a)
    p.set('b', b)
    p.set(k, v)
    setParams(p, { replace: true })
  }

  if (runs.loading) return <Loading label="Loading runs" />
  if (runs.error) return <ErrorState error={runs.error} onRetry={runs.reload} />
  if (!runs.data || runs.data.length < 2) {
    return (
      <div className="state">
        <h1>Diff</h1>
        <p>You need two runs to compare. Run the pack against another bot variant first.</p>
      </div>
    )
  }
  const d = diff.data
  const samePack = d ? d.a.pack === d.b.pack : true

  return (
    <>
      <div className="page-head">
        <h1>
          {d ? (
            <>Fixed <span className="fixed-n">{d.counts.fixed}</span> · Broke <span className="broke-n">{d.counts.broke}</span></>
          ) : 'Diff'}
        </h1>
        {d && (
          <p className="lead">
            {variantLabel(d.b.variant)} against {variantLabel(d.a.variant).toLowerCase()} on {CHECK_LABEL[check].toLowerCase()}:{' '}
            <strong>{pct(d.a[check === 'overall' || check === 'fact' || check === 'judge' ? check : 'overall'])}</strong> →{' '}
            <strong>{pct(d.b[check === 'overall' || check === 'fact' || check === 'judge' ? check : 'overall'])}</strong>
            {check !== 'overall' && check !== 'fact' && check !== 'judge' && ' overall'}. {d.counts.still_fail} still failing.
            {!samePack && ' These runs used different packs, so scenarios only in one run are listed separately.'}
          </p>
        )}
      </div>

      <div className="controls">
        {(['a', 'b'] as const).map((side) => (
          <label key={side} className="field">
            Run {side.toUpperCase()}{side === 'a' ? ' (before)' : ' (after)'}
            <select value={side === 'a' ? a : b} onChange={(e) => set(side, e.target.value)}>
              {runs.data!.map((r) => <option key={r.id} value={r.id}>{runLabel(r)}</option>)}
            </select>
          </label>
        ))}
        <label className="field">
          Compare on
          <select value={check} onChange={(e) => set('check', e.target.value)}>
            {CHECKS.map((c) => <option key={c} value={c}>{CHECK_LABEL[c]}</option>)}
          </select>
        </label>
      </div>

      {diff.loading && <Loading label="Comparing runs" />}
      {diff.error && <ErrorState error={diff.error} onRetry={diff.reload} />}
      {d && (
        <>
          <section className="panel" aria-label="Every scenario, run A above run B">
            <Strips key={`${a}|${b}|${check}`} waveKey={`${a}|${b}|${check}`} diff={d} ticks={ticks} onPick={setPicked} picked={picked} />
          </section>
          {picked && <SideBySide diff={d} t={picked} />}
          <section className="section" aria-labelledby="lists-h">
            <h2 id="lists-h">By outcome</h2>
            <div className="cat-grid">
              {DIFF_CATEGORIES.filter((c) => c !== 'still_pass' && d.counts[c] > 0).map((c) => (
                <div key={c} className="panel section">
                  <h3>{CAT_LABEL[c]} <span className="muted">{d.counts[c]}</span></h3>
                  <ul className="cat-list">
                    {d[c].map((it) => {
                      const t = ticks.find((x) => x.sample_id === it.sample_id && x.epoch === it.epoch)!
                      return (
                        <li key={`${it.sample_id}-${it.epoch}`}>
                          <button className="linkish id" onClick={() => setPicked(t)}>{it.sample_id}</button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
              <div className="panel section">
                <h3>Still passing <span className="muted">{d.counts.still_pass}</span></h3>
                <p className="small muted">Unchanged passes are counted, not listed.</p>
              </div>
            </div>
          </section>
        </>
      )}
    </>
  )
}
