import { useCallback, useEffect, useRef, useState } from 'react'
import type { DailyLeaderRow } from './types'
import {
  fetchDailyLeaders,
  generateReport,
  previewTicker,
  validateTicker,
} from './api'

const TONES_ORDER = [
  'Safer Buy',
  'Buy',
  'Neutral',
  'Sell',
  'Sell Soon',
] as const

function toneBadgeClass(tone: string): string {
  const base = 'rounded-full px-2.5 py-0.5 text-xs font-medium ring-1'
  switch (tone) {
    case 'Safer Buy':
      return `${base} bg-emerald-500/15 text-emerald-200 ring-emerald-500/40`
    case 'Buy':
      return `${base} bg-green-500/15 text-green-200 ring-green-500/35`
    case 'Neutral':
      return `${base} bg-slate-500/20 text-slate-200 ring-slate-400/35`
    case 'Sell':
      return `${base} bg-amber-500/15 text-amber-200 ring-amber-400/35`
    case 'Sell Soon':
      return `${base} bg-rose-500/15 text-rose-200 ring-rose-400/35`
    default:
      return `${base} bg-slate-600/25 text-slate-200 ring-slate-400/35`
  }
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div
      className="h-1.5 flex-1 max-w-[120px] overflow-hidden rounded-full bg-slate-800"
      title={`${pct}%`}
    >
      <div
        className="h-full rounded-full bg-cyan-500/70"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export default function App() {
  const [symbolInput, setSymbolInput] = useState('')
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [companyName, setCompanyName] = useState<string | null>(null)
  const [scaleHighlight, setScaleHighlight] = useState<string | null>(null)
  const [shortTone, setShortTone] = useState<string | null>(null)
  const [longTone, setLongTone] = useState<string | null>(null)
  const [riskPreview, setRiskPreview] = useState<string | null>(null)
  const [sentPreview, setSentPreview] = useState<{
    label: string
    count: number
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

  const [quickOpen, setQuickOpen] = useState(false)
  const [leadersLoading, setLeadersLoading] = useState(false)
  const [dailyLeaders, setDailyLeaders] = useState<DailyLeaderRow[]>([])
  const quickCloseTimer = useRef<number | null>(null)

  const cancelQuickClose = useCallback(() => {
    if (quickCloseTimer.current != null) {
      window.clearTimeout(quickCloseTimer.current)
      quickCloseTimer.current = null
    }
  }, [])

  useEffect(() => () => cancelQuickClose(), [cancelQuickClose])

  const scheduleQuickClose = useCallback(() => {
    cancelQuickClose()
    quickCloseTimer.current = window.setTimeout(() => setQuickOpen(false), 150)
  }, [cancelQuickClose])

  const loadDailyLeaders = useCallback(async () => {
    setLeadersLoading(true)
    try {
      const res = await fetchDailyLeaders(5)
      setDailyLeaders(res.leaders ?? [])
    } catch {
      setDailyLeaders([])
    } finally {
      setLeadersLoading(false)
    }
  }, [])

  const lookup = useCallback(
    async (raw: string) => {
      const sym = raw.trim().toUpperCase()
      if (!sym) {
        setErrorMsg('Enter a ticker symbol.')
        return
      }
      setErrorMsg(null)
      setLoadingSearch(true)
      setReport(null)
      setPreviewConf(null)
      setSentPreview(null)

      try {
        const validated = await validateTicker(sym)
        if (!validated.valid) {
          setSelectedSymbol(null)
          setCompanyName(null)
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
        })
        setCompanyName((n) => n ?? preview.name ?? null)
      } catch (err) {
        setErrorMsg(err instanceof Error ? err.message : 'Search failed.')
        setSelectedSymbol(null)
      } finally {
        setLoadingSearch(false)
      }
    },
    [],
  )

  const pickQuickSymbol = useCallback(
    async (sym: string) => {
      cancelQuickClose()
      setQuickOpen(false)
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
    <div className="mx-auto min-h-svh max-w-3xl px-4 py-10">
      <header className="mb-10 border-b border-slate-800 pb-8">
        <p className="text-sm uppercase tracking-[0.2em] text-cyan-500/90">
          Tranquilytics
        </p>
        <h1 className="mt-2 text-3xl font-semibold text-white sm:text-4xl">
          Stress-free insights
        </h1>
        <p className="mt-2 max-w-xl text-sm text-slate-400">
          Signals are modeled from recent price patterns—not financial advice, use at your own discretion.
        </p>

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
              <span className="text-xs text-slate-500">Ticker</span>
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
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-white placeholder:text-slate-600 focus:border-cyan-600 focus:outline-none focus:ring-1 focus:ring-cyan-600"
              />
            </label>

            {quickOpen ? (
              <div
                className="absolute left-0 right-0 top-full z-50 -mt-px max-h-80 overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 py-2 shadow-xl shadow-black/40 ring-1 ring-slate-600/60"
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={cancelQuickClose}
              >
                <p className="border-b border-slate-800 px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Today&apos;s top movers · curated large caps
                </p>
                {leadersLoading && dailyLeaders.length === 0 ? (
                  <p className="px-3 py-3 text-sm text-slate-500">Loading…</p>
                ) : dailyLeaders.length === 0 ? (
                  <p className="px-3 py-3 text-sm text-slate-500">
                    Movers unavailable — type a symbol instead.
                  </p>
                ) : (
                  <ul className="mt-1">
                    {dailyLeaders.map((row) => (
                      <li key={row.symbol}>
                        <button
                          type="button"
                          className="flex w-full flex-col gap-0.5 px-3 py-2 text-left hover:bg-slate-800/80"
                          onClick={() => void pickQuickSymbol(row.symbol)}
                        >
                          <div className="flex flex-wrap items-baseline gap-2">
                            <span className="font-semibold text-cyan-300">
                              {row.symbol}
                            </span>
                            <span className="text-[11px] text-slate-500">
                              {row.name ?? '—'} ·{' '}
                              <span
                                className={
                                  row.change_pct_day >= 0
                                    ? 'text-emerald-400'
                                    : 'text-rose-400'
                                }
                              >
                                {row.change_pct_day >= 0 ? '+' : ''}
                                {row.change_pct_day.toFixed(2)}% day
                              </span>
                            </span>
                          </div>
                          {row.description ? (
                            <p className="line-clamp-2 text-xs text-slate-500">
                              {row.description}
                            </p>
                          ) : (
                            <p className="text-xs text-slate-600 italic">
                              No company summary from data provider right now.
                            </p>
                          )}
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
            className="rounded-lg bg-cyan-600 px-6 py-2.5 font-medium text-white transition hover:bg-cyan-500 disabled:opacity-50"
          >
            {loadingSearch ? 'Looking up…' : 'Look up'}
          </button>
        </form>

        <div
          className="mt-5 rounded-xl border border-slate-800/80 bg-slate-900/40 px-4 py-3"
          aria-label="Outlook scale legend"
        >
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Outlook scale
            </span>
            <div className="flex flex-wrap gap-2">
              {TONES_ORDER.map((t) => (
                <span
                  key={t}
                  className={`${toneBadgeClass(t)} transition ${
                    scaleHighlight === t
                      ? 'ring-2 ring-cyan-400 ring-offset-2 ring-offset-slate-900'
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
          </div>
          <p className="mt-2 border-t border-slate-800/60 pt-2 text-xs text-slate-600">
            These labels describe modeled tilt—not instructions. After a successful lookup, the{' '}
            <span className="text-slate-500">cyan ring</span> marks{' '}
            <span className="text-slate-400">short-term</span> tone (long-term can differ).
          </p>
        </div>
      </header>

      {errorMsg ? (
        <div
          className="mb-6 rounded-lg border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200"
          role="alert"
        >
          {errorMsg}
        </div>
      ) : null}

      {selectedSymbol && !loadingSearch && shortTone && longTone ? (
        <section className="mb-10 rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg shadow-black/20">
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-xl font-semibold text-white">{selectedSymbol}</h2>
            {companyName ? (
              <span className="text-sm text-slate-500">{companyName}</span>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs text-slate-500">Short term</p>
              <div className="mt-1 flex items-center gap-2">
                <span className={toneBadgeClass(shortTone)}>{shortTone}</span>
                {previewConf ? (
                  <ConfidenceBar value={previewConf.short} />
                ) : null}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-500">Long term</p>
              <div className="mt-1 flex items-center gap-2">
                <span className={toneBadgeClass(longTone)}>{longTone}</span>
                {previewConf ? (
                  <ConfidenceBar value={previewConf.long} />
                ) : null}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-500">Risk (volatility view)</p>
              <p className="mt-2 text-lg font-medium text-white">
                {riskPreview ?? '—'}
              </p>
            </div>
          </div>

          {sentPreview ? (
            <p className="mt-4 text-sm text-slate-400">
              <span className="text-slate-500">Headline sentiment (preview): </span>
              <span className="font-medium text-slate-200">{sentPreview.label}</span>
              {sentPreview.count > 0
                ? ` — ${sentPreview.count} headline(s) scored and blended into tones with technical signals`
                : ' — no headlines returned; blended as neutral headline layer'}
              .
            </p>
          ) : null}

          <button
            type="button"
            onClick={() => void onGenerateAnalysis()}
            disabled={loadingReport || !selectedSymbol}
            className="mt-6 w-full rounded-lg border border-cyan-700/80 bg-slate-800/80 px-4 py-3 font-medium text-cyan-100 transition hover:bg-slate-800 disabled:opacity-50 sm:w-auto"
          >
            {loadingReport ? 'Generating analysis…' : 'Generate Analysis'}
          </button>
        </section>
      ) : null}

      {report ? (
        <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-lg font-semibold text-white">Analysis</h2>
          <p className="mt-2 rounded-md border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-sm text-amber-100/95">
            {report.disclaimer}
          </p>
          <p className="mt-4 text-slate-300">{report.summary}</p>
          <p className="mt-3 text-sm text-slate-500">
            Aggregate headline tilt:{' '}
            <span className="text-slate-300">{report.sentiment_label}</span>
            {' · '}
            {report.sentiment_headlines_used > 0
              ? `${report.sentiment_headlines_used} headline(s) in blend`
              : 'no headline text (neutral in blend)'}
          </p>

          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-700/80 bg-slate-950/40 p-4">
              <h3 className="text-sm font-medium text-slate-300">Short-term</h3>
              <p className="mt-2">
                <span className={toneBadgeClass(report.short_term.tone)}>
                  {report.short_term.tone}
                </span>
                <span className="ml-2 text-sm text-slate-500">
                  ~{report.short_term.window_trading_days} sessions
                </span>
              </p>
              <div className="mt-3 rounded-md border border-slate-700/70 bg-slate-950/50 p-3 text-xs text-slate-400">
                <p className="font-medium text-slate-300">Technical + sentiment synthesizer</p>
                <ul className="mt-2 list-inside list-disc space-y-0.5 marker:text-slate-600">
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
                    <span className="text-slate-600">
                      (weights {(report.short_term.synthesis.technical_weight * 100).toFixed(0)}%
                      technical / {(report.short_term.synthesis.sentiment_weight * 100).toFixed(0)}%
                      headlines)
                    </span>
                  </li>
                </ul>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                {report.short_term.reasoning}
              </p>
            </div>
            <div className="rounded-lg border border-slate-700/80 bg-slate-950/40 p-4">
              <h3 className="text-sm font-medium text-slate-300">Long-term</h3>
              <p className="mt-2">
                <span className={toneBadgeClass(report.long_term.tone)}>
                  {report.long_term.tone}
                </span>
                <span className="ml-2 text-sm text-slate-500">
                  ~{report.long_term.window_trading_days} sessions
                </span>
              </p>
              <div className="mt-3 rounded-md border border-slate-700/70 bg-slate-950/50 p-3 text-xs text-slate-400">
                <p className="font-medium text-slate-300">Technical + sentiment synthesizer</p>
                <ul className="mt-2 list-inside list-disc space-y-0.5 marker:text-slate-600">
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
                    <span className="text-slate-600">
                      (weights {(report.long_term.synthesis.technical_weight * 100).toFixed(0)}%
                      technical / {(report.long_term.synthesis.sentiment_weight * 100).toFixed(0)}%
                      headlines)
                    </span>
                  </li>
                </ul>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                {report.long_term.reasoning}
              </p>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-xs uppercase tracking-wider text-slate-500">
              Overall risk level
            </p>
            <p className="mt-1 text-lg font-semibold text-white">{report.risk_level}</p>
          </div>

          <details className="mt-8">
            <summary className="cursor-pointer text-sm font-medium text-cyan-400/95">
              Citations & data sources
            </summary>
            <ul className="mt-3 space-y-2 text-sm text-slate-400">
              {report.citations.map((c, i) => (
                <li key={`${c.kind}-${i}`}>
                  <span className="text-slate-500">[{c.kind}]</span> {c.source}
                  {c.as_of ? (
                    <span className="text-slate-600">
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
    </div>
  )
}
