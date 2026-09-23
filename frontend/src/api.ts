const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

/** One row of data/yale_som_classes.json, as served by GET /api/courses. */
export interface Course {
  'Course ID': string
  'Course Number': string
  'Course Title': string
  Section: string
  'Course Category': string
  'Course Type': string
  'Bid Or Permission': string
  'Course Session': string
  Daytimes: string
  Room: string
  Units: string
  'Faculty 1': string
  'Faculty 1 Email': string
  Syllabus: string
  'Old Syllabus': string
  'Course Description': string
  faculty_bio: string
  Visible: string
}

export interface CoursesResponse {
  count: number
  courses: Course[]
}

export interface ChatReply {
  reply: string
  tools_used: string[]
}

const TOKEN_KEY = 'som_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const token = getToken()
  const headers = new Headers(init?.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`${API_URL}${path}`, { ...init, headers, signal })

  if (!res.ok) {
    // Surface the server's own message ("That username is already taken")
    // instead of a bare status code.
    let detail = ''
    try {
      detail = (await res.json())?.detail ?? ''
    } catch {
      detail = ''
    }
    throw new Error(detail || `Server returned ${res.status}`)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export function fetchCourses(q: string, signal?: AbortSignal): Promise<CoursesResponse> {
  const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''
  return request<CoursesResponse>(`/api/courses${query}`, undefined, signal)
}

export function sendChat(message: string): Promise<ChatReply> {
  return request<ChatReply>('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}

/* ----------------------------------------------------------- auth + history */

export interface Session {
  token: string
  username: string
}

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
  tools_used: string[]
  created_at?: string | null
}

function credentials(username: string, password: string): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }
}

export async function signup(username: string, password: string): Promise<Session> {
  const session = await request<Session>('/api/signup', credentials(username, password))
  setToken(session.token)
  return session
}

export async function login(username: string, password: string): Promise<Session> {
  const session = await request<Session>('/api/login', credentials(username, password))
  setToken(session.token)
  return session
}

export async function logout(): Promise<void> {
  try {
    await request<{ ok: boolean }>('/api/logout', { method: 'POST' })
  } finally {
    // Drop the local token even if the server call failed.
    setToken(null)
  }
}

/** Resolve the stored token to a session, or null if it is missing/expired. */
export async function me(): Promise<Session | null> {
  if (!getToken()) return null
  try {
    return await request<Session>('/api/me')
  } catch {
    setToken(null)
    return null
  }
}

export function fetchHistory(): Promise<HistoryMessage[]> {
  return request<HistoryMessage[]>('/api/history')
}

export function clearHistory(): Promise<{ deleted: number }> {
  return request<{ deleted: number }>('/api/history', { method: 'DELETE' })
}
