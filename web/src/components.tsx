import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ApiError, type Cell, type CitationText, type Verdict } from './api'
import { pct, verdict } from './format'
import { ecfrUrl } from './lib/ecfr'

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  // Results are tagged with the inputs that produced them, so a screen never shows the
  // previous filter's data under the new filter while the new request is in flight.
  const key = JSON.stringify(deps)
  const [tick, setTick] = useState(0)
  const [state, setState] = useState<{ key: string; data: T | null; error: ApiError | null }>({
    key: '', data: null, error: null,
  })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fn, deps)
  const want = `${key}#${tick}`
  useEffect(() => {
    let live = true
    run().then(
      (data) => live && setState({ key: want, data, error: null }),
      (e) => live && setState({ key: want, data: null, error: e instanceof ApiError ? e : new ApiError(0, String(e)) }),
    )
    return () => {
      live = false
    }
  }, [run, want])
  const current = state.key === want
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: !current,
    reload: () => setTick((t) => t + 1),
  }
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <span>{label}…</span>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div className="state error" role="alert">
      <p>{error.status === 0 ? error.detail : `${error.detail} (HTTP ${error.status})`}</p>
      {error.status === 0 && (
        <p className="small">
          Run <code>uv run examiner serve</code> in the examiner folder, then retry.
        </p>
      )}
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>
}

export function Chip({ v, error, label }: { v: Verdict; error?: string | null; label?: string }) {
  const { word, tone } = verdict(v, error)
  return (
    <span className={`chip ${tone}`}>
      {label ? <span className="sr-only">{label}: </span> : null}
      {word}
    </span>
  )
}

export function Rate({ cell, label }: { cell: Cell; label?: string }) {
  const width = cell.rate === null ? 0 : Math.round(cell.rate * 1000) / 10
  return (
    <div className="rate" aria-label={label ? `${label}: ${pct(cell)}, ${cell.passed} of ${cell.n}` : undefined}>
      <div className="rate-top">
        <span className="rate-pct">{pct(cell)}</span>
        <span className="rate-n">{cell.n ? `${cell.passed}/${cell.n}` : 'no data'}</span>
      </div>
      <div className="bar" aria-hidden="true">
        <span style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

const SPEAKER = /^(USER|CUSTOMER|BOT|ASSISTANT):\s?/

export function parseTranscript(text: string): { who: 'Customer' | 'Bot'; text: string }[] {
  const turns: { who: 'Customer' | 'Bot'; text: string }[] = []
  for (const line of text.split('\n')) {
    const m = SPEAKER.exec(line)
    if (m) turns.push({ who: m[1] === 'BOT' || m[1] === 'ASSISTANT' ? 'Bot' : 'Customer', text: line.slice(m[0].length) })
    else if (turns.length) turns[turns.length - 1].text += `\n${line}`
    else turns.push({ who: 'Customer', text: line })
  }
  return turns.map((t) => ({ ...t, text: t.text.trim() }))
}

/** Bot replies are Markdown; show **bold** as bold instead of raw asterisks. Nothing else is parsed. */
export function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*\n]+\*\*)/g).map((part, i) =>
    /^\*\*[^*\n]+\*\*$/.test(part) ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

export function Transcript({ text }: { text: string | null }) {
  if (!text) return <p className="muted">No transcript was recorded.</p>
  return (
    <div className="transcript">
      {parseTranscript(text).map((t, i) => (
        <div key={i} className={`turn ${t.who === 'Bot' ? 'bot' : 'user'}`}>
          <div className="turn-who">{t.who === 'Bot' ? 'Meridian bot' : 'Customer'}</div>
          <div className="turn-text">{renderInline(t.text)}</div>
        </div>
      ))}
    </div>
  )
}

export function Citation({ c }: { c: CitationText }) {
  const url = ecfrUrl(c.cite)
  return (
    <figure className="cite" style={{ margin: 0 }}>
      <figcaption className="cite-head">
        <strong>{c.display}</strong>
        {url && (
          <a href={url} target="_blank" rel="noreferrer">
            Read on eCFR<span className="sr-only"> (opens in a new tab)</span>
          </a>
        )}
      </figcaption>
      <blockquote className="cite-text" style={{ margin: 0 }}>
        {c.text ?? 'Text not found in the regulation snapshot.'}
      </blockquote>
    </figure>
  )
}

/** A horizontally scrollable table container that keyboard users can scroll too. */
export function TableWrap({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  )
}
