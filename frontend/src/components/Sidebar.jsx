import Icon from './Icon'

const NAV = [
  { key: 'home', label: '홈', icon: 'home' },
  { key: 'plans', label: '기획안', icon: 'plan' },
  { key: 'stats', label: '통계', icon: 'chart' },
]

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
  view,
  onNavigate,
}) {
  const wantKind = view === 'plans' ? 'plan' : 'chat'
  const filtered =
    view === 'stats' ? [] : conversations.filter((c) => (c.kind || 'chat') === wantKind)
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-head">
        <div className="logo-badge">O</div>
        <span className="logo-text">오네시스</span>
      </div>

      <nav className="side-nav">
        {NAV.map((n) => (
          <button
            key={n.key}
            className={`side-nav-item ${view === n.key ? 'active' : ''}`}
            onClick={() => onNavigate(n.key)}
          >
            <Icon name={n.icon} size={19} />
            <span>{n.label}</span>
          </button>
        ))}
      </nav>

      <button className="new-chat-btn" onClick={onNew}>
        <Icon name="plus" size={17} />
        {view === 'plans' ? '새 기획안' : '새 대화'}
      </button>

      <div className="conv-list">
        {filtered.length === 0 && (
          <div className="conv-empty">
            {view === 'plans' ? '아직 기획안이 없어요.' : '아직 대화가 없어요.'}
          </div>
        )}
        {filtered.map((c) => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId && view !== 'stats' ? 'active' : ''}`}
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
              <Icon name="close" size={14} strokeWidth={2} />
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-foot">
        <button className="icon-btn" onClick={onToggleTheme}>
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16} />
          {theme === 'dark' ? '밝게' : '어둡게'}
        </button>
        <button className="icon-btn" onClick={onLogout} title="로그아웃" style={{ marginLeft: 'auto' }}>
          <Icon name="logout" size={16} />
        </button>
      </div>
    </aside>
  )
}
