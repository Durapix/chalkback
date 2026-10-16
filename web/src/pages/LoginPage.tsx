import { useState, type FormEvent } from 'react'
import { useAuth } from '../auth'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  const fillDemo = (who: 'teacher' | 'student') => {
    setEmail(who === 'teacher' ? 'teacher@demo.chalkback' : 'mia@demo.chalkback')
    setPassword('demo-password')
  }

  return (
    <div className="cb-login">
      <form className="cb-card cb-login-card" onSubmit={submit}>
        <div className="cb-brand cb-brand-lg">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" width={36} height={36} />
          Chalkback
        </div>
        <p className="cb-muted">Your whiteboard remembers, so your students do too.</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <div className="cb-error">{error}</div>}
        <button className="cb-btn cb-btn-primary" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
        <div className="cb-demo">
          Try the demo as{' '}
          <button type="button" className="cb-link" onClick={() => fillDemo('teacher')}>
            teacher
          </button>{' '}
          or{' '}
          <button type="button" className="cb-link" onClick={() => fillDemo('student')}>
            student
          </button>
        </div>
      </form>
    </div>
  )
}
