import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// The labeling screen must stay blind: no endpoint that returns judge verdicts or rationales.
describe('Label screen', () => {
  it('only uses the label queue, label posting, run names and batch progress', () => {
    const src = readFileSync(resolve(__dirname, 'Label.tsx'), 'utf8')
    const calls = [...src.matchAll(/api\s*\.(\w+)\(/g)].map((m) => m[1])
    expect(new Set(calls)).toEqual(new Set(['runs', 'batches', 'labelQueue', 'postLabel']))
    expect(src).not.toMatch(/rationale|judge_pass|\.overall|\.scores/)
  })
})
