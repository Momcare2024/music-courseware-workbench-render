from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx

from .settings import get_settings


class JimengNotConfigured(RuntimeError):
    pass


class JimengError(RuntimeError):
    pass


def _ark_headers() -> dict[str, str]:
    settings = get_settings()
    api_key = settings.ark_api_key.strip()
    if not api_key:
        raise JimengNotConfigured("请先填写方舟 API Key，也就是截图里 API Key 列的 ark-...，不是资源 ID。")
    if not api_key.startswith("ark-"):
        raise JimengNotConfigured("当前填写的不是 ark-... 格式的方舟 API Key。请复制截图中 API Key 那一列。")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def test_jimeng_connection() -> dict:
    settings = get_settings()
    url = settings.ark_base_url.rstrip("/") + "/models"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url, headers=_ark_headers())
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise JimengError("方舟 API 请求超时") from exc
        except httpx.HTTPStatusError as exc:
            raise JimengError(_friendly_http_error("方舟 API", response)) from exc
        except httpx.ConnectError as exc:
            raise JimengError(f"无法连接方舟 API：{exc}") from exc
    return response.json()


async def generate_image(prompt: str, output_path: Path, width: int = 2560, height: int = 1440) -> dict:
    settings = get_settings()
    url = settings.ark_base_url.rstrip("/") + "/images/generations"
    payload = {
        "model": settings.ark_image_model,
        "prompt": prompt[:4000],
        "size": "2K",
        "response_format": "b64_json",
        "watermark": False,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        try:
            response = await client.post(url, headers=_ark_headers(), json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise JimengError("方舟图片生成请求超时，已等待 180 秒") from exc
        except httpx.HTTPStatusError as exc:
            raise JimengError(_friendly_http_error("方舟图片生成", response)) from exc
        except httpx.ConnectError as exc:
            raise JimengError(f"无法连接方舟图片生成接口：{exc}") from exc

    data = response.json()
    items = data.get("data") or []
    if not items:
        raise JimengError(f"图片生成响应为空：{data}")
    image = items[0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if image.get("b64_json"):
        output_path.write_bytes(base64.b64decode(image["b64_json"]))
    elif image.get("url"):
        async with httpx.AsyncClient(timeout=60) as client:
            image_response = await client.get(image["url"])
            image_response.raise_for_status()
        output_path.write_bytes(image_response.content)
    else:
        raise JimengError(f"图片生成完成但没有返回图片内容：{data}")

    return {
        "task_id": data.get("id") or "",
        "status": "done",
        "file": output_path.name,
        "raw": data,
    }


def _friendly_http_error(label: str, response: httpx.Response) -> str:
    text = response.text[:600]
    try:
        data = response.json()
        error = data.get("error") or {}
        message = error.get("message") or data.get("message") or text
        code = error.get("code") or data.get("code") or response.status_code
        return f"{label}失败：{response.status_code} {code}，{message}"
    except json.JSONDecodeError:
        return f"{label}失败：{response.status_code} {text}"
