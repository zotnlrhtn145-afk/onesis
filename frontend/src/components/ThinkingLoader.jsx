// 토론 진행 중 표시: 단계 대신 로고가 은은하게 도는 로딩 + "몇 분째 고민 중"
export default function ThinkingLoader({ count = 0, elapsed = 0 }) {
  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  const timeText = mins > 0 ? `${mins}분 ${secs}초째` : `${secs}초째`
  const title =
    count > 1 ? `${count}명의 AI가 의논하고 있어요` : '답변을 준비하고 있어요'

  return (
    <div className="thinking">
      <div className="thinking-logo">
        <span className="thinking-ring" />
        <span className="thinking-core">O</span>
      </div>
      <div className="thinking-text">
        <div className="thinking-title">{title}</div>
        <div className="thinking-time">
          {timeText} 고민 중<span className="dots" />
        </div>
      </div>
    </div>
  )
}
