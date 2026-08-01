import { useState } from 'react'
import Markdown from './Markdown'

export default function PreviewPanel({ content, live, editing, onEditToggle, onChange, onBuild, onToast }) {
  const [width] = useState(null)

  function copy() {
    navigator.clipboard.writeText(content || '').then(
      () => onToast('복사했습니다.'),
      () => onToast('복사에 실패했습니다.')
    )
  }

  return (
    <>
      <div className="preview-head">
        <span className="label">
          미리보기
          {live && (
            <span className="live-badge">
              <span className="pulse" /> 실시간
            </span>
          )}
        </span>
        <button className="pv-btn" onClick={onEditToggle} disabled={!content}>
          {editing ? '완료' : '편집'}
        </button>
        <button className="pv-btn" onClick={copy} disabled={!content}>
          복사
        </button>
        <button className="pv-btn primary" onClick={onBuild} disabled={!content}>
          이대로 제작하기
        </button>
      </div>
      <div className="preview-body">
        {!content ? (
          <div className="preview-empty">
            질문을 보내면 여기에 결과물(기획안)이<br />실시간으로 만들어집니다.
          </div>
        ) : editing ? (
          <textarea value={content} onChange={(e) => onChange(e.target.value)} />
        ) : (
          <Markdown>{content}</Markdown>
        )}
      </div>
    </>
  )
}
