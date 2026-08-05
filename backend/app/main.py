"""오네시스(Onesis) FastAPI 앱 — API + 정적 프론트엔드 서빙."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ai_clients, auth, builder, config, db, debate, jobs, market, prompts, schemas

app = FastAPI(title="Onesis", docs_url=None, redoc_url=None)

# 개발 시 Vite(5173)에서의 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    market.init()


# ---------------- 공개 엔드포인트 ----------------
@app.get("/api/config")
def api_config() -> dict[str, Any]:
    return {
        "app": "오네시스",
        "requires_password": True,
        "participants": [
            {
                "id": p["id"],
                "name": p["name"],
                "color": p["color"],
                "available": ai_clients.is_available(p["id"]),
            }
            for p in config.PARTICIPANTS
        ],
        "moderator": config.MODERATOR_ID,
    }


@app.post("/api/login")
def api_login(req: schemas.LoginReq) -> dict[str, str]:
    if not auth.check_password(req.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
    return {"token": auth.create_token()}


# ---------------- 대화 관리 (인증 필요) ----------------
@app.get("/api/conversations", dependencies=[Depends(auth.require_auth)])
def api_list_conversations(kind: Optional[str] = None) -> list[dict[str, Any]]:
    return db.list_conversations(kind)


@app.post("/api/conversations", dependencies=[Depends(auth.require_auth)])
def api_new_conversation(req: schemas.NewConversationReq) -> dict[str, str]:
    cid = db.create_conversation(req.title or "새 대화")
    return {"id": cid}


@app.get("/api/conversations/{cid}", dependencies=[Depends(auth.require_auth)])
def api_get_conversation(cid: str) -> dict[str, Any]:
    conv = db.get_conversation(cid)
    if not conv:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return conv


@app.patch("/api/conversations/{cid}", dependencies=[Depends(auth.require_auth)])
def api_rename_conversation(cid: str, req: schemas.RenameReq) -> dict[str, bool]:
    db.rename_conversation(cid, req.title)
    return {"ok": True}


@app.put("/api/conversations/{cid}/preview", dependencies=[Depends(auth.require_auth)])
def api_set_preview(cid: str, req: schemas.PreviewReq) -> dict[str, bool]:
    """오프라인에서 수정한 미리보기(기획안)를 서버에 동기화."""
    db.update_preview(cid, req.preview)
    return {"ok": True}


@app.delete("/api/conversations/{cid}", dependencies=[Depends(auth.require_auth)])
def api_delete_conversation(cid: str) -> dict[str, bool]:
    db.delete_conversation(cid)
    return {"ok": True}


# ---------------- 토론 (SSE) ----------------
def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# SSE 주석 라인(클라이언트는 무시). 유휴 연결 유지용 하트비트.
_KEEPALIVE = ": ping\n\n"


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # nginx 등에서 버퍼링 방지
}


@app.post("/api/ask", dependencies=[Depends(auth.require_auth)])
async def api_ask(req: schemas.AskReq) -> StreamingResponse:
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력하세요.")

    kind = req.kind if req.kind in ("chat", "plan") else "chat"
    conversation_id = req.conversation_id
    is_new = not conversation_id
    if is_new:
        conversation_id = db.create_conversation(question, kind=kind)

    # 토론을 HTTP 연결과 분리해 백그라운드로 시작한다.
    # → 페이지를 벗어나거나 인터넷이 끊겨도 서버는 끝까지 진행해 결론을 저장한다.
    # 기획안(plan) 모드면 상세 개발 기획서(force_build)로 만든다.
    jobs.start_job(conversation_id, question, req.ai_ids, force_build=(kind == "plan"))

    async def gen() -> AsyncIterator[str]:
        yield _sse({"type": "conversation", "id": conversation_id,
                    "is_new": is_new, "question": question})
        # 진행 상황을 관찰만 한다. 여기서 연결이 끊겨도 토론 자체는 계속된다.
        async for evt in jobs.subscribe(conversation_id):
            yield _KEEPALIVE if evt.get("type") == "ping" else _sse(evt)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/running", dependencies=[Depends(auth.require_auth)])
def api_running() -> dict[str, list[str]]:
    """지금 서버에서 진행 중인 토론의 대화 id 목록(재접속 판단용)."""
    return {"ids": jobs.running_ids()}


@app.get("/api/conversations/{cid}/live", dependencies=[Depends(auth.require_auth)])
async def api_live(cid: str) -> StreamingResponse:
    """진행 중인(또는 방금 끝난) 토론에 다시 붙는다. 연결이 끊겼다 돌아왔을 때 사용."""
    async def gen() -> AsyncIterator[str]:
        job = jobs.get_job(cid)
        if not job:
            yield _sse({"type": "no_job"})
            yield _sse({"type": "done"})
            return
        yield _sse({"type": "conversation", "id": cid, "is_new": False,
                    "question": job.get("question", "")})
        async for evt in jobs.subscribe(cid):
            yield _KEEPALIVE if evt.get("type") == "ping" else _sse(evt)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/refine", dependencies=[Depends(auth.require_auth)])
async def api_refine(req: schemas.RefineReq) -> StreamingResponse:
    if not (req.instruction or "").strip():
        raise HTTPException(status_code=400, detail="수정 요청을 입력하세요.")

    async def gen() -> AsyncIterator[str]:
        new_doc = None
        try:
            async for evt in debate.run_refine(req.current_doc, req.instruction):
                if evt.get("type") == "final":
                    new_doc = evt.get("content")
                yield _sse(evt)
        except Exception as e:
            yield _sse({"type": "error", "error": f"서버 오류: {e}"})
        finally:
            if new_doc is not None:
                try:
                    db.update_preview(req.conversation_id, new_doc)
                except Exception:
                    pass
            yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------------- 화면 미리보기 (실제 UI 목업) ----------------
def _clean_html(text: str) -> str:
    """AI 응답에서 순수 HTML만 추출(코드펜스/설명 제거)."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    low = t.lower()
    for marker in ("<!doctype", "<html"):
        i = low.find(marker)
        if i != -1:
            return t[i:].strip()
    i = t.find("<")
    return t[i:].strip() if i != -1 else t


