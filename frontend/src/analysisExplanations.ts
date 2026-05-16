/**
 * Copy for explanation modals: formulas aligned with `advice_policy.py` and `synthesizer.py`
 * (keep both sides in sync when thresholds change).
 */

export type ExplanationSection = {
  heading: string
  /** Plain text; embed `\n` for breaks (shown with whitespace-pre-wrap). */
  content: string
}

/** Fixed weights from backend/app/services/synthesizer.py */
export const SYNTH_WEIGHTS = {
  short: { technical: 0.56, sentiment: 0.44 },
  long: { technical: 0.7, sentiment: 0.3 },
} as const

export function getConfidenceExplanationSections(): ExplanationSection[] {
  return [
    {
      heading: 'What the bar shows',
      content:
        'The bar is the width of the numeric confidence value returned for the current tone, after blending technical and headline signals. It is clamped to 0–100% for display. It is not a forecast accuracy score.',
    },
    {
      heading: 'Inputs to the policy layer',
      content:
        '• p = blended "probability up" from the synthesizer (technical + headlines), in [0, 1].\n' +
        '• μ = sentiment-nudged expected fractional return over the horizon (heuristic, clamped).\n' +
        '• σ = estimated daily return volatility from recent bars.\n\n' +
        'Derived scalars (from backend advice policy):\n' +
        '  buffer = clamp(σ × 0.75, 0.005, 0.030)\n' +
        '  edge_buffer = buffer × 1.35',
    },
    {
      heading: 'Tone selection and confidence formula',
      content:
        'Rules are evaluated in order:\n\n' +
        '1) Safer Buy:  p ≥ 0.73  and  μ ≥ edge_buffer\n' +
        '   confidence = min(1, max(p, 0.5 + μ / buffer × 0.05))\n\n' +
        '2) Sell Soon:  p ≤ 0.27  and  μ ≤ −edge_buffer\n' +
        '   confidence = min(1, max(1 − p, 0.5 + (−μ) / buffer × 0.05))\n\n' +
        '3) Buy:  p ≥ 0.58  and  μ ≥ buffer       →  confidence = p\n\n' +
        '4) Sell:  p ≤ 0.42  and  μ ≤ −buffer     →  confidence = 1 − p\n\n' +
        '5) Neutral (else):\n' +
        '   confidence = 1 − 2 × |p − 0.5|   (highest near p = 0.5)',
    },
  ]
}

export function getSynthesizerExplanationSections(
  horizon: 'short' | 'long',
  weights?: { technical: number; sentiment: number },
): ExplanationSection[] {
  const resolved = weights ?? {
    technical: SYNTH_WEIGHTS[horizon].technical,
    sentiment: SYNTH_WEIGHTS[horizon].sentiment,
  }
  const wTech = resolved.technical
  const wSent = resolved.sentiment
  const label = horizon === 'short' ? 'Short (≈ 5 trading sessions)' : 'Long (≈ 30 trading sessions)'

  return [
    {
      heading: `Synthesizer — ${label}`,
      content:
        'Technical stream: P(up) from a scaled logistic regression on engineered OHLCV features, with optional isotonic calibration (time-series CV when valid).\n\n' +
        'Headline stream: titles scored with VADER; pooled and mapped to a probability in [0, 1] per horizon (short uses a recency window; long uses a narrative anchor).',
    },
    {
      heading: 'Blend (same code path for short and long)',
      content:
        'Let P_tech = technical P(up), P_sent = headline P(up). Weights are normalized if needed:\n\n' +
        `  w_t = ${(wTech * 100).toFixed(0)}%,  w_s = ${(wSent * 100).toFixed(0)}%\n` +
        '  p_blend = (w_t × P_tech + w_s × P_sent) / (w_t + w_s)\n\n' +
        'That p_blend is the p fed into the tone policy above.',
    },
    {
      heading: 'Expected-return nudge',
      content:
        'A small additive sentiment tilt on the drift heuristic (then clamped):\n\n' +
        '  μ_raw = mean_daily_return(last ~20 bars) × horizon_days\n' +
        '  μ = clip(μ_raw + 0.02 × mean_VADER_compound, −0.25, 0.25)',
    },
  ]
}

/**
 * Optional numeric lines when the full report exposes synthesis breakdown.
 */
export function formatSynthesizerRuntimeLines(details: {
  technical_probability: number
  sentiment_probability: number
  blended_probability: number
  technical_weight: number
  sentiment_weight: number
}): string {
  const fmt = (x: number) => `${(x * 100).toFixed(1)}%`
  return (
    'This analysis used:\n' +
    `  P_tech ≈ ${fmt(details.technical_probability)}\n` +
    `  P_sent ≈ ${fmt(details.sentiment_probability)}\n` +
    `  P_blend ≈ ${fmt(details.blended_probability)}\n` +
    `  weights ${(details.technical_weight * 100).toFixed(0)}% technical / ${(details.sentiment_weight * 100).toFixed(0)}% headlines`
  )
}
