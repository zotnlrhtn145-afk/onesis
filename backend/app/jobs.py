"""토론을 HTTP 연결과 분리해 서버에서 독립적으로 끝까지 실행한다.

브라우저가 페이지를 벗어나거나 인터넷이 끊겨도 토론(백그라운드 태스크)은 계속
진행되어 결론까지 만들고 DB에 저장한다. 다시 접속하면 저장된 결과를 볼 수 있고,
진행 중이면 실시간 스트림에 다시 붙을 수도 있다.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from . import db, debate

# conversation_id -> job dict
_jobs: dict[str, dict[str, Any]] = {}


def get_job(conversation_id: str) -> dict[str, Any] | None:
    return _jobs.get(conversation_id)


def running_ids() -> list[str]:
    """아직 진행 중인 토론의 대화 id 목록."""
    return [cid for cid, j in _jobs.items() if not j.get("done")]


def start_job(conversation_id: str, question: str) -> dict[str, Any]:
    """이 대화의 토론 작업을 시작(이미 진행 중이면 그것을 반환)."""
    existing = _jobs.get(conversation_id)
    if existing and not existing["done"]:
        return existing
    job: dict[str, Any] = {
        "question": question,
        "buffer": [],           # 지금까지의 모든 이벤트(재접속 재생용)
        "subscribers": [],      # 실시간 구독자 큐 목록
        "done": False,
    }
    _jobs[conversation_id] = job
    asyncio.create_task(_run(conversation_id, question, job))
    return job


async def _run(conversation_id: str, question: str, job: dict[str, Any]) -> None:
    def emit(evt: dict[str, Any]) -> None:
        job["buffer"].append(evt)
        for q in list(job["subscribers"]):
            try:
                q.put_nowait(evt)
            except Exception:
                pass

    final_content = None
    transcript: dict[str, Any] | None = None
    is_build = False
    try:
        async for evt in debate.run_debate(question):
            if evt.get("type") == "final":
                final_content = evt.get("content")
                transcript = evt.get("transcript")
                is_build = evt.get("is_build", False)
            emit(evt)
    except asyncio.CancelledError:
        # 서버 종료 등으로 취소되어도 조용히 마무리 시도
        raise
    except Exception as e:  # 방어
        emit({"type": "error", "error": f"서버 오류: {e}"})
    finally:
        # 결론이 나왔으면 연결 여부와 무관하게 저장
        if final_content is not None:
            try:
                mid = db.add_exchange(
                    conversation_id, question, final_content,
                    transcript or {}, is_build, final_content,
                )
                emit({"type": "saved", "conversation_id": conversation_id, "message_id": mid})
            except Exception as e:
                emit({"type": "error", "error": f"저장 실패: {e}"})
        emit({"type": "done"})
        job["done"] = True
        asyncio.create_task(_cleanup(conversation_id))


async def _cleanup(conversation_id: str) -> None:
    # 재접속 여유를 두고 정리
    await asyncio.sleep(600)
    j = _jobs.get(conversation_id)
    if j and j["done"]:
        _jobs.pop(conversation_id, None)


async def subscribe(conversation_id: str) -> AsyncIterator[dict[str, Any]]:
    """버퍼된 이벤트를 재생한 뒤, 끝날 때까지 실시간 이벤트를 낸다.

    구독자가 끊겨도(스트림 취소) 백그라운드 토론은 계속 진행된다.
    """
    job = _jobs.get(conversation_id)
    if not job:
        return
    # 1) 지금까지의 이벤트 재생
    for evt in list(job["buffer"]):
        yield evt
        if evt.get("type") == "done":
            return
    if job["done"]:
        return
    # 2) 실시간 구독
    q: asyncio.Queue = asyncio.Queue()
    job["subscribers"].append(q)
    try:
        while True:
            evt = await q.get()
            yield evt
            if evt.get("type") == "done":
                break
    finally:
        if q in job["subscribers"]:
            job["subscribers"].remove(q)
