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
      'Cannot reach the API server. Start the backend: uvicorn app.main:app --reload --port 8000 (run from backend/)',
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
    throw new Error(
      (detail && detail.length < 280 ? `${detail.trim()} ` : '') +
        `HTTP ${res.status} ${res.statusText}.${proxyHint}`.trim(),
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
