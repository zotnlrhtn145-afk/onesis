"""3개 AI 공급자를 각자의 공식 SDK로 비동기 호출합니다.

한 AI가 오류를 내도 예외로 알리고, 오케스트레이터가 나머지로 계속 진행합니다.
"""
from __future__ import annotations

import asyncio

from . import config


class AIError(Exception):
    """특정 AI 호출 실패. 전체를 멈추지 않고 이 AI만 건너뛰기 위한 신호."""


def is_available(ai_id: str) -> bool:
    p = config.participant(ai_id)
    if not p:
        return False
    if config.MOCK:
        return True
    prov = p["provider"]
    if prov == "anthropic":
        return bool(config.ANTHROPIC_API_KEY)
    if prov == "openai":
        return bool(config.OPENAI_API_KEY)
    if prov == "google":
        return bool(config.GEMINI_API_KEY)
    return False


def available_ids() -> list[str]:
    return [p["id"] for p in config.PARTICIPANTS if is_available(p["id"])]


async def call_ai(
    ai_id: str, system: str, user_prompt: str, max_tokens: int = 0
) -> str:
    """지정한 AI에게 system + user 프롬프트를 보내고 텍스트 응답을 반환."""
    p = config.participant(ai_id)
    if not p:
        raise AIError(f"알 수 없는 AI: {ai_id}")
    if config.MOCK:
        return await _mock_reply(ai_id, system, user_prompt)
    mt = max_tokens or config.MAX_TOKENS
    prov = p["provider"]
    try:
        coro = {
            "anthropic": _call_claude,
            "openai": _call_openai,
            "google": _call_gemini,
        }[prov](system, user_prompt, mt)
        return await asyncio.wait_for(coro, timeout=config.AI_TIMEOUT)
    except AIError:
        raise
    except asyncio.TimeoutError:
        raise AIError(f"{p['name']} 응답 시간 초과")
    except Exception as e:  # SDK/네트워크 오류 등
        raise AIError(f"{p['name']} 오류: {type(e).__name__}: {e}")


_MOCK_BUILD_DOC = """## 프로젝트 개요
사용자의 요청을 바탕으로 만든 데모 기획안입니다. (실제 AI 응답이 아니라 데모 모드 예시입니다.)

## 기능 목록
- 핵심 기능 A: 사용자가 가장 자주 쓰는 동작
- 핵심 기능 B: 보조 기능
- 설정 및 개인화

## 화면 구성과 디자인
- 첫 화면: 큰 입력창과 간결한 안내
- 목록 화면: 카드형 배치
- 밝은 배경 + 파랑~보라 포인트 색, 다크 모드 지원

## 기술 구성
- 프론트엔드: React
- 백엔드: FastAPI
- 저장소: SQLite

## 완료 기준
- 위 기능이 모두 동작하고 화면이 모바일에서도 깨지지 않는다.
"""

_MOCK_ANSWER_DOC = """## 최종 답변
데모 모드 예시 답변입니다. 실제로는 세 AI의 토론을 종합한 결론이 이 자리에 들어갑니다.

## AI들이 모두 동의한 점
- 핵심 방향에 대한 공통된 결론

## 의견이 갈린 점
- 세부 방법론에서 일부 관점 차이
"""


async def _mock_reply(ai_id: str, system: str, user_prompt: str) -> str:
    """데모 모드: 실제 API 호출 없이 그럴듯한 응답을 생성."""
    await asyncio.sleep(0.4)
    name = config.name_of(ai_id)
    if "## 프로젝트 개요" in user_prompt:
        return _MOCK_BUILD_DOC
    if "## 최종 답변" in user_prompt:
        return _MOCK_ANSWER_DOC
    if "다듬는" in system or "편집자" in system:
        return "문서를 요청하신 방향으로 다듬었습니다. (데모 모드)\n\n" + _MOCK_BUILD_DOC
    if "비평" in system:
        return (
            f"**{name}의 검토**\n\n"
            "- **동의하는 점**: 전체 방향은 합리적입니다.\n"
            "- **반대하는 점**: 일부 근거가 부족합니다.\n"
            "- **보완할 점**: 예시를 추가하면 좋겠습니다."
        )
    if "개선" in system:
        return (
            f"**{name}의 수정 답변**\n\n"
            "받은 지적을 반영해 근거와 예시를 보강했습니다. (데모 모드)"
        )
    return (
        f"**{name}의 1차 답변**\n\n"
        "이것은 데모(mock) 응답입니다. 실제 API 키를 넣으면 진짜 AI 답변이 표시됩니다.\n\n"
        "1. 핵심 요점\n2. 근거\n3. 제안"
    )


async def _call_claude(system: str, user_prompt: str, max_tokens: int) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise AIError("ANTHROPIC_API_KEY 가 설정되지 않았습니다.")
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    kwargs: dict = dict(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # 토론용 짧은 답변이므로 사고(thinking)는 끕니다(속도·비용·예측성).
    # 최신 모델에서만 유효한 옵션이라 실패하면 옵션 없이 재시도합니다.
    try:
        resp = await client.messages.create(thinking={"type": "disabled"}, **kwargs)
    except Exception:
        resp = await client.messages.create(**kwargs)
    if getattr(resp, "stop_reason", None) == "refusal":
        raise AIError("클로드가 안전상 이유로 응답을 거부했습니다.")
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    text = "".join(parts).strip()
    if not text:
        raise AIError("클로드가 빈 응답을 반환했습니다.")
    return text


async def _call_openai(system: str, user_prompt: str, max_tokens: int) -> str:
    if not config.OPENAI_API_KEY:
        raise AIError("OPENAI_API_KEY 가 설정되지 않았습니다.")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    try:
        resp = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
        )
    except Exception:
        # 일부 최신 모델은 max_tokens 대신 max_completion_tokens 를 요구합니다.
        resp = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise AIError("챗지피티가 빈 응답을 반환했습니다.")
    return text


async def _call_gemini(system: str, user_prompt: str, max_tokens: int) -> str:
    if not config.GEMINI_API_KEY:
        raise AIError("GEMINI_API_KEY 가 설정되지 않았습니다.")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = await client.aio.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        raise AIError("제미나이가 빈 응답을 반환했습니다.")
    return text
