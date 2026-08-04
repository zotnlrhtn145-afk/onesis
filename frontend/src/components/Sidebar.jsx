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
        새 대화
      </button>

      <div className="conv-list">
        {conversations.length === 0 && <div className="conv-empty">아직 기획안이 없어요.</div>}
        {conversations.map((c) => (
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
