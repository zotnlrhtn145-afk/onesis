"""오네시스(Onesis) 설정 — 모델 이름/키/저장경로를 한 곳에 모아둡니다."""
from __future__ import annotations

import os
from pathlib import Path


def _get(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


# ---------- 로그인 / 보안 ----------
# 이 비밀번호를 알아야만 접속 가능. 반드시 환경변수로 바꾸세요.
LOGIN_PASSWORD = _get("LOGIN_PASSWORD", "onesis")
# 로그인 토큰 서명용 비밀키
SESSION_SECRET = _get("SESSION_SECRET", "onesis-dev-secret-change-me")
# 로그인 유지 시간(초). 기본 30일.
TOKEN_TTL_SECONDS = int(_get("TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 30)))

# ---------- 데이터 저장 ----------
# 클라우드에서는 영구 볼륨 경로(예: /data)를 DATA_DIR 로 지정하세요.
DATA_DIR = Path(_get("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
DB_PATH = DATA_DIR / "onesis.db"

# ---------- API 키 (환경변수로만 관리) ----------
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _get("OPENAI_API_KEY")
GEMINI_API_KEY = _get("GEMINI_API_KEY")

# ---------- 모델 이름 (★ 여기 한 곳만 바꾸면 됩니다) ----------
# 더 저렴/빠르게: claude-sonnet-4-5, gpt-4o-mini, gemini-2.0-flash-lite 등으로 교체 가능.
ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-opus-5")
OPENAI_MODEL = _get("OPENAI_MODEL", "gpt-4o")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.0-flash")

# 각 AI 응답 최대 토큰 수
MAX_TOKENS = int(_get("MAX_TOKENS", "2000"))
# 한 AI 호출 타임아웃(초)
AI_TIMEOUT = int(_get("AI_TIMEOUT", "120"))

# 데모 모드: API 키 없이 가짜(mock) 응답으로 전체 흐름을 체험. ONESIS_MOCK=1
MOCK = str(_get("ONESIS_MOCK", "0")).lower() in ("1", "true", "yes", "on")

# ---------- "이대로 제작하기" (클로드 코드 연동) ----------
# 제작 결과물이 만들어지는 전용 상위 폴더. 각 제작은 그 아래 새 하위폴더에서만 진행됩니다.
BUILDS_DIR = Path(_get("BUILDS_DIR", str(Path.home() / "onesis-builds")))
# 클로드 코드 실행 파일 경로
CLAUDE_BIN = _get("CLAUDE_BIN", "claude")
# 자동 허용할 도구(이 목록 밖 도구는 거부 → 폴더 밖 위험 작업 차단에 도움)
CLAUDE_ALLOWED_TOOLS = (
    _get("CLAUDE_ALLOWED_TOOLS", "Read Write Edit Glob Grep Bash") or ""
).split()
# 제작 1건 최대 시간(초)
BUILD_TIMEOUT = int(_get("BUILD_TIMEOUT", "1800"))

# ---------- 참가 AI ----------
PARTICIPANTS = [
    {"id": "claude", "name": "클로드", "provider": "anthropic", "color": "#D97757"},
    {"id": "gpt", "name": "챗지피티", "provider": "openai", "color": "#10A37F"},
    {"id": "gemini", "name": "제미나이", "provider": "google", "color": "#4285F4"},
]
# 사회자(최종 정리 담당)
MODERATOR_ID = "claude"


def participant(ai_id: str) -> dict | None:
    for p in PARTICIPANTS:
        if p["id"] == ai_id:
            return p
    return None


def name_of(ai_id: str) -> str:
    p = participant(ai_id)
    return p["name"] if p else ai_id
