"""토론 각 단계의 한국어 프롬프트."""
from __future__ import annotations

from . import config

# 프로그램/앱/웹 제작 관련 질문인지 판별하는 키워드
_BUILD_KEYWORDS = [
    "앱", "어플", "애플리케이션", "프로그램", "웹", "웹사이트", "홈페이지", "사이트",
    "서비스", "플랫폼", "만들", "제작", "개발", "구현", "코딩", "봇", "게임",
    "app", "application", "website", "web", "site", "build", "develop", "program",
]


def detect_build(question: str) -> bool:
    q = (question or "").lower()
    return any(k in q for k in _BUILD_KEYWORDS)


def initial_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다. 여러 AI가 함께 토론해 최선의 답을 만드는 자리에 참여합니다. "
        "사용자의 질문에 대해 명확하고 근거 있는 답변을 한국어 마크다운으로 작성하세요. "
        "간결하되 핵심을 빠뜨리지 마세요."
    )


def initial_user(question: str, is_build: bool) -> str:
    extra = ""
    if is_build:
        extra = (
            "\n\n이 질문은 무언가를 '만드는' 기획/설계에 관한 것입니다. "
            "실제 코드는 쓰지 말고, 무엇을 어떻게 만들지(기능·화면·구성)를 구체적으로 제안하세요."
        )
    return f"[질문]\n{question}{extra}"


def critique_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다. 다른 두 AI의 답변을 비평합니다. "
        "각 답변마다 '동의하는 점 / 반대하는 점(근거 포함) / 보완할 점'을 항목으로 명확히 정리하세요. "
        "예의 있고 건설적으로, 한국어로 작성하세요."
    )


def critique_user(question: str, others: dict[str, str]) -> str:
    blocks = []
    for ai_id, ans in others.items():
        blocks.append(f"### {config.name_of(ai_id)}의 답변\n{ans}")
    joined = "\n\n".join(blocks)
    return (
        f"[원래 질문]\n{question}\n\n"
        f"[검토할 다른 AI들의 답변]\n{joined}\n\n"
        "위 각 답변에 대해 '동의하는 점 / 반대하는 점(근거) / 보완할 점'을 정리하세요."
    )


def revise_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다. 다른 AI들이 남긴 지적을 반영해 당신의 답변을 개선합니다. "
        "개선된 최종 답변만 한국어 마크다운으로 출력하세요(지적을 그대로 나열하지 말 것)."
    )


def revise_user(question: str, own_answer: str, feedback: dict[str, str]) -> str:
    fb = []
    for ai_id, txt in feedback.items():
        fb.append(f"### {config.name_of(ai_id)}의 지적\n{txt}")
    joined = "\n\n".join(fb) if fb else "(받은 지적 없음)"
    return (
        f"[원래 질문]\n{question}\n\n"
        f"[당신의 기존 답변]\n{own_answer}\n\n"
        f"[다른 AI들이 남긴 지적]\n{joined}\n\n"
        "지적 중 타당한 부분을 반영해 당신의 답변을 개선해 다시 작성하세요."
    )


def moderator_system() -> str:
    return (
        "당신은 여러 AI 토론의 '사회자'입니다. 각 AI의 최종 답변과 서로에 대한 검토를 종합해 "
        "하나의 완성된 결과물을 한국어 마크다운으로 작성합니다. 균형 있고 중립적으로 정리하세요."
    )


def moderator_user(
    question: str,
    revised: dict[str, str],
    critiques2: dict[str, str],
    is_build: bool,
) -> str:
    ans_blocks = "\n\n".join(
        f"### {config.name_of(a)}의 수정 답변\n{t}" for a, t in revised.items()
    )
    crit_blocks = "\n\n".join(
        f"### {config.name_of(a)}의 2차 검토\n{t}" for a, t in critiques2.items()
    ) or "(검토 없음)"

    if is_build:
        fmt = (
            "이 질문은 무언가를 '만드는' 것에 관한 것입니다. 결과물을 클로드 코드(개발 AI)에 "
            "그대로 전달할 수 있는 '개발 지시문' 형태로 작성하세요. 실제 코드는 절대 넣지 말고, "
            "무엇을 만들지만 구체적으로 적으세요. 반드시 아래 구조를 사용하세요:\n\n"
            "## 프로젝트 개요\n## 기능 목록\n## 화면 구성과 디자인\n## 기술 구성\n## 완료 기준"
        )
    else:
        fmt = (
            "반드시 아래 구조를 사용하세요:\n\n"
            "## 최종 답변\n## AI들이 모두 동의한 점\n## 의견이 갈린 점"
        )

    return (
        f"[원래 질문]\n{question}\n\n"
        f"[각 AI의 수정 답변]\n{ans_blocks}\n\n"
        f"[2차 상호 검토]\n{crit_blocks}\n\n"
        f"[작성 지침]\n{fmt}"
    )


def refine_system() -> str:
    return (
        "당신은 결과물 문서를 다듬는 편집자입니다. 사용자가 요청한 부분을 중심으로 문서를 수정하되, "
        "요청과 무관한 부분은 최대한 그대로 유지하세요. 수정된 '전체 문서'를 한국어 마크다운으로 출력하세요."
    )


def refine_user(current_doc: str, instruction: str) -> str:
    return (
        f"[현재 문서]\n{current_doc}\n\n"
        f"[수정 요청]\n{instruction}\n\n"
        "위 요청을 반영해 문서 전체를 다시 출력하세요."
    )
