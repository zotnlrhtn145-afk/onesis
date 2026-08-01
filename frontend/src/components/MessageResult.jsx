import Markdown from './Markdown'

const STAGE_LABELS = {
  initial: '1차 답변',
  critique1: '토론 1바퀴 · 서로에 대한 지적',
  revise1: '수정된 답변',
  critique2: '토론 2바퀴 · 재검토',
}

export default function MessageResult({ message }) {
  const { final, transcript = {} } = message
  const participants = transcript.participants || []
  const nameOf = (id) => participants.find((p) => p.id === id)?.name || id
  const colorOf = (id) => participants.find((p) => p.id === id)?.color || 'var(--accent)'

  const stages = ['initial', 'critique1', 'revise1', 'critique2'].filter(
    (s) => transcript[s] && Object.keys(transcript[s]).length > 0
  )

  return (
    <div className="result">
      <div className="final-card">
        <Markdown>{final}</Markdown>
      </div>

      {stages.length > 0 && (
        <details className="transcript">
          <summary>토론 과정 보기</summary>
          {stages.map((stage) => (
            <div className="stage-block" key={stage}>
              <div className="stage-title">{STAGE_LABELS[stage]}</div>
              {Object.entries(transcript[stage]).map(([aiId, val]) => {
                const isErr = val && typeof val === 'object' && 'error' in val
                return (
                  <div
                    className={`transcript-ai ${isErr ? 'err' : ''}`}
                    key={aiId}
                    style={{ '--dot': colorOf(aiId) }}
                  >
                    <div className="name">{nameOf(aiId)}</div>
                    {isErr ? (
                      <div style={{ color: '#e5484d', fontSize: 13 }}>⚠ {val.error}</div>
                    ) : (
                      <Markdown>{val}</Markdown>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </details>
      )}
    </div>
  )
}
