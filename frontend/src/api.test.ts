import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()

describe('api client', () => {
  beforeEach(() => {
    vi.resetModules()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('validateTicker GETs validate endpoint with symbol query', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ valid: true, symbol: 'AAPL', name: null }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const { validateTicker } = await import('./api')
    const r = await validateTicker('aapl')
    expect(r.valid).toBe(true)
    expect(r.symbol).toBe('AAPL')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toMatch(/\/ticker\/validate\?/)
    expect(url).toContain('symbol=aapl')
    expect(init?.method).toBeUndefined()
  })

  it('throws friendly message when fetch fails (network)', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const { validateTicker } = await import('./api')
    await expect(validateTicker('MSFT')).rejects.toThrow(/Cannot reach the API server/)
  })

  it('502 from /api includes proxy hint', async () => {
    fetchMock.mockResolvedValue(new Response('bad gateway', { status: 502 }))
    const { validateTicker } = await import('./api')
    await expect(validateTicker('X')).rejects.toThrow(/502/)
    await expect(validateTicker('X')).rejects.toThrow(/Dev proxy/)
  })

  it('fetchDailyPicks adds refresh=1 when requested', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ picks: [], note: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const { fetchDailyPicks } = await import('./api')
    await fetchDailyPicks('curated', true)
    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url).toContain('universe=curated')
    expect(url).toContain('refresh=1')
  })

  it('generateReport POSTs JSON body', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ summary: 'x', disclaimer: 'd' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const { generateReport } = await import('./api')
    await generateReport('IBM', false)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({ symbol: 'IBM', include_citations: false }))
  })
})
