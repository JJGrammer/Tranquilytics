import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { DailyLeaderRow, DailyPickRow, WatchlistItem } from './types'
import {
  addWatchlistSymbol,
  fetchDailyLeaders,
  fetchDailyPicks,
  fetchWatchlist,
  generateReport,
  isAbortError,
  previewTicker,
  removeWatchlistSymbol,
  validateTicker,
} from './api'
import {
  applyColorModeToDocument,
  persistColorMode,
  readStoredColorMode,
  type ColorMode,
} from './theme'
import {
  formatSynthesizerRuntimeLines,
  getConfidenceExplanationSections,
  getSynthesizerExplanationSections,
  type ExplanationSection,
} from './analysisExplanations'
import { ExplanationModal } from './components/ExplanationModal'

/** Full S&P scan can exceed this; we abort client-side so the UI never sticks on “Scanning…”. */
const SCREENER_FETCH_TIMEOUT_MS = 12 * 60 * 1000

const TONES_ORDER = [
  'Safer Buy',
  'Buy',
  'Neutral',
  'Sell',
  'Sell Soon',
] as const

function ThinkingCloudBackdrop({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 400 160"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
      focusable="false"
    >
      <g
        className="text-emerald-500/90 dark:text-cyan-400"
        opacity={0.14}
      >
        <ellipse cx="204" cy="78" rx="102" ry="40" fill="currentColor" />
        <ellipse cx="128" cy="74" rx="52" ry="36" fill="currentColor" />
        <ellipse cx="278" cy="76" rx="54" ry="38" fill="currentColor" />
        <ellipse cx="200" cy="58" rx="58" ry="30" fill="currentColor" />
      </g>
      <g
        className="text-emerald-500/90 dark:text-cyan-400"
        opacity={0.1}
      >
        <circle cx="108" cy="124" r="11" fill="currentColor" />
        <circle cx="82" cy="136" r="7" fill="currentColor" />
        <circle cx="58" cy="146" r="4" fill="currentColor" />
      </g>
      <ellipse
        cx="200"
        cy="74"
        rx="118"
        ry="48"
        className="text-emerald-400/80 dark:text-cyan-300/80"
        stroke="currentColor"
        strokeOpacity={0.12}
        strokeWidth={1}
        fill="none"
      />
    </svg>
  )
}

const LOOKUP_BUBBLE_SLOTS: { left: string; bottom: string; delay: string; cls: string }[] = [
  { left: '6%', bottom: '0', delay: '0ms', cls: 'h-1.5 w-1.5' },
  { left: '18%', bottom: '2px', delay: '200ms', cls: 'h-2 w-2' },
  { left: '32%', bottom: '0', delay: '420ms', cls: 'h-1 w-1' },
  { left: '48%', bottom: '4px', delay: '100ms', cls: 'h-2 w-2' },
  { left: '62%', bottom: '1px', delay: '300ms', cls: 'h-1.5 w-1.5' },
  { left: '78%', bottom: '3px', delay: '560ms', cls: 'h-1 w-1' },
  { left: '88%', bottom: '0', delay: '680ms', cls: 'h-2 w-2' },
]

function filterAndRankLeaders(
  rows: DailyLeaderRow[],
  query: string,
): DailyLeaderRow[] {
  const q = query.trim().toLowerCase()
  if (!q) return rows

  type Keyed = { row: DailyLeaderRow; rank: number }
  const keyed: Keyed[] = []

  for (const row of rows) {
    const sym = row.symbol.toLowerCase()
    const name = (row.name ?? '').toLowerCase()
    let rank = Number.POSITIVE_INFINITY
    if (sym === q) rank = 0
    else if (sym.startsWith(q)) rank = 15
    else if (name.startsWith(q)) rank = 110
    else {
      const si = sym.indexOf(q)
      if (si >= 0) rank = 380 + si
      else {
        const ni = name.indexOf(q)
        if (ni >= 0) rank = 600 + ni
      }
    }
    if (rank < Number.POSITIVE_INFINITY) keyed.push({ row, rank })
  }

  keyed.sort((a, b) => {
    if (a.rank !== b.rank) return a.rank - b.rank
    return b.row.change_pct_day - a.row.change_pct_day
  })
  return keyed.map((k) => k.row)
}

type WatchlistShortHint =
  | { status: 'loading' }
  | { status: 'ok'; tone: string; confidence: number; changePctDay: number | null }
  | { status: 'unavailable' }

function toneBadgeClass(tone: string): string {
  const base = 'rounded-full px-2.5 py-0.5 text-xs font-medium ring-1'
  switch (tone) {
    case 'Safer Buy':
      return `${base} bg-emerald-100 text-emerald-900 ring-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200 dark:ring-emerald-500/40`
    case 'Buy':
      return `${base} bg-green-100 text-green-900 ring-green-600/35 dark:bg-green-500/15 dark:text-green-200 dark:ring-green-500/35`
    case 'Neutral':
      return `${base} bg-slate-200 text-slate-800 ring-slate-400/60 dark:bg-slate-500/20 dark:text-slate-200 dark:ring-slate-400/35`
    case 'Sell':
      return `${base} bg-amber-100 text-amber-900 ring-amber-500/40 dark:bg-amber-500/15 dark:text-amber-200 dark:ring-amber-400/35`
    case 'Sell Soon':
      return `${base} bg-rose-100 text-rose-900 ring-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200 dark:ring-rose-400/35`
    default:
      return `${base} bg-slate-200 text-slate-800 ring-slate-400/50 dark:bg-slate-600/25 dark:text-slate-200 dark:ring-slate-400/35`
  }
}

function citationSourceWithLinks(source: string): ReactNode {
  const segments = source.split(/(https?:\/\/[^\s]+)/gi)
  return segments.map((part, i) => {
    if (/^https?:\/\//i.test(part)) {
      const href = part.replace(/[)\].,;:]+$/, '')
      const tail = part.slice(href.length)
      return (
        <span key={`u-${i}-${href.slice(0, 28)}`} className="inline min-w-0">
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline text-emerald-700 underline decoration-emerald-500/40 underline-offset-2 [overflow-wrap:anywhere] break-all hover:text-emerald-800 dark:text-cyan-400/90 dark:decoration-cyan-500/40 dark:hover:text-cyan-300"
          >
            {href}
          </a>
          {tail}
        </span>
      )
    }
    return (
      <span key={`t-${i}`} className="[overflow-wrap:anywhere] break-words">
        {part}
      </span>
    )
  })
}

