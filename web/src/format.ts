import type { Cell, Verdict } from './api'

export type Tone = 'pass' | 'fail' | 'warning' | 'neutral'

const pctFmt = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })

export function pct(cell: Cell): string {
  return cell.rate === null || cell.n === 0 ? '–' : pctFmt.format(cell.rate)
}

export function rateWithN(cell: Cell): string {
  return cell.n === 0 ? '–' : `${pct(cell)} · ${cell.passed}/${cell.n}`
}

export function verdict(v: Verdict, error?: string | null): { word: string; tone: Tone } {
  if (error) return { word: 'Error', tone: 'warning' }
  if (v === 1) return { word: 'Pass', tone: 'pass' }
  if (v === 0) return { word: 'Fail', tone: 'fail' }
  return { word: 'Not judged', tone: 'neutral' }
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function money(v: number | null | undefined): string {
  return v === null || v === undefined ? '–' : usd.format(v)
}

export function secs(v: number | null | undefined): string {
  if (v === null || v === undefined) return '–'
  const s = Math.round(v)
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}

export function when(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export const VARIANT_LABEL: Record<string, string> = {
  naive: 'Naive',
  guarded: 'Guarded',
  misinformed: 'Misinformed (fixture)',
}

export function variantLabel(v: string): string {
  return VARIANT_LABEL[v] ?? v
}
