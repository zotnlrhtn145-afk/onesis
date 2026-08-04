// 백엔드 API 클라이언트 + SSE 스트림 파서

const TOKEN_KEY = 'onesis_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(t) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

function authHeaders(extra = {}) {
  const t = getToken()
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra
}

async function handle(res) {
  if (res.status === 401) {
    clearToken()
    throw new Error('401')
  }
  if (!res.ok) {
    let msg = `오류 ${res.status}`
    try {
      const j = await res.json()
      if (j.detail) msg = j.detail
    } catch (_) {}
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  getConfig: () => fetch('/api/config').then(handle),

  login: (password) =>
    fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }).then(handle),

  listConversations: () =>
    fetch('/api/conversations', { headers: authHeaders() }).then(handle),

  getConversation: (id) =>
    fetch(`/api/conversations/${id}`, { headers: authHeaders() }).then(handle),

  renameConversation: (id, title) =>
    fetch(`/api/conversations/${id}`, {
      method: 'PATCH',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ title }),
    }).then(handle),

  deleteConversation: (id) =>
    fetch(`/api/conversations/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    }).then(handle),

  setPreview: (id, preview) =>
    fetch(`/api/conversations/${id}/preview`, {
      method: 'PUT',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ preview }),
    }).then(handle),

  makeMockup: (payload) =>
    fetch('/api/mockup', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    }).then(handle),

  runningIds: () =>
    fetch('/api/running', { headers: authHeaders() }).then(handle),

  // 시장 통계
  marketStats: (query) =>
    fetch('/api/market/stats', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ query }),
    }).then(handle),

  marketExplain: (symbol) =>
    fetch('/api/market/explain', {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ symbol }),
    }).then(handle),

  marketAssets: () =>
    fetch('/api/market/assets', { headers: authHeaders() }).then(handle),
}

// SSE 블록(빈 줄로 구분)을 파싱해 onEvent 로 넘긴다.
async function pumpSSE(res, onEvent, onError) {
  if (res.status === 401) {
    clearToken()
    onError && onError(new Error('401'))
    return
  }
  if (!res.ok || !res.body) {
    onError && onError(new Error(`오류 ${res.status}`))
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of block.split('\n')) {
        const trimmed = line.startsWith('data:') ? line.slice(5).trim() : ''
        if (!trimmed) continue
        try {
          onEvent(JSON.parse(trimmed))
        } catch (_) {}
      }
    }
  }
}

// GET 방식 SSE (진행 중인 토론 재접속용). 반환값: abort 함수
export function streamGet(path, onEvent, onError) {
  const controller = new AbortController()
  ;(async () => {
    try {
      const res = await fetch(path, { headers: authHeaders(), signal: controller.signal })
      await pumpSSE(res, onEvent, onError)
    } catch (e) {
      if (e.name !== 'AbortError') onError && onError(e)
    }
  })()
  return () => controller.abort()
}

// SSE: fetch + ReadableStream 으로 이벤트를 파싱해 onEvent 로 전달.
// 반환값: abort 함수
export function streamPost(path, body, onEvent, onError) {
  const controller = new AbortController()
  ;(async () => {
    try {
      const res = await fetch(path, {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      await pumpSSE(res, onEvent, onError)
    } catch (e) {
      if (e.name !== 'AbortError') onError && onError(e)
    }
  })()
  return () => controller.abort()
}
