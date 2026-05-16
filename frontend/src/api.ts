import type {
  DailyLeadersResponse,
  DailyPicksResponse,
  PreviewResponse,
  ReportResponse,
  TickerValidateResponse,
  WatchlistListResponse,
} from './types'

const base =
  typeof import.meta.env.VITE_API_BASE === 'string' && import.meta.env.VITE_API_BASE
    ? import.meta.env.VITE_API_BASE.replace(/\/$/, '')
    : '/api'

export function isAbortError(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') return true
  return e instanceof Error && e.name === 'AbortError'
}

/**
 * Typed JSON GET/POST helper: prefixes `base` (dev proxy `/api` or `VITE_API_BASE`).
 * Throws on network failure; on HTTP errors includes status text and optional JSON `detail`.
 */
async function jsonFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    })
  } catch (e) {
    if (isAbortError(e)) throw e
    throw new Error(
      'Cannot reach the API server. From backend/, start it: python run.py --reload --port 8000 (or: uvicorn app.main:app --port 8000)',
    )
  }

  if (!res.ok) {
    const proxyHint =
      base === '/api' && [502, 503, 504].includes(res.status)
        ? ' Dev proxy sends /api to http://127.0.0.1:8000 — start FastAPI there.'
        : ''
    let detail = ''
    try {
      detail = await res.text()
    } catch {
      /* ignore */
    }
    let parsedDetail = ''
    try {
      const j = JSON.parse(detail) as { detail?: string }
      if (typeof j.detail === 'string' && j.detail.trim()) parsedDetail = j.detail.trim()
    } catch {
      /* not JSON */
    }
    if (parsedDetail && res.status === 503) {
      throw new Error(parsedDetail)
    }
    const tail = `HTTP ${res.status} ${res.statusText}.${proxyHint}`.trim()
    throw new Error(
      (parsedDetail ? `${parsedDetail} ` : detail && detail.length < 280 ? `${detail.trim()} ` : '') +
        tail,
    )
  }
  return res.json() as Promise<T>
}

export function fetchDailyLeaders(limit = 5): Promise<DailyLeadersResponse> {
  const q = new URLSearchParams({ limit: String(limit) })
  return jsonFetch<DailyLeadersResponse>(`/market/daily-leaders?${q}`)
}

export function fetchDailyPicks(
  universe: 'sp500' | 'curated' = 'sp500',
  refresh = false,
  focus: 'short' | 'long' = 'short',
  init?: RequestInit,
): Promise<DailyPicksResponse> {
  const q = new URLSearchParams({ universe, focus })
  if (refresh) q.set('refresh', '1')
  return jsonFetch<DailyPicksResponse>(`/market/daily-picks?${q}`, init)
}

export function validateTicker(symbol: string): Promise<TickerValidateResponse> {
  const q = new URLSearchParams({ symbol })
  return jsonFetch<TickerValidateResponse>(`/ticker/validate?${q}`)
}

export function previewTicker(symbol: string): Promise<PreviewResponse> {
  const q = new URLSearchParams({ symbol })
  return jsonFetch<PreviewResponse>(`/ticker/preview?${q}`)
}

export function generateReport(
  symbol: string,
  includeCitations = true,
): Promise<ReportResponse> {
  return jsonFetch<ReportResponse>(`/report`, {
    method: 'POST',
    body: JSON.stringify({ symbol, include_citations: includeCitations }),
  })
}

export function fetchWatchlist(): Promise<WatchlistListResponse> {
  return jsonFetch<WatchlistListResponse>('/watchlist')
}

export function addWatchlistSymbol(symbol: string): Promise<WatchlistListResponse> {
  return jsonFetch<WatchlistListResponse>('/watchlist', {
    method: 'POST',
    body: JSON.stringify({ symbol }),
  })
}

export function removeWatchlistSymbol(symbol: string): Promise<WatchlistListResponse> {
  const enc = encodeURIComponent(symbol)
  return jsonFetch<WatchlistListResponse>(`/watchlist/${enc}`, { method: 'DELETE' })
}
