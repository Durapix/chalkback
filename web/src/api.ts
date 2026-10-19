export type Role = 'teacher' | 'student'
export type JobStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface User {
  id: number
  email: string
  name: string
  role: Role
}

export interface Student extends User {
  language: string
  telegram_chat_id: string | null
  remind_by_email: boolean
  remind_by_telegram: boolean
  next_lesson_at: string | null
}

export interface BoardBrief {
  id: number
  position: number
  status: JobStatus
  error: string | null
  image_url: string | null
  width: number
  height: number
  title: string | null
}

// Mirrors api/app/scene.py. Coordinates and sizes are board pixels; `scale` only enlarges
// text, labels and strokes.
export type Color =
  | 'black'
  | 'grey'
  | 'light-violet'
  | 'violet'
  | 'blue'
  | 'light-blue'
  | 'yellow'
  | 'orange'
  | 'green'
  | 'light-green'
  | 'light-red'
  | 'red'
  | 'white'
export type Font = 'draw' | 'sans' | 'serif' | 'mono'
export type Size = 's' | 'm' | 'l' | 'xl'
export type Align = 'start' | 'middle' | 'end'
export type Arrowhead = 'none' | 'arrow' | 'triangle' | 'dot' | 'diamond'
export interface Pt {
  x: number
  y: number
}
interface ElementBase {
  id: string
  rotation: number
  opacity: number
}

export type SceneElement = ElementBase &
  (
    | {
        kind: 'text'
        x: number
        y: number
        w: number
        h: number
        text: string
        size: Size
        color: Color
        font: Font
        align: Align
        wrap: boolean
        scale: number
      }
    | { kind: 'math'; x: number; y: number; w: number; h: number; latex: string; color: Color }
    | {
        kind: 'geo'
        x: number
        y: number
        w: number
        h: number
        geo: string
        color: Color
        fill: 'none' | 'semi' | 'solid' | 'fill'
        dash: 'solid' | 'dashed' | 'dotted' | 'draw'
        label: string
        label_color: Color | null
        font: Font
        size: Size
        align: Align
        valign: Align
        scale: number
      }
    | { kind: 'note'; x: number; y: number; w: number; text: string; color: Color; font: Font }
    | { kind: 'code'; x: number; y: number; w: number; text: string; color: Color; scale: number }
    | {
        kind: 'connector' | 'arrow'
        x1: number
        y1: number
        x2: number
        y2: number
        from_id: string
        to_id: string
        from_anchor: Pt | null
        to_anchor: Pt | null
        route: 'straight' | 'elbow' | 'curved'
        bend: number
        start_head: Arrowhead
        end_head: Arrowhead
        color: Color
        dash: 'solid' | 'dashed' | 'dotted' | 'draw'
        label: string
        scale: number
      }
    | {
        kind: 'draw'
        points: Pt[]
        color: Color
        freehand: boolean
        closed: boolean
        filled: boolean
        size: Size
      }
    | {
        kind: 'image'
        x: number
        y: number
        w: number
        h: number
        file: string
        crop: { x: number; y: number; w: number; h: number } | null
        alt: string
      }
    | { kind: 'frame'; x: number; y: number; w: number; h: number; name: string }
  )

export interface Scene {
  title: string
  transcript: string
  source: 'ai' | 'drawio' | 'mock'
  elements: SceneElement[]
}

export interface Board extends BoardBrief {
  lesson_id: number
  scene: Scene | null
  snapshot: Record<string, unknown> | null
  updated_at: string
}

export interface LessonSummary {
  headline: string
  topics: string[]
  key_points: string[]
  formulas: string[]
  exercises: string[]
  recap_message: string
  review_suggestions: string[]
}

export interface Lesson {
  id: number
  title: string
  subject: string
  taught_at: string
  notes: string
  student: User
  summary: LessonSummary | null
  summary_status: JobStatus | null
  summary_error: string | null
  boards: BoardBrief[]
}

export interface Reminder {
  id: number
  lesson_id: number
  channel: string
  status: string
  detail: string | null
  sent_at: string
}

const TOKEN_KEY = 'chalkback.token'

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      // storage unavailable (private mode); session-only login
    }
  },
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload })
  if (res.status === 401 && token) {
    tokenStore.set(null)
    window.dispatchEvent(new Event('chalkback:logout'))
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>('POST', '/auth/login', { email, password }),
  me: () => request<User>('GET', '/auth/me'),

  students: () => request<Student[]>('GET', '/students'),
  createStudent: (data: Partial<Student> & { password: string }) =>
    request<Student>('POST', '/students', data),
  updateStudent: (id: number, data: Partial<Student>) =>
    request<Student>('PATCH', `/students/${id}`, data),
  remindNow: (id: number) => request<Reminder[]>('POST', `/students/${id}/remind`),
  reminders: (id: number) => request<Reminder[]>('GET', `/students/${id}/reminders`),

  lessons: (studentId?: number) =>
    request<Lesson[]>('GET', `/lessons${studentId ? `?student_id=${studentId}` : ''}`),
  lesson: (id: number) => request<Lesson>('GET', `/lessons/${id}`),
  createLesson: (data: { student_id: number; title: string; taught_at?: string; notes?: string }) =>
    request<Lesson>('POST', '/lessons', data),
  updateLesson: (id: number, data: Partial<Pick<Lesson, 'title' | 'notes' | 'taught_at'>>) =>
    request<Lesson>('PATCH', `/lessons/${id}`, data),
  deleteLesson: (id: number) => request<void>('DELETE', `/lessons/${id}`),
  uploadBoards: (lessonId: number, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<BoardBrief[]>('POST', `/lessons/${lessonId}/boards`, form)
  },
  summarize: (lessonId: number) => request<Lesson>('POST', `/lessons/${lessonId}/summarize`),

  board: (id: number) => request<Board>('GET', `/boards/${id}`),
  saveSnapshot: (id: number, snapshot: unknown) =>
    request<Board>('PUT', `/boards/${id}/snapshot`, { snapshot }),
  reconstruct: (id: number) => request<Board>('POST', `/boards/${id}/reconstruct`),
  deleteBoard: (id: number) => request<void>('DELETE', `/boards/${id}`),
}
