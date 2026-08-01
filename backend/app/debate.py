"""토론 오케스트레이션.

질문 하나가 들어오면 고정된 순서로 진행하며, 각 단계마다 진행 상황 이벤트를
생성(yield)합니다. 라우터가 이 이벤트들을 SSE 로 프론트엔드에 실시간 전송합니다.

순서:
  1) 1차 답변 (3 AI 병렬)
  2) 토론 1바퀴 (서로의 답변 비평)
  3) 답변 수정
  4) 토론 2바퀴 (수정된 답변 재검토)
  5) 최종 정리 (사회자=클로드)
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Awaitable

from . import ai_clients, config, prompts

STEP_LABELS = {
    "initial": "1단계 · 각 AI가 답변 작성 중…",
    "critique1": "2단계 · 서로의 답변을 검토하는 중…",
    "revise1": "3단계 · 지적을 반영해 답변 수정 중…",
    "critique2": "4단계 · 수정된 답변을 재검토하는 중…",
    "final": "5단계 · 사회자가 최종 정리 중…",
}


async def _gather_stream(tasks: dict[str, Awaitable[str]]):
    """ai_id -> coroutine 을 병렬 실행하고 완료되는 순서대로 (ai_id, ok, value)를 낸다."""
    async def wrap(ai_id: str, coro: Awaitable[str]):
        try:
            return ai_id, True, await coro
        except ai_clients.AIError as e:
            return ai_id, False, str(e)
        except Exception as e:  # 방어
            return ai_id, False, f"예상치 못한 오류: {e}"

    pending = [asyncio.create_task(wrap(a, c)) for a, c in tasks.items()]
    for fut in asyncio.as_completed(pending):
        yield await fut


def _interim_preview(answers: dict[str, str], label: str) -> str:
    if not answers:
        return "_아직 초안이 없습니다._"
    lead = answers.get(config.MODERATOR_ID) or next(iter(answers.values()))
    return f"> ⏳ {label}\n\n{lead}"


def _fallback_doc(question: str, answers: dict[str, str], is_build: bool) -> str:
    parts = [f"## 최종 답변\n\n(사회자 정리에 실패하여 각 AI 답변을 모았습니다.)\n"]
    for a, t in answers.items():
        parts.append(f"### {config.name_of(a)}\n{t}")
    return "\n\n".join(parts)


async def run_debate(question: str) -> AsyncIterator[dict[str, Any]]:
    is_build = prompts.detect_build(question)
    ais = ai_clients.available_ids()

    transcript: dict[str, Any] = {
        "participants": [
            {"id": p["id"], "name": p["name"], "color": p["color"]}
            for p in config.PARTICIPANTS
            if p["id"] in ais
        ],
        "is_build": is_build,
        "initial": {},
        "critique1": {},
        "revise1": {},
        "critique2": {},
    }

    if not ais:
        yield {"type": "error", "error": "사용 가능한 AI가 없습니다. API 키를 설정하세요."}
        return

    yield {"type": "meta", "is_build": is_build,
           "participants": transcript["participants"]}

    # ---------- 1) 1차 답변 (병렬) ----------
    yield {"type": "status", "step": "initial", "label": STEP_LABELS["initial"]}
    for a in ais:
        yield {"type": "ai_start", "ai": a, "stage": "initial"}
    answers: dict[str, str] = {}
    tasks = {
        a: ai_clients.call_ai(a, prompts.initial_system(config.name_of(a)),
                              prompts.initial_user(question, is_build))
        for a in ais
    }
    async for ai_id, ok, val in _gather_stream(tasks):
        if ok:
            answers[ai_id] = val
            transcript["initial"][ai_id] = val
            yield {"type": "ai_done", "ai": ai_id, "stage": "initial", "content": val}
        else:
            transcript["initial"][ai_id] = {"error": val}
            yield {"type": "ai_error", "ai": ai_id, "stage": "initial", "error": val}

    if not answers:
        yield {"type": "error", "error": "모든 AI가 1차 답변에 실패했습니다."}
        return
    yield {"type": "preview", "content": _interim_preview(answers, "1차 답변 완료 — 다듬는 중")}

    have_debate = len(answers) >= 2

    # ---------- 2) 토론 1바퀴 ----------
    critiques1: dict[str, str] = {}
    if have_debate:
        yield {"type": "status", "step": "critique1", "label": STEP_LABELS["critique1"]}
        critics = list(answers.keys())
        for a in critics:
            yield {"type": "ai_start", "ai": a, "stage": "critique1"}
        tasks = {
            a: ai_clients.call_ai(
                a, prompts.critique_system(config.name_of(a)),
                prompts.critique_user(question, {o: answers[o] for o in answers if o != a}),
            )
            for a in critics
        }
        async for ai_id, ok, val in _gather_stream(tasks):
            if ok:
                critiques1[ai_id] = val
                transcript["critique1"][ai_id] = val
                yield {"type": "ai_done", "ai": ai_id, "stage": "critique1", "content": val}
            else:
                transcript["critique1"][ai_id] = {"error": val}
                yield {"type": "ai_error", "ai": ai_id, "stage": "critique1", "error": val}

    # ---------- 3) 답변 수정 ----------
    if have_debate and critiques1:
        yield {"type": "status", "step": "revise1", "label": STEP_LABELS["revise1"]}
        revisers = list(answers.keys())
        for a in revisers:
            yield {"type": "ai_start", "ai": a, "stage": "revise1"}
        tasks = {
            a: ai_clients.call_ai(
                a, prompts.revise_system(config.name_of(a)),
                prompts.revise_user(question, answers[a],
                                    {c: critiques1[c] for c in critiques1 if c != a}),
            )
            for a in revisers
        }
        async for ai_id, ok, val in _gather_stream(tasks):
            if ok:
                answers[ai_id] = val  # 답변 갱신
                transcript["revise1"][ai_id] = val
                yield {"type": "ai_done", "ai": ai_id, "stage": "revise1", "content": val}
            else:
                transcript["revise1"][ai_id] = {"error": val}
                yield {"type": "ai_error", "ai": ai_id, "stage": "revise1", "error": val}
        yield {"type": "preview",
               "content": _interim_preview(answers, "수정 답변 완료 — 최종 정리 준비 중")}

    # ---------- 4) 토론 2바퀴 ----------
    critiques2: dict[str, str] = {}
    if have_debate:
        yield {"type": "status", "step": "critique2", "label": STEP_LABELS["critique2"]}
        critics = list(answers.keys())
        for a in critics:
            yield {"type": "ai_start", "ai": a, "stage": "critique2"}
        tasks = {
            a: ai_clients.call_ai(
                a, prompts.critique_system(config.name_of(a)),
                prompts.critique_user(question, {o: answers[o] for o in answers if o != a}),
            )
            for a in critics
        }
        async for ai_id, ok, val in _gather_stream(tasks):
            if ok:
                critiques2[ai_id] = val
                transcript["critique2"][ai_id] = val
                yield {"type": "ai_done", "ai": ai_id, "stage": "critique2", "content": val}
            else:
                transcript["critique2"][ai_id] = {"error": val}
                yield {"type": "ai_error", "ai": ai_id, "stage": "critique2", "error": val}

    # ---------- 5) 최종 정리 (사회자) ----------
    yield {"type": "status", "step": "final", "label": STEP_LABELS["final"]}
    moderator = config.MODERATOR_ID if config.MODERATOR_ID in answers else next(iter(answers))
    yield {"type": "ai_start", "ai": moderator, "stage": "final"}
    final_doc = None
    order = [moderator] + [a for a in answers if a != moderator]
    for mod in order:
        try:
            final_doc = await ai_clients.call_ai(
                mod, prompts.moderator_system(),
                prompts.moderator_user(question, answers, critiques2, is_build),
            )
            moderator = mod
            break
        except ai_clients.AIError:
            continue
    if not final_doc:
        final_doc = _fallback_doc(question, answers, is_build)

    transcript["final_by"] = moderator
    yield {"type": "ai_done", "ai": moderator, "stage": "final", "content": final_doc}
    yield {"type": "preview", "content": final_doc}
    yield {"type": "final", "content": final_doc, "transcript": transcript, "is_build": is_build}


async def run_refine(current_doc: str, instruction: str) -> AsyncIterator[dict[str, Any]]:
    """이미 나온 결과물을 사용자의 수정 요청에 맞게 다시 다듬는다."""
    ais = ai_clients.available_ids()
    if not ais:
        yield {"type": "error", "error": "사용 가능한 AI가 없습니다."}
        return
    editor = config.MODERATOR_ID if config.MODERATOR_ID in ais else ais[0]
    yield {"type": "status", "step": "refine", "label": "요청한 부분을 다시 다듬는 중…"}
    yield {"type": "ai_start", "ai": editor, "stage": "refine"}
    new_doc = None
    for ed in [editor] + [a for a in ais if a != editor]:
        try:
            new_doc = await ai_clients.call_ai(
                ed, prompts.refine_system(), prompts.refine_user(current_doc, instruction)
            )
            editor = ed
            break
        except ai_clients.AIError:
            continue
    if not new_doc:
        yield {"type": "error", "error": "수정에 실패했습니다. 잠시 후 다시 시도하세요."}
        return
    yield {"type": "ai_done", "ai": editor, "stage": "refine", "content": new_doc}
    yield {"type": "preview", "content": new_doc}
    yield {"type": "final", "content": new_doc, "refine": True}
