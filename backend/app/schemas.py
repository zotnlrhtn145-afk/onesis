"""요청 본문 스키마."""
from __future__ import annotations

from typing import Optional

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


class RefineReq(BaseModel):
    conversation_id: str
    current_doc: str
    instruction: str


class BuildReq(BaseModel):
    title: Optional[str] = None
    instruction: str
    conversation_id: Optional[str] = None


class PreviewReq(BaseModel):
    preview: str
