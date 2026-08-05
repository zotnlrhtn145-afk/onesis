import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getToken, clearToken, streamPost, streamGet } from './api'
import { cache, queue, pendingPreview } from './offline'
import Login from './components/Login'
import Sidebar from './components/Sidebar'
import ThinkingLoader from './components/ThinkingLoader'
import MessageResult from './components/MessageResult'
import PreviewPanel from './components/PreviewPanel'
import BuildModal from './components/BuildModal'
import StatsView from './components/StatsView'
import Icon from './components/Icon'
import AiLogo from './components/AiLogo'

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
  const [elapsed, setElapsed] = useState(0) // 고민 중 경과 시간(초)
  const [selectedAis, setSelectedAis] = useState(null) // 질문에 쓸 AI 선택(null=아직 미설정→전체)
  const [mode, setMode] = useState('ask') // 'ask' | 'refine'
  const [sending, setSending] = useState(false)
  const abortRef = useRef(null)
  const textareaRef = useRef(null)

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [view, setView] = useState('home') // 'home' | 'plans' | 'stats'
  const [mobileTab, setMobileTab] = useState('chat')
  const [previewWidth, setPreviewWidth] = useState(440)
  const [previewOpen, setPreviewOpen] = useState(false) // 데스크톱 미리보기 패널 열림
  const userClosedPreviewRef = useRef(false) // 사용자가 직접 닫았으면 자동으로 다시 열지 않음
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
  const reconnectTimerRef = useRef(null) // 재접속 대기 타이머
  const reconnectAbortRef = useRef(null) // 재접속 스트림 중단 함수
  const runningIdsRef = useRef(new Set()) // 서버에서 진행 중인 대화 id들

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
    // 서버에서 아직 진행 중인 토론이 있으면 기억해 둔다(대화 열 때 자동 재접속용)
    try {
      const r = await api.runningIds()
      runningIdsRef.current = new Set(r.ids || [])
    } catch (_) {
      /* 무시 */
    }
  }, [])

  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        setConfig(cfg)
        // 처음엔 사용 가능한 AI 전체를 선택(기존과 동일한 3AI 토론)
        setSelectedAis((prev) =>
          prev != null ? prev : (cfg.participants || []).filter((p) => p.available).map((p) => p.id)
        )
      })
      .catch(() => {})
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

  // 고민 중 경과 시간(초) — 진행 중에만 1초마다 증가, 끝나면 0으로
  useEffect(() => {
    if (!sending) {
      setElapsed(0)
      return
    }
    setElapsed(0)
    const t = setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => clearInterval(t)
  }, [sending])

  // 전송/초기화로 입력이 비면 입력창 높이를 원래대로 되돌린다
  useEffect(() => {
    if (input === '' && textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [input])

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

  // 미리보기 패널 열기/닫기 (데스크톱=슬라이드 패널, 모바일=탭 전환)
  function openPreview() {
    if (window.innerWidth <= 900) setMobileTab('preview')
    else setPreviewOpen(true)
  }
  function closePreview() {
    userClosedPreviewRef.current = true
    if (window.innerWidth <= 900) setMobileTab('chat')
    else setPreviewOpen(false)
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
    const picked = conversations.find((c) => c.id === id)
    setView(picked?.kind === 'plan' ? 'plans' : 'home')
    setActiveId(id)
    setRun(null)
    setRunError('')
    setEditing(false)
    setPreviewOpen(false) // 기존 대화를 열 땐 채팅에 집중, 패널은 카드/버튼으로 열기
    userClosedPreviewRef.current = false
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
      // 이 대화의 토론이 서버에서 아직 진행 중이면 라이브로 이어서 본다.
      if (runningIdsRef.current.has(id)) {
        attachLive(id, conv.title || '')
      }
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
    setPreviewOpen(false)
    userClosedPreviewRef.current = false
    if (view === 'stats') setView('home') // 통계에서 새 대화 누르면 홈으로
  }

  // 섹션 이동(홈/기획안/통계). 홈·기획안은 각자의 새 대화로 시작한다.
  function navigate(v) {
    setSidebarOpen(false)
    if (v === view) return
    setView(v)
    if ((v === 'home' || v === 'plans') && !sending) {
      setActiveId(null)
      setMessages([])
      setRun(null)
      setRunError('')
      setPreview('')
      setMockup('')
      setPreviewLive(false)
      setEditing(false)
      setMode('ask')
      setMobileTab('chat')
      setPreviewOpen(false)
      userClosedPreviewRef.current = false
    }
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
        if (r) {
          r.convId = evt.id
          if (!r.question && evt.question) r.question = evt.question
        }
        if (evt.is_new) {
          setMockup('')
          setConversations((cs) => [
            { id: evt.id, title: evt.question.slice(0, 60), updated_at: '', kind: r?.kind || 'chat' },
            ...cs,
          ])
        }
        break
      case 'meta':
        r.participants = evt.participants
        r.is_build = evt.is_build
        r.single = evt.single || (evt.participants || []).length <= 1
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
        setRunError('') // 최종 도달 → 진행 중 떴던 일시적 오류 문구 해제
        // 기획안(plan) 대화일 때만 데스크톱에서 미리보기 패널을 한 번 자동으로 연다
        if (r?.kind === 'plan' && window.innerWidth > 900 && !userClosedPreviewRef.current) {
          setPreviewOpen(true)
        }
        break
      case 'error':
        setRunError(evt.error)
        break
      default:
        break
    }
    setRun({ ...r })
  }

  // 재접속 관련 타이머/스트림 정리
  function clearReconnect() {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (reconnectAbortRef.current) {
      reconnectAbortRef.current()
      reconnectAbortRef.current = null
    }
  }

  function finishAsk() {
    clearReconnect()
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

  // 스트림이 끊겼을 때: 서버 토론은 계속 진행 중이므로 라이브 스트림으로 다시 붙는다.
  function onAskStreamError(e) {
    if (e.message === '401') {
      doLogout()
      finishAsk()
      return
    }
    const r = runRef.current
    if (r && r.convId) {
      // 대화가 이미 시작됨 → 서버에서 계속 진행 중. 재접속을 시도한다.
      r.reconnecting = true
      setRun({ ...r })
      abortRef.current = null
      scheduleReconnect(r.convId, 1200)
    } else {
      // 아직 시작 전 초기 연결 실패 → 실제 오류(결과는 없음)
      setRunError('연결 오류가 발생했습니다.')
      finishAsk()
    }
  }

  function scheduleReconnect(cid, delay) {
    if (reconnectTimerRef.current || reconnectAbortRef.current) return
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null
      tryReconnect(cid)
    }, delay)
  }

  // 진행 중인 토론에 다시 붙기(라이브 스트림). 실패하면 잠시 후 재시도.
  function tryReconnect(cid) {
    if (!cid || !runRef.current || !runRef.current.reconnecting) return
    if (reconnectAbortRef.current) return
    if (!navigator.onLine) {
      scheduleReconnect(cid, 3000)
      return
    }
    reconnectAbortRef.current = streamGet(
      `/api/conversations/${cid}/live`,
      (evt) => {
        if (evt.type === 'no_job') {
          // 서버에 진행 중 작업 없음(이미 끝나 저장됐거나 서버 재시작) → 저장본을 불러온다
          clearReconnect()
          reloadFinished(cid)
          return
        }
        const rr = runRef.current
        if (rr && rr.reconnecting) {
          rr.reconnecting = false
          setRunError('') // 재접속 성공 → 오류 문구 해제
        }
        handleAskEventWithDone(evt)
      },
      () => {
        // 재접속 실패 → 잠시 후 다시 시도
        reconnectAbortRef.current = null
        if (runRef.current && runRef.current.reconnecting) scheduleReconnect(cid, 3000)
      }
    )
  }

  // 진행 중이던 작업이 이미 끝나 서버 메모리에서 사라진 경우: 저장된 결과를 불러온다.
  async function reloadFinished(cid) {
    try {
      const conv = await api.getConversation(cid)
      setActiveId(cid)
      setMessages(
        (conv.messages || []).map((m) => ({
          question: m.question,
          final: m.final,
          transcript: m.transcript,
          is_build: m.is_build,
        }))
      )
      if (conv.preview) setPreview(conv.preview)
      setMockup(conv.mockup || '')
    } catch (_) {
      /* 무시 */
    }
    runRef.current = null
    setRun(null)
    setSending(false)
    setPreviewLive(false)
    busyRef.current = false
    loadConversations()
    setTimeout(maybeProcessQueue, 400)
  }

  function newRun(question, conversationId, aiIds) {
    const sel = aiIds && aiIds.length ? aiIds : null
    const parts = (config?.participants || []).filter(
      (p) => p.available && (!sel || sel.includes(p.id))
    )
    return {
      question,
      convId: conversationId || null,
      participants: parts,
      single: parts.length <= 1,
      currentStep: null,
      stepLabel: '',
      completed: [],
      aiStatus: {},
      finalMsg: null,
      reconnecting: false,
    }
  }

  function runAsk(question, conversationId, aiIds, kind) {
    const ais = aiIds !== undefined ? aiIds : selectedAis
    const k = kind || (view === 'plans' ? 'plan' : 'chat')
    clearReconnect()
    busyRef.current = true
    setSending(true)
    setPreviewLive(true)
    setRunError('')
    setMobileTab('chat')
    setActiveId(conversationId || null)
    runRef.current = newRun(question, conversationId, ais)
    runRef.current.kind = k
    setRun({ ...runRef.current })
    abortRef.current = streamPost(
      '/api/ask',
      { question, conversation_id: conversationId, ai_ids: ais, kind: k },
      handleAskEventWithDone,
      onAskStreamError
    )
  }

  // 이미 진행 중인(서버) 토론이 있는 대화를 열 때: 라이브로 이어서 본다.
  function attachLive(cid, title) {
    clearReconnect()
    busyRef.current = true
    setSending(true)
    setPreviewLive(true)
    setRunError('')
    setActiveId(cid)
    runRef.current = newRun(title || '', cid)
    setRun({ ...runRef.current })
    reconnectAbortRef.current = streamGet(
      `/api/conversations/${cid}/live`,
      (evt) => {
        if (evt.type === 'no_job') {
          clearReconnect()
          reloadFinished(cid)
          return
        }
        handleAskEventWithDone(evt)
      },
      () => {
        reconnectAbortRef.current = null
        if (runRef.current) {
          runRef.current.reconnecting = true
          setRun({ ...runRef.current })
          scheduleReconnect(cid, 3000)
        }
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
    runAsk(item.question, item.conversation_id || null, item.ai_ids, item.kind)
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
    const kind = view === 'plans' ? 'plan' : 'chat'
    if (!online) {
      queue.add({ question: text, conversation_id: activeId, ai_ids: selectedAis, kind, ts: Date.now() })
      setQueueCount(queue.count())
      setInput('')
      showToast('오프라인 — 예약 질문함에 저장했어요. 연결되면 자동으로 시작됩니다.')
      return
    }
    setInput('')
    runAsk(text, activeId, selectedAis, kind)
  }

  // 질문에 참여할 AI 선택 토글(최소 1개는 유지)
  function toggleAi(id) {
    setSelectedAis((prev) => {
      const cur = prev || []
      if (cur.includes(id)) {
        if (cur.length <= 1) return cur // 최소 1개는 남긴다
        return cur.filter((x) => x !== id)
      }
      const order = (config?.participants || []).map((p) => p.id)
      return order.filter((x) => cur.includes(x) || x === id)
    })
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

  // 승인한 화면 미리보기(디자인) 그대로 실제 화면을 제작
  function onBuildFromMockup() {
    if (!online) {
      showToast('오프라인 상태에서는 제작할 수 없어요.')
      return
    }
    if (!mockup) {
      showToast('먼저 마음에 드는 화면 미리보기를 만들어 주세요.')
      return
    }
    if (
      !window.confirm(
        '지금 보이는 이 화면 디자인 그대로,\n기획안의 기능을 담아 실제로 동작하는 화면을 만들어요.\n\n' +
          '클로드 코드가 전용 폴더에서만 제작하고, 끝나면 결과물을 zip으로 받을 수 있어요.'
      )
    )
      return
    const title = messages.find((m) => !m.refine)?.question || '오네시스 제작물'
    setBuild({ active: true, logs: [], buildId: null, files: [], done: false, error: '' })
    buildAbortRef.current = streamPost(
      '/api/build',
      { title, instruction: preview || '', design_html: mockup, conversation_id: activeId },
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
      // 원래 사용자의 디자인 요청(첫 질문)까지 함께 넘겨 톤·레퍼런스가 묻히지 않게 한다.
      const firstQ = messages.find((m) => !m.refine)?.question || ''
      const briefText = [firstQ && `원래 요청: ${firstQ}`, preview || '']
        .filter(Boolean)
        .join('\n\n')
      const r = await api.makeMockup({
        conversation_id: activeId,
        brief: instruction ? undefined : briefText,
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
    // 진행 중이던 토론이 끊겼다면 즉시 재접속을 시도(대기 타이머를 앞당김)
    if (runRef.current && runRef.current.reconnecting && !reconnectAbortRef.current) {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      tryReconnect(runRef.current.convId)
    }
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
  // 가장 최근 '결과' 메시지 인덱스(그 아래에 미리보기 열기 카드를 붙인다)
  let lastResultIdx = -1
  for (let i = messages.length - 1; i >= 0; i--) {
    if (!messages[i].refine) {
      lastResultIdx = i
      break
    }
  }

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
        view={view}
        onNavigate={navigate}
      />
      <div className={`backdrop ${sidebarOpen ? 'show' : ''}`} onClick={() => setSidebarOpen(false)} />

      {view === 'stats' && <StatsView onMenu={() => setSidebarOpen(true)} />}

      <div
        className="main-area"
        data-mobile={mobileTab}
        data-notabs={view !== 'plans' ? 'true' : undefined}
        style={view === 'stats' ? { display: 'none' } : undefined}
      >
        <div className="chat-pane">
          <div className="topbar">
            <button className="hamburger" onClick={() => setSidebarOpen(true)}>
              <Icon name="menu" size={22} />
            </button>
            <div className="logo-badge" style={{ width: 26, height: 26, fontSize: 14 }}>
              O
            </div>
            <span style={{ fontWeight: 800 }}>오네시스</span>
          </div>

          {preview && !previewOpen && view === 'plans' && (
            <button className="preview-toggle-pill" onClick={openPreview} title="미리보기 패널 열기">
              <Icon name="panel" size={16} />
              미리보기
            </button>
          )}

          {!online && <div className="offline-banner">오프라인 — 열람과 수정만 가능해요</div>}

          {showWelcome ? (
            <div className="welcome">
              <h1>{view === 'plans' ? '기획안 만들기' : '오네시스'}</h1>
              <p>
                {view === 'plans'
                  ? '무엇을 만들까요? 3개의 AI가 환경·화면·기능까지 상세한 기획안을 만들어 드려요.'
                  : '무엇이 궁금하세요? 3개의 AI가 토론해 최선의 답을 만들어 드려요.'}
              </p>
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
                      {i === lastResultIdx && preview && view === 'plans' && (
                        <button className="artifact-card" onClick={openPreview}>
                          <span className="artifact-ic">
                            <Icon name="doc" size={22} />
                          </span>
                          <span className="artifact-tx">
                            <b>기획안 · 화면 미리보기</b>
                            <small>패널에서 보기 · 편집 · 화면 만들기 →</small>
                          </span>
                        </button>
                      )}
                    </div>
                  )
                )}

                {run && run.question && (
                  <div>
                    <div className="q-bubble">{run.question}</div>
                    {run.reconnecting && (
                      <div className="reconnect-note">
                        <div className="spinner" />
                        <span>연결이 잠시 끊겼어요. 토론은 서버에서 계속 진행 중이고, 다시 연결하고 있어요…</span>
                      </div>
                    )}
                    <ThinkingLoader
                      count={(run.participants || []).length}
                      elapsed={elapsed}
                    />
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
              {preview && view === 'plans' && (
                <div className="mode-toggle">
                  <button className={mode === 'ask' ? 'on' : ''} onClick={() => setMode('ask')}>
                    새 질문
                  </button>
                  <button className={mode === 'refine' ? 'on' : ''} onClick={() => setMode('refine')}>
                    미리보기 고치기
                  </button>
                </div>
              )}
              {mode === 'ask' && (config?.participants || []).some((p) => p.available) && (
                <div className="ai-select">
                  <span className="ai-select-label">질문할 AI</span>
                  {config.participants
                    .filter((p) => p.available)
                    .map((p) => {
                      const on = (selectedAis || []).includes(p.id)
                      return (
                        <button
                          key={p.id}
                          type="button"
                          className={`ai-pill logo-only ${on ? 'on' : ''}`}
                          style={{ '--dot': p.color }}
                          onClick={() => toggleAi(p.id)}
                          title={`${p.name} ${on ? '· 켜짐 (끄려면 클릭)' : '· 꺼짐 (켜려면 클릭)'}`}
                          aria-label={p.name}
                        >
                          <AiLogo id={p.id} size={22} />
                        </button>
                      )
                    })}
                  <span className="ai-select-hint">
                    {(selectedAis || []).length <= 1
                      ? '· 단독 답변'
                      : `· ${(selectedAis || []).length}개 AI 토론`}
                  </span>
                </div>
              )}
              <div className="input-row">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  placeholder={
                    mode === 'refine'
                      ? '예) 기술 구성 부분을 더 쉽게 풀어서 써줘'
                      : !online
                      ? '오프라인 — 질문을 쓰면 예약함에 저장돼요'
                      : view === 'plans'
                      ? '무엇을 만들지 설명해 주세요… (예: 헬스장 회원관리 웹앱)'
                      : '무엇이든 물어보세요…'
                  }
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value)
                    e.target.style.height = 'auto'
                    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px'
                  }}
                  onKeyDown={(e) => {
                    // Enter = 줄바꿈, Shift+Enter = 전송
                    if (e.key === 'Enter' && e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                />
                <button className="send-btn" onClick={send} disabled={!canSend} title="보내기">
                  {sending ? '…' : <Icon name="send" size={18} strokeWidth={2} />}
                </button>
              </div>
              <div className="composer-hint">
                {sending
                  ? '토론이 진행 중입니다…'
                  : 'Shift+Enter 로 전송 · Enter 로 줄바꿈 · 모바일은 ↑ 버튼'}
              </div>
            </div>
          </div>

        </div>

        {previewOpen && <div className="splitter" onMouseDown={startDrag} />}

        <div
          className={`preview-pane ${previewOpen ? 'open' : ''}`}
          style={{ width: previewOpen ? previewWidth : 0 }}
        >
          <div className="preview-inner" style={{ width: previewWidth }}>
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
              onBuildFromMockup={onBuildFromMockup}
              onToast={showToast}
              onClose={closePreview}
              mockup={mockup}
              mockupLoading={mockupLoading}
              onMakeMockup={onMakeMockup}
            />
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

      {toast && <div className="toast">{toast}</div>}
      <BuildModal build={build} onClose={closeBuild} />
    </div>
  )
}
