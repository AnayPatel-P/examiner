import { describe, expect, it } from 'vitest'
import type { Diff } from '../api'
import { ecfrUrl } from './ecfr'
import { kappaWord } from './kappa'
import { initialLabelState, labelReducer } from './labelReducer'
import { stripModel, tickTone } from './strip'

describe('ecfrUrl', () => {
  it('links a Reg E paragraph to its eCFR anchor', () => {
    expect(ecfrUrl('12 CFR 1005.11(c)(2)(i)')).toBe(
      'https://www.ecfr.gov/current/title-12/part-1005/section-1005.11#p-1005.11(c)(2)(i)',
    )
    expect(ecfrUrl('12 CFR 1005.6')).toBe('https://www.ecfr.gov/current/title-12/part-1005/section-1005.6')
  })
  it('has no link for a fee schedule entry', () => {
    expect(ecfrUrl('fee:overdraft')).toBeNull()
  })
})

describe('kappaWord', () => {
  it('uses the Landis-Koch bands', () => {
    expect(kappaWord(null)).toBe('No data')
    expect(kappaWord(-0.1)).toBe('Worse than chance')
    expect(kappaWord(0.1)).toBe('Slight')
    expect(kappaWord(0.3)).toBe('Fair')
    expect(kappaWord(0.5)).toBe('Moderate')
    expect(kappaWord(0.7)).toBe('Substantial')
    expect(kappaWord(0.85)).toBe('Almost perfect')
  })
})

const item = (id: string) => ({ run_id: 'r', sample_id: id, epoch: 1, rubric: 'factual' as const })

describe('labelReducer', () => {
  const loaded = labelReducer(initialLabelState, { type: 'loaded', items: [item('a'), item('b')] })

  it('starts a save on a key and ignores keys while saving', () => {
    const saving = labelReducer(loaded, { type: 'key', pass: true })
    expect(saving.status).toBe('saving')
    expect(saving.pending).toEqual({ ...item('a'), human_pass: true })
    expect(labelReducer(saving, { type: 'key', pass: false })).toBe(saving)
    expect(labelReducer(saving, { type: 'skip' })).toBe(saving)
  })
  it('advances after a save and counts it', () => {
    const saving = labelReducer(loaded, { type: 'key', pass: false })
    const done = labelReducer(saving, { type: 'saved', key: saving.pending! })
    expect(done.index).toBe(1)
    expect(done.status).toBe('idle')
    expect(done.history).toEqual([{ ...item('a'), human_pass: false }])
  })
  it('keeps the item when a save fails', () => {
    const saving = labelReducer(loaded, { type: 'key', pass: true })
    const failed = labelReducer(saving, { type: 'failed', key: saving.pending!, message: 'down' })
    expect(failed.index).toBe(0)
    expect(failed.status).toBe('idle')
    expect(failed.error).toBe('down')
  })
  it('takes the rubric from the item, not from the page', () => {
    const disc = labelReducer(initialLabelState, {
      type: 'loaded', items: [{ ...item('a'), rubric: 'disclosure' as const }],
    })
    expect(labelReducer(disc, { type: 'key', pass: true }).pending?.rubric).toBe('disclosure')
  })
  it('ignores a save confirmation for a label that is no longer pending', () => {
    const savingA = labelReducer(loaded, { type: 'key', pass: true })
    const stale = savingA.pending!
    // queue reloads mid-save, then the user labels the new first item
    const reloaded = labelReducer(savingA, { type: 'loaded', items: [item('x'), item('y')] })
    const savingX = labelReducer(reloaded, { type: 'key', pass: false })
    expect(labelReducer(savingX, { type: 'saved', key: stale })).toBe(savingX)
    expect(labelReducer(savingX, { type: 'failed', key: stale, message: 'old' })).toBe(savingX)
  })
  it('reset clears the queue so nothing stale can be labeled', () => {
    const r = labelReducer(loaded, { type: 'reset' })
    expect(r.items).toEqual([])
    expect(labelReducer(r, { type: 'key', pass: true }).pending).toBeNull()
  })
  it('skip advances without a save', () => {
    const s = labelReducer(loaded, { type: 'skip' })
    expect(s.index).toBe(1)
    expect(s.history).toEqual([])
  })
  it('undo steps back to the last labeled item', () => {
    const saving = labelReducer(loaded, { type: 'key', pass: true })
    const done = labelReducer(saving, { type: 'saved', key: saving.pending! })
    const back = labelReducer(done, { type: 'undo' })
    expect(back.index).toBe(0)
    expect(back.history).toEqual([])
  })
})

describe('stripModel', () => {
  const diff = {
    fixed: [{ sample_id: 'b', epoch: 1, a: 0, b: 1 }],
    broke: [{ sample_id: 'a', epoch: 1, a: 1, b: 0 }],
    still_fail: [],
    still_pass: [{ sample_id: 'c', epoch: 1, a: 1, b: 1 }],
    unscored: [{ sample_id: 'd', epoch: 1, a: null, b: 1 }],
    only_a: [{ sample_id: 'e', epoch: 1, a: 0, b: null }],
    only_b: [{ sample_id: 'f', epoch: 1, a: null, b: 1 }],
    counts: { fixed: 1, broke: 1, still_fail: 0, still_pass: 1, unscored: 1, only_a: 1, only_b: 1 },
  } as unknown as Diff

  it('has one tick per sample in the union, sorted by id', () => {
    const ticks = stripModel(diff)
    expect(ticks.map((t) => t.sample_id)).toEqual(['a', 'b', 'c', 'd', 'e', 'f'])
    expect(ticks.length).toBe(Object.values(diff.counts).reduce((x, y) => x + y, 0))
  })
  it('keeps category and both verdicts', () => {
    const e = stripModel(diff).find((t) => t.sample_id === 'e')!
    expect(e).toMatchObject({ category: 'only_a', a: 0, b: null })
  })
})

describe('tickTone', () => {
  it('tells a scenario missing from a run apart from one the judge did not score', () => {
    const base = { sample_id: 's', epoch: 1 }
    expect(tickTone({ ...base, a: 0, b: null, category: 'only_a' }, 'b')).toBe('absent')
    expect(tickTone({ ...base, a: null, b: 1, category: 'only_b' }, 'a')).toBe('absent')
    expect(tickTone({ ...base, a: null, b: 1, category: 'unscored' }, 'a')).toBe('unjudged')
    expect(tickTone({ ...base, a: 0, b: 1, category: 'fixed' }, 'b')).toBe('pass')
    expect(tickTone({ ...base, a: 0, b: 1, category: 'fixed' }, 'a')).toBe('fail')
  })
})
