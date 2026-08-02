# ===== 단순 배포용 Dockerfile =====
# 프론트엔드는 미리 빌드해 backend/static 에 넣어두므로, 서버에서는
# 파이썬(FastAPI)만 설치해 정적 파일 + API 를 함께 서빙합니다. (가볍고 안정적)
FROM python:3.12-slim
WORKDIR /app

# 파이썬 의존성
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 백엔드 소스 (미리 빌드된 backend/static 포함)
COPY backend/ ./backend/

# 대화 기록 + 제작 결과물 저장 폴더 (Railway 볼륨이 /data 를 담당 — Docker VOLUME 은 Railway가 미지원)
ENV DATA_DIR=/data
ENV BUILDS_DIR=/data/onesis-builds

WORKDIR /app/backend
EXPOSE 8000
# Railway 등은 $PORT 를 주입합니다. 없으면 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
