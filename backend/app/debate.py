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


def _participants(ais: list[str]) -> list[dict[str, Any]]:
    return [
        {"id": p["id"], "name": p["name"], "color": p["color"]}
        for p in config.PARTICIPANTS
        if p["id"] in ais
    ]


def resolve_lead(part: str, ais: list[str]):
    """파트의 주도 AI. 지정이 없거나 사용 불가면 None(=다같이 대칭 토론)."""
    lead = config.ROLE_LEADS.get(part)
    return lead if (lead and lead in ais) else None


async def run_debate(
    question: str, selected: list[str] | None = None
) -> AsyncIterator[dict[str, Any]]:
    is_build = prompts.detect_build(question)
    part = prompts.detect_part(question)
    available = ai_clients.available_ids()
    # 사용자가 고른 AI만 남긴다(순서는 config 기준 유지). 고른 게 없으면 전체 사용.
    if selected:
        ais = [a for a in available if a in selected]
        if not ais:
            ais = available
    else:
        ais = available
    if not ais:
        yield {"type": "error", "error": "사용 가능한 AI가 없습니다. API 키를 설정하세요."}
        return
    # 한 개만 고르면 토론 없이 그 AI가 바로 답한다.
    if len(ais) == 1:
        async for e in _run_single(question, ais[0], is_build, part):
            yield e
        return
    lead = resolve_lead(part, ais)
    if lead is None:
        async for e in _run_symmetric(question, ais, is_build, part):
            yield e
    else:
        async for e in _run_lead(question, ais, lead, is_build, part):
            yield e


async def _run_single(
    question: str, ai: str, is_build: bool, part: str
) -> AsyncIterator[dict[str, Any]]:
    """AI 한 개만 선택했을 때: 토론 없이 그 AI가 직접 답한다."""
    name = config.name_of(ai)
    part_label = config.PART_LABELS.get(part, part)
    transcript: dict[str, Any] = {
        "participants": _participants([ai]),
        "is_build": is_build, "part": part, "lead": ai, "mode": "single",
    }
    yield {"type": "meta", "is_build": is_build, "part": part, "lead": ai,
           "single": True, "part_label": part_label,
           "participants": transcript["participants"]}
    yield {"type": "status", "step": "final", "label": f"{name}가 답변을 작성 중…"}
    yield {"type": "ai_start", "ai": ai, "stage": "final"}
    try:
        doc = await ai_clients.call_ai(
            ai, prompts.initial_system(name), prompts.initial_user(question, is_build))
    except ai_clients.AIError as e:
        yield {"type": "ai_error", "ai": ai, "stage": "final", "error": str(e)}
        yield {"type": "error", "error": f"{name}가 응답하지 못했습니다: {e}"}
        return
    doc = _append_build_note(doc, part)
    transcript["final_by"] = ai
    yield {"type": "ai_done", "ai": ai, "stage": "final", "content": doc}
    yield {"type": "preview", "content": doc}
    yield {"type": "final", "content": doc, "transcript": transcript, "is_build": is_build}