_MOCK_MOCKUP = """<!doctype html><html lang=ko><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>body{margin:0;font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;background:#f4f5f7;color:#1a1a2e}
.top{background:linear-gradient(135deg,#4f8cff,#8b5cf6);color:#fff;padding:20px 18px;border-radius:0 0 20px 20px}
.top h1{margin:0;font-size:20px}.top p{margin:4px 0 0;opacity:.9;font-size:13px}
.card{background:#fff;margin:14px;padding:16px;border-radius:14px;box-shadow:0 2px 10px rgba(0,0,0,.06)}
.card h3{margin:0 0 6px;font-size:15px}.card p{margin:0;color:#667;font-size:13px}
.btn{display:block;margin:16px;padding:14px;background:#4f8cff;color:#fff;text-align:center;border-radius:12px;font-weight:700}
.nav{position:sticky;bottom:0;display:flex;background:#fff;border-top:1px solid #eee}
.nav div{flex:1;text-align:center;padding:10px;font-size:12px;color:#889}.nav .on{color:#4f8cff}</style>
<div class=top><h1>✨ 데모 화면</h1><p>실제 AI가 만든 화면이 여기에 나옵니다</p></div>
<div class=card><h3>📌 예시 항목 1</h3><p>실제 제작 시 이 자리에 진짜 콘텐츠가 들어갑니다.</p></div>
<div class=card><h3>🎯 예시 항목 2</h3><p>버튼·색·글자를 말로 고치면 바로 반영돼요.</p></div>
<div class=btn>시작하기</div>
<div class=nav><div class=on>🏠 홈</div><div>🔍 검색</div><div>👤 내정보</div></div></html>"""


@app.post("/api/mockup", dependencies=[Depends(auth.require_auth)])
async def api_mockup(req: schemas.MockupReq) -> dict[str, str]:
    ais = ai_clients.available_ids()
    if config.MOCK:
        html = _MOCK_MOCKUP
    else:
        if not ais:
            raise HTTPException(status_code=400, detail="사용 가능한 AI가 없습니다.")
        # 목업은 렌더링 완성도가 중요 → 가장 정교한 모델(사회자=클로드) 우선,
        # 없으면 디자인 담당, 그것도 없으면 사용 가능한 아무 AI.
        designer = None
        for cand in (config.MODERATOR_ID, config.ROLE_LEADS.get("design")):
            if cand in ais:
                designer = cand
                break
        if designer is None:
            designer = ais[0]
        if req.instruction and req.current_html:
            user = prompts.mockup_refine_user(req.current_html, req.instruction)
        else:
            user = prompts.mockup_user(req.brief or "")
        try:
            raw = await ai_clients.call_ai(
                designer, prompts.mockup_system(), user, max_tokens=6000
            )
        except ai_clients.AIError as e:
            raise HTTPException(status_code=502, detail=str(e))
        html = _clean_html(raw)
    if req.conversation_id:
        try:
            db.update_mockup(req.conversation_id, html)
        except Exception:
            pass
    return {"html": html}


