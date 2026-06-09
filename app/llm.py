from __future__ import annotations

import base64
import mimetypes
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

import httpx

from .settings import get_settings


class LLMNotConfigured(RuntimeError):
    pass


MAX_VISION_IMAGE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_IMAGE_BYTES = 12 * 1024 * 1024
TARGET_VISION_IMAGE_EDGE = 1024
TARGET_VISION_IMAGE_QUALITY = "75"


def _image_part(path: Path) -> dict:
    image_bytes, mime_type = _prepared_image_bytes(path)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{mime_type};base64,{encoded}",
        },
    }


def _prepared_image_bytes(path: Path) -> tuple[bytes, str]:
    original = path.read_bytes()
    original_mime = mimetypes.guess_type(path.name)[0] or "image/png"
    compressed = _compress_image_for_vision(path)
    if compressed and len(compressed) <= MAX_VISION_IMAGE_BYTES:
        return compressed, "image/jpeg"
    if len(original) > MAX_VISION_IMAGE_BYTES:
        raise RuntimeError(f"参考图过大，已跳过：{path.name}")
    return original, original_mime


def _compress_image_for_vision(path: Path) -> bytes | None:
    sips_path = Path("/usr/bin/sips")
    if not sips_path.exists():
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="ppt-style-ref-") as tmpdir:
            output = Path(tmpdir) / f"{path.stem}.jpg"
            subprocess.run(
                [
                    str(sips_path),
                    "-s",
                    "format",
                    "jpeg",
                    "-s",
                    "formatOptions",
                    TARGET_VISION_IMAGE_QUALITY,
                    "-Z",
                    str(TARGET_VISION_IMAGE_EDGE),
                    str(path),
                    "--out",
                    str(output),
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
            if output.exists() and output.stat().st_size <= MAX_VISION_IMAGE_BYTES:
                return output.read_bytes()
    except Exception:
        return None
    return None


def _user_content(user_prompt: str, image_paths: Sequence[Path] | None = None) -> str | list[dict]:
    parts: list[dict] = [{"type": "text", "text": user_prompt}]
    for path in image_paths or []:
        try:
            if path.exists() and path.stat().st_size <= MAX_SOURCE_IMAGE_BYTES:
                parts.append(_image_part(path))
        except OSError:
            continue
        except RuntimeError:
            continue

    if len(parts) == 1:
        return user_prompt

    return parts[:3]


async def chat_completion(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    timeout_seconds: float = 180,
    image_paths: Sequence[Path] | None = None,
) -> str:
    settings = get_settings()
    api_key = settings.vectorengine_api_key.strip()
    if not api_key:
        raise LLMNotConfigured("VECTORENGINE_API_KEY is not configured")

    base_url = settings.vectorengine_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model or settings.text_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _user_content(user_prompt, image_paths)},
        ],
        "temperature": 0.4,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.ConnectError as exc:
            detail = str(exc).strip() or "网络连接失败"
            raise RuntimeError(f"无法连接到 API 网关：{detail}") from exc
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"API 请求超时，已等待 {timeout_seconds:g} 秒") from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500]
            raise RuntimeError(f"{exc.response.status_code} {exc.response.reason_phrase}: {detail}") from exc
        data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"LLM response missing choices: {data}")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or item) for item in content)
    return str(content)
