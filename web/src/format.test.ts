import { describe, expect, it } from 'vitest'
import { money, pct, rateWithN, secs, verdict } from './format'

describe('format', () => {
  it('shows a dash for a cell with no data', () => {
    expect(pct({ passed: 0, n: 0, rate: null })).toBe('–')
  })
  it('formats a rate with one decimal and n', () => {
    expect(pct({ passed: 115, n: 127, rate: 115 / 127 })).toBe('90.6%')
    expect(rateWithN({ passed: 115, n: 127, rate: 115 / 127 })).toBe('90.6% · 115/127')
  })
  it('never calls a null verdict a fail', () => {
    expect(verdict(null)).toEqual({ word: 'Not judged', tone: 'neutral' })
    expect(verdict(0)).toEqual({ word: 'Fail', tone: 'fail' })
    expect(verdict(1)).toEqual({ word: 'Pass', tone: 'pass' })
    expect(verdict(null, 'target error: boom')).toEqual({ word: 'Error', tone: 'warning' })
  })
  it('formats money and seconds', () => {
    expect(money(1.7016)).toBe('$1.70')
    expect(money(0.0698)).toBe('$0.07')
    expect(money(null)).toBe('–')
    expect(secs(174.4)).toBe('2 min 54 s')
    expect(secs(null)).toBe('–')
  })
})
