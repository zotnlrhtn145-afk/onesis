import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getToken, clearToken, streamPost } from './api'
import { cache, queue, pendingPreview } from './offline'
import Login from './components/Login'
import Sidebar from './components/Sidebar'
import DebateProgress from './components/DebateProgress'
import MessageResult from './components/MessageResult'
import PreviewPanel from './components/PreviewPanel'
import BuildModal from './components/BuildModal'

export default function App() {
  const [authed, setAuthed] = useState(!!getToken())
  const [booted, setBooted] = useState(false)
  const [config, setConfig] = useState(null)
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute('data-theme') || 'light'
  )

  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])

  const [run, setRun] = useState(null) // 진행 중인 토론
  const runRef = useRef(null)
  const [runError, setRunError] = useState('')

  const [preview, setPreview] = useState('')
  const [previewLive, setPreviewLive] = useState(false)
  const [editing, setEditing] = useState(false)

  const [input, setInput] = useState('')
  const [mode, setMode] = useState('ask') // 'ask' | 'refine'
  const [sending, setSending] = useState(false)
  const abortRef = useRef(null)

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mobileTab, setMobileTab] = useState('chat')
  const [previewWidth, setPreviewWidth] = useState(440)
  const [toast, setToast] = useState('')
  const [online, setOnline] = useState(navigator.onLine)
  const [build, setBuild] = useState(null) // 제작 진행/결과
  const buildAbortRef = useRef(null)
  const [mockup, setMockup] = useState('') // 화면 미리보기 HTML
  const [mockupLoading, setMockupLoading] = useState(false)
  const [queueCount, setQueueCount] = useState(queue.count())
  const busyRef = useRef(false) // 토론 진행 중 여부(예약 질문 순차 처리용)
  const activeIdRef = useRef(null)
  const onlineHandlerRef = useRef(() => {})

  const messagesEndRef = useRef(null)

  // ---------- 초기 로딩 ----------
  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations()
      setConversations(list)
      cache.saveConvList(list)
    } catch (e) {
      if (e.message === '401') doLogout()
      else {
        const cached = cache.loadConvList()
        if (cached.length) setConversations(cached)
      }
    }
  }, [])

  useEffect(() => {
    api.getConfig().then(setConfig).catch(() => {})
  }, [])

  useEffect(() => {
    if (!authed) return
    setBooted(false)
    loadConversations().finally(() => setBooted(true))
  }, [authed, loadConversations])

  useEffect(() => {
    const on = () => onlineHandlerRef.current()
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, run])

  useEffect(() => {
    activeIdRef.current = activeId
  }, [activeId])

  // 현재 대화를 기기에 캐시(오프라인 열람용). 진행 중에는 저장하지 않음.
  useEffect(() => {
    if (!activeId || run) return
    cache.saveConv(activeId, {
      id: activeId,
      title: conversations.find((c) => c.id === activeId)?.title || '',
      preview,
      mockup,
      messages: messages
        .filter((m) => !m.refine)
        .map((m) => ({
          question: m.question,
          final: m.final,
          transcript: m.transcript,
          is_build: m.is_build,
        })),
    })
  }, [messages, preview, mockup, activeId, run, conversations])

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(''), 2200)
  }

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
    localStorage.setItem('onesis_theme', next)
  }

  function doLogout() {
    clearToken()
    setAuthed(false)
    setConversations([])
    setMessages([])
    setActiveId(null)
    setPreview('')
    setRun(null)
  }

  // ---------- 대화 선택/생성/삭제 ----------
  async function selectConversation(id) {
    if (sending) return
    setSidebarOpen(false)
    setActiveId(id)
    setRun(null)
    setRunError('')
    setEditing(false)
    const applyConv = (conv, fromCache) => {
      setMessages(
        (conv.messages || []).map((m) => ({
          question: m.question,
          final: m.final,
          transcript: m.transcript,
          is_build: m.is_build,
        }))
      )
      // 오프라인에서 수정했지만 아직 동기화 안 된 미리보기가 있으면 그것을 우선 표시
      const pp = pendingPreview.get(id)
      setPreview(pp != null ? pp : conv.preview || '')
      setMockup(conv.mockup || '')
      setPreviewLive(false)
    }
    try {
      const conv = await api.getConversation(id)
      cache.saveConv(id, conv)
      applyConv(conv, false)
    } catch (e) {
      if (e.message === '401') return doLogout()
      const c = cache.loadConv(id)
      if (c) applyConv(c, true)
      else showToast('오프라인 상태예요. 저장된 내용이 없습니다.')
    }
  }

  function newConversation() {
    if (sending) return
    setActiveId(null)
    setMessages([])
    setRun(null)
    setRunError('')
    setPreview('')
    setMockup('')
    setPreviewLive(false)
    setEditing(false)
    setMode('ask')
    setSidebarOpen(false)
    setMobileTab('chat')
  }

  async function deleteConversation(id) {
    if (!window.confirm('이 대화를 삭제할까요?')) return
    try {
      await api.deleteConversation(id)
      setConversations((cs) => cs.filter((c) => c.id !== id))
      if (id === activeId) newConversation()
    } catch (e) {
      if (e.message === '401') doLogout()
    }
  }

  // ---------- SSE 이벤트 처리 (질문) ----------
  function handleAskEvent(evt) {
    const r = runRef.current
    switch (evt.type) {
      case 'conversation':
        setActiveId(evt.id)
        if (evt.is_new) {
          setMockup('')
          setConversations((cs) => [
            { id: evt.id, title: evt.question.slice(0, 60), updated_at: '' },
            ...cs,
          ])
        }
        break
      case 'meta':
        r.participants = evt.participants
        r.is_build = evt.is_build
        break
      case 'status':
        if (r.currentStep && r.currentStep !== evt.step && !r.completed.includes(r.currentStep)) {
          r.completed.push(r.currentStep)
        }
        r.currentStep = evt.step
        r.stepLabel = evt.label
        r.aiStatus = {}
        break
      case 'ai_start':
        r.aiStatus[evt.ai] = { status: 'running' }
        break
      case 'ai_done':
        r.aiStatus[evt.ai] = { status: 'done' }
        break
      case 'ai_error':
        r.aiStatus[evt.ai] = { status: 'error', error: evt.error }
        break
      case 'preview':
        if (!editing) setPreview(evt.content)
        break
      case 'final':
        r.finalMsg = {
          question: r.question,
          final: evt.content,
          transcript: evt.transcript,
          is_build: evt.is_build,
        }
        setPreview(evt.content)
        break
      case 'error':
        setRunError(evt.error)
        break
      default:
        break
    }
    setRun({ ...r })
  }

  function finishAsk() {
    const r = runRef.current
    if (r && r.finalMsg) {
      setMessages((ms) => [...ms, r.finalMsg])
      loadConversations()
    }
    setRun(null)
    runRef.current = null
    setSending(false)
    setPreviewLive(false)
    abortRef.current = null
    busyRef.current = false
    // 예약 질문이 남아 있으면 이어서 처리
    setTimeout(maybeProcessQueue, 400)
  }

  function runAsk(question, conversationId) {
    busyRef.current = true
    setSending(true)
    setPreviewLive(true)
    setRunError('')
    setMobileTab('chat')
    setActiveId(conversationId || null)
    runRef.current = {
      question,
      participants: (config?.participants || []).filter((p) => p.available),
      currentStep: null,
      stepLabel: '',
      completed: [],
      aiStatus: {},
      finalMsg: null,
    }
    setRun({ ...runRef.current })
    abortRef.current = streamPost(
      '/api/ask',
      { question, conversation_id: conversationId },
      handleAskEventWithDone,
      (e) => {
        if (e.message === '401') doLogout()
        else setRunError('연결 오류가 발생했습니다.')
        finishAsk()
      }
    )
  }

  // 예약 질문함 순차 처리 (온라인 & 진행 중 아님)
  function maybeProcessQueue() {
    if (!navigator.onLine || busyRef.current) return
    const q = queue.all()
    if (!q.length) return
    const item = q[0]
    queue.remove(item.ts)
    setQueueCount(queue.count())
    showToast('예약 질문을 시작합니다…')
    runAsk(item.question, item.conversation_id || null)
  }

  // 오프라인에서 수정한 미리보기를 서버와 동기화
  async function flushPendingPreviews() {
    for (const id of pendingPreview.allIds()) {
      try {
        await api.setPreview(id, pendingPreview.get(id) || '')
        pendingPreview.clear(id)
      } catch (_) {
        /* 다음 기회에 재시도 */
      }
    }
  }

  // ---------- SSE 이벤트 처리 (미리보기 수정) ----------
  function handleRefineEvent(evt) {
    const r = runRef.current
    switch (evt.type) {
      case 'status':
        r.stepLabel = evt.label
        setRun({ ...r })
        break
      case 'ai_done':
      case 'preview':
        if (evt.content && !editing) setPreview(evt.content)
        break
      case 'final':
        r.done = true
        if (evt.content) setPreview(evt.content)
        break
      case 'error':
        setRunError(evt.error)
        break
      default:
        break
    }
  }

  function finishRefine(instruction) {
    setMessages((ms) => [
      ...ms,
      { refine: true, question: instruction, note: '미리보기를 수정했습니다.' },
    ])
    setRun(null)
    runRef.current = null
    setSending(false)
    setPreviewLive(false)
    abortRef.current = null
    showToast('미리보기를 수정했습니다.')
  }

  // ---------- 전송 ----------
  function send() {
    const text = input.trim()
    if (!text || sending) return

    if (mode === 'refine') {
      if (!online) {
        showToast('오프라인에서는 미리보기 수정(AI)이 안 돼요. 직접 편집은 가능합니다.')
        return
      }
      if (!preview) {
        showToast('먼저 결과물이 있어야 수정할 수 있어요.')
        return
      }
      setInput('')
      setSending(true)
      setPreviewLive(true)
      setRunError('')
      runRef.current = { refine: true, stepLabel: '요청을 반영하는 중…' }
      setRun({ ...runRef.current })
      abortRef.current = streamPost(
        '/api/refine',
        { conversation_id: activeId, current_doc: preview, instruction: text },
        (evt) => handleRefineEventWithDone(evt, text),
        (e) => {
          if (e.message === '401') doLogout()
          else setRunError('연결 오류가 발생했습니다.')
          finishRefine(text)
        }
      )
      return
    }

    // 새 질문
    if (!online) {
      queue.add({ question: text, conversation_id: activeId, ts: Date.now() })
      setQueueCount(queue.count())
      setInput('')
      showToast('오프라인 — 예약 질문함에 저장했어요. 연결되면 자동으로 시작됩니다.')
      return
    }
    setInput('')
    runAsk(text, activeId)
  }

  // 백엔드가 마지막에 보내는 'done' 이벤트를 감지해 마무리한다.
  function handleAskEventWithDone(evt) {
    if (evt.type === 'done') {
      finishAsk()
      return
    }
    if (evt.type === 'saved') {
      loadConversations()
      return
    }
    handleAskEvent(evt)
  }
  function handleRefineEventWithDone(evt, instruction) {
    if (evt.type === 'done') {
      finishRefine(instruction)
      return
    }
    handleRefineEvent(evt)
  }

  function handleBuildEvent(evt) {
    setBuild((b) => {
      if (!b) return b
      const nb = { ...b }
      if (evt.type === 'build_start') nb.buildId = evt.build_id
      else if (evt.type === 'log') nb.logs = [...nb.logs, evt.line]
      else if (evt.type === 'build_done') {
        nb.files = evt.files || []
        nb.hasZip = evt.zip
        nb.buildId = evt.build_id
        nb.done = true
        nb.active = false
      } else if (evt.type === 'error') nb.error = evt.error
      else if (evt.type === 'done') nb.active = false
      return nb
    })
  }

  function onBuild() {
    if (!preview || !online) {
      if (!online) showToast('오프라인 상태에서는 제작할 수 없어요.')
      return
    }
    if (
      !window.confirm(
        '이 내용 그대로 클로드 코드에게 제작을 맡길까요?\n\n전용 폴더에서만 작업하며, 끝나면 결과물을 zip으로 받을 수 있어요.'
      )
    )
      return
    const title = messages.find((m) => !m.refine)?.question || '오네시스 제작물'
    setBuild({ active: true, logs: [], buildId: null, files: [], done: false, error: '' })
    buildAbortRef.current = streamPost(
      '/api/build',
      { title, instruction: preview, conversation_id: activeId },
      handleBuildEvent,
      (e) => {
        if (e.message === '401') doLogout()
        setBuild((b) => (b ? { ...b, active: false, error: '연결 오류가 발생했습니다.' } : b))
      }
    )
  }

  function closeBuild() {
    if (buildAbortRef.current) {
      buildAbortRef.current()
      buildAbortRef.current = null
    }
    setBuild(null)
  }

  // 화면 미리보기(실제 UI 목업) 생성/수정
  async function onMakeMockup(instruction) {
    if (!online) {
      showToast('오프라인에서는 화면을 만들 수 없어요.')
      return
    }
    setMockupLoading(true)
    try {
      const r = await api.makeMockup({
        conversation_id: activeId,
        brief: instruction ? undefined : preview || '',
        instruction: instruction || undefined,
        current_html: instruction ? mockup : undefined,
      })
      setMockup(r.html || '')
    } catch (e) {
      if (e.message === '401') doLogout()
      else showToast('화면 생성에 실패했어요. 잠시 후 다시 시도하세요.')
    } finally {
      setMockupLoading(false)
    }
  }

  // ---------- 스플리터 드래그 ----------
  function startDrag(e) {
    e.preventDefault()
    const startX = e.clientX
    const startW = previewWidth
    function move(ev) {
      const dx = startX - ev.clientX
      const w = Math.min(Math.max(startW + dx, 300), Math.min(760, window.innerWidth - 380))
      setPreviewWidth(w)
    }
    function up() {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }

  // 다시 온라인이 되면: 상태 갱신 → 미리보기 동기화 → 목록 새로고침 → 예약 질문 처리
  onlineHandlerRef.current = () => {
    setOnline(true)
    if (!config) api.getConfig().then(setConfig).catch(() => {})
    flushPendingPreviews().finally(() => {
      loadConversations()
      setTimeout(maybeProcessQueue, 600)
    })
  }

  // ---------- 렌더 ----------
  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />
  }

  const showWelcome = messages.length === 0 && !run
  const canSend = input.trim() && !sending

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={deleteConversation}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={doLogout}
        open={sidebarOpen}
      />
      <div className={`backdrop ${sidebarOpen ? 'show' : ''}`} onClick={() => setSidebarOpen(false)} />

      <div className="main-area" data-mobile={mobileTab}>
        <div className="chat-pane">
          <div className="topbar">
            <button className="hamburger" onClick={() => setSidebarOpen(true)}>
              ☰
            </button>
            <div className="logo-badge" style={{ width: 26, height: 26, fontSize: 14 }}>
              O
            </div>
            <span style={{ fontWeight: 800 }}>오네시스</span>
          </div>

          {!online && <div className="offline-banner">오프라인 — 열람과 수정만 가능해요</div>}

          {showWelcome ? (
            <div className="welcome">
              <h1>오네시스</h1>
              <p>무엇이 궁금하세요? 3개의 AI가 토론해 최선의 답을 만들어 드려요.</p>
            </div>
          ) : (
            <div className="messages">
              <div className="messages-inner">
                {messages.map((m, i) =>
                  m.refine ? (
                    <div key={i}>
                      <div className="q-bubble">✎ {m.question}</div>
                      <div style={{ color: 'var(--muted)', fontSize: 13, margin: '4px 4px 16px' }}>
                        {m.note}
                      </div>
                    </div>
                  ) : (
                    <div key={i}>
                      <div className="q-bubble">{m.question}</div>
                      <MessageResult message={m} />
                    </div>
                  )
                )}

                {run && run.question && (
                  <div>
                    <div className="q-bubble">{run.question}</div>
                    <DebateProgress run={run} />
                  </div>
                )}
                {run && run.refine && (
                  <div className="debate-status">
                    <div className="spinner" />
                    <span>{run.stepLabel || '미리보기를 다듬는 중…'}</span>
                  </div>
                )}
                {runError && (
                  <div style={{ color: '#e5484d', fontSize: 14, margin: '8px 4px' }}>⚠ {runError}</div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}

          {/* 입력창 */}
          <div className="composer-wrap">
            <div className="composer">
              {queueCount > 0 && (
                <div className="queue-chip">
                  ⏳ 대기 중인 질문 {queueCount}개 — 연결되면 자동으로 시작해요
                </div>
              )}
              {preview && (
                <div className="mode-toggle">
                  <button className={mode === 'ask' ? 'on' : ''} onClick={() => setMode('ask')}>
                    새 질문
                  </button>
                  <button className={mode === 'refine' ? 'on' : ''} onClick={() => setMode('refine')}>
                    미리보기 고치기
                  </button>
                </div>
              )}
              <div className="input-row">
                <textarea
                  rows={1}
                  placeholder={
                    mode === 'refine'
                      ? '예) 기술 구성 부분을 더 쉽게 풀어서 써줘'
                      : online
                      ? '무엇이든 물어보세요…'
                      : '오프라인 — 질문을 쓰면 예약함에 저장돼요'
                  }
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value)
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px'
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                <button className="send-btn" onClick={send} disabled={!canSend}>
                  {sending ? '…' : '↑'}
                </button>
              </div>
              <div className="composer-hint">
                {sending
                  ? '토론이 진행 중입니다…'
                  : 'Enter 로 전송 · Shift+Enter 로 줄바꿈'}
              </div>
            </div>
          </div>

          <div className="mobile-tabs">
            <button className={mobileTab === 'chat' ? 'on' : ''} onClick={() => setMobileTab('chat')}>
              대화
            </button>
            <button className={mobileTab === 'preview' ? 'on' : ''} onClick={() => setMobileTab('preview')}>
              미리보기{preview ? ' •' : ''}
            </button>
          </div>
        </div>

        <div className="splitter" onMouseDown={startDrag} />

        <div className="preview-pane" style={{ width: previewWidth }}>
          <PreviewPanel
            content={preview}
            live={previewLive}
            editing={editing}
            onEditToggle={() => setEditing((v) => !v)}
            onChange={(v) => {
              setPreview(v)
              // 오프라인 편집 내용은 기기에 저장했다가 연결 시 자동 동기화
              if (!online && activeId) pendingPreview.set(activeId, v)
            }}
            onBuild={onBuild}
            onToast={showToast}
            mockup={mockup}
            mockupLoading={mockupLoading}
            onMakeMockup={onMakeMockup}
          />
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
      <BuildModal build={build} onClose={closeBuild} />
    </div>
  )
}
