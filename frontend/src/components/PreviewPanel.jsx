import { useState } from 'react'
import Markdown from './Markdown'

export default function PreviewPanel({
  content,
  live,
  editing,
  onEditToggle,
  onChange,
  onBuildFromMockup,
  onToast,
  onClose,
  mockup,
  mockupLoading,
  onMakeMockup,
}) {
  const [tab, setTab] = useState('plan') // 'plan' | 'screen'
  const [device, setDevice] = useState('mobile') // 'mobile' | 'desktop'
  const [fix, setFix] = useState('')

  function copy() {
    navigator.clipboard.writeText(content || '').then(
      () => onToast('복사했습니다.'),
      () => onToast('복사에 실패했습니다.')
    )
  }
  function copyHtml() {
    navigator.clipboard.writeText(mockup || '').then(
      () => onToast('화면 HTML을 복사했습니다.'),
      () => onToast('복사에 실패했습니다.')
    )
  }
  function sendFix() {
    const t = fix.trim()
    if (!t || mockupLoading) return
    setFix('')
    onMakeMockup(t)
  }

  return (
    <>
      <div className="preview-head">
        <div className="pv-tabs">
          <button className={tab === 'plan' ? 'on' : ''} onClick={() => setTab('plan')}>
            기획안
          </button>
          <button className={tab === 'screen' ? 'on' : ''} onClick={() => setTab('screen')}>
            화면 미리보기
          </button>
        </div>

        {tab === 'plan' ? (
          <>
            {live && (
              <span className="live-badge">
                <span className="pulse" /> 실시간
              </span>
            )}
            <button className="pv-btn" onClick={onEditToggle} disabled={!content}>
              {editing ? '완료' : '편집'}
            </button>
            <button className="pv-btn" onClick={copy} disabled={!content}>
              복사
            </button>
          </>
        ) : (
          <>
            <div className="device-toggle" title="화면 크기">
              <button className={device === 'mobile' ? 'on' : ''} onClick={() => setDevice('mobile')}>
                📱
              </button>
              <button className={device === 'desktop' ? 'on' : ''} onClick={() => setDevice('desktop')}>
                💻
              </button>
            </div>
            {mockup && (
              <button
                className="pv-btn"
                onClick={() => onMakeMockup()}
                disabled={mockupLoading || !content}
                title="기획안 기준으로 새로 만들기"
              >
                새로 만들기
              </button>
            )}
            <button className="pv-btn" onClick={copyHtml} disabled={!mockup}>
              코드 복사
            </button>
            <button
              className="pv-btn primary"
              onClick={onBuildFromMockup}
              disabled={!mockup}
              title="지금 이 화면 그대로 실제로 만들기"
            >
              이 화면 그대로 제작하기
            </button>
          </>
        )}
        {onClose && (
          <button className="pv-close" onClick={onClose} title="패널 닫기" aria-label="패널 닫기">
            ✕
          </button>
        )}
      </div>

      <div className={'preview-body' + (tab === 'screen' ? ' screen' : '')}>
        {tab === 'plan' ? (
          !content ? (
            <div className="preview-empty">
              질문을 보내면 여기에 결과물(기획안)이<br />실시간으로 만들어집니다.
            </div>
          ) : editing ? (
            <textarea value={content} onChange={(e) => onChange(e.target.value)} />
          ) : (
            <Markdown>{content}</Markdown>
          )
        ) : !mockup ? (
          <div className="screen-make">
            {mockupLoading ? (
              <div className="screen-loading">
                <span className="spinner" /> 화면을 그리는 중이에요…
              </div>
            ) : !content ? (
              <div className="preview-empty">
                먼저 기획안이 있어야<br />화면을 만들 수 있어요.
              </div>
            ) : (
              <>
                <p>기획안을 바탕으로 실제 사용자 화면을 미리 그려볼게요.</p>
                <button className="pv-btn primary big" onClick={() => onMakeMockup()}>
                  🎨 이 기획안으로 화면 만들기
                </button>
              </>
            )}
          </div>
        ) : (
          <div className={'screen-stage ' + device}>
            <div className="screen-wrap">
              <iframe
                title="화면 미리보기"
                className="screen-frame"
                sandbox="allow-scripts"
                srcDoc={mockup}
              />
            </div>
            {mockupLoading && (
              <div className="screen-overlay">
                <span className="spinner" /> 고치는 중…
              </div>
            )}
          </div>
        )}
      </div>

      {tab === 'screen' && mockup && (
        <div className="fix-bar">
          <input
            placeholder="이 화면 이렇게 고쳐줘 (예: 버튼을 크게, 상단을 파란색으로)"
            value={fix}
            onChange={(e) => setFix(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') sendFix()
            }}
            disabled={mockupLoading}
          />
          <button onClick={sendFix} disabled={mockupLoading || !fix.trim()}>
            고치기
          </button>
        </div>
      )}
    </>
  )
}