async def _run_symmetric(
    question: str, ais: list[str], is_build: bool, part: str
) -> AsyncIterator[dict[str, Any]]:
    """기획안/일반 질문: 주도자 없이 셋이 다같이 토론(대칭)."""
    transcript: dict[str, Any] = {
        "participants": _participants(ais),
        "is_build": is_build,
        "part": part,
        "lead": None,
        "mode": "symmetric",
        "initial": {},
        "critique1": {},
        "revise1": {},
        "critique2": {},
    }

    yield {"type": "meta", "is_build": is_build, "part": part, "lead": None,
           "part_label": config.PART_LABELS.get(part, part),
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


def _append_build_note(doc: str, part: str) -> str:
    if part == "build" and "이대로 제작하기" not in doc:
        return (
            doc
            + "\n\n---\n> 💡 실제 코드 제작은 오른쪽 **[이대로 제작하기]** 버튼을 누르면 "
            "클로드 코드가 이 내용대로 만들어 줍니다."
        )
    return doc


async def _run_lead(
    question: str, ais: list[str], lead: str, is_build: bool, part: str
) -> AsyncIterator[dict[str, Any]]:
    """주도(lead) 방식: 담당 AI가 이끌고, 나머지가 의견을 2번 주고받아 최적안으로 수렴."""
    lead_name = config.name_of(lead)
    part_label = config.PART_LABELS.get(part, part)
    others = [a for a in ais if a != lead]
    transcript: dict[str, Any] = {
        "participants": _participants(ais),
        "is_build": is_build, "part": part, "lead": lead, "mode": "lead",
        "initial": {}, "critique1": {}, "revise1": {}, "critique2": {},
    }
    yield {"type": "meta", "is_build": is_build, "part": part, "lead": lead,
           "part_label": part_label, "participants": transcript["participants"]}

    # 1) 주도자 제안
    yield {"type": "status", "step": "initial",
           "label": f"1단계 · {part_label} — {lead_name}가 제안 작성 중…"}
    yield {"type": "ai_start", "ai": lead, "stage": "initial"}
    try:
        current = await ai_clients.call_ai(
            lead, prompts.lead_propose_system(lead_name, part),
            prompts.lead_propose_user(question, part))
        transcript["initial"][lead] = current
        yield {"type": "ai_done", "ai": lead, "stage": "initial", "content": current}
    except ai_clients.AIError as e:
        transcript["initial"][lead] = {"error": str(e)}
        yield {"type": "ai_error", "ai": lead, "stage": "initial", "error": str(e)}
        # 주도자가 제안에 실패하면 남은 AI로 다같이(대칭) 전환
        if others:
            async for ev in _run_symmetric(question, others, is_build, part):
                yield ev
        else:
            yield {"type": "error", "error": "주도 AI가 응답하지 못했습니다."}
        return
    yield {"type": "preview",
           "content": _interim_preview({lead: current}, f"{lead_name}의 제안 완료 — 의견 수렴 중")}

    async def finalize(feedback: dict[str, str]):
        yield {"type": "status", "step": "final",
               "label": f"5단계 · {lead_name}가 최적안으로 정리 중…"}
        yield {"type": "ai_start", "ai": lead, "stage": "final"}
        try:
            doc = await ai_clients.call_ai(
                lead, prompts.lead_final_system(lead_name),
                prompts.lead_final_user(question, current, feedback, is_build))
        except ai_clients.AIError:
            doc = current
        doc = _append_build_note(doc, part)
        transcript["final_by"] = lead
        yield {"type": "ai_done", "ai": lead, "stage": "final", "content": doc}
        yield {"type": "preview", "content": doc}
        yield {"type": "final", "content": doc, "transcript": transcript, "is_build": is_build}

    # 주도자만 있으면 바로 최종
    if not others:
        async for ev in finalize({}):
            yield ev
        return

    # 2번 주고받기: 1차 의견 → 수정 → 2차 의견 → 최종
    rounds = [("critique1", "revise1", 2, 1), ("critique2", None, 4, 2)]
    for crit_key, rev_key, crit_step_no, round_no in rounds:
        yield {"type": "status", "step": crit_key,
               "label": f"{crit_step_no}단계 · 나머지 AI가 {round_no}차 의견 제시 중…"}
        for a in others:
            yield {"type": "ai_start", "ai": a, "stage": crit_key}
        feedback: dict[str, str] = {}
        tasks = {
            a: ai_clients.call_ai(
                a, prompts.lead_feedback_system(config.name_of(a)),
                prompts.lead_feedback_user(question, lead_name, current))
            for a in others
        }
        async for ai_id, ok, val in _gather_stream(tasks):
            if ok:
                feedback[ai_id] = val
                transcript[crit_key][ai_id] = val
                yield {"type": "ai_done", "ai": ai_id, "stage": crit_key, "content": val}
            else:
                transcript[crit_key][ai_id] = {"error": val}
                yield {"type": "ai_error", "ai": ai_id, "stage": crit_key, "error": val}

        if rev_key == "revise1":
            # 주도자가 1차 의견 반영해 수정
            yield {"type": "status", "step": "revise1",
                   "label": f"3단계 · {lead_name}가 의견 반영해 수정 중…"}
            yield {"type": "ai_start", "ai": lead, "stage": "revise1"}
            try:
                current = await ai_clients.call_ai(
                    lead, prompts.lead_revise_system(lead_name),
                    prompts.lead_revise_user(question, current, feedback))
                transcript["revise1"][lead] = current
                yield {"type": "ai_done", "ai": lead, "stage": "revise1", "content": current}
            except ai_clients.AIError as e:
                transcript["revise1"][lead] = {"error": str(e)}
                yield {"type": "ai_error", "ai": lead, "stage": "revise1", "error": str(e)}
            yield {"type": "preview",
                   "content": _interim_preview({lead: current}, "수정안 완료 — 최종 수렴 중")}
        else:
            # 2차 의견 반영해 최종 완성
            async for ev in finalize(feedback):
                yield ev


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
