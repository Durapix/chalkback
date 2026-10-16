import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Lesson, type Student } from '../api'
import { useAuth } from '../auth'
import { StatusChip, formatDate, fromLocalInput, toLocalInput } from '../ui'

export function Dashboard() {
  const { user } = useAuth()
  return user?.role === 'teacher' ? <TeacherDashboard /> : <StudentDashboard />
}

function StudentDashboard() {
  const [lessons, setLessons] = useState<Lesson[] | null>(null)
  useEffect(() => {
    api.lessons().then(setLessons)
  }, [])
  return (
    <div className="cb-page">
      <h1>Your lessons</h1>
      {lessons === null && <p className="cb-muted">Loading…</p>}
      {lessons?.length === 0 && <p className="cb-muted">No lessons yet.</p>}
      <div className="cb-grid">
        {lessons?.map((l) => (
          <Link key={l.id} to={`/lessons/${l.id}`} className="cb-card cb-lesson-card">
            <div className="cb-lesson-card-head">
              <strong>{l.title}</strong>
              <small className="cb-muted">{formatDate(l.taught_at)}</small>
            </div>
            {l.summary ? (
              <p>{l.summary.recap_message}</p>
            ) : (
              <p className="cb-muted">Summary coming soon.</p>
            )}
            <small className="cb-muted">{l.boards.length} board(s)</small>
          </Link>
        ))}
      </div>
    </div>
  )
}

