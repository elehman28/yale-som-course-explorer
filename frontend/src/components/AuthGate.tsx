import { useState } from 'react'
import { login, signup } from '../api'
import type { Session } from '../api'

interface Props {
  onSignedIn: (session: Session) => void
}

/** Sign-in / create-account screen shown before the catalog. */
export default function AuthGate({ onSignedIn }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const isSignup = mode === 'signup'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    setError('')

    if (isSignup && password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    setBusy(true)
    try {
      const session = isSignup
        ? await signup(username, password)
        : await login(username, password)
      onSignedIn(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth__card" onSubmit={submit}>
        <h1 className="auth__title">Yale SOM Course Explorer</h1>
        <p className="auth__subtitle">
          {isSignup
            ? 'Create an account to save your chat history.'
            : 'Sign in to pick up where you left off.'}
        </p>

        <label className="auth__label" htmlFor="username">
          Username
        </label>
        <input
          id="username"
          className="auth__input"
          value={username}
          autoComplete="username"
          autoFocus
          required
          minLength={3}
          onChange={(e) => setUsername(e.target.value)}
        />

        <label className="auth__label" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="auth__input"
          type="password"
          value={password}
          autoComplete={isSignup ? 'new-password' : 'current-password'}
          required
          minLength={8}
          onChange={(e) => setPassword(e.target.value)}
        />
        {isSignup && <p className="auth__hint">At least 8 characters.</p>}

        {error && (
          <p className="auth__error" role="alert">
            {error}
          </p>
        )}

        <button className="auth__submit" type="submit" disabled={busy}>
          {busy ? 'Working…' : isSignup ? 'Create account' : 'Sign in'}
        </button>

        <button
          type="button"
          className="auth__switch"
          onClick={() => {
            setMode(isSignup ? 'login' : 'signup')
            setError('')
          }}
        >
          {isSignup ? 'Already have an account? Sign in' : 'New here? Create an account'}
        </button>
      </form>
    </div>
  )
}