function ConfidenceBar({
  value,
  onExplain,
  explainAriaLabel = 'How confidence is calculated',
}: {
  value: number
  onExplain?: () => void
  explainAriaLabel?: string
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div className="flex min-w-0 flex-1 items-center gap-1.5">
      {onExplain ? (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault()
            onExplain()
          }}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-sky-300/80 text-[11px] font-semibold text-emerald-800 transition hover:bg-sky-100 dark:border-slate-600 dark:text-cyan-400 dark:hover:bg-slate-800"
          aria-label={explainAriaLabel}
        >
          ?
        </button>
      ) : null}
      <div
        className="h-1.5 min-w-0 flex-1 max-w-[120px] overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
        title={`${pct}%`}
      >
        <div
          className="h-full rounded-full bg-emerald-600/75 dark:bg-cyan-500/70"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/** Same shell as watchlist / screener cards for visual alignment */
const SECTION_CARD_CLASS =
  'rounded-xl border border-sky-200/90 bg-white/80 px-4 py-3 text-left shadow-sm dark:border-slate-800/80 dark:bg-slate-900/40 dark:shadow-none'

function OutlookScaleLegend({
  scaleHighlight,
  variant,
}: {
  scaleHighlight: string | null
  variant: 'rail' | 'strip'
}) {
  const rail = variant === 'rail'
  return (
    <div className={SECTION_CARD_CLASS} aria-label="Outlook scale legend">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
        Outlook scale
      </p>
      <div
        className={
          rail
            ? 'mt-2 flex flex-col items-stretch gap-1.5'
            : 'mt-2 flex flex-wrap gap-2'
        }
      >
        {TONES_ORDER.map((t) => (
          <span
            key={t}
            className={`${toneBadgeClass(t)} transition ${
              rail ? 'w-full justify-center text-center' : ''
            } ${
              scaleHighlight === t
                ? 'ring-2 ring-emerald-500 ring-offset-2 ring-offset-sky-50 dark:ring-cyan-400 dark:ring-offset-slate-900'
                : ''
            }`}
            title={
              scaleHighlight === t
                ? 'Matches current short-term tone after lookup'
                : undefined
            }
          >
            {t}
          </span>
        ))}
      </div>
      <p
        className="mt-2 border-t border-sky-200/80 pt-2 text-xs leading-snug text-slate-600 dark:border-slate-800/60 dark:text-slate-600"
      >
        {rail ? (
          <>
            Model tilt, not advice. Ring = short-term after lookup; long-term can differ.
          </>
        ) : (
          <>
            These labels describe our model's tilt; they are not instructions. After a successful lookup,
            the <span className="text-slate-700 dark:text-slate-500">highlight ring</span> marks{' '}
            <span className="text-slate-800 dark:text-slate-400">short-term</span> tone (long-term can differ).
          </>
        )}
      </p>
    </div>
  )
}