function TeacherDashboard() {
  const [students, setStudents] = useState<Student[]>([])
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [filter, setFilter] = useState<number | null>(null)

  const reload = useCallback(async () => {
    const [s, l] = await Promise.all([api.students(), api.lessons()])
    setStudents(s)
    setLessons(l)
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  const shown = filter ? lessons.filter((l) => l.student.id === filter) : lessons

  return (
    <div className="cb-page cb-dashboard">
      <section>
        <div className="cb-section-head">
          <h1>Lessons</h1>
          <NewLesson students={students} />
        </div>
        <div className="cb-filter">
          <button className={`cb-pill ${filter === null ? 'on' : ''}`} onClick={() => setFilter(null)}>
            All
          </button>
          {students.map((s) => (
            <button
              key={s.id}
              className={`cb-pill ${filter === s.id ? 'on' : ''}`}
              onClick={() => setFilter(s.id)}
            >
              {s.name}
            </button>
          ))}
        </div>
        <div className="cb-list">
          {shown.map((l) => (
            <Link key={l.id} to={`/lessons/${l.id}`} className="cb-card cb-row">
              <div>
                <strong>{l.title}</strong>
                <div className="cb-muted">
                  {l.student.name} · {formatDate(l.taught_at)} · {l.boards.length} board(s)
                </div>
              </div>
              <StatusChip status={l.summary_status} />
            </Link>
          ))}
          {shown.length === 0 && <p className="cb-muted">No lessons yet.</p>}
        </div>
      </section>

      <aside>
        <div className="cb-section-head">
          <h2>Students</h2>
          <NewStudent onCreated={reload} />
        </div>
        {students.map((s) => (
          <StudentCard key={s.id} student={s} onChange={reload} />
        ))}
      </aside>
    </div>
  )
}

function NewLesson({ students }: { students: Student[] }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    try {
      const lesson = await api.createLesson({
        student_id: Number(f.get('student')),
        title: String(f.get('title')),
        taught_at: fromLocalInput(String(f.get('taught_at'))) ?? undefined,
        notes: String(f.get('notes') ?? ''),
      })
      navigate(`/lessons/${lesson.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create lesson')
    }
  }

  if (!open)
    return (
      <button className="cb-btn cb-btn-primary" onClick={() => setOpen(true)} disabled={!students.length}>
        + New lesson
      </button>
    )
  return (
    <form className="cb-card cb-form cb-popover" onSubmit={submit}>
      <label>
        Student
        <select name="student" required>
          {students.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Title
        <input name="title" placeholder="e.g. Quadratic equations" required />
      </label>
      <label>
        When
        <input name="taught_at" type="datetime-local" defaultValue={toLocalInput(new Date().toISOString())} />
      </label>
      <label>
        Notes for the AI (optional)
        <textarea name="notes" rows={3} placeholder="What you focused on, homework given…" />
      </label>
      {error && <div className="cb-error">{error}</div>}
      <div className="cb-actions">
        <button type="button" className="cb-btn cb-btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button className="cb-btn cb-btn-primary">Create & upload boards</button>
      </div>
    </form>
  )
}

function NewStudent({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    try {
      await api.createStudent({
        name: String(f.get('name')),
        email: String(f.get('email')),
        password: String(f.get('password')),
        language: String(f.get('language')),
      })
      setOpen(false)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add student')
    }
  }

  if (!open)
    return (
      <button className="cb-btn cb-btn-ghost" onClick={() => setOpen(true)}>
        + Add
      </button>
    )
  return (
    <form className="cb-card cb-form cb-popover" onSubmit={submit}>
      <label>
        Name
        <input name="name" required />
      </label>
      <label>
        Email
        <input name="email" type="email" required />
      </label>
      <label>
        Initial password
        <input name="password" type="text" minLength={8} required />
      </label>
      <label>
        Summary language
        <input name="language" defaultValue="English" />
      </label>
      {error && <div className="cb-error">{error}</div>}
      <div className="cb-actions">
        <button type="button" className="cb-btn cb-btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button className="cb-btn cb-btn-primary">Add student</button>
      </div>
    </form>
  )
}

function StudentCard({ student, onChange }: { student: Student; onChange: () => void }) {
  const [editing, setEditing] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    await api.updateStudent(student.id, {
      language: String(f.get('language')),
      telegram_chat_id: String(f.get('telegram') || '') || null,
      remind_by_email: f.get('by_email') === 'on',
      remind_by_telegram: f.get('by_telegram') === 'on',
      next_lesson_at: fromLocalInput(String(f.get('next') ?? '')),
    })
    setEditing(false)
    onChange()
  }

  const remind = async () => {
    setMessage('Sending…')
    try {
      const res = await api.remindNow(student.id)
      setMessage(
        res.length
          ? res.map((r) => `${r.channel}: ${r.status}${r.detail ? ` (${r.detail})` : ''}`).join(' · ')
          : 'No reminder channels enabled',
      )
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed')
    }
  }

  const channels = [student.remind_by_email && 'email', student.remind_by_telegram && 'Telegram']
    .filter(Boolean)
    .join(' + ')

  return (
    <div className="cb-card cb-student">
      <div className="cb-row-plain">
        <div>
          <strong>{student.name}</strong>
          <div className="cb-muted">{student.email}</div>
        </div>
        <button className="cb-btn cb-btn-ghost cb-btn-sm" onClick={() => setEditing(!editing)}>
          {editing ? 'Close' : 'Edit'}
        </button>
      </div>
      <div className="cb-muted cb-small">
        Next lesson: {formatDate(student.next_lesson_at)}
        <br />
        Reminders: {channels || 'off'} · {student.language}
      </div>
      {editing && (
        <form className="cb-form" onSubmit={save}>
          <label>
            Next lesson
            <input name="next" type="datetime-local" defaultValue={toLocalInput(student.next_lesson_at)} />
          </label>
          <label>
            Summary language
            <input name="language" defaultValue={student.language} />
          </label>
          <label>
            Telegram chat ID
            <input name="telegram" defaultValue={student.telegram_chat_id ?? ''} placeholder="e.g. 123456789" />
          </label>
          <label className="cb-check">
            <input type="checkbox" name="by_email" defaultChecked={student.remind_by_email} /> Email reminders
          </label>
          <label className="cb-check">
            <input type="checkbox" name="by_telegram" defaultChecked={student.remind_by_telegram} /> Telegram
            reminders
          </label>
          <button className="cb-btn cb-btn-primary">Save</button>
        </form>
      )}
      <button className="cb-btn cb-btn-ghost cb-btn-sm" onClick={remind}>
        Send last recap now
      </button>
      {message && <div className="cb-small cb-muted">{message}</div>}
    </div>
  )
}
