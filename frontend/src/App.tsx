import { useEffect, useMemo, useState } from 'react'
import { fetchCourses, logout, me } from './api'
import type { Course, Session } from './api'
import AuthGate from './components/AuthGate'
import ChatPanel from './components/ChatPanel'
import CourseCard from './components/CourseCard'

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)

  // Resolve any stored token once on load so a returning user skips the gate.
  useEffect(() => {
    let alive = true
    me()
      .then((s) => alive && setSession(s))
      .finally(() => alive && setCheckingSession(false))
    return () => {
      alive = false
    }
  }, [])

  const [query, setQuery] = useState('')
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [category, setCategory] = useState('All')

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true)
      fetchCourses(query, controller.signal)
        .then((res) => {
          setCourses(res.courses)
          setError('')
        })
        .catch((e: unknown) => {
          if (e instanceof DOMException && e.name === 'AbortError') return
          setError('Could not load courses. Start the backend: uvicorn main:app --port 8000')
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const categories = useMemo(() => {
    const counts = new Map<string, number>()
    for (const c of courses) counts.set(c['Course Category'], (counts.get(c['Course Category']) ?? 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [courses])

  const shown = category === 'All' ? courses : courses.filter((c) => c['Course Category'] === category)

  if (checkingSession) {
    return <div className="boot">Loading…</div>
  }

  if (!session) {
    return <AuthGate onSignedIn={setSession} />
  }

  return (
    <>
      <div className="userbar">
        <span className="userbar__who">
          Signed in as <b>{session.username}</b>
        </span>
        <button
          type="button"
          className="userbar__out"
          onClick={async () => {
            await logout()
            setSession(null)
          }}
        >
          Sign out
        </button>
      </div>
      <header className="hero">
        <div className="hero__inner">
          <p className="hero__eyebrow">Yale School of Management</p>
          <h1>Course Explorer</h1>
          <p className="hero__sub">Browse the full course list, or ask the assistant in the corner.</p>
          <input
            className="search"
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setCategory('All')
            }}
            placeholder="Search by title, number, professor, day…"
            aria-label="Search courses"
          />
        </div>
      </header>

      <main className="main">
        <div className="filters" role="group" aria-label="Filter by category">
          <button type="button" className={category === 'All' ? 'is-on' : ''} onClick={() => setCategory('All')}>
            All <span>{courses.length}</span>
          </button>
          {categories.map(([name, n]) => (
            <button
              key={name}
              type="button"
              className={category === name ? 'is-on' : ''}
              onClick={() => setCategory(name)}
            >
              {name} <span>{n}</span>
            </button>
          ))}
        </div>

        {error ? <p className="notice notice--error">{error}</p> : null}
        {loading && courses.length === 0 && !error ? <p className="notice">Loading courses…</p> : null}
        {!loading && !error && shown.length === 0 ? <p className="notice">No courses match that search.</p> : null}

        {!error ? (
          <>
            <p className="count">
              {shown.length} {shown.length === 1 ? 'course' : 'courses'}
            </p>
            <div className={`grid ${loading ? 'grid--loading' : ''}`}>
              {shown.map((c, i) => (
                <CourseCard key={`${c['Course ID']}-${i}`} course={c} />
              ))}
            </div>
          </>
        ) : null}
      </main>

      <ChatPanel username={session.username} />
    </>
  )
}
