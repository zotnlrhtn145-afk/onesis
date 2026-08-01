import { useEffect, useRef } from 'react'
import { getToken } from '../api'

export default function BuildModal({ build, onClose }) {
  const logRef = useRef(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [build?.logs])

  if (!build) return null
  const { active, logs = [], files = [], done, error, buildId, hasZip } = build

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="build-modal" onClick={(e) => e.stopPropagation()}>
        <div className="build-head">
          <span className="label">
            {active ? (
              <>
                <span className="spinner" /> 제작 중…
              </>
            ) : done ? (
              '✅ 제작 완료'
            ) : (
              '제작'
            )}
          </span>
          <button className="pv-btn" onClick={onClose}>
            닫기
          </button>
        </div>

        <div className="build-log" ref={logRef}>
          {logs.length === 0 && <div style={{ color: 'var(--muted)' }}>준비 중…</div>}
          {logs.map((l, i) => (
            <div className="log-line" key={i}>
              {l}
            </div>
          ))}
          {error && <div className="log-line err">⚠ {error}</div>}
        </div>

        {done && (
          <div className="build-foot">
            <div className="files">
              <div className="files-title">만들어진 파일 ({files.length}개)</div>
              <ul>
                {files.slice(0, 40).map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
                {files.length > 40 && <li>… 외 {files.length - 40}개</li>}
              </ul>
            </div>
            {hasZip && buildId && (
              <a
                className="pv-btn primary download"
                href={`/api/build/${buildId}/download?token=${encodeURIComponent(getToken())}`}
              >
                ⬇ 결과물 zip 다운로드
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
