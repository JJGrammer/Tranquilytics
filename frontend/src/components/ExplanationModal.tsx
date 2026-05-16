import { useEffect } from 'react'
import { type ExplanationSection } from '../analysisExplanations'

type Props = {
  open: boolean
  title: string
  sections: ExplanationSection[]
  extraNote?: string
  onClose: () => void
}

export function ExplanationModal({ open, title, sections, extraNote, onClose }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center"
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="absolute inset-0 bg-slate-900/50 dark:bg-black/60" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="explanation-modal-title"
        className="relative max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-sky-200/90 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex items-start justify-between gap-3 border-b border-sky-200/80 pb-3 dark:border-slate-700">
          <h2 id="explanation-modal-title" className="font-faculty text-lg font-semibold text-slate-900 dark:text-white">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-slate-600 transition hover:bg-sky-100 dark:text-slate-400 dark:hover:bg-slate-800"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {extraNote ? (
          <p className="mt-3 whitespace-pre-wrap rounded-md border border-sky-200/70 bg-sky-50/80 px-3 py-2 font-mono text-[11px] leading-relaxed text-slate-800 dark:border-slate-600 dark:bg-slate-950/50 dark:text-slate-300">
            {extraNote}
          </p>
        ) : null}
        <div className="mt-4 space-y-4">
          {sections.map((s) => (
            <section key={s.heading}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-500">
                {s.heading}
              </h3>
              <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                {s.content}
              </p>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
