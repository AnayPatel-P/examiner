import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api, CHECKS, DIFF_CATEGORIES, type Check, type Diff, type DiffCategory, type RunSummary, type Verdict } from '../api'
import { Chip, ErrorState, Loading, Transcript, useLoad } from '../components'
import { pct, variantLabel } from '../format'
import { stripModel, type Tick } from '../lib/strip'

const CAT_LABEL: Record<DiffCategory, string> = {
  fixed: 'Fixed', broke: 'Broke', still_fail: 'Still failing', still_pass: 'Still passing',
  unscored: 'Not judged in one run', only_a: 'Only in A', only_b: 'Only in B',
}
const CHECK_LABEL: Record<Check, string> = {
  overall: 'Overall', fact: 'Fact check', judge: 'Judge', factual: 'Factual', disclosure: 'Disclosure', commitments: 'Commitments',
}

function tone(v: Verdict): string {
  return v === 1 ? 'pass' : v === 0 ? 'fail' : 'none'
}

function runLabel(r: RunSummary) {
  return `${variantLabel(r.variant)} · ${r.pack} · ${r.id.slice(0, 8)}`
}

/** The signature: B's ticks turn from A's verdict to their own in one left-to-right wave, once per comparison. */
function Strips({ diff, onPick, picked }: { diff: Diff; onPick: (t: Tick) => void; picked: Tick | null }) {
  const ticks = useMemo(() => stripModel(diff), [diff])
  const key = `${diff.a.id}|${diff.b.id}|${diff.check}`
  const played = useRef<string | null>(null)
  const [phase, setPhase] = useState<'before' | 'after'>('after')
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || played.current === key) return
    setPhase('before')
    let inner = 0
    const outer = requestAnimationFrame(() => {
      inner = requestAnimationFrame(() => {
        played.current = key // mark played only once the wave really starts
        setPhase('after')
      })
    })
    return () => {
      cancelAnimationFrame(outer)
      cancelAnimationFrame(inner)
      setPhase('after') // never leave B showing A's verdicts
    }
  }, [key])
  const step = Math.min(2, 300 / Math.max(ticks.length, 1))

  const row = (side: 'a' | 'b') => (
    <div className="strip-row">
      <div className="strip-label">
        <strong>{side === 'a' ? 'A' : 'B'}</strong> {runLabel(diff[side])}
        <span className="muted"> · {pct(diff[side].overall)} overall</span>
      </div>
      <div className="strip" role="group" aria-label={`Run ${side.toUpperCase()} verdicts, one tick per scenario`}>
        {ticks.map((t, i) => {
          const v = side === 'b' && phase === 'before' ? t.a : t[side]
          const marked = side === 'b' && (t.category === 'fixed' || t.category === 'broke')
          return (
            <button
              key={`${t.sample_id}-${t.epoch}`}
              className={`tick ${tone(v)}${marked && phase === 'after' ? ` ring ${t.category}` : ''}${picked === t ? ' picked' : ''}`}
              style={side === 'b' ? { transitionDelay: phase === 'after' ? `${i * step}ms` : '0ms' } : undefined}
              onClick={() => onPick(t)}
              aria-label={`${t.sample_id}: ${CAT_LABEL[t.category]}`}
              tabIndex={side === 'a' ? -1 : 0}
            />
          )
        })}
      </div>
    </div>
  )

  return (
    <div className="strips">
      {row('a')}
      {row('b')}
      <p className="small muted strip-key">
        <span className="tick pass static" aria-hidden="true" /> pass <span className="tick fail static" aria-hidden="true" /> fail{' '}
        <span className="tick none static" aria-hidden="true" /> not judged or missing · ringed ticks changed · click a tick to compare
      </p>
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
        <Chip v={t[side]} />
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
      <h2 id="cmp-h"><span className="id">{t.sample_id}</span> · {CAT_LABEL[t.category]}</h2>
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
  const a = params.get('a') ?? pick('naive') ?? runs.data?.[1]?.id ?? ''
  const b = params.get('b') ?? pick('guarded') ?? runs.data?.[0]?.id ?? ''
  const diff = useLoad(() => (a && b ? api.diff(a, b, check) : Promise.resolve(null)), [a, b, check])
  const [picked, setPicked] = useState<Tick | null>(null)
  useEffect(() => setPicked(null), [a, b, check])

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
            <Strips diff={d} onPick={setPicked} picked={picked} />
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
                      const t = stripModel(d).find((x) => x.sample_id === it.sample_id && x.epoch === it.epoch)!
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