export default function App() {
  const [symbolInput, setSymbolInput] = useState('')
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [companyName, setCompanyName] = useState<string | null>(null)
  const [companyDescription, setCompanyDescription] = useState<string | null>(null)
  const [scaleHighlight, setScaleHighlight] = useState<string | null>(null)
  const [shortTone, setShortTone] = useState<string | null>(null)
  const [longTone, setLongTone] = useState<string | null>(null)
  const [riskPreview, setRiskPreview] = useState<string | null>(null)
  const [sentPreview, setSentPreview] = useState<{
    label: string
    count: number
    labelLong: string
    countLong: number
  } | null>(null)
  const [previewConf, setPreviewConf] = useState<{
    short: number
    long: number
  } | null>(null)
  const [report, setReport] = useState<Awaited<
    ReturnType<typeof generateReport>
  > | null>(null)

  const [loadingSearch, setLoadingSearch] = useState(false)
  const [loadingReport, setLoadingReport] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [colorMode, setColorMode] = useState<ColorMode>(() => readStoredColorMode())

  const [explanationModal, setExplanationModal] = useState<{
    title: string
    sections: ExplanationSection[]
    extraNote?: string
  } | null>(null)

  useLayoutEffect(() => {
    applyColorModeToDocument(colorMode)
    persistColorMode(colorMode)
  }, [colorMode])

  const [quickOpen, setQuickOpen] = useState(false)
  const [leadersLoading, setLeadersLoading] = useState(false)
  const [dailyLeaders, setDailyLeaders] = useState<DailyLeaderRow[]>([])
  const [dailyPicks, setDailyPicks] = useState<DailyPickRow[]>([])
  const [picksLoading, setPicksLoading] = useState(false)
  const [picksNote, setPicksNote] = useState<string | null>(null)
  const [picksExpanded, setPicksExpanded] = useState(false)
  const [picksFocus, setPicksFocus] = useState<'short' | 'long'>('short')
  const [mainTab, setMainTab] = useState<'ticker' | 'screener'>('ticker')
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([])
  const [watchlistMax, setWatchlistMax] = useState(50)
  const [watchlistLoading, setWatchlistLoading] = useState(true)
  const [watchlistBusy, setWatchlistBusy] = useState(false)
  const [watchlistErr, setWatchlistErr] = useState<string | null>(null)
  const [watchlistAddErr, setWatchlistAddErr] = useState<string | null>(null)
  const [watchlistShortHints, setWatchlistShortHints] = useState<
    Record<string, WatchlistShortHint>
  >({})
  const quickCloseTimer = useRef<number | null>(null)
  const picksLoadGeneration = useRef(0)
  const picksAbortRef = useRef<AbortController | null>(null)
  const picksAbortReason = useRef<'timeout' | 'user' | null>(null)

  const cancelQuickClose = useCallback(() => {
    if (quickCloseTimer.current != null) {
      window.clearTimeout(quickCloseTimer.current)
      quickCloseTimer.current = null
    }
  }, [])

  useEffect(() => () => cancelQuickClose(), [cancelQuickClose])

  const loadDailyPicksScreen = useCallback(
    async (refresh: boolean, focus: 'short' | 'long') => {
      picksAbortRef.current?.abort()
      const ac = new AbortController()
      picksAbortRef.current = ac
      picksAbortReason.current = null

      const myGen = ++picksLoadGeneration.current
      setMainTab('screener')
      setPicksFocus(focus)
      setPicksExpanded(true)
      setPicksLoading(true)
      setPicksNote(null)

      const timeoutId = window.setTimeout(() => {
        if (picksLoadGeneration.current !== myGen) return
        picksAbortReason.current = 'timeout'
        ac.abort()
      }, SCREENER_FETCH_TIMEOUT_MS)

      try {
        const r = await fetchDailyPicks('sp500', refresh, focus, { signal: ac.signal })
        if (myGen !== picksLoadGeneration.current) return
        setDailyPicks(r.picks ?? [])
        setPicksNote(r.note ?? '')
      } catch (e) {
        if (myGen !== picksLoadGeneration.current) return
        if (isAbortError(e)) {
          setDailyPicks([])
          if (picksAbortReason.current === 'timeout') {
            setPicksNote(
              'This request timed out on the client after 12 minutes. A cold S&P 500 scan can take longer than that on the server — wait and use “Re-scan … (ignore cache)” once the backend finishes, or run the API with a smaller universe during development.',
            )
          } else {
            setPicksNote('Scan cancelled.')
          }
          return
        }
        setDailyPicks([])
        setPicksNote(null)
      } finally {
        window.clearTimeout(timeoutId)
        if (myGen === picksLoadGeneration.current) {
          setPicksLoading(false)
        }
      }
    },
    [],
  )

  const cancelDailyPicksScreen = useCallback(() => {
    picksAbortReason.current = 'user'
    picksAbortRef.current?.abort()
  }, [])

  const scheduleQuickClose = useCallback(() => {
    cancelQuickClose()
    quickCloseTimer.current = window.setTimeout(() => setQuickOpen(false), 150)
  }, [cancelQuickClose])

  const suggestedLeaders = useMemo(
    () => filterAndRankLeaders(dailyLeaders, symbolInput),
    [dailyLeaders, symbolInput],
  )

  const loadDailyLeaders = useCallback(async () => {
    setLeadersLoading(true)
    try {
      const res = await fetchDailyLeaders(10)
      setDailyLeaders(res.leaders ?? [])
    } catch {
      setDailyLeaders([])
    } finally {
      setLeadersLoading(false)
    }
  }, [])

  const refreshWatchlist = useCallback(async () => {
    setWatchlistLoading(true)
    setWatchlistErr(null)
    try {
      const r = await fetchWatchlist()
      setWatchlistItems(r.items ?? [])
      setWatchlistMax(r.max_items ?? 50)
    } catch (e) {
      setWatchlistItems([])
      setWatchlistErr(e instanceof Error ? e.message : 'Watchlist unavailable')
    } finally {
      setWatchlistLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshWatchlist()
  }, [refreshWatchlist])

  useEffect(() => {
    setWatchlistAddErr(null)
  }, [selectedSymbol])

  const addLookupToWatchlist = useCallback(async () => {
    if (!selectedSymbol) return
    if (watchlistItems.length >= watchlistMax) {
      setWatchlistAddErr('Watchlist is full.')
      return
    }
    if (watchlistItems.some((i) => i.symbol === selectedSymbol)) return
    setWatchlistBusy(true)
    setWatchlistAddErr(null)
    try {
      const r = await addWatchlistSymbol(selectedSymbol)
      setWatchlistItems(r.items ?? [])
    } catch (err) {
      setWatchlistAddErr(err instanceof Error ? err.message : 'Could not add to watchlist')
    } finally {
      setWatchlistBusy(false)
    }
  }, [selectedSymbol, watchlistItems, watchlistMax])

  const removeFromWatchlist = useCallback(async (symbol: string) => {
    setWatchlistBusy(true)
    setWatchlistErr(null)
    try {
      const r = await removeWatchlistSymbol(symbol)
      setWatchlistItems(r.items ?? [])
    } catch (err) {
      setWatchlistErr(err instanceof Error ? err.message : 'Could not remove symbol')
    } finally {
      setWatchlistBusy(false)
    }
  }, [])

  const watchlistSymbolsKey = useMemo(
    () => watchlistItems.map((i) => i.symbol).join('|'),
    [watchlistItems],
  )

  useEffect(() => {
    if (!watchlistSymbolsKey) {
      setWatchlistShortHints({})
      return
    }
    let cancelled = false
    const symbols = watchlistSymbolsKey.split('|')
    setWatchlistShortHints(
      Object.fromEntries(symbols.map((s) => [s, { status: 'loading' as const }])),
    )
    void (async () => {
      const entries = await Promise.all(
        symbols.map(async (sym): Promise<[string, WatchlistShortHint]> => {
          try {
            const p = await previewTicker(sym)
            if (!p.valid || !p.short_term) return [sym, { status: 'unavailable' as const }]
            return [
              sym,
              {
                status: 'ok' as const,
                tone: p.short_term.tone,
                confidence: p.short_term.confidence,
                changePctDay:
                  typeof p.change_pct_day === 'number' && Number.isFinite(p.change_pct_day)
                    ? p.change_pct_day
                    : null,
              },
            ]
          } catch {
            return [sym, { status: 'unavailable' as const }]
          }
        }),
      )
      if (cancelled) return
      setWatchlistShortHints(Object.fromEntries(entries))
    })()
    return () => {
      cancelled = true
    }
  }, [watchlistSymbolsKey])

  const lookup = useCallback(
    async (raw: string) => {
      const sym = raw.trim().toUpperCase()
      if (!sym) {
        setErrorMsg('Enter a ticker symbol.')
        return
      }
      setErrorMsg(null)
      setLoadingSearch(true)
      setCompanyDescription(null)
      setReport(null)
      setPreviewConf(null)
      setSentPreview(null)

      try {
        const validated = await validateTicker(sym)
        if (!validated.valid) {
          setSelectedSymbol(null)
          setCompanyName(null)
          setCompanyDescription(null)
          setShortTone(null)
          setLongTone(null)
          setRiskPreview(null)
          setScaleHighlight(null)
          setSentPreview(null)
          setErrorMsg(`No ticker found for “${sym}”.`)
          setLoadingSearch(false)
          return
        }

        setSelectedSymbol(validated.symbol)
        setCompanyName(validated.name ?? null)

        const preview = await previewTicker(validated.symbol)
        if (!preview.valid || !preview.short_term || !preview.long_term) {
          setShortTone(null)
          setLongTone(null)
          setRiskPreview(null)
          setScaleHighlight(null)
          setSentPreview(null)
          setErrorMsg('Unable to load a preview for that symbol.')
          setLoadingSearch(false)
          return
        }

        setShortTone(preview.short_term.tone)
        setLongTone(preview.long_term.tone)
        setRiskPreview(preview.risk_level)
        setPreviewConf({
          short: preview.short_term.confidence,
          long: preview.long_term.confidence,
        })
        setScaleHighlight(preview.short_term.tone)
        setSentPreview({
          label: preview.sentiment_label,
          count: preview.sentiment_headlines_used,
          labelLong: preview.sentiment_label_long,
          countLong: preview.sentiment_headlines_long,
        })
        setCompanyName((n) => n ?? preview.name ?? null)
        setCompanyDescription(
          preview.description?.trim() ? preview.description.trim() : null,
        )

        setWatchlistShortHints((prev) => {
          const onList = watchlistItems.some((i) => i.symbol === validated.symbol)
          if (!onList || !preview.short_term) return prev
          return {
            ...prev,
            [validated.symbol]: {
              status: 'ok',
              tone: preview.short_term.tone,
              confidence: preview.short_term.confidence,
              changePctDay:
                typeof preview.change_pct_day === 'number' &&
                Number.isFinite(preview.change_pct_day)
                  ? preview.change_pct_day
                  : null,
            },
          }
        })
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Search failed.')
        setSelectedSymbol(null)
      } finally {
        setLoadingSearch(false)
      }
    },
    [watchlistItems],
  )

  const pickQuickSymbol = useCallback(
    async (sym: string) => {
      cancelQuickClose()
      setQuickOpen(false)
      setMainTab('ticker')
      setSymbolInput(sym)
      await lookup(sym)
    },
    [lookup, cancelQuickClose],
  )

  const onGenerateAnalysis = useCallback(async () => {
    if (!selectedSymbol) return
    setErrorMsg(null)
    setLoadingReport(true)
    try {
      const r = await generateReport(selectedSymbol, true)
      setReport(r)
      setScaleHighlight(r.short_term.tone)
      setRiskPreview(r.risk_level)
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : 'Could not generate analysis.',
      )
    } finally {
      setLoadingReport(false)
    }
  }, [selectedSymbol])

  return (
    <div className="min-h-svh bg-gradient-to-b from-sky-50/50 to-slate-50/30 dark:from-slate-950 dark:to-slate-950">
      <div className="mx-auto max-w-5xl px-4 py-10 pb-16 lg:px-6">
        <div className="min-w-0 space-y-8">
            <header className="border-b border-sky-200/90 pb-6 text-center dark:border-slate-800">
              <div className="mb-4 flex justify-end">
                <button
                  type="button"
                  className="rounded-lg border border-sky-300/90 bg-white/90 px-3 py-1.5 text-xs font-medium text-emerald-900 shadow-sm ring-1 ring-emerald-900/10 transition hover:bg-sky-50 dark:border-slate-600 dark:bg-slate-800/90 dark:text-cyan-100 dark:ring-slate-600/60 dark:hover:bg-slate-800"
                  onClick={() => setColorMode((m) => (m === 'dark' ? 'light' : 'dark'))}
                  aria-label={colorMode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                >
                  {colorMode === 'dark' ? 'Light mode' : 'Dark mode'}
                </button>
              </div>
              <p className="font-faculty text-sm uppercase tracking-[0.2em] text-emerald-700/95 dark:text-cyan-500/90">
                Tranquilytics
              </p>
              <div className="relative mx-auto mt-3 flex min-h-[5rem] w-full max-w-lg items-center justify-center">
                <ThinkingCloudBackdrop className="pointer-events-none absolute left-1/2 top-1/2 h-[9.5rem] w-[min(100%,26rem)] -translate-x-1/2 -translate-y-1/2" />
                <h1 className="font-faculty relative z-10 px-4 text-3xl font-normal leading-tight text-slate-900 drop-shadow-sm dark:text-white sm:text-4xl">
                  Stress-free insights
                </h1>
              </div>
              <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-slate-600 dark:text-slate-500">
                Use the search below, then open the full analysis when you want depth. Use the{' '}
                <span className="font-medium text-slate-700 dark:text-slate-400">Screener</span> tab for optional bulk
                index scans (slow).
              </p>
            </header>

            <form
              className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-end"
              onSubmit={(e) => {
                e.preventDefault()
                cancelQuickClose()
                setQuickOpen(false)
                void lookup(symbolInput)
              }}
              role="search"
            >
              <div className="relative flex-1 text-left">
                <label htmlFor="ticker-search" className="block">
                  <span className="text-xs text-slate-600 dark:text-slate-500">Ticker</span>
                  <input
                    id="ticker-search"
                    type="text"
                    autoCapitalize="characters"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="e.g. AAPL"
                    value={symbolInput}
                    onChange={(e) => setSymbolInput(e.target.value)}
                    onFocus={() => {
                      cancelQuickClose()
                      setQuickOpen(true)
                      void loadDailyLeaders()
                    }}
                    onBlur={() => scheduleQuickClose()}
                    className="mt-1 w-full rounded-lg border border-sky-300/90 bg-white px-4 py-2.5 text-slate-900 shadow-sm placeholder:text-slate-500 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-600 dark:focus:border-cyan-600 dark:focus:ring-cyan-600"
                  />
                </label>

                {quickOpen ? (
                  <div
                    className="absolute left-0 right-0 top-full z-50 -mt-px max-h-80 overflow-y-auto rounded-xl border border-sky-200 bg-white py-2 shadow-xl shadow-slate-900/10 ring-1 ring-sky-200/80 dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40 dark:ring-slate-600/60"
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={cancelQuickClose}
                  >
                    <p className="border-b border-sky-200 px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:border-slate-800 dark:text-slate-500">
                      {symbolInput.trim()
                        ? 'Tickers matching your query · curated list'
                        : "Today's top movers · curated large caps"}
                    </p>
                    <p className="px-3 pt-1 text-[11px] text-slate-600 dark:text-slate-600">
                      Symbol or company substring; Enter still checks any valid ticker.
                    </p>
                    {leadersLoading && dailyLeaders.length === 0 ? (
                      <p className="px-3 py-3 text-sm text-slate-600 dark:text-slate-500">Loading…</p>
                    ) : dailyLeaders.length === 0 ? (
                      <p className="px-3 py-3 text-sm text-slate-600 dark:text-slate-500">
                        Movers unavailable — type a symbol instead.
                      </p>
                    ) : suggestedLeaders.length === 0 ? (
                      <p className="px-3 py-3 text-sm text-slate-600 dark:text-slate-500">
                        No rows match in this list — press Enter or Look up for your ticker.
                      </p>
                    ) : (
                      <ul className="mt-1">
                        {suggestedLeaders.map((row) => (
                          <li key={row.symbol}>
                            <button
                              type="button"
                              className="flex w-full flex-wrap items-baseline gap-x-2 gap-y-0.5 px-3 py-2 text-left hover:bg-sky-100/90 dark:hover:bg-slate-800/80"
                              onClick={() => void pickQuickSymbol(row.symbol)}
                            >
                              <span className="font-semibold text-emerald-800 dark:text-cyan-300">
                                {row.symbol}
                              </span>
                              <span className="min-w-0 truncate text-[11px] text-slate-600 dark:text-slate-500">
                                {row.name ?? '—'}
                              </span>
                              <span
                                className={
                                  row.change_pct_day >= 0
                                    ? 'ml-auto shrink-0 text-[11px] font-medium tabular-nums text-emerald-400'
                                    : 'ml-auto shrink-0 text-[11px] font-medium tabular-nums text-rose-400'
                                }
                              >
                                {row.change_pct_day >= 0 ? '+' : ''}
                                {row.change_pct_day.toFixed(2)}% day
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </div>
              <button
                type="submit"
                disabled={loadingSearch}
                className="group font-faculty relative isolate overflow-hidden rounded-lg bg-emerald-600 px-6 py-2.5 font-medium text-white shadow-sm transition hover:bg-emerald-500 disabled:opacity-50 dark:bg-cyan-600 dark:hover:bg-cyan-500"
              >
                <span
                  className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100 motion-reduce:hidden"
                  aria-hidden
                >
                  <span className="absolute -left-6 top-1/2 h-14 w-24 -translate-y-1/2 rounded-full bg-white/20 blur-md" />
                  {LOOKUP_BUBBLE_SLOTS.map((slot, i) => (
                    <span
                      key={i}
                      className={`pointer-events-none absolute animate-lookup-rise rounded-full bg-emerald-100/60 dark:bg-cyan-100/50 ${slot.cls}`}
                      style={{
                        left: slot.left,
                        bottom: slot.bottom,
                        animationDelay: slot.delay,
                      }}
                    />
                  ))}
                </span>
                <span className="relative z-10">
                  {loadingSearch ? 'Looking up…' : 'Look up'}
                </span>
              </button>
            </form>

            <nav
              role="tablist"
              className="flex gap-1 rounded-xl border border-sky-200/90 bg-white/80 p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900/50"
              aria-label="Main sections"
            >
              <button
                type="button"
                role="tab"
                aria-selected={mainTab === 'ticker'}
                onClick={() => setMainTab('ticker')}
                className={`font-faculty min-w-0 flex-1 rounded-lg px-3 py-2 text-sm font-medium transition sm:flex-none sm:px-5 ${
                  mainTab === 'ticker'
                    ? 'bg-emerald-600 text-white shadow-sm dark:bg-cyan-600'
                    : 'text-slate-700 hover:bg-sky-100/80 dark:text-slate-300 dark:hover:bg-slate-800/80'
                }`}
              >
                Ticker
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mainTab === 'screener'}
                onClick={() => setMainTab('screener')}
                className={`font-faculty min-w-0 flex-1 rounded-lg px-3 py-2 text-sm font-medium transition sm:flex-none sm:px-5 ${
                  mainTab === 'screener'
                    ? 'bg-emerald-600 text-white shadow-sm dark:bg-cyan-600'
                    : 'text-slate-700 hover:bg-sky-100/80 dark:text-slate-300 dark:hover:bg-slate-800/80'
                }`}
              >
                Screener
              </button>
            </nav>

      {mainTab === 'ticker' ? (
      <>
      {errorMsg ? (
        <div
          className="mb-6 rounded-lg border border-rose-400/50 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:border-rose-500/40 dark:bg-rose-950/40 dark:text-rose-200"
          role="alert"
        >
          {errorMsg}
        </div>
      ) : null}

      {selectedSymbol && !loadingSearch && shortTone && longTone ? (
        <section className="mb-10 rounded-xl border border-sky-200/90 bg-white/90 p-6 shadow-lg shadow-slate-900/10 dark:border-slate-800 dark:bg-slate-900/60 dark:shadow-black/20">
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="font-faculty text-xl font-semibold text-slate-900 dark:text-white">
              {selectedSymbol}
            </h2>
            {companyName ? (
              <span className="text-sm text-slate-600 dark:text-slate-500">{companyName}</span>
            ) : null}
          </div>
          {companyDescription ? (
            <p className="mt-3 text-sm leading-relaxed text-slate-700 dark:text-slate-400">{companyDescription}</p>
          ) : (
            <p className="mt-3 text-xs italic leading-relaxed text-slate-600 dark:text-slate-600">
              Company description was not returned by the data provider for this symbol.
            </p>
          )}

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-slate-600 dark:text-slate-500">Short term</p>
              <div className="mt-1 flex items-center gap-2">
                <span className={toneBadgeClass(shortTone)}>{shortTone}</span>
                {previewConf ? (
                  <ConfidenceBar
                    value={previewConf.short}
                    onExplain={() =>
                      setExplanationModal({
                        title: 'Short-term confidence',
                        sections: getConfidenceExplanationSections(),
                      })
                    }
                    explainAriaLabel="Explain short-term confidence"
                  />
                ) : null}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-600 dark:text-slate-500">Long term</p>
              <div className="mt-1 flex items-center gap-2">
                <span className={toneBadgeClass(longTone)}>{longTone}</span>
                {previewConf ? (
                  <ConfidenceBar
                    value={previewConf.long}
                    onExplain={() =>
                      setExplanationModal({
                        title: 'Long-term confidence',
                        sections: getConfidenceExplanationSections(),
                      })
                    }
                    explainAriaLabel="Explain long-term confidence"
                  />
                ) : null}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-600 dark:text-slate-500">Risk (volatility view)</p>
              <p className="mt-2 text-lg font-medium text-slate-900 dark:text-white">
                {riskPreview ?? '—'}
              </p>
            </div>
          </div>

          {sentPreview ? (
            <div className="mt-4 space-y-1.5 text-sm text-slate-700 dark:text-slate-400">
              <p>
                <span className="text-slate-600 dark:text-slate-500">Recent headlines: </span>
                <span className="font-medium text-slate-900 dark:text-slate-200">{sentPreview.label}</span>
                {sentPreview.count > 0
                  ? ` — ${sentPreview.count} timely headline(s) scored for the short-horizon blend`
                  : ' — none in the recent window; short headline layer neutral'}
                .
              </p>
              <p>
                <span className="text-slate-600 dark:text-slate-500">Narrative headline: </span>
                <span className="font-medium text-slate-900 dark:text-slate-200">{sentPreview.labelLong}</span>
                {sentPreview.countLong > 0
                  ? ` — ${sentPreview.countLong} title(s) in the long-horizon headline layer`
                  : ' — no narrative text; long headline layer neutral'}
                .
              </p>
            </div>
          ) : null}

          <div className="mt-6 flex flex-col gap-2 border-t border-sky-200/80 pt-6 dark:border-slate-700/80">
            {watchlistItems.some((i) => i.symbol === selectedSymbol) ? (
              <p className="text-xs text-slate-600 dark:text-slate-500">
                <span className="font-medium text-slate-800 dark:text-slate-400">{selectedSymbol}</span> is on your watchlist.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => void addLookupToWatchlist()}
                  disabled={
                    watchlistBusy ||
                    watchlistLoading ||
                    watchlistItems.length >= watchlistMax
                  }
                  className="font-faculty w-full rounded-lg border border-sky-300/90 bg-white px-4 py-2.5 text-sm font-medium text-slate-800 shadow-sm transition hover:bg-sky-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:bg-slate-800 sm:w-auto"
                >
                  {watchlistBusy ? 'Saving…' : 'Add to watchlist'}
                </button>
                {watchlistAddErr ? (
                  <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
                    {watchlistAddErr}
                  </p>
                ) : (
                  <p className="text-xs text-slate-600 dark:text-slate-600">
                    Only tickers you have looked up can be saved (avoids invalid symbols).
                  </p>
                )}
              </>
            )}
          </div>

          <button
            type="button"
            onClick={() => void onGenerateAnalysis()}
            disabled={loadingReport || !selectedSymbol}
            className="font-faculty mt-6 w-full rounded-lg border border-emerald-800/40 bg-emerald-50 px-4 py-3 font-medium text-emerald-950 transition hover:bg-emerald-100/90 disabled:opacity-50 dark:border-cyan-700/80 dark:bg-slate-800/80 dark:text-cyan-100 dark:hover:bg-slate-800 sm:w-auto"
          >
            {loadingReport ? 'Generating analysis…' : 'Generate Analysis'}
          </button>
        </section>
      ) : null}

      {report ? (
        <section className="rounded-xl border border-sky-200/90 bg-white/90 p-6 dark:border-slate-800 dark:bg-slate-900/40">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Analysis</h2>
          <p className="mt-2 rounded-md border border-amber-400/40 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-100/95">
            {report.disclaimer}
          </p>
          <p className="mt-4 text-slate-800 dark:text-slate-300">{report.summary}</p>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-500">
            Headline layers: recent{' '}
            <span className="text-slate-800 dark:text-slate-300">{report.sentiment_label}</span>
            {report.sentiment_headlines_used > 0
              ? ` (${report.sentiment_headlines_used} scored)`
              : ' (neutral)'}
            {' · '}long narrative{' '}
            <span className="text-slate-800 dark:text-slate-300">{report.sentiment_label_long}</span>
            {report.sentiment_headlines_long > 0
              ? ` (${report.sentiment_headlines_long} scored)`
              : ' (neutral)'}
          </p>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div className="rounded-lg border border-sky-200/90 bg-sky-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-950/40">
              <h3 className="text-sm font-medium text-slate-800 dark:text-slate-300">Short-term</h3>
              <p className="mt-2">
                <span className={toneBadgeClass(report.short_term.tone)}>
                  {report.short_term.tone}
                </span>
                <span className="ml-2 text-sm text-slate-600 dark:text-slate-500">
                  ~{report.short_term.window_trading_days} sessions
                </span>
              </p>
              <div className="mt-3 rounded-md border border-sky-200/80 bg-white/90 p-3 text-xs text-slate-700 dark:border-slate-700/70 dark:bg-slate-950/50 dark:text-slate-400">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-slate-800 dark:text-slate-300">
                    Technical + sentiment synthesizer
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setExplanationModal({
                        title: 'Short-term synthesizer',
                        sections: getSynthesizerExplanationSections('short', {
                          technical: report.short_term.synthesis.technical_weight,
                          sentiment: report.short_term.synthesis.sentiment_weight,
                        }),
                        extraNote: formatSynthesizerRuntimeLines(report.short_term.synthesis),
                      })
                    }
                    className="shrink-0 text-[11px] font-medium text-emerald-800 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-900 dark:text-cyan-400/90 dark:hover:text-cyan-300"
                  >
                    How it works
                  </button>
                </div>
                <ul className="mt-2 list-inside list-disc space-y-0.5 marker:text-slate-500 dark:marker:text-slate-600">
                  <li>
                    Technical model P(up) ≈{' '}
                    {(report.short_term.synthesis.technical_probability * 100).toFixed(1)}%
                  </li>
                  <li>
                    Headline layer P(up) ≈{' '}
                    {(report.short_term.synthesis.sentiment_probability * 100).toFixed(1)}%
                  </li>
                  <li>
                    Blended P(up) ≈{' '}
                    {(report.short_term.synthesis.blended_probability * 100).toFixed(1)}%
                    {' '}
                    <span className="text-slate-600 dark:text-slate-600">
                      (weights {(report.short_term.synthesis.technical_weight * 100).toFixed(0)}%
                      technical / {(report.short_term.synthesis.sentiment_weight * 100).toFixed(0)}%
                      headlines)
                    </span>
                  </li>
                </ul>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-700 dark:text-slate-400">
                {report.short_term.reasoning}
              </p>
            </div>
            <div className="rounded-lg border border-sky-200/90 bg-sky-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-950/40">
              <h3 className="text-sm font-medium text-slate-800 dark:text-slate-300">Long-term</h3>
              <p className="mt-2">
                <span className={toneBadgeClass(report.long_term.tone)}>
                  {report.long_term.tone}
                </span>
                <span className="ml-2 text-sm text-slate-600 dark:text-slate-500">
                  ~{report.long_term.window_trading_days} sessions
                </span>
              </p>
              <div className="mt-3 rounded-md border border-sky-200/80 bg-white/90 p-3 text-xs text-slate-700 dark:border-slate-700/70 dark:bg-slate-950/50 dark:text-slate-400">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-slate-800 dark:text-slate-300">
                    Technical + sentiment synthesizer
                  </p>
                  <button
                    type="button"
                    onClick={() =>
                      setExplanationModal({
                        title: 'Long-term synthesizer',
                        sections: getSynthesizerExplanationSections('long', {
                          technical: report.long_term.synthesis.technical_weight,
                          sentiment: report.long_term.synthesis.sentiment_weight,
                        }),
                        extraNote: formatSynthesizerRuntimeLines(report.long_term.synthesis),
                      })
                    }
                    className="shrink-0 text-[11px] font-medium text-emerald-800 underline decoration-emerald-500/40 underline-offset-2 hover:text-emerald-900 dark:text-cyan-400/90 dark:hover:text-cyan-300"
                  >
                    How it works
                  </button>
                </div>
                <ul className="mt-2 list-inside list-disc space-y-0.5 marker:text-slate-500 dark:marker:text-slate-600">
                  <li>
                    Technical model P(up) ≈{' '}
                    {(report.long_term.synthesis.technical_probability * 100).toFixed(1)}%
                  </li>
                  <li>
                    Headline layer P(up) ≈{' '}
                    {(report.long_term.synthesis.sentiment_probability * 100).toFixed(1)}%
                  </li>
                  <li>
                    Blended P(up) ≈{' '}
                    {(report.long_term.synthesis.blended_probability * 100).toFixed(1)}%
                    {' '}
                    <span className="text-slate-600 dark:text-slate-600">
                      (weights {(report.long_term.synthesis.technical_weight * 100).toFixed(0)}%
                      technical / {(report.long_term.synthesis.sentiment_weight * 100).toFixed(0)}%
                      headlines)
                    </span>
                  </li>
                </ul>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-700 dark:text-slate-400">
                {report.long_term.reasoning}
              </p>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-500">
              Overall risk level
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{report.risk_level}</p>
          </div>

          <details className="mt-8">
            <summary className="cursor-pointer text-sm font-medium text-emerald-800 dark:text-cyan-400/95">
              Citations & data sources
            </summary>
            <ul className="mt-3 max-w-full space-y-2 text-sm text-slate-700 dark:text-slate-400">
              {report.citations.map((c, i) => (
                <li key={`${c.kind}-${i}`} className="min-w-0 max-w-full [overflow-wrap:anywhere] break-words">
                  <span className="text-slate-600 dark:text-slate-500">[{c.kind}]</span>{' '}
                  {citationSourceWithLinks(c.source)}
                  {c.as_of ? (
                    <span className="text-slate-600 dark:text-slate-600">
                      {' '}
                      — as of {new Date(c.as_of).toLocaleString()}
                    </span>
                  ) : null}
                </li>
              ))}
              {report.citations.length === 0 ? (
                <li>No citations returned.</li>
              ) : null}
            </ul>
          </details>
        </section>
      ) : null}

        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-4">
          <div className="shrink-0 lg:w-[11.5rem]" aria-label="How to read tones">
            <div className="lg:hidden">
              <OutlookScaleLegend scaleHighlight={scaleHighlight} variant="strip" />
            </div>
            <div className="hidden lg:block">
              <OutlookScaleLegend scaleHighlight={scaleHighlight} variant="rail" />
            </div>
          </div>
          <div className="min-w-0 flex-1">
        <div className={SECTION_CARD_CLASS} aria-label="Saved watchlist">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
              Your watchlist
            </p>
            <p className="text-[11px] tabular-nums text-slate-500 dark:text-slate-600">
              {watchlistLoading ? '…' : `${watchlistItems.length} / ${watchlistMax}`} symbols
            </p>
          </div>
          {watchlistErr ? (
            <p className="mt-2 text-xs text-rose-600 dark:text-rose-400" role="alert">
              {watchlistErr}
            </p>
          ) : null}
          {watchlistLoading && watchlistItems.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-500">Loading watchlist…</p>
          ) : watchlistItems.length === 0 ? (
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-500">
              No symbols yet — look up a ticker, then add it from the preview (up to {watchlistMax}).
            </p>
          ) : (
            <ul className="mt-3 divide-y divide-sky-200/80 dark:divide-slate-800/80">
              {watchlistItems.map((row) => {
                const hint = watchlistShortHints[row.symbol]
                return (
                  <li
                    key={row.symbol}
                    className="flex items-center gap-2 gap-x-3 py-2 first:pt-0 last:pb-0"
                  >
                    <div className="flex shrink-0 flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-x-2">
                      <span className="font-semibold text-emerald-800 dark:text-cyan-300">
                        {row.symbol}
                      </span>
                      {hint?.status === 'ok' && hint.changePctDay != null ? (
                        <span
                          className={
                            hint.changePctDay >= 0
                              ? 'text-[11px] font-medium tabular-nums text-emerald-600 dark:text-emerald-400'
                              : 'text-[11px] font-medium tabular-nums text-rose-600 dark:text-rose-400'
                          }
                          title="Latest session vs prior close (approx.)"
                        >
                          {hint.changePctDay >= 0 ? '+' : ''}
                          {hint.changePctDay.toFixed(2)}% day
                        </span>
                      ) : hint?.status === 'ok' ? (
                        <span
                          className="text-[11px] text-slate-500 dark:text-slate-600"
                          title="Daily % change unavailable"
                        >
                          —
                        </span>
                      ) : null}
                    </div>
                    <div
                      className="min-w-0 flex-1 text-left"
                      aria-label="Short-term model outlook"
                    >
                      {!hint || hint.status === 'loading' ? (
                        <span
                          className="text-[11px] text-slate-500 dark:text-slate-600"
                          title="Loading short-term outlook"
                        >
                          …
                        </span>
                      ) : hint.status === 'unavailable' ? (
                        <span
                          className="text-[11px] text-slate-500 dark:text-slate-600"
                          title="Preview unavailable"
                        >
                          —
                        </span>
                      ) : (
                        <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                          <span className={toneBadgeClass(hint.tone)}>{hint.tone}</span>
                          <span className="text-[11px] tabular-nums text-slate-600 dark:text-slate-500">
                            ~{Math.round(hint.confidence * 100)}% conf.
                          </span>
                        </span>
                      )}
                    </div>
                    <div className="ml-auto flex shrink-0 flex-wrap items-center gap-2">
                      <button
                        type="button"
                        disabled={watchlistBusy}
                        onClick={() => {
                          setSymbolInput(row.symbol)
                          void lookup(row.symbol)
                        }}
                        className="rounded-md border border-sky-300/90 px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:bg-sky-100/80 disabled:opacity-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-800/80"
                      >
                        Look up
                      </button>
                      <button
                        type="button"
                        disabled={watchlistBusy}
                        onClick={() => void removeFromWatchlist(row.symbol)}
                        className="rounded-md px-2.5 py-1 text-xs font-medium text-rose-700 underline decoration-rose-400/50 underline-offset-2 hover:text-rose-800 disabled:opacity-50 dark:text-rose-400 dark:hover:text-rose-300"
                      >
                        Remove
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
          </div>
        </div>
      </>
      ) : null}

            {mainTab === 'screener' ? (
            <>
            <OutlookScaleLegend scaleHighlight={scaleHighlight} variant="strip" />
            <div className={SECTION_CARD_CLASS} aria-label="S and P 500 model screens">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
            S&amp;P 500 model screens
          </p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-600">
            Optional bulk scan — same preview stack as a single lookup; can take many minutes. Results share one list; last run wins.
          </p>

          <p className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
            Short-term screen
          </p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-600">
            Safer Buy, or Buy when interpreted risk is Low — evaluated on the short-term horizon.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={picksLoading}
              onClick={() => void loadDailyPicksScreen(false, 'short')}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white ring-1 ring-emerald-900/20 transition hover:bg-emerald-600 disabled:opacity-50 dark:bg-slate-800 dark:text-cyan-100 dark:ring-slate-600/80 dark:hover:bg-slate-800/90"
            >
              {picksLoading && picksFocus === 'short' ? 'Scanning…' : 'Run short-term screen'}
            </button>
            <button
              type="button"
              disabled={picksLoading}
              onClick={() => void loadDailyPicksScreen(true, 'short')}
              className="rounded-lg border border-sky-300/90 bg-transparent px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-sky-100/80 disabled:opacity-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-800/80"
            >
              Re-scan short (ignore cache)
            </button>
            {picksExpanded ? (
              <button
                type="button"
                onClick={() => setPicksExpanded(false)}
                className="text-xs text-slate-600 underline decoration-slate-400 underline-offset-2 hover:text-slate-800 dark:text-slate-500 dark:decoration-slate-600 dark:hover:text-slate-400"
              >
                Hide results
              </button>
            ) : null}
          </div>

          <p className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
            Long-term buy screen
          </p>
          <p className="mt-1 text-xs text-slate-600 dark:text-slate-600">
            Same inclusion rules applied to the long-term horizon (still uses one shared risk bucket from
            the preview).
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={picksLoading}
              onClick={() => void loadDailyPicksScreen(false, 'long')}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white ring-1 ring-emerald-900/20 transition hover:bg-emerald-600 disabled:opacity-50 dark:bg-slate-800 dark:text-cyan-100 dark:ring-slate-600/80 dark:hover:bg-slate-800/90"
            >
              {picksLoading && picksFocus === 'long' ? 'Scanning…' : 'Run long-term screen'}
            </button>
            <button
              type="button"
              disabled={picksLoading}
              onClick={() => void loadDailyPicksScreen(true, 'long')}
              className="rounded-lg border border-sky-300/90 bg-transparent px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-sky-100/80 disabled:opacity-50 dark:border-slate-600 dark:text-slate-400 dark:hover:bg-slate-800/80"
            >
              Re-scan long (ignore cache)
            </button>
          </div>
          {picksExpanded ? (
            <>
              {picksNote ? (
                <p className="mt-3 text-xs text-slate-600 dark:text-slate-600">{picksNote}</p>
              ) : null}
              {picksLoading ? (
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <p className="text-sm text-slate-600 dark:text-slate-500">
                    Working through the index… (can take many minutes for S&amp;P 500)
                  </p>
                  <button
                    type="button"
                    onClick={() => cancelDailyPicksScreen()}
                    className="rounded-md border border-sky-300/90 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-sky-100/80 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800/80"
                  >
                    Cancel scan
                  </button>
                </div>
              ) : dailyPicks.length === 0 ? (
                picksNote != null &&
                (picksNote.startsWith('Scan cancelled') ||
                  picksNote.startsWith('This request timed out')) ? null : (
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-500">
                  {picksNote === null
                    ? 'Request failed. Is the API running?'
                    : picksFocus === 'long'
                      ? 'No tickers passed the long-term screen (Safer Buy, or Buy with Low volatility).'
                      : 'No tickers passed the short-term screen (Safer Buy, or Buy with Low volatility).'}
                </p>
                )
              ) : (
                <ul className="mt-3 max-w-full space-y-1">
                  {dailyPicks.map((row) => (
                    <li
                      key={row.symbol}
                      className="min-w-0 max-w-full rounded-lg border border-sky-200/90 bg-sky-50/80 dark:border-slate-800/80 dark:bg-slate-950/30"
                    >
                      <button
                        type="button"
                        className="flex w-full flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2 text-left hover:bg-sky-100/90 dark:hover:bg-slate-800/50"
                        onClick={() => void pickQuickSymbol(row.symbol)}
                      >
                        <span className="font-semibold text-emerald-800 dark:text-cyan-300">{row.symbol}</span>
                        {row.name ? (
                          <span className="min-w-0 truncate text-xs text-slate-600 dark:text-slate-500">{row.name}</span>
                        ) : null}
                        <span className={toneBadgeClass(row.screen_tone)}>{row.screen_tone}</span>
                        <span className="text-[11px] text-slate-600 dark:text-slate-500">
                          Risk {row.risk_level} ·{' '}
                          {row.screen_horizon === 'long' ? 'Long' : 'Short'}
                          -term conf. ~{Math.round(row.confidence * 100)}%
                        </span>
                      </button>
                      <p className="px-3 pb-2 text-[11px] leading-snug text-slate-600 dark:text-slate-600">
                        {row.pick_reason}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : null}

            </div>
            </>
      ) : null}
          </div>
      </div>
      <ExplanationModal
        open={explanationModal !== null}
        title={explanationModal?.title ?? ''}
        sections={explanationModal?.sections ?? []}
        extraNote={explanationModal?.extraNote}
        onClose={() => setExplanationModal(null)}
      />
    </div>
  )
}

