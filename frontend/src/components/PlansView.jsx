import Icon from './Icon'

export default function PlansView({ conversations, onSelect, onNew, onMenu }) {
  return (
    <div className="plans-view">
      <div className="topbar">
        <button className="hamburger" onClick={onMenu}>
          <Icon name="menu" size={22} />
        </button>
        <div className="logo-badge" style={{ width: 26, height: 26, fontSize: 14 }}>
          O
        </div>
        <span style={{ fontWeight: 700 }}>기획안</span>
      </div>

      <div className="plans-inner">
        <div className="plans-head">
          <h1 className="plans-title">기획안</h1>
          <button className="plans-new" onClick={onNew}>
            <Icon name="plus" size={16} />
            새로 만들기
          </button>
        </div>
        <p className="plans-sub">지금까지 만든 기획안이에요. 눌러서 이어서 보거나 다듬을 수 있어요.</p>

        {conversations.length === 0 ? (
          <div className="plans-empty">
            <Icon name="doc" size={30} strokeWidth={1.4} />
            <p>아직 만든 기획안이 없어요.</p>
            <button className="plans-new" onClick={onNew}>
              <Icon name="plus" size={16} />
              새로 만들기
            </button>
          </div>
        ) : (
          <div className="plans-grid">
            {conversations.map((c) => (
              <button key={c.id} className="plan-card" onClick={() => onSelect(c.id)}>
                <span className="plan-ic">
                  <Icon name="doc" size={20} />
                </span>
                <span className="plan-title-t">{c.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
