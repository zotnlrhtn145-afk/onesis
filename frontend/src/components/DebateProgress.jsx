const STEPS = [
  { key: 'initial', label: '1차 답변' },
  { key: 'critique1', label: '토론 1바퀴' },
  { key: 'revise1', label: '답변 수정' },
  { key: 'critique2', label: '토론 2바퀴' },
  { key: 'final', label: '최종 정리' },
]

export default function DebateProgress({ run }) {
  const { stepLabel, currentStep, completed = [], participants = [], aiStatus = {} } = run
  const single = run.single || participants.length <= 1

  return (
    <div className="debate">
      <div className="debate-status">
        <div className="spinner" />
        <span>{stepLabel || (single ? '답변을 준비합니다…' : '토론을 시작합니다…')}</span>
      </div>

      {!single && (
        <div className="steps">
          {STEPS.map((s) => {
            const isActive = s.key === currentStep
            const isDone = completed.includes(s.key)
            return (
              <span
                key={s.key}
                className={`step-chip ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
              >
                {isDone ? '✓ ' : ''}
                {s.label}
              </span>
            )
          })}
        </div>
      )}

      <div
        className="ai-cards"
        style={{ gridTemplateColumns: `repeat(${Math.min(participants.length || 1, 3)}, 1fr)` }}
      >
        {participants.map((p) => {
          const st = aiStatus[p.id] || { status: 'wait' }
          return (
            <div className="ai-card" key={p.id} style={{ '--dot': p.color }}>
              <div className="head">
                <span className="ai-dot" />
                {p.name}
              </div>
              <div className={`state ${st.status === 'error' ? 'error' : ''} ${st.status === 'done' ? 'done' : ''}`}>
                {st.status === 'running' && (
                  <>
                    <span className="spinner" style={{ width: 12, height: 12 }} />
                    <span className="dots">작성 중</span>
                  </>
                )}
                {st.status === 'done' && <>✓ 완료</>}
                {st.status === 'error' && <>⚠ {st.error || '오류'}</>}
                {(!st.status || st.status === 'wait') && <>대기 중</>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
