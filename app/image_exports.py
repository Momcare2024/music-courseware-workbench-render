from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path


def export_wps_upload_assets(project: dict, base_dir: Path, pdf_path: Path, zip_path: Path) -> dict:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("缺少 Pillow 依赖，无法导出 WPS 上传图片/PDF") from exc

    pages = project.get("pages") or []
    images_dir = base_dir / "artifacts" / "images"
    output_dir = base_dir / "artifacts" / "wps-upload-images"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_images: list[Path] = []
    missing_pages: list[int] = []
    for page in pages:
        index = int(page.get("index") or 0)
        image_file = str(page.get("image_file") or "")
        image_path = images_dir / Path(image_file).name
        if not image_file or not image_path.exists():
            missing_pages.append(index)
            continue

        title = _safe_filename(str(page.get("title") or f"第{index}页"))
        output_image = output_dir / f"{index:02d}-{title}.jpg"
        with Image.open(image_path) as image:
            rgb_image = _to_rgb(ImageOps.exif_transpose(image))
            rgb_image.save(output_image, "JPEG", quality=95, optimize=True)
        exported_images.append(output_image)

    if not exported_images:
        raise RuntimeError("还没有已生成的页面图片，请先生成至少一页")

    _save_pdf(exported_images, pdf_path)
    _save_zip(exported_images, zip_path)
    return {
        "image_count": len(exported_images),
        "missing_pages": [page for page in missing_pages if page],
        "image_dir": output_dir.name,
        "pdf": pdf_path.name,
        "zip": zip_path.name,
    }


def _to_rgb(image):
    from PIL import Image

    if image.mode == "RGB":
        return image.copy()
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _save_pdf(images: list[Path], pdf_path: Path) -> None:
    from PIL import Image

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    opened = [Image.open(path).convert("RGB") for path in images]
    try:
        first, rest = opened[0], opened[1:]
        first.save(pdf_path, "PDF", save_all=True, append_images=rest, resolution=216.0)
    finally:
        for image in opened:
            image.close()


def _save_zip(images: list[Path], zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for image in images:
            archive.write(image, image.name)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\s]+", "-", value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned[:36] or "slide"
