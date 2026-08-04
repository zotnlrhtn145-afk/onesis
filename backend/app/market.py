"""시장 데이터 창고 + 통계 엔진.

yfinance로 여러 자산(주식·코인·원자재·환율)의 과거 가격을 로컬 SQLite(market.db)에
계속 축적하고, 쌓인 데이터로 '다각도' 통계를 계산한다.
자산은 조회할수록·시간이 지날수록 데이터가 쌓여 통계가 정교해진다(성장).

- 계산은 코드(정확한 숫자), 해석은 AI가 담당한다.
- 투자 자문이 아니라 '과거 데이터 기반 정보' 제공용이다.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Any, Optional

from . import config

# ---------------- 시드 유니버스(시장별 대표 자산) ----------------
# aliases: 사용자가 부를 법한 이름들(한글/영문/티커)
UNIVERSE: list[dict[str, Any]] = [
    # 미국주식
    {"symbol": "AAPL", "name": "애플", "market": "미국주식", "aliases": ["apple", "애플"]},
    {"symbol": "MSFT", "name": "마이크로소프트", "market": "미국주식", "aliases": ["microsoft", "마소", "마이크로소프트"]},
    {"symbol": "NVDA", "name": "엔비디아", "market": "미국주식", "aliases": ["nvidia", "엔비디아"]},
    {"symbol": "TSLA", "name": "테슬라", "market": "미국주식", "aliases": ["tesla", "테슬라"]},
    {"symbol": "GOOGL", "name": "구글(알파벳)", "market": "미국주식", "aliases": ["google", "구글", "알파벳", "alphabet"]},
    {"symbol": "AMZN", "name": "아마존", "market": "미국주식", "aliases": ["amazon", "아마존"]},
    {"symbol": "META", "name": "메타(페이스북)", "market": "미국주식", "aliases": ["meta", "메타", "페이스북", "facebook"]},
    # 한국주식
    {"symbol": "005930.KS", "name": "삼성전자", "market": "한국주식", "aliases": ["삼성", "삼성전자", "samsung"]},
    {"symbol": "000660.KS", "name": "SK하이닉스", "market": "한국주식", "aliases": ["하이닉스", "sk하이닉스", "hynix"]},
    {"symbol": "035420.KS", "name": "네이버", "market": "한국주식", "aliases": ["네이버", "naver"]},
    {"symbol": "035720.KS", "name": "카카오", "market": "한국주식", "aliases": ["카카오", "kakao"]},
    # 코인
    {"symbol": "BTC-USD", "name": "비트코인", "market": "코인", "aliases": ["btc", "비트코인", "bitcoin"]},
    {"symbol": "ETH-USD", "name": "이더리움", "market": "코인", "aliases": ["eth", "이더리움", "ethereum"]},
    {"symbol": "SOL-USD", "name": "솔라나", "market": "코인", "aliases": ["sol", "솔라나", "solana"]},
    # 원자재/환율/지수
    {"symbol": "GC=F", "name": "금", "market": "원자재", "aliases": ["금", "gold", "골드"]},
    {"symbol": "CL=F", "name": "WTI 원유", "market": "원자재", "aliases": ["원유", "석유", "oil", "wti"]},
    {"symbol": "USDKRW=X", "name": "원/달러 환율", "market": "환율", "aliases": ["환율", "원달러", "달러", "usdkrw"]},
    {"symbol": "^GSPC", "name": "S&P500 지수", "market": "지수", "aliases": ["s&p", "sp500", "s&p500", "에스앤피"]},
]

_BY_SYMBOL = {a["symbol"]: a for a in UNIVERSE}


# ---------------- DB ----------------
def _conn() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.MARKET_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init() -> None:
    con = _conn()
    con.execute(
        "CREATE TABLE IF NOT EXISTS assets ("
        "symbol TEXT PRIMARY KEY, name TEXT, market TEXT, last_updated TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS prices ("
        "symbol TEXT, date TEXT, close REAL, PRIMARY KEY(symbol, date))"
    )
    con.commit()
    con.close()


def _market_of(symbol: str) -> str:
    a = _BY_SYMBOL.get(symbol)
    return a["market"] if a else "기타"


def _name_of(symbol: str) -> str:
    a = _BY_SYMBOL.get(symbol)
    return a["name"] if a else symbol


# ---------------- 이름 → 심볼 해석 ----------------
def resolve(query: str) -> Optional[dict[str, str]]:
    """사용자 입력(이름/티커)을 자산으로 해석."""
    q = (query or "").strip()
    if not q:
        return None
    low = q.lower()
    # 1) 유니버스 별칭/이름/심볼 매칭
    for a in UNIVERSE:
        if low == a["symbol"].lower() or low == a["name"].lower():
            return {"symbol": a["symbol"], "name": a["name"], "market": a["market"]}
        for al in a["aliases"]:
            if al.lower() in low or low in al.lower():
                return {"symbol": a["symbol"], "name": a["name"], "market": a["market"]}
    # 2) 티커처럼 보이면 그대로 사용(라이브 조회로 확장 가능)
    if q.replace(".", "").replace("-", "").replace("=", "").replace("^", "").isalnum():
        return {"symbol": q.upper(), "name": q.upper(), "market": "기타"}
    return None


# ---------------- yfinance 적재 ----------------
def _fetch_yf(symbol: str, start: Optional[str] = None) -> list[tuple[str, float]]:
    import warnings

    warnings.filterwarnings("ignore")
    import yfinance as yf  # 지연 임포트(무거움)

    t = yf.Ticker(symbol)
    hist = t.history(start=start, auto_adjust=True) if start else t.history(period="max", auto_adjust=True)
    if hist is None or hist.empty or "Close" not in hist:
        return []
    out: list[tuple[str, float]] = []
    for idx, val in hist["Close"].dropna().items():
        try:
            out.append((idx.date().isoformat(), float(val)))
        except Exception:
            continue
    return out


def _store(symbol: str, name: str, market: str, rows: list[tuple[str, float]]) -> None:
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO assets(symbol, name, market, last_updated) VALUES(?,?,?,?)",
        (symbol, name, market, dt.date.today().isoformat()),
    )
    con.executemany(
        "INSERT OR IGNORE INTO prices(symbol, date, close) VALUES(?,?,?)",
        [(symbol, d, c) for d, c in rows],
    )
    con.commit()
    con.close()


def ensure(symbol: str, name: Optional[str] = None, market: Optional[str] = None,
           force: bool = False) -> int:
    """자산의 가격 데이터를 확보(없으면 전체 적재, 오래됐으면 최근분 추가). 저장된 일수 반환."""
    con = _conn()
    row = con.execute(
        "SELECT MAX(date) md, COUNT(*) n FROM prices WHERE symbol=?", (symbol,)
    ).fetchone()
    con.close()
    n = row["n"] or 0
    md = row["md"]

    if n == 0:
        rows = _fetch_yf(symbol)
        if not rows:
            return 0
        _store(symbol, name or _name_of(symbol), market or _market_of(symbol), rows)
        return len(rows)

    last = dt.date.fromisoformat(md)
    if force or (dt.date.today() - last).days >= 2:
        rows = _fetch_yf(symbol, start=md)
        if rows:
            _store(symbol, name or _name_of(symbol), market or _market_of(symbol), rows)
            con = _conn()
            n = con.execute("SELECT COUNT(*) n FROM prices WHERE symbol=?", (symbol,)).fetchone()["n"]
            con.close()
    return n


def _load(symbol: str) -> tuple[list[dt.date], list[float]]:
    con = _conn()
    rows = con.execute(
        "SELECT date, close FROM prices WHERE symbol=? ORDER BY date", (symbol,)
    ).fetchall()
    con.close()
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]
    closes = [float(r["close"]) for r in rows]
    return dates, closes


# ---------------- 통계 계산(다각도) ----------------
def _price_on_or_before(dates: list[dt.date], closes: list[float], target: dt.date) -> Optional[float]:
    # dates 오름차순. target 이하의 마지막 종가.
    lo, hi, res = 0, len(dates) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if dates[mid] <= target:
            res = closes[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return res


def _pct(a: float, b: float) -> Optional[float]:
    return (a / b - 1) * 100 if b else None


def compute_stats(symbol: str) -> Optional[dict[str, Any]]:
    dates, closes = _load(symbol)
    if len(closes) < 30:
        return None
    con = _conn()
    meta = con.execute("SELECT name, market FROM assets WHERE symbol=?", (symbol,)).fetchone()
    con.close()
    name = meta["name"] if meta else _name_of(symbol)
    market = meta["market"] if meta else _market_of(symbol)

    cur = closes[-1]
    as_of = dates[-1]
    first = closes[0]
    years = (dates[-1] - dates[0]).days / 365.25

    # 52주
    y1 = as_of - dt.timedelta(days=365)
    w52 = [c for d, c in zip(dates, closes) if d >= y1]
    hi52, lo52 = (max(w52), min(w52)) if w52 else (max(closes), min(closes))

    # 역대(저장된 범위)
    ath, atl = max(closes), min(closes)

    # 백분위(현재가보다 낮았던 날 비율)
    below = sum(1 for c in closes if c < cur)
    percentile = below / len(closes) * 100

    # 최대 낙폭(역사상 고점→저점)
    peak = closes[0]
    mdd = 0.0
    for c in closes:
        if c > peak:
            peak = c
        dd = (c / peak - 1) * 100
        if dd < mdd:
            mdd = dd

    # 변동성(연율화, 일간수익률 표준편차)
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes)) if closes[i - 1]]
    vol = None
    if len(rets) > 5:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        vol = (var ** 0.5) * (252 ** 0.5) * 100

    # 이동평균
    ma50 = sum(closes[-50:]) / len(closes[-50:]) if len(closes) >= 50 else None
    ma200 = sum(closes[-200:]) / len(closes[-200:]) if len(closes) >= 200 else None

    # 기간별 수익률
    periods = {"1주": 7, "1개월": 30, "3개월": 91, "6개월": 182, "1년": 365, "3년": 1095}
    returns = {}
    for label, days in periods.items():
        past = _price_on_or_before(dates, closes, as_of - dt.timedelta(days=days))
        returns[label] = _pct(cur, past) if past else None
    returns["전체"] = _pct(cur, first)

    cagr = ((cur / first) ** (1 / years) - 1) * 100 if years > 0 and first > 0 else None

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "as_of": as_of.isoformat(),
        "data_points": len(closes),
        "history_start": dates[0].isoformat(),
        "years": round(years, 1),
        "current": cur,
        "high_52w": hi52,
        "low_52w": lo52,
        "from_high_52w": _pct(cur, hi52),
        "from_low_52w": _pct(cur, lo52),
        "ath": ath,
        "atl": atl,
        "from_ath": _pct(cur, ath),  # 고점 대비 낙폭
        "from_atl": _pct(cur, atl),
        "percentile": percentile,  # 현재가의 역사적 위치(낮을수록 저평가 구간)
        "max_drawdown": mdd,       # 역대 최대 낙폭
        "volatility": vol,         # 연율화 변동성(%)
        "ma50": ma50,
        "ma200": ma200,
        "vs_ma50": _pct(cur, ma50) if ma50 else None,
        "vs_ma200": _pct(cur, ma200) if ma200 else None,
        "returns": returns,
        "cagr": cagr,
    }


# ---------------- 시드/목록 ----------------
def seed(force: bool = False) -> list[dict[str, Any]]:
    """유니버스 전체 자산의 데이터를 확보(축적)."""
    init()
    result = []
    for a in UNIVERSE:
        try:
            n = ensure(a["symbol"], a["name"], a["market"], force=force)
            result.append({"symbol": a["symbol"], "name": a["name"], "market": a["market"], "points": n})
        except Exception as e:  # 방어
            result.append({"symbol": a["symbol"], "name": a["name"], "market": a["market"], "error": str(e)})
    return result


def list_assets() -> list[dict[str, Any]]:
    """저장된 자산 목록(축적 현황 포함)."""
    con = _conn()
    rows = con.execute(
        "SELECT a.symbol, a.name, a.market, a.last_updated, "
        "(SELECT COUNT(*) FROM prices p WHERE p.symbol=a.symbol) AS points "
        "FROM assets a ORDER BY a.market, a.name"
    ).fetchall()
    con.close()
    stored = {r["symbol"]: dict(r) for r in rows}
    # 유니버스 기준으로 병합(아직 안 쌓인 것도 표시)
    out = []
    for a in UNIVERSE:
        s = stored.get(a["symbol"])
        out.append({
            "symbol": a["symbol"], "name": a["name"], "market": a["market"],
            "points": s["points"] if s else 0,
            "last_updated": s["last_updated"] if s else None,
        })
    return out
