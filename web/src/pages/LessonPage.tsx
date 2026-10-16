import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type Board, type Lesson } from '../api'
import { useAuth } from '../auth'
import { StatusChip, Tex, formatDate, isBusy } from '../ui'

const POLL_MS = 2000
// tldraw is large; load it only when a board is actually opened.
const BoardEditor = lazy(() => import('../board/BoardEditor').then((m) => ({ default: m.BoardEditor })))

export function LessonPage() {
  const { lessonId } = useParams()
  const id = Number(lessonId)
  const { user } = useAuth()
  const navigate = useNavigate()
  const isTeacher = user?.role === 'teacher'
  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<number | null>(null)

  const reload = useCallback(
    () =>
      api
        .lesson(id)
        .then(setLesson)
        .catch((e) => setError(e.message)),
    [id],
  )

  useEffect(() => {
    reload()
  }, [reload])

  // Poll while the AI is working on anything in this lesson.
  const working = !!lesson && (isBusy(lesson.summary_status) || lesson.boards.some((b) => isBusy(b.status)))
  useEffect(() => {
    if (!working) return
    const t = window.setInterval(reload, POLL_MS)
    return () => window.clearInterval(t)
  }, [working, reload])

  useEffect(() => {
    if (lesson && selected === null && lesson.boards.length) setSelected(lesson.boards[0].id)
  }, [lesson, selected])

  if (error) return <div className="cb-page cb-error">{error}</div>
  if (!lesson) return <div className="cb-page cb-muted">Loading…</div>

  const current = lesson.boards.find((b) => b.id === selected) ?? null

  const remove = async () => {
    if (!confirm(`Delete "${lesson.title}" and all its boards?`)) return
    await api.deleteLesson(lesson.id)
    navigate('/')
  }

  return (
    <div className="cb-lesson">
      <div className="cb-lesson-head">
        <div>
          <h1>{lesson.title}</h1>
          <div className="cb-muted">
            {lesson.student.name} · {lesson.subject} · {formatDate(lesson.taught_at)}
          </div>
        </div>
        {isTeacher && (
          <div className="cb-actions">
            <UploadButton lessonId={lesson.id} onUploaded={(ids) => (setSelected(ids[0] ?? null), reload())} />
            <button className="cb-btn cb-btn-ghost" onClick={remove}>
              Delete
            </button>
          </div>
        )}
      </div>

      <div className="cb-lesson-body">
        <div className="cb-lesson-boards">
          <div className="cb-tabs">
            {lesson.boards.map((b, i) => (
              <button
                key={b.id}
                className={`cb-tab ${b.id === selected ? 'on' : ''}`}
                onClick={() => setSelected(b.id)}
              >
                Board {i + 1}
                {b.title ? ` · ${b.title}` : ''} {b.status !== 'ready' && <StatusChip status={b.status} />}
              </button>
            ))}
          </div>
          {lesson.boards.length === 0 && (
            <div className="cb-empty">
              <h3>No boards yet</h3>
              <p className="cb-muted">
                {isTeacher
                  ? 'Upload screenshots or a PDF export of the whiteboard from this lesson. Claude will rebuild each one as an editable board.'
                  : 'Your tutor has not added boards for this lesson yet.'}
              </p>
            </div>
          )}
          {current && <BoardPane key={current.id} brief={current} canRetry={isTeacher} onRetry={reload} />}
        </div>

        <SummaryPanel lesson={lesson} canGenerate={isTeacher} onRequested={setLesson} />
      </div>
    </div>
  )
}

function BoardPane({
  brief,
  canRetry,
  onRetry,
}: {
  brief: Lesson['boards'][number]
  canRetry: boolean
  onRetry: () => void
}) {
  const [board, setBoard] = useState<Board | null>(null)
  useEffect(() => {
    if (brief.status === 'ready') api.board(brief.id).then(setBoard)
  }, [brief.id, brief.status])

  if (isBusy(brief.status))
    return (
      <div className="cb-empty cb-working">
        <div className="cb-spinner" />
        <h3>Reconstructing the board…</h3>
        <p className="cb-muted">Claude is reading the handwriting, formulas and diagrams.</p>
      </div>
    )
  if (brief.status === 'failed')
    return (
      <div className="cb-empty">
        <h3>Reconstruction failed</h3>
        <p className="cb-error">{brief.error}</p>
        {canRetry && (
          <button className="cb-btn cb-btn-primary" onClick={() => api.reconstruct(brief.id).then(onRetry)}>
            Try again
          </button>
        )}
      </div>
    )
  if (!board) return <div className="cb-empty cb-muted">Loading board…</div>
  return (
    <Suspense fallback={<div className="cb-empty cb-muted">Loading editor…</div>}>
      <BoardEditor board={board} />
    </Suspense>
  )
}

function SummaryPanel({
  lesson,
  canGenerate,
  onRequested,
}: {
  lesson: Lesson
  canGenerate: boolean
  onRequested: (l: Lesson) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const s = lesson.summary
  const generate = async () => {
    setError(null)
    try {
      onRequested(await api.summarize(lesson.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed')
    }
  }
  return (
    <aside className="cb-card cb-summary">
      <div className="cb-row-plain">
        <h2>Lesson recap</h2>
        <StatusChip status={lesson.summary_status} />
      </div>
      {s ? (
        <>
          <p className="cb-recap">{s.recap_message}</p>
          {s.topics.length > 0 && (
            <div className="cb-topics">
              {s.topics.map((t) => (
                <span key={t} className="cb-pill on">
                  {t}
                </span>
              ))}
            </div>
          )}
          <Section title="Key points" items={s.key_points} />
          {s.formulas.length > 0 && (
            <>
              <h4>Formulas</h4>
              <div className="cb-formulas">
                {s.formulas.map((f) => (
                  <Tex key={f} latex={f} block />
                ))}
              </div>
            </>
          )}
          <Section title="Exercises" items={s.exercises} />
          <Section title="Before next lesson" items={s.review_suggestions} />
        </>
      ) : (
        <p className="cb-muted">
          {isBusy(lesson.summary_status) ? 'Writing the recap…' : 'No recap yet.'}
        </p>
      )}
      {lesson.summary_error && <p className="cb-error">{lesson.summary_error}</p>}
      {canGenerate && (
        <button className="cb-btn cb-btn-primary" onClick={generate} disabled={isBusy(lesson.summary_status)}>
          {s ? 'Regenerate recap' : 'Generate recap'}
        </button>
      )}
      {error && <p className="cb-error">{error}</p>}
      {lesson.notes && (
        <>
          <h4>Tutor notes</h4>
          <p className="cb-small">{lesson.notes}</p>
        </>
      )}
    </aside>
  )
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <>
      <h4>{title}</h4>
      <ul>
        {items.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </>
  )
}

function UploadButton({ lessonId, onUploaded }: { lessonId: number; onUploaded: (ids: number[]) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      const boards = await api.uploadBoards(lessonId, Array.from(files))
      onUploaded(boards.map((b) => b.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }
  return (
    <>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp,application/pdf"
        multiple
        hidden
        onChange={(e) => upload(e.target.files)}
      />
      <button className="cb-btn cb-btn-primary" onClick={() => input.current?.click()} disabled={busy}>
        {busy ? 'Uploading…' : 'Upload boards'}
      </button>
      {error && <span className="cb-error">{error}</span>}
    </>
  )
}