# ---------------- 시장 통계 (실제 데이터 축적 + 다각도 계산) ----------------
@app.get("/api/market/assets", dependencies=[Depends(auth.require_auth)])
def api_market_assets() -> dict[str, Any]:
    """축적 중인 자산 목록과 데이터량."""
    return {"assets": market.list_assets()}


@app.post("/api/market/stats", dependencies=[Depends(auth.require_auth)])
def api_market_stats(req: schemas.StatsReq) -> dict[str, Any]:
    """자산 이름/티커로 통계 계산(없으면 데이터 적재 후 계산, 오래됐으면 갱신=축적)."""
    r = market.resolve(req.query)
    if not r:
        raise HTTPException(status_code=404, detail="자산을 찾지 못했어요. 이름이나 티커를 확인해 주세요.")
    try:
        market.ensure(r["symbol"], r["name"], r["market"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"데이터를 가져오지 못했어요: {e}")
    stats = market.compute_stats(r["symbol"])
    if not stats:
        raise HTTPException(status_code=404, detail="데이터가 충분하지 않아요.")
    return {"stats": stats}


@app.post("/api/market/seed", dependencies=[Depends(auth.require_auth)])
def api_market_seed() -> dict[str, Any]:
    """대표 자산들의 데이터를 미리 축적(환경 구축)."""
    return {"seeded": market.seed()}


@app.post("/api/market/explain", dependencies=[Depends(auth.require_auth)])
async def api_market_explain(req: schemas.ExplainReq) -> dict[str, str]:
    """계산된 통계를 AI가 다각도로 해설(투자자문 아님)."""
    stats = market.compute_stats(req.symbol)
    if not stats:
        raise HTTPException(status_code=404, detail="먼저 통계를 계산해 주세요.")
    ais = ai_clients.available_ids()
    if config.MOCK or not ais:
        return {"text": "_(데모 모드) 실제 AI 키를 넣으면 통계를 다각도로 해설해 드려요._"}
    ai = config.MODERATOR_ID if config.MODERATOR_ID in ais else ais[0]
    try:
        text = await ai_clients.call_ai(
            ai, prompts.market_explain_system(), prompts.market_explain_user(stats),
            max_tokens=1500,
        )
    except ai_clients.AIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"text": text}


# ---------------- 이대로 제작하기 (클로드 코드 연동) ----------------
@app.post("/api/build", dependencies=[Depends(auth.require_auth)])
async def api_build(req: schemas.BuildReq) -> StreamingResponse:
    instruction = (req.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="제작할 내용이 비어 있습니다.")

    # 승인한 화면 디자인(HTML)이 있으면 '이 디자인 그대로' 만들도록 지시문에 합친다.
    design = (req.design_html or "").strip()
    if design:
        instruction = prompts.build_with_design(instruction, design)

    async def gen() -> AsyncIterator[str]:
        try:
            async for evt in builder.run_build(req.title or "build", instruction):
                yield _sse(evt)
        except Exception as e:
            yield _sse({"type": "error", "error": f"제작 오류: {e}"})
        finally:
            yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/build/{build_id}/download", dependencies=[Depends(auth.require_auth)])
def api_build_download(build_id: str) -> FileResponse:
    zip_path = builder.build_zip_path(build_id)
    if not zip_path:
        raise HTTPException(status_code=404, detail="결과물을 찾을 수 없습니다.")
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"{build_id}.zip",
    )


# ---------------- 정적 프론트엔드 ----------------
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    # html=True → "/" 에서 index.html 서빙, 자산 파일도 서빙
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
else:
    @app.get("/")
    def _dev_root() -> JSONResponse:
        return JSONResponse(
            {"message": "오네시스 백엔드 실행 중. 개발 중에는 프론트엔드(Vite, 5173)로 접속하세요."}
        )
