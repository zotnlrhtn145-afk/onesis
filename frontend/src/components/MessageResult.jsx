import Markdown from './Markdown'

const STAGE_LABELS = {
  initial: '1차 제안',
  critique1: '1차 의견 주고받기',
  revise1: '1차 수정안',
  critique2: '2차 의견 주고받기',
}

const PART_LABELS = { idea: '아이디어', design: '디자인', plan: '기획', build: '제작·코딩' }

export default function MessageResult({ message }) {
  const { final, transcript = {} } = message
  const participants = transcript.participants || []
  const nameOf = (id) => participants.find((p) => p.id === id)?.name || id
  const colorOf = (id) => participants.find((p) => p.id === id)?.color || 'var(--accent)'

  const stages = ['initial', 'critique1', 'revise1', 'critique2'].filter(
    (s) => transcript[s] && Object.keys(transcript[s]).length > 0
  )

  const partLabel = PART_LABELS[transcript.part] || null
  const lead = transcript.lead
  const badge = partLabel
    ? lead
      ? `${partLabel} · ${nameOf(lead)} 주도`
      : `${partLabel} · 다같이`
    : null

  return (
    <div className="result">
      {badge && <div className="part-badge">{badge}</div>}
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
