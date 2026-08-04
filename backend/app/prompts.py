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


# 파트(주제) 분류용 키워드 — 위에서부터 먼저 맞는 것을 선택
_PART_KEYWORDS = [
    ("build", [
        "코딩", "코드", "프로그래밍", "구현", "개발해", "함수", "버그", "리팩터", "리팩토링",
        "디버그", "데이터베이스", "스크립트", "코드 짜", "코드로", "직접 만들어", "깃허브",
        "배포", "api 만들", "백엔드 코드", "프론트 코드",
    ]),
    ("design", [
        "디자인", "ui", "ux", "화면 구성", "레이아웃", "색상", "컬러", "색깔", "폰트", "글꼴",
        "로고", "아이콘", "그래픽", "스타일", "테마", "배치", "시각", "비주얼", "목업",
        "와이어프레임", "화면 디자인",
    ]),
    ("idea", [
        "아이디어", "브레인스토밍", "컨셉", "무엇을 만들", "뭘 만들", "어떤 걸 만들",
        "주제 추천", "기능 추천", "뭐가 좋을", "아이템", "영감", "방향 잡", "떠올",
    ]),
    ("plan", ["기획", "기획안", "설계", "정리", "문서", "계획", "스펙", "요구사항", "로드맵"]),
]


def detect_part(question: str) -> str:
    """질문을 idea/design/plan/build 중 하나로 분류. 기본값은 plan(다같이)."""
    q = (question or "").lower()
    for part, kws in _PART_KEYWORDS:
        if any(k in q for k in kws):
            return part
    return "plan"


# ---------- 주도(lead) 방식 프롬프트 ----------
_PART_GUIDE = {
    "idea": "아이디어와 컨셉을 발굴하고 다양한 가능성을 제시",
    "design": "화면 구성·UI·색과 폰트 등 디자인을 구체적으로 제시",
    "plan": "전체 기획을 정리",
    "build": "무엇을 어떻게 만들지 개발 관점에서 구체화",
}


# 결과 끝에 붙이는 '어떻게 이 결론이 나왔는지' 설명 섹션.
# 각 AI 의견 → 그중 좋은 점 반영 → 그래서 이런 결론, 을 사용자에게 보여준다.
_SYNTHESIS_SECTION = (
    "\n\n[매우 중요] 답변 본문은 핵심 위주로 명료하게 쓰고(장황하게 늘어놓지 말 것), "
    "분량이 많아지더라도 반드시 맨 끝에 아래 '## 이렇게 결론이 나왔어요' 섹션을 포함해 마무리하세요. "
    "이 섹션을 빠뜨리면 안 됩니다. 이 섹션은 5~7줄로 간결하게:\n\n"
    "## 이렇게 결론이 나왔어요\n"
    "- 각 AI가 어떤 의견·강조점을 냈는지 한 줄씩. 예) **클로드**: … / **챗지피티**: … / **제미나이**: …\n"
    "- 그중 어떤 점이 좋아서 반영했고 어떤 의견은 왜 덜 반영했는지, "
    "그래서 왜 이런 결론이 되었는지 2~3문장으로 설명."
)


def _final_format(is_build: bool) -> str:
    if is_build:
        return (
            "결과물을 클로드 코드(개발 AI)에 그대로 넘길 수 있는 '개발 지시문'으로 작성하세요. "
            "실제 코드는 넣지 말고, 아래 구조를 사용하세요:\n\n"
            "## 프로젝트 개요\n## 기능 목록\n## 화면 구성과 디자인\n## 기술 구성\n## 완료 기준"
            + _SYNTHESIS_SECTION
        )
    return (
        "질문에 대한 답을 자연스럽고 읽기 좋게 작성하세요. 개인적인 궁금증이면 딱딱한 보고서 형식 말고 "
        "대화하듯 명확하게 답하되 근거를 함께 제시하세요. 답은 '## 답변' 섹션으로 시작하세요."
        + _SYNTHESIS_SECTION
    )


def lead_propose_system(name: str, part: str) -> str:
    return (
        f"당신은 '{name}'입니다. 이번 주제('{config.PART_LABELS.get(part, part)}')의 주도자로서 "
        f"{_PART_GUIDE.get(part, '최선의 방향을 제시')}합니다. "
        "명확하고 근거 있는 제안을 한국어 마크다운으로 작성하세요."
    )


def lead_propose_user(question: str, part: str) -> str:
    return f"[요청]\n{question}\n\n당신이 주도해 최선의 방향을 제안하세요."


def lead_feedback_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다. 주도자의 제안을 검토해 '동의하는 점 / 반대(근거) / 더 나은 대안'을 "
        "간결하게 제시합니다. 목표는 더 좋은 최적안을 함께 찾는 것입니다. 한국어로 작성하세요."
    )


def lead_feedback_user(question: str, lead_name: str, current: str) -> str:
    return (
        f"[요청]\n{question}\n\n"
        f"[{lead_name}(주도)의 현재 제안]\n{current}\n\n"
        "이 제안을 더 좋게 만들 의견을 주세요."
    )


def lead_revise_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다(주도자). 받은 의견 중 타당한 것을 반영해 제안을 더 낫게 개선합니다. "
        "개선된 제안만 한국어 마크다운으로 출력하세요."
    )


