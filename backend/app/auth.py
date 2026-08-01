"""간단한 비밀번호 로그인 + 서명 토큰. 서버에 상태를 저장하지 않습니다."""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Optional

from fastapi import Header, HTTPException, Query

from . import config


def _sign(msg: str) -> str:
    sig = hmac.new(config.SESSION_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def check_password(password: str) -> bool:
    # 타이밍 공격 방지용 상수시간 비교
    return hmac.compare_digest(password or "", config.LOGIN_PASSWORD or "")


def create_token() -> str:
    exp = int(time.time()) + config.TOKEN_TTL_SECONDS
    msg = str(exp)
    return f"{msg}.{_sign(msg)}"


def verify_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    msg, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(msg)):
        return False
    try:
        exp = int(msg)
    except ValueError:
        return False
    return exp >= int(time.time())


async def require_auth(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> None:
    """헤더(Authorization: Bearer ...) 또는 ?token= 쿼리로 인증."""
    tok = None
    if authorization and authorization.lower().startswith("bearer "):
        tok = authorization[7:].strip()
    elif token:
        tok = token
    if not verify_token(tok):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
