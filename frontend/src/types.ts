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

export type PreviewResponse = {
  valid: boolean
  symbol: string
  name?: string | null
  exchange?: string | null
  currency?: string | null
  risk_level: string
  short_term: HorizonPreview | null
  long_term: HorizonPreview | null
}

export type Citation = {
  kind: string
  source: string
  as_of?: string | null
}

export type HorizonAdvice = {
  horizon: string
  window_trading_days: number
  tone: string
  confidence: number
  reasoning: string
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
  short_term: HorizonAdvice
  long_term: HorizonAdvice
  summary: string
  disclaimer: string
  citations: Citation[]
}
