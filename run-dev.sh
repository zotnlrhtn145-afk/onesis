#!/usr/bin/env bash
# ===== 오네시스 로컬 실행 스크립트 =====
# 백엔드(8000) + 프론트엔드(5173)를 한 번에 실행합니다.
#   ./run-dev.sh
# 종료: Ctrl + C

set -e
cd "$(dirname "$0")"

# 이 컴퓨터에 직접 설치한 Node 경로가 있으면 PATH 에 추가
[ -d "$HOME/.local/node/bin" ] && export PATH="$HOME/.local/node/bin:$PATH"

# --- 준비물 확인 ---
command -v python3 >/dev/null || { echo "python3 가 필요합니다."; exit 1; }
command -v pnpm >/dev/null || command -v npm >/dev/null || { echo "pnpm 또는 npm 이 필요합니다."; exit 1; }
PKG=$(command -v pnpm >/dev/null && echo pnpm || echo npm)

# --- 백엔드 ---
cd backend
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

# .env 가 있으면 불러오기 (없으면 데모용 기본값)
if [ -f .env ]; then
  set -a; . ./.env; set +a
else
  echo "⚠  backend/.env 가 없습니다. 데모(mock) 모드로 실행합니다."
  echo "   실제 AI를 쓰려면 backend/.env.example 을 복사해 .env 로 만들고 키를 넣으세요."
  export ONESIS_MOCK=1 LOGIN_PASSWORD=test SESSION_SECRET=dev-secret
fi

# 키가 하나도 없으면 자동으로 데모(mock) 모드로 전환 → 앱이 항상 동작
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
  export ONESIS_MOCK=1
  echo "ℹ  API 키가 없어 데모(mock) 모드로 실행합니다. 키를 넣으면 자동으로 진짜 AI로 바뀝니다."
fi

./.venv/bin/uvicorn app.main:app --reload --port 8000 &
BACK=$!
cd ..

# --- 프론트엔드 ---
cd frontend
$PKG install
$PKG run dev &
FRONT=$!
cd ..

echo ""
echo "======================================================"
echo "  오네시스 실행 중!  브라우저에서 아래 주소로 접속하세요:"
echo "     👉  http://localhost:5173"
echo "  (종료하려면 이 창에서 Ctrl + C)"
echo "======================================================"

# 둘 중 하나라도 꺼지면 같이 종료
trap "kill $BACK $FRONT 2>/dev/null" EXIT
wait
