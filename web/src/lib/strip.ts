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
