import type { Diff, DiffCategory, Verdict } from '../api'

export interface Tick {
  sample_id: string
  epoch: number
  a: Verdict
  b: Verdict
  category: DiffCategory
}

const CATS: DiffCategory[] = ['fixed', 'broke', 'still_fail', 'still_pass', 'unscored', 'only_a', 'only_b']

/** One tick per scenario in either run, in id order (variants sit next to their seed). */
export function stripModel(diff: Diff): Tick[] {
  const ticks: Tick[] = []
  for (const category of CATS) for (const it of diff[category] ?? []) ticks.push({ ...it, category })
  return ticks.sort((x, y) => x.sample_id.localeCompare(y.sample_id) || x.epoch - y.epoch)
}

export type TickTone = 'pass' | 'fail' | 'unjudged' | 'absent'

/** What a tick shows for one run: absent (scenario not in that run) differs from not judged. */
export function tickTone(t: Tick, side: 'a' | 'b'): TickTone {
  if ((side === 'a' && t.category === 'only_b') || (side === 'b' && t.category === 'only_a')) return 'absent'
  const v = t[side]
  return v === 1 ? 'pass' : v === 0 ? 'fail' : 'unjudged'
}
