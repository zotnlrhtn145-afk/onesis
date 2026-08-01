export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  theme,
  onToggleTheme,
  onLogout,
  open,
}) {
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-head">
        <div className="logo-badge">O</div>
        <span className="logo-text">오네시스</span>
      </div>
      <button className="new-chat-btn" onClick={onNew}>
        <span style={{ fontSize: 18, lineHeight: 1 }}>＋</span> 새 대화
      </button>
      <div className="conv-list">
        {conversations.length === 0 && (
          <div style={{ padding: '12px', color: 'var(--muted)', fontSize: 13 }}>
            아직 대화가 없어요.
          </div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="title">{c.title}</span>
            <button
              className="del"
              title="삭제"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(c.id)
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <div className="sidebar-foot">
        <button className="icon-btn" onClick={onToggleTheme}>
          {theme === 'dark' ? '☀️ 밝게' : '🌙 어둡게'}
        </button>
        <button className="icon-btn" onClick={onLogout} style={{ marginLeft: 'auto' }}>
          로그아웃
        </button>
      </div>
    </aside>
  )
}
