import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { useAuth } from './auth'
import { Dashboard } from './pages/Dashboard'
import { LessonPage } from './pages/LessonPage'
import { LoginPage } from './pages/LoginPage'

export function App() {
  const { user, loading, logout } = useAuth()
  if (loading) return <div className="cb-center">Loading…</div>
  if (!user) return <LoginPage />

  return (
    <div className="cb-shell">
      <header className="cb-topbar">
        <Link to="/" className="cb-brand">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width={26} height={26} />
          Chalkback
        </Link>
        <div className="cb-topbar-user">
          <span>
            {user.name} <small>· {user.role}</small>
          </span>
          <button className="cb-btn cb-btn-ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </header>
      <main className="cb-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/lessons/:lessonId" element={<LessonRoute />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

// Remount per lesson so board selection and polling never leak between lessons.
function LessonRoute() {
  const { lessonId } = useParams()
  return <LessonPage key={lessonId} />
}
