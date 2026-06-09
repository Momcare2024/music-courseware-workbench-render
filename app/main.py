from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .file_extract import describe_upload
from .generator import asset_checklist, generate_lesson, generate_slide_design
from .image_exports import export_wps_upload_assets
from .jimeng import JimengNotConfigured, generate_image, test_jimeng_connection
from .llm import chat_completion
from .ppt_script import parse_full_page_design
from .pptx_export import export_image_deck
from .prompt_store import read_lesson_prompt, write_lesson_prompt
from .settings import PROJECT_ROOT, get_settings
from .storage import (
    artifact_path,
    ensure_project_dirs,
    export_zip,
    list_projects,
    load_project,
    new_project_id,
    now_iso,
    project_dir,
    save_project,
    save_upload,
)

import httpx

app = FastAPI(title="音乐课件工作台", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

IMAGE_REFERENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_STYLE_REFERENCE_IMAGES = 2
MAX_STYLE_REFERENCE_BYTES = 12 * 1024 * 1024
ACCESS_COOKIE = "music_workbench_access"


@app.middleware("http")
async def require_access_code(request: Request, call_next):
    settings = get_settings()
    if not settings.access_code.strip() or _is_public_path(request.url.path):
        return await call_next(request)

    supplied = request.headers.get("X-Access-Code") or request.cookies.get(ACCESS_COOKIE) or ""
    if not secrets.compare_digest(supplied, settings.access_code.strip()):
        return JSONResponse(
            {"ok": False, "message": "请先输入访问码。"},
            status_code=401,
        )
    return await call_next(request)


def _is_public_path(path: str) -> bool:
    return (
        path == "/"
        or path.startswith("/static/")
        or path in {"/api/access", "/api/access/status", "/favicon.ico"}
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/access/status")
def access_status() -> dict:
    settings = get_settings()
    return {"required": bool(settings.access_code.strip())}


@app.post("/api/access")
def verify_access(payload: dict, response: Response) -> dict:
    settings = get_settings()
    expected = settings.access_code.strip()
    if not expected:
        return {"ok": True, "message": "当前未设置访问码。"}

    supplied = str(payload.get("access_code") or "").strip()
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="访问码不正确")

    response.set_cookie(
        ACCESS_COOKIE,
        expected,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 14,
    )
    return {"ok": True, "message": "访问码正确。"}


@app.get("/api/config")
def config() -> dict:
    settings = get_settings()
    return {
        "text_model": settings.text_model,
        "image_model": settings.image_model,
        "vectorengine_configured": bool(settings.vectorengine_api_key.strip()),
        "vectorengine_base_url": settings.vectorengine_base_url,
        "volcengine_configured": bool(settings.ark_api_key.strip()),
        "ark_configured": bool(settings.ark_api_key.strip()),
        "ark_base_url": settings.ark_base_url,
        "ark_image_model": settings.ark_image_model,
        "data_dir": str(settings.workbench_data_dir),
        "ppt_master_root": str(settings.ppt_master_root),
        "access_required": bool(settings.access_code.strip()),
        "web_config_enabled": settings.allow_web_config,
    }


@app.post("/api/config")
def save_config(payload: dict) -> dict:
    settings = get_settings()
    if not settings.allow_web_config:
        raise HTTPException(status_code=403, detail="云端版本请在 Render 环境变量里配置 API Key，网页端不保存密钥。")
    env_path = PROJECT_ROOT / ".env"
    current = _read_env(env_path)
    api_key = str(payload.get("vectorengine_api_key") or "").strip()
    if api_key:
        current["VECTORENGINE_API_KEY"] = api_key
    else:
        current["VECTORENGINE_API_KEY"] = current.get("VECTORENGINE_API_KEY", "")
    current["VECTORENGINE_BASE_URL"] = str(
        payload.get("vectorengine_base_url") or current.get("VECTORENGINE_BASE_URL") or "https://api.vectorengine.ai/v1"
    ).strip()
    current["TEXT_MODEL"] = str(payload.get("text_model") or current.get("TEXT_MODEL") or "claude-sonnet-4-5").strip()
    current["IMAGE_MODEL"] = str(
        payload.get("image_model") or current.get("IMAGE_MODEL") or "doubao-seedream-4-5-251128"
    ).strip()
    if payload.get("volcengine_access_key"):
        current["VOLCENGINE_ACCESS_KEY"] = str(payload.get("volcengine_access_key") or "").strip()
    else:
        current["VOLCENGINE_ACCESS_KEY"] = current.get("VOLCENGINE_ACCESS_KEY", "")
    if payload.get("volcengine_secret_key"):
        current["VOLCENGINE_SECRET_KEY"] = str(payload.get("volcengine_secret_key") or "").strip()
    else:
        current["VOLCENGINE_SECRET_KEY"] = current.get("VOLCENGINE_SECRET_KEY", "")
    current["JIMENG_ENDPOINT"] = str(
        payload.get("jimeng_endpoint") or current.get("JIMENG_ENDPOINT") or "https://visual.volcengineapi.com"
    ).strip()
    current["JIMENG_REQ_KEY"] = str(payload.get("jimeng_req_key") or current.get("JIMENG_REQ_KEY") or "jimeng_t2i_v40").strip()
    if payload.get("ark_api_key"):
        current["ARK_API_KEY"] = str(payload.get("ark_api_key") or "").strip()
    else:
        current["ARK_API_KEY"] = current.get("ARK_API_KEY", "")
    current["ARK_BASE_URL"] = str(
        payload.get("ark_base_url") or current.get("ARK_BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3"
    ).strip()
    current["ARK_IMAGE_MODEL"] = str(
        payload.get("ark_image_model") or current.get("ARK_IMAGE_MODEL") or "doubao-seedream-4-0-250828"
    ).strip()
    current["PPT_MASTER_ROOT"] = str(current.get("PPT_MASTER_ROOT") or PROJECT_ROOT / "ppt-master")
    current["WORKBENCH_DATA_DIR"] = str(current.get("WORKBENCH_DATA_DIR") or PROJECT_ROOT / "data")
    _write_env(env_path, current)
    get_settings.cache_clear()
    return config()


@app.post("/api/config/test")
async def test_config() -> dict:
    settings = get_settings()
    if not settings.vectorengine_api_key.strip():
        return {
            "ok": False,
            "message": "还没有填写 VectorEngine API Key。",
        }
    try:
        content = await chat_completion(
            "你是 API 连通性检测助手。只回复 OK。",
            "请只回复 OK，用于测试 API 是否连通。",
            model=settings.text_model,
            timeout_seconds=30,
        )
        return {
            "ok": True,
            "message": f"API 连接成功，模型返回：{content[:80]}",
        }
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        return {
            "ok": False,
            "message": f"API 连接失败：{message}",
        }


@app.post("/api/config/jimeng/test")
async def test_jimeng_config() -> dict:
    settings = get_settings()
    if not settings.ark_api_key.strip():
        return {"ok": False, "message": "还没有填写方舟 API Key。请复制截图中 API Key 那一列的 ark-...。"}
    if settings.ark_api_key.strip().lower().startswith("apikey-"):
        return {
            "ok": False,
            "message": "你填的是资源 ID apikey-...。请复制左边 API Key 列的 ark-...，不要复制资源 ID。",
        }
    if not settings.ark_api_key.strip().startswith("ark-"):
        return {"ok": False, "message": "当前填写的不是 ark-... 格式。请复制截图中 API Key 那一列。"}
    try:
        data = await test_jimeng_connection()
        count = len(data.get("data") or [])
        return {"ok": True, "message": f"方舟 API Key 可用，已读取到 {count} 个模型信息。"}
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        if "401" in message or "Unauthorized" in message:
            message = "方舟 API Key 无效或没有权限，请确认复制的是 API Key 列的 ark-...，且状态为生效中。"
        return {"ok": False, "message": f"即梦 API 测试失败：{message}"}


@app.get("/api/models")
def available_models() -> dict:
    settings = get_settings()
    if not settings.vectorengine_api_key.strip():
        return {"ok": False, "message": "还没有填写 VectorEngine API Key。", "models": []}
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                settings.vectorengine_base_url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {settings.vectorengine_api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        models = data.get("data") or []
        text_models = [
            {
                "id": item.get("id", ""),
                "description": item.get("description", ""),
                "tags": item.get("tags", ""),
                "model_type": item.get("model_type", ""),
            }
            for item in models
            if item.get("id")
        ]
        return {"ok": True, "message": f"读取到 {len(text_models)} 个模型。", "models": text_models}
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        return {"ok": False, "message": f"读取模型列表失败：{message}", "models": []}


@app.get("/api/prompts/lesson")
def get_lesson_prompt() -> dict:
    return {"content": read_lesson_prompt()}


@app.post("/api/prompts/lesson")
def save_lesson_prompt(payload: dict) -> dict:
    return {"content": write_lesson_prompt(str(payload.get("content") or ""))}


@app.get("/api/projects")
def projects() -> list[dict]:
    return list_projects()


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


@app.post("/api/image-projects")
async def create_image_project(payload: dict) -> dict:
    title = str(payload.get("title") or "").strip() or "音乐课件"
    lesson_text = str(payload.get("lesson_text") or "")
    design_text = str(payload.get("design_text") or "")
    global_style = str(payload.get("global_style") or "").strip()
    if not design_text.strip():
        raise HTTPException(status_code=400, detail="PPT 页面设计稿不能为空")

    project_id = new_project_id()
    ensure_project_dirs(project_id)
    pages = parse_full_page_design(design_text, global_style)
    project = {
        "id": project_id,
        "workflow": "image_pptx",
        "title": title,
        "global_style": global_style,
        "lesson_text": lesson_text,
        "design_text": design_text,
        "pages": pages,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "artifacts": {},
    }
    write_artifacts(project)
    save_project(project)
    return project


@app.patch("/api/projects/{project_id}/image-pages")
async def update_image_pages(project_id: str, payload: dict) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    pages = payload.get("pages") or []
    if not isinstance(pages, list):
        raise HTTPException(status_code=400, detail="pages must be a list")
    project["pages"] = pages
    if payload.get("design_text") is not None:
        project["design_text"] = str(payload.get("design_text") or "")
    if payload.get("global_style") is not None:
        project["global_style"] = str(payload.get("global_style") or "")
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/image-pages/reparse")
async def reparse_image_pages(project_id: str, payload: dict | None = None) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = payload or {}
    design_text = str(payload.get("design_text") or project.get("design_text") or "")
    global_style = str(payload.get("global_style") or project.get("global_style") or "")
    project["design_text"] = design_text
    project["global_style"] = global_style
    project["pages"] = parse_full_page_design(design_text, global_style)
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/image-pages/{page_index}/generate")
async def generate_image_page(project_id: str, page_index: int) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    page = _find_page(project, page_index)
    page["image_status"] = "generating"
    page["error"] = ""
    save_project(project)

    image_name = f"slide-{page_index:02d}.png"
    image_path = artifact_path(project_id, "images") / image_name
    try:
        result = await generate_image(str(page.get("prompt") or page.get("raw_design") or ""), image_path)
        page["image_status"] = "done"
        page["image_file"] = image_name
        page["task_id"] = result.get("task_id", "")
        page["error"] = ""
    except JimengNotConfigured as exc:
        page["image_status"] = "error"
        page["error"] = str(exc)
    except Exception as exc:
        page["image_status"] = "error"
        page["error"] = str(exc) or exc.__class__.__name__
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/image-pages/generate-all")
async def generate_all_image_pages(project_id: str) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    for page in project.get("pages") or []:
        if page.get("image_status") == "done":
            continue
        project = await generate_image_page(project_id, int(page.get("index") or 0))
    return project


@app.post("/api/projects/{project_id}/export-pptx")
def export_project_pptx(project_id: str) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    pptx_path = artifact_path(project_id, f"{project_id}-wps-image-deck.pptx")
    export_image_deck(project, project_dir(project_id), pptx_path)
    project.setdefault("artifacts", {})["pptx"] = pptx_path.name
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/export-wps-upload")
def export_project_wps_upload(project_id: str) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    pdf_path = artifact_path(project_id, f"{project_id}-wps-aippt-upload.pdf")
    zip_path = artifact_path(project_id, f"{project_id}-slide-images.zip")
    try:
        summary = export_wps_upload_assets(project, project_dir(project_id), pdf_path, zip_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    artifacts = project.setdefault("artifacts", {})
    artifacts["wps_upload_pdf"] = pdf_path.name
    artifacts["image_zip"] = zip_path.name
    artifacts.pop("editable_pptx", None)
    legacy_editable = artifact_path(project_id, f"{project_id}-editable-text-deck.pptx")
    if legacy_editable.exists():
        legacy_editable.unlink()
    project["wps_upload_export"] = summary
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects")
async def create_project(
    title: Annotated[str, Form()],
    grade: Annotated[str, Form()] = "小学音乐",
    textbook: Annotated[str, Form()] = "",
    lesson_minutes: Annotated[int, Form()] = 40,
    style: Annotated[str, Form()] = "儿童友好、音乐课堂、清晰明亮",
    notes: Annotated[str, Form()] = "",
    lesson_prompt: Annotated[str, Form()] = "",
    text_model: Annotated[str, Form()] = "",
    image_model: Annotated[str, Form()] = "",
    use_ai: Annotated[bool, Form()] = True,
    files: Annotated[list[UploadFile], File()] = [],
) -> dict:
    settings = get_settings()
    project_id = new_project_id()
    ensure_project_dirs(project_id)

    uploads = []
    for upload in files:
        if not upload.filename:
            continue
        path = save_upload(project_id, upload.filename, await upload.read())
        uploads.append(describe_upload(path))

    project = {
        "id": project_id,
        "title": title,
        "grade": grade,
        "textbook": textbook,
        "lesson_minutes": lesson_minutes,
        "style": style,
        "notes": notes,
        "lesson_prompt": lesson_prompt or read_lesson_prompt(),
        "slide_style_prompt": "",
        "use_style_reference_images": False,
        "style_reference_images": [],
        "text_model": text_model or settings.text_model,
        "image_model": image_model or settings.image_model,
        "use_ai": use_ai,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "uploads": uploads,
        "lesson": {"status": "generating", "content": "", "source": ""},
        "slide_design": {"status": "not_started", "content": "", "source": ""},
        "artifacts": {},
    }
    save_project(project)

    lesson_content, source = await generate_lesson(project, uploads)
    project["lesson"] = {
        "status": "draft",
        "content": lesson_content,
        "source": source,
        "updated_at": now_iso(),
    }
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/lesson/regenerate")
async def regenerate_lesson(project_id: str, payload: dict | None = None) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    payload = payload or {}
    previous = project.get("lesson") or {}
    if previous.get("content"):
        versions = project.setdefault("lesson_versions", [])
        versions.append(
            {
                "saved_at": now_iso(),
                "status": previous.get("status", "draft"),
                "source": previous.get("source", ""),
                "content": previous.get("content", ""),
            }
        )
        project["lesson_versions"] = versions[-10:]

    if payload.get("notes") is not None:
        project["notes"] = str(payload.get("notes") or "")
    if payload.get("lesson_prompt") is not None:
        project["lesson_prompt"] = str(payload.get("lesson_prompt") or read_lesson_prompt())
    else:
        project["lesson_prompt"] = project.get("lesson_prompt") or read_lesson_prompt()
    if payload.get("text_model"):
        project["text_model"] = str(payload.get("text_model"))
    project["use_ai"] = bool(payload.get("use_ai", project.get("use_ai", True)))

    project["lesson"] = {
        "status": "generating",
        "content": previous.get("content", ""),
        "source": previous.get("source", ""),
        "updated_at": now_iso(),
    }
    save_project(project)

    try:
        lesson_content, source = await generate_lesson(project, project.get("uploads") or [])
    except Exception as exc:
        lesson_content = f"# 《{project.get('title') or '音乐课'}》教案重新生成失败\n\n> {exc}\n"
        source = "error"

    project["lesson"] = {
        "status": "draft",
        "content": lesson_content,
        "source": source,
        "updated_at": now_iso(),
    }
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.patch("/api/projects/{project_id}/lesson")
async def update_lesson(project_id: str, payload: dict) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    project["lesson"] = {
        **(project.get("lesson") or {}),
        "content": payload.get("content", ""),
        "status": payload.get("status", "draft"),
        "updated_at": now_iso(),
    }
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/uploads")
async def add_project_uploads(
    project_id: str,
    files: Annotated[list[UploadFile], File()] = [],
) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")

    ensure_project_dirs(project_id)
    uploads = project.setdefault("uploads", [])
    for upload in files:
        if not upload.filename:
            continue
        path = save_upload(project_id, upload.filename, await upload.read())
        uploads.append(describe_upload(path))

    project["uploads"] = uploads
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/slide-design")
async def create_slide_design(project_id: str, payload: dict | None = Body(default=None)) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = payload or {}
    if payload.get("slide_style_prompt") is not None:
        project["slide_style_prompt"] = str(payload.get("slide_style_prompt") or "").strip()
    project["use_style_reference_images"] = bool(
        payload.get("use_style_reference_images", project.get("use_style_reference_images", False))
    )
    if payload.get("text_model"):
        project["text_model"] = str(payload.get("text_model"))
    if payload.get("image_model"):
        project["image_model"] = str(payload.get("image_model"))

    lesson = project.get("lesson") or {}
    content = lesson.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=400, detail="Lesson content is empty")
    style_reference_image_paths = (
        _style_reference_image_paths(project_id, project) if project.get("use_style_reference_images") else []
    )
    project["style_reference_images"] = [path.name for path in style_reference_image_paths]
    project["slide_design"] = {"status": "generating", "content": "", "source": ""}
    save_project(project)

    design_content, source = await generate_slide_design(
        project,
        content,
        project.get("uploads") or [],
        style_reference_image_paths=style_reference_image_paths,
    )
    project["slide_design"] = {
        "status": "draft",
        "content": design_content,
        "source": source,
        "updated_at": now_iso(),
    }
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.patch("/api/projects/{project_id}/slide-design")
async def update_slide_design(project_id: str, payload: dict) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    project["slide_design"] = {
        **(project.get("slide_design") or {}),
        "content": payload.get("content", ""),
        "status": payload.get("status", "draft"),
        "updated_at": now_iso(),
    }
    project["updated_at"] = now_iso()
    write_artifacts(project)
    save_project(project)
    return project


@app.post("/api/projects/{project_id}/export")
def export_project(project_id: str) -> dict:
    try:
        project = load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
    write_artifacts(project)
    zip_path = export_zip(project_id)
    project["artifacts"]["zip"] = zip_path.name
    project["updated_at"] = now_iso()
    save_project(project)
    return project


@app.get("/api/projects/{project_id}/download/{artifact}")
def download_artifact(project_id: str, artifact: str) -> FileResponse:
    allowed = {
        "lesson": "lesson.md",
        "slide_design": "slide_design.md",
        "page_design": "page_design.md",
        "pages_json": "pages.json",
        "pptx": f"{project_id}-wps-image-deck.pptx",
        "wps_upload_pdf": f"{project_id}-wps-aippt-upload.pdf",
        "image_zip": f"{project_id}-slide-images.zip",
        "asset_checklist": "asset_checklist.txt",
        "project": "project.json",
        "zip": f"{project_id}-deliverables.zip",
    }
    name = allowed.get(artifact)
    if not name:
        raise HTTPException(status_code=404, detail="Unknown artifact")
    if artifact == "project":
        path = project_dir(project_id) / "project.json"
    else:
        path = artifact_path(project_id, name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=path.name)


@app.get("/api/projects/{project_id}/images/{filename}")
def get_project_image(project_id: str, filename: str) -> FileResponse:
    path = artifact_path(project_id, "images") / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, filename=path.name)


def write_artifacts(project: dict) -> None:
    if project.get("workflow") == "image_pptx":
        write_image_project_artifacts(project)
        return

    project_id = project["id"]
    artifacts_dir = project_dir(project_id) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    lesson_path = artifact_path(project_id, "lesson.md")
    design_path = artifact_path(project_id, "slide_design.md")
    assets_path = artifact_path(project_id, "asset_checklist.txt")

    lesson_path.write_text((project.get("lesson") or {}).get("content", ""), encoding="utf-8")
    design_path.write_text((project.get("slide_design") or {}).get("content", ""), encoding="utf-8")
    assets_path.write_text(asset_checklist(project), encoding="utf-8")

    project["artifacts"] = {
        **(project.get("artifacts") or {}),
        "lesson": lesson_path.name,
        "slide_design": design_path.name,
        "asset_checklist": assets_path.name,
    }


def write_image_project_artifacts(project: dict) -> None:
    project_id = project["id"]
    artifacts_dir = project_dir(project_id) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "images").mkdir(parents=True, exist_ok=True)

    lesson_path = artifact_path(project_id, "lesson.md")
    design_path = artifact_path(project_id, "page_design.md")
    pages_path = artifact_path(project_id, "pages.json")

    lesson_path.write_text(str(project.get("lesson_text") or ""), encoding="utf-8")
    design_path.write_text(str(project.get("design_text") or ""), encoding="utf-8")
    pages_path.write_text(__import__("json").dumps(project.get("pages") or [], ensure_ascii=False, indent=2), encoding="utf-8")

    project["artifacts"] = {
        **(project.get("artifacts") or {}),
        "lesson": lesson_path.name,
        "page_design": design_path.name,
        "pages_json": pages_path.name,
    }


def _find_page(project: dict, page_index: int) -> dict:
    for page in project.get("pages") or []:
        if int(page.get("index") or 0) == page_index:
            return page
    raise HTTPException(status_code=404, detail="Page not found")


def _style_reference_image_paths(project_id: str, project: dict) -> list[Path]:
    upload_dir = project_dir(project_id) / "uploads"
    paths: list[Path] = []
    for item in project.get("uploads") or []:
        filename = Path(str(item.get("filename") or "")).name
        if not filename:
            continue
        suffix = str(item.get("suffix") or Path(filename).suffix).lower()
        if suffix not in IMAGE_REFERENCE_SUFFIXES:
            continue
        path = upload_dir / filename
        try:
            if path.exists() and path.stat().st_size <= MAX_STYLE_REFERENCE_BYTES:
                paths.append(path)
        except OSError:
            continue
        if len(paths) >= MAX_STYLE_REFERENCE_IMAGES:
            break
    return paths


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    lines = [
        "# VectorEngine / OpenAI-compatible gateway",
        f"VECTORENGINE_API_KEY={values.get('VECTORENGINE_API_KEY', '')}",
        f"VECTORENGINE_BASE_URL={values.get('VECTORENGINE_BASE_URL', 'https://api.vectorengine.ai/v1')}",
        "",
        "# Pick models available in your VectorEngine account.",
        f"TEXT_MODEL={values.get('TEXT_MODEL', 'claude-sonnet-4-5')}",
        f"IMAGE_MODEL={values.get('IMAGE_MODEL', 'doubao-seedream-4-5-251128')}",
        "",
        "# Optional: point to the installed PPT Master clone for future PPTX export.",
        f"PPT_MASTER_ROOT={values.get('PPT_MASTER_ROOT', str(PROJECT_ROOT / 'ppt-master'))}",
        "",
        "# Volcengine Jimeng image generation.",
        f"VOLCENGINE_ACCESS_KEY={values.get('VOLCENGINE_ACCESS_KEY', '')}",
        f"VOLCENGINE_SECRET_KEY={values.get('VOLCENGINE_SECRET_KEY', '')}",
        f"JIMENG_ENDPOINT={values.get('JIMENG_ENDPOINT', 'https://visual.volcengineapi.com')}",
        f"JIMENG_REQ_KEY={values.get('JIMENG_REQ_KEY', 'jimeng_t2i_v40')}",
        "",
        "# Volcengine Ark image generation. Copy the ark-... value from Ark API Key Management.",
        f"ARK_API_KEY={values.get('ARK_API_KEY', '')}",
        f"ARK_BASE_URL={values.get('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')}",
        f"ARK_IMAGE_MODEL={values.get('ARK_IMAGE_MODEL', 'doubao-seedream-4-0-250828')}",
        "",
        "# Local data directory for projects and generated artifacts.",
        f"WORKBENCH_DATA_DIR={values.get('WORKBENCH_DATA_DIR', str(PROJECT_ROOT / 'data'))}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
