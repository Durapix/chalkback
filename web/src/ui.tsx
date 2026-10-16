import katex from 'katex'
import type { JobStatus } from './api'

export function Tex({ latex, block = false }: { latex: string; block?: boolean }) {
  const html = katex.renderToString(latex, { throwOnError: false, displayMode: block })
  return <span className="cb-tex" dangerouslySetInnerHTML={{ __html: html }} />
}

const STATUS_LABEL: Record<JobStatus, string> = {
  pending: 'Queued',
  processing: 'AI working…',
  ready: 'Ready',
  failed: 'Failed',
}

export function StatusChip({ status }: { status: JobStatus | null }) {
  if (!status) return null
  return <span className={`cb-chip cb-chip-${status}`}>{STATUS_LABEL[status]}</span>
}

export const formatDate = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
    : '—'

/** ISO string -> value for <input type="datetime-local"> (local time). */
export function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : null)

export const isBusy = (status: JobStatus | null) => status === 'pending' || status === 'processing'
