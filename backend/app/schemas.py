"""요청 본문 스키마."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class LoginReq(BaseModel):
    password: str


class NewConversationReq(BaseModel):
    title: Optional[str] = None


class RenameReq(BaseModel):
    title: str


class AskReq(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    ai_ids: Optional[List[str]] = None  # 참여시킬 AI 선택(없으면 사용 가능한 전체)


class RefineReq(BaseModel):
    conversation_id: str
    current_doc: str
    instruction: str


class BuildReq(BaseModel):
    title: Optional[str] = None
    instruction: str
    conversation_id: Optional[str] = None
    design_html: Optional[str] = None  # 승인한 화면 미리보기(HTML) — 이 디자인 그대로 제작


class PreviewReq(BaseModel):
    preview: str


class MockupReq(BaseModel):
    conversation_id: Optional[str] = None
    brief: Optional[str] = None          # 기획안(설명)으로 화면 새로 만들기
    instruction: Optional[str] = None    # 현재 화면을 수정
    current_html: Optional[str] = None
