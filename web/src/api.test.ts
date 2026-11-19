import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './api'

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('builds result filter URLs without empty params', async () => {
    const f = mockFetch(200, [])
    await api.results('run 1', { status: 'fail' })
    expect(f.mock.calls[0][0]).toBe('/api/runs/run%201/results?status=fail')
  })
  it('encodes sample ids and epoch', async () => {
    const f = mockFetch(200, {})
    await api.result('r', 'fees-005--v1', 2)
    expect(f.mock.calls[0][0]).toBe('/api/runs/r/results/fees-005--v1?epoch=2')
  })
  it('throws ApiError with the server detail', async () => {
    mockFetch(404, { detail: 'no run nope' })
    await expect(api.run('nope')).rejects.toEqual(new ApiError(404, 'no run nope'))
  })
  it('posts labels as JSON', async () => {
    const f = mockFetch(201, {})
    await api.postLabel({ run_id: 'r', sample_id: 's', epoch: 1, rubric: 'factual', human_pass: true })
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/labels')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toMatchObject({ human_pass: true })
  })
  it('turns a network failure into a stated ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.runs()).rejects.toMatchObject({ status: 0 })
  })
})