def lead_revise_user(question: str, current: str, feedback: dict[str, str]) -> str:
    fb = "\n\n".join(f"### {config.name_of(a)}\n{t}" for a, t in feedback.items()) or "(의견 없음)"
    return (
        f"[요청]\n{question}\n\n"
        f"[당신의 현재 제안]\n{current}\n\n"
        f"[받은 의견]\n{fb}\n\n"
        "의견을 반영해 제안을 개선해 다시 작성하세요."
    )


def lead_final_system(name: str) -> str:
    return (
        f"당신은 '{name}'입니다(주도자). 지금까지의 논의를 종합해 최적의 결과물을 완성합니다. "
        "결과물만 한국어 마크다운으로 출력하세요."
    )


def lead_final_user(question: str, current: str, feedback: dict[str, str], is_build: bool) -> str:
    fb = "\n\n".join(f"### {config.name_of(a)}\n{t}" for a, t in feedback.items()) or "(의견 없음)"
    return (
        f"[요청]\n{question}\n\n"
        f"[당신(주도)이 다듬어 온 제안]\n{current}\n\n"
        f"[다른 AI들이 낸 의견]\n{fb}\n\n"
        f"[작성 지침]\n{_final_format(is_build)}"
    )


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
            + _SYNTHESIS_SECTION
        )
    else:
        fmt = (
            "질문에 대한 답을 자연스럽고 읽기 좋게 작성하세요. 개인적인 궁금증이면 딱딱한 보고서 형식 "
            "말고 대화하듯 명확하게 답하되, 근거를 함께 제시하세요. 답은 '## 답변' 섹션으로 시작하세요."
            + _SYNTHESIS_SECTION
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


# ---------- 화면 미리보기(실제 UI 목업) ----------
def mockup_system() -> str:
    return (
        "당신은 토스·인스타그램·에어비앤비·Linear 같은 완성도 높은 제품을 만들어 온 시니어 프로덕트 "
        "디자이너입니다. 주어진 기획을 바탕으로 실제 앱에서 바로 볼 법한 '완성된 화면'을 단일 HTML "
        "문서 하나로 만듭니다. 포트폴리오에 올릴 수준의 결과물을 냅니다.\n\n"
        "[디자인 원칙 — 반드시 지킬 것]\n"
        "- 기획/요청에 적힌 분위기·스타일·레퍼런스를 최우선으로 충실히 재현한다. "
        "'인스타그램처럼', '심플', '미니멀', '밝게', '감성적인' 같은 표현이 있으면 그 시각 언어를 그대로 구현한다.\n"
        "- 특별한 지시가 없으면 '밝고 깨끗한' 톤이 기본이다. 요청하지 않았는데 어두운(다크) 테마로 만들지 말 것.\n"
        "- 여백을 넉넉히 준다(답답하지 않게). 요소 간 간격·정렬을 정돈한다.\n"
        "- 타이포 위계를 뚜렷하게(큰 제목 / 본문 / 작은 캡션의 크기·굵기 대비). 시스템 폰트 사용.\n"
        "- 색은 절제한다: 중립 톤(흰·회색) 바탕 + 포인트 컬러 1~2개. 부드러운 그림자, 둥근 모서리(14~20px).\n"
        "- 상단바·탭바·카드·버튼 등 실제 앱 구조를 갖춘다. 터치 타깃은 넉넉히.\n"
        "- 실제 제품처럼 보이도록 자연스러운 한국어 콘텐츠로 채운다. "
        "'예시 항목 1', 'placeholder', 로렘입숨 같은 성의 없는 텍스트 금지 — 진짜 서비스처럼 구체적으로.\n\n"
        "[기술 규칙]\n"
        "- <!doctype html> 로 시작하는 완결된 단일 문서.\n"
        "- 모든 CSS는 문서 안 <style> 에 인라인. 외부 폰트·이미지·스크립트·URL 금지.\n"
        "- 아이콘은 이모지로, 사진 자리는 은은한 그라데이션/색 블록으로 대체.\n"
        "- 모바일 세로(가로 ~390px) 우선.\n"
        "- 설명·마크다운·코드펜스(```) 없이 '오직 HTML' 만 출력.\n\n"
        "절대 '데모처럼 대충 만든 어두운 화면'을 내지 말 것."
    )


def mockup_user(brief: str) -> str:
    return (
        "아래는 이 앱/화면의 기획과 '원하는 느낌'이야. 여기서 디자인 톤·분위기·레퍼런스를 정확히 읽어내서 "
        "그대로 반영해줘. 요청한 스타일이 있으면 반드시 그 스타일을 따를 것.\n\n"
        f"[기획 / 원하는 디자인]\n{brief}\n\n"
        "이걸로 실제 사용자에게 보일 완성된 화면 하나를 만들어줘. 포트폴리오 수준으로. HTML만 출력."
    )


def mockup_refine_user(current_html: str, instruction: str) -> str:
    return (
        f"[현재 화면 HTML]\n{current_html}\n\n"
        f"[수정 요청]\n{instruction}\n\n"
        "요청을 반영해 화면 전체 HTML을 다시 출력해줘. HTML만 출력."
    )
