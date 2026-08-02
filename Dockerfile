# ===== 1단계: 프론트엔드(React) 빌드 =====
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
RUN corepack enable
# 프론트 소스 전체 복사 후 설치·빌드 (개별 파일 누락 위험 제거)
COPY frontend/ ./
RUN pnpm install --no-frozen-lockfile
RUN pnpm build

# ===== 2단계: 백엔드(FastAPI) + 정적 파일 서빙 =====
FROM python:3.12-slim AS app
WORKDIR /app

# Node.js + 클로드 코드 CLI 설치 ("이대로 제작하기" 기능에 필요)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y curl && apt-get autoremove -y \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 백엔드 소스
COPY backend/ ./backend/
# 프론트엔드 빌드 결과물을 backend/static 으로 복사 → FastAPI 가 함께 서빙
COPY --from=frontend /app/frontend/dist ./backend/static

# 대화 기록 + 제작 결과물 저장 폴더(영구 볼륨을 여기에 연결)
ENV DATA_DIR=/data
ENV BUILDS_DIR=/data/onesis-builds
VOLUME ["/data"]

WORKDIR /app/backend
EXPOSE 8000
# Railway 등은 $PORT 를 주입합니다. 없으면 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
