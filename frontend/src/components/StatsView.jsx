import { useState } from 'react'
import { api } from '../api'
import Markdown from './Markdown'

const PICKS = ['삼성전자', '애플', '엔비디아', '테슬라', '비트코인', '이더리움', '금', 'S&P500']

function fmtNum(n) {
  if (n == null || isNaN(n)) return '—'
  const abs = Math.abs(n)
  const d = abs >= 1000 ? 0 : abs >= 1 ? 2 : 4
  return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
}
function fmtPct(n) {
  if (n == null || isNaN(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toFixed(1) + '%'
}
function cls(n) {
  if (n == null || isNaN(n)) return ''
  return n > 0 ? 'pos' : n < 0 ? 'neg' : ''
}

function positionLabel(p) {
  if (p == null) return ''
  if (p >= 80) return `역사적 고가권 (상위 ${(100 - p).toFixed(0)}%)`
  if (p <= 20) return `역사적 저가권 (하위 ${p.toFixed(0)}%)`
  return '역사적 중간 구간'
}

export default function StatsView({ onMenu }) {
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [err, setErr] = useState('')
  const [explain, setExplain] = useState('')
  const [explaining, setExplaining] = useState(false)

  async function run(query) {
    const text = (query ?? q).trim()
    if (!text || loading) return
    setLoading(true)
    setErr('')
    setStats(null)
    setExplain('')
    try {
      const r = await api.marketStats(text)
      setStats(r.stats)
      // 이어서 AI 해석
      setExplaining(true)
      api
        .marketExplain(r.stats.symbol)
        .then((e) => setExplain(e.text || ''))
        .catch(() => setExplain(''))
        .finally(() => setExplaining(false))
    } catch (e) {
      setErr(e.message === '404' ? '자산을 찾지 못했어요.' : e.message || '통계를 가져오지 못했어요.')
    } finally {
      setLoading(false)
    }
  }

  const s = stats

  return (
    <div className="stats-view">
      <div className="topbar">
        <button className="hamburger" onClick={onMenu}>
          ☰
        </button>
        <div className="logo-badge" style={{ width: 26, height: 26, fontSize: 14 }}>
          O
        </div>
        <span style={{ fontWeight: 800 }}>시장 통계</span>
      </div>
      <div className="stats-inner">
        <h1 className="stats-title">📊 시장 통계</h1>
        <p className="stats-sub">
          자산 이름이나 티커를 입력하면, 실제 과거 데이터로 <b>저점·고점·낙폭·백분위</b> 등을 계산해 드려요.
        </p>

        <div className="stats-search">
          <input
            placeholder="예) 삼성전자, 애플, 비트코인, AAPL, 금…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
          />
          <button onClick={() => run()} disabled={loading || !q.trim()}>
            {loading ? '계산 중…' : '통계 보기'}
          </button>
        </div>
        <div className="stats-picks">
          {PICKS.map((p) => (
            <button key={p} onClick={() => { setQ(p); run(p) }} disabled={loading}>
              {p}
            </button>
          ))}
        </div>

        {err && <div className="stats-err">⚠ {err}</div>}

        {loading && (
          <div className="stats-loading">
            <span className="spinner" /> 실제 데이터를 가져와 계산하고 있어요…
          </div>
        )}

        {s && (
          <>
            <div className="stats-head-card">
              <div className="sh-left">
                <div className="sh-name">
                  {s.name} <span className="sh-market">{s.market}</span>
                </div>
                <div className="sh-price">{fmtNum(s.current)}</div>
                <div className="sh-asof">
                  기준일 {s.as_of} · <b>{s.data_points.toLocaleString()}일</b> 축적 ({s.history_start}~, {s.years}년)
                </div>
              </div>
            </div>

            <div className="stats-section-title">지금 어디쯤인가요?</div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="sc-label">역대 고점 대비</div>
                <div className={`sc-val ${cls(s.from_ath)}`}>{fmtPct(s.from_ath)}</div>
                <div className="sc-sub">고점 {fmtNum(s.ath)}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">역대 저점 대비</div>
                <div className={`sc-val ${cls(s.from_atl)}`}>{fmtPct(s.from_atl)}</div>
                <div className="sc-sub">저점 {fmtNum(s.atl)}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">52주 고점 대비</div>
                <div className={`sc-val ${cls(s.from_high_52w)}`}>{fmtPct(s.from_high_52w)}</div>
                <div className="sc-sub">고점 {fmtNum(s.high_52w)}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">52주 저점 대비</div>
                <div className={`sc-val ${cls(s.from_low_52w)}`}>{fmtPct(s.from_low_52w)}</div>
                <div className="sc-sub">저점 {fmtNum(s.low_52w)}</div>
              </div>
              <div className="stat-card wide">
                <div className="sc-label">역사적 위치(백분위)</div>
                <div className="sc-val">{s.percentile.toFixed(0)}%</div>
                <div className="sc-sub">{positionLabel(s.percentile)}</div>
              </div>
            </div>

            <div className="stats-section-title">기간별 수익률</div>
            <div className="stats-returns">
              {Object.entries(s.returns).map(([k, v]) => (
                <div className="ret-cell" key={k}>
                  <div className="ret-k">{k}</div>
                  <div className={`ret-v ${cls(v)}`}>{fmtPct(v)}</div>
                </div>
              ))}
            </div>

            <div className="stats-section-title">추세 · 리스크 · 장기</div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="sc-label">50일 이평 대비</div>
                <div className={`sc-val ${cls(s.vs_ma50)}`}>{fmtPct(s.vs_ma50)}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">200일 이평 대비</div>
                <div className={`sc-val ${cls(s.vs_ma200)}`}>{fmtPct(s.vs_ma200)}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">연율 변동성</div>
                <div className="sc-val">{s.volatility ? s.volatility.toFixed(0) + '%' : '—'}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">역대 최대 낙폭</div>
                <div className="sc-val neg">{s.max_drawdown ? s.max_drawdown.toFixed(0) + '%' : '—'}</div>
              </div>
              <div className="stat-card">
                <div className="sc-label">연평균 성장(CAGR)</div>
                <div className={`sc-val ${cls(s.cagr)}`}>{s.cagr != null ? fmtPct(s.cagr) : '—'}</div>
              </div>
            </div>

            <div className="stats-section-title">AI 해석</div>
            <div className="stats-explain">
              {explaining ? (
                <div className="stats-loading">
                  <span className="spinner" /> AI가 다각도로 해설하는 중…
                </div>
              ) : explain ? (
                <Markdown>{explain}</Markdown>
              ) : (
                <div className="stats-muted">해설을 불러오지 못했어요.</div>
              )}
            </div>

            <div className="stats-disc">
              ※ 실제 과거 데이터 기반 정보이며, <b>투자 자문이 아닙니다</b>. 데이터는 조회할수록 계속 쌓여요.
            </div>
          </>
        )}
      </div>
    </div>
  )
}
