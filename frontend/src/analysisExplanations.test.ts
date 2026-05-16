import { describe, expect, it } from 'vitest'
import {
  getConfidenceExplanationSections,
  getSynthesizerExplanationSections,
} from './analysisExplanations'

describe('analysisExplanations', () => {
  it('confidence sections include policy formulas', () => {
    const s = getConfidenceExplanationSections()
    const joined = s.map((x) => x.content).join('\n')
    expect(joined).toMatch(/buffer/)
    expect(joined).toMatch(/0\.73/)
  })

  it('synthesizer sections use default short/long weights', () => {
    const short = getSynthesizerExplanationSections('short')
    const long = getSynthesizerExplanationSections('long')
    expect(short[1].content).toContain('56%')
    expect(long[1].content).toContain('70%')
  })
})
