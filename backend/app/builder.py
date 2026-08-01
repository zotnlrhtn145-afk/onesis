"""'이대로 제작하기' — 클로드 코드를 헤드리스로 실행해 전용 폴더 안에서만 제작.

안전장치:
  - 매 제작마다 ~/onesis-builds/날짜_제목/ 형태의 새 폴더를 만들고 그 안에서만 실행(cwd).
  - --allowedTools 로 허용 도구를 지정(목록 밖 도구는 거부).
  - 진행 로그를 SSE 로 실시간 전송, 완료 시 파일 목록 + zip 제공.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any, AsyncIterator

from . import config

_BUILD_ID_RE = re.compile(r"^\d{8}_\d{6}_[0-9A-Za-z가-힣_\-]+$")


def _slug(title: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", (title or "build").strip())
    s = s.strip("-")[:40].strip("-")
    return s or "build"


def _new_build(title: str) -> tuple[str, Path]:
    ts = time.strftime("%Y%m%d_%H%M%S")
    name = f"{ts}_{_slug(title)}"
    d = config.BUILDS_DIR / name
    return name, d


def build_zip_path(build_id: str) -> Path | None:
    """다운로드용 zip 경로. build_id 검증 실패/파일 없음이면 None."""
    if not _BUILD_ID_RE.match(build_id or ""):
        return None
    p = config.BUILDS_DIR / f"{build_id}.zip"
    return p if p.is_file() else None


def _zip_dir(build_id: str, d: Path) -> Path:
    zip_path = config.BUILDS_DIR / f"{build_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(d))
    return zip_path


def _build_prompt(instruction: str) -> str:
    return (
        "아래 개발 지시문에 따라, 지금 이 폴더(현재 작업 디렉터리) 안에 프로그램을 실제로 만들어줘.\n"
        "규칙:\n"
        "- 이 폴더 밖의 파일은 절대 만들거나 수정하지 마.\n"
        "- 필요한 파일을 직접 생성하고, 완성 후 README에 실행 방법을 한국어로 적어줘.\n"
        "- 설명은 짧게, 실제 파일 작성에 집중해줘.\n\n"
        "=== 개발 지시문 ===\n"
        f"{instruction}"
    )


async def run_build(title: str, instruction: str) -> AsyncIterator[dict[str, Any]]:
    config.BUILDS_DIR.mkdir(parents=True, exist_ok=True)
    build_id, d = _new_build(title)
    d.mkdir(parents=True, exist_ok=True)
    (d / "지시문.md").write_text(instruction or "", encoding="utf-8")

    yield {"type": "build_start", "build_id": build_id, "dir": str(d)}
    yield {"type": "log", "line": f"📁 전용 작업 폴더 생성: {d}"}
    yield {"type": "log", "line": "📝 지시문.md 저장 완료"}

    import shutil

    use_mock = config.MOCK or shutil.which(config.CLAUDE_BIN) is None
    if use_mock:
        yield {"type": "log", "line": "⚙️  (데모 모드) 클로드 코드 실행을 시뮬레이션합니다."}
        async for e in _mock_build(d):
            yield e
    else:
        yield {"type": "log", "line": f"⚙️  클로드 코드 실행 중… (허용 도구: {' '.join(config.CLAUDE_ALLOWED_TOOLS)})"}
        try:
            async for e in _real_build(d, instruction):
                yield e
        except Exception as e:  # 방어
            yield {"type": "log", "line": f"⚠ 실행 오류: {e}"}

    files = [str(p.relative_to(d)) for p in sorted(d.rglob("*")) if p.is_file()]
    try:
        _zip_dir(build_id, d)
        has_zip = True
    except Exception as e:
        has_zip = False
        yield {"type": "log", "line": f"⚠ 압축 실패: {e}"}

    yield {
        "type": "build_done",
        "build_id": build_id,
        "files": files,
        "zip": has_zip,
    }


async def _real_build(d: Path, instruction: str) -> AsyncIterator[dict[str, Any]]:
    args = [
        config.CLAUDE_BIN,
        "-p",
        _build_prompt(instruction),
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        *config.CLAUDE_ALLOWED_TOOLS,
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(d),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def _pump():
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if not line.strip():
                continue
            for msg in _format_stream_json(line):
                yield {"type": "log", "line": msg}

    try:
        async for e in _timeout_iter(_pump(), config.BUILD_TIMEOUT):
            yield e
    except asyncio.TimeoutError:
        proc.kill()
        yield {"type": "log", "line": "⏱ 제한 시간을 초과해 중단했습니다."}
    await proc.wait()
    yield {"type": "log", "line": f"✅ 클로드 코드 종료 (코드 {proc.returncode})"}


async def _timeout_iter(agen, timeout: int):
    """비동기 제너레이터 전체에 대략적인 전체 타임아웃 적용."""
    start = asyncio.get_event_loop().time()
    it = agen.__aiter__()
    while True:
        remaining = timeout - (asyncio.get_event_loop().time() - start)
        if remaining <= 0:
            raise asyncio.TimeoutError()
        try:
            item = await asyncio.wait_for(it.__anext__(), timeout=remaining)
        except StopAsyncIteration:
            return
        yield item


def _format_stream_json(line: str) -> list[str]:
    """stream-json 한 줄을 사람이 읽기 쉬운 로그로 변환."""
    try:
        obj = json.loads(line)
    except ValueError:
        return [line]
    t = obj.get("type")
    out: list[str] = []
    if t == "assistant":
        for block in obj.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                out.append("🤖 " + block["text"].strip())
            elif block.get("type") == "tool_use":
                name = block.get("name", "?")
                inp = block.get("input", {})
                target = inp.get("file_path") or inp.get("path") or inp.get("command") or ""
                target = str(target)[:80]
                out.append(f"🔧 {name}: {target}".rstrip())
    elif t == "result":
        res = obj.get("result") or obj.get("subtype") or ""
        if res:
            out.append("📄 " + str(res)[:200])
    elif t == "system" and obj.get("subtype") == "init":
        out.append("🚀 세션 시작")
    return out


async def _mock_build(d: Path) -> AsyncIterator[dict[str, Any]]:
    steps = [
        "🚀 세션 시작",
        "🔧 Write: index.html",
        "🔧 Write: style.css",
        "🔧 Write: README.md",
        "🤖 요청하신 화면을 만들었습니다. 실행 방법은 README를 참고하세요.",
        "✅ 클로드 코드 종료 (코드 0)",
    ]
    (d / "index.html").write_text(
        "<!doctype html>\n<meta charset=utf-8>\n<title>데모 결과물</title>\n"
        "<h1>오네시스 데모 제작 결과물</h1>\n<p>실제 제작 시 여기에 클로드 코드가 만든 파일이 들어갑니다.</p>\n",
        encoding="utf-8",
    )
    (d / "README.md").write_text(
        "# 데모 결과물\n\n실행: index.html 파일을 브라우저로 열면 됩니다.\n", encoding="utf-8"
    )
    for s in steps:
        await asyncio.sleep(0.5)
        yield {"type": "log", "line": s}
