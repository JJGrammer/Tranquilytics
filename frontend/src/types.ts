export type Tone =
  | 'Safer Buy'
  | 'Buy'
  | 'Neutral'
  | 'Sell'
  | 'Sell Soon'

export type TickerValidateResponse = {
  valid: boolean
  symbol: string
  name?: string | null
  exchange?: string | null
  currency?: string | null
}

export type HorizonPreview = {
  tone: string
  confidence: number
}

export type DailyLeaderRow = {
  symbol: string
  change_pct_day: number
  name?: string | null
  description?: string | null
}

export type DailyLeadersResponse = {
  leaders: DailyLeaderRow[]
  as_of?: string | null
  note: string
}

export type PreviewResponse = {
  valid: boolean
  symbol: string
  name?: string | null
  exchange?: string | null
  currency?: string | null
  risk_level: string
  sentiment_label: string
  sentiment_headlines_used: number
  short_term: HorizonPreview | null
  long_term: HorizonPreview | null
}

export type Citation = {
  kind: string
  source: string
  as_of?: string | null
}

export type HorizonSynthesis = {
  technical_probability: number
  sentiment_probability: number
  blended_probability: number
  technical_weight: number
  sentiment_weight: number
}

export type HorizonAdvice = {
  horizon: string
  window_trading_days: number
  tone: string
  confidence: number
  reasoning: string
  synthesis: HorizonSynthesis
  expected_return?: number | null
  volatility?: number | null
}

export type ReportResponse = {
  symbol: string
  name?: string | null
  currency?: string | null
  exchange?: string | null
  generated_at: string
  as_of?: string | null
  risk_level: string
  sentiment_label: string
  sentiment_headlines_used: number
  short_term: HorizonAdvice
  long_term: HorizonAdvice
  summary: string
  disclaimer: string
  citations: Citation[]
}
