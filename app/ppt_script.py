from __future__ import annotations

import re


DEFAULT_SLIDE_TITLES = [
    "封面导入",
    "学习目标",
    "情境导入",
    "初听感受",
    "节奏体验",
    "旋律学唱",
    "歌词与表现",
    "律动/合作",
    "课堂展示",
    "课堂小结",
]


def infer_title(lesson_text: str, fallback: str = "音乐课") -> str:
    patterns = [
        r"[《<]([^》>]{2,40})[》>]",
        r"课题[：:]\s*([^\n\r]{2,40})",
        r"题目[：:]\s*([^\n\r]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, lesson_text)
        if match:
            return match.group(1).strip()
    first_line = next((line.strip("# 　") for line in lesson_text.splitlines() if line.strip()), "")
    return first_line[:30] or fallback


def extract_stage_titles(lesson_text: str) -> list[str]:
    titles: list[str] = []
    for line in lesson_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(?:#{2,4}\s*)?(?:环节[一二三四五六七八九十\d]+|第[一二三四五六七八九十\d]+环节|[一二三四五六七八九十\d]+[\.、])\s*[:：]?\s*(.+)$", stripped)
        if not match:
            continue
        title = re.sub(r"[（(].*?[）)]", "", match.group(1)).strip()
        title = title.strip("：: -")
        if 2 <= len(title) <= 24 and not any(title == item for item in titles):
            titles.append(title)
    return titles[:8]


def _screen_text_for(title: str, course_title: str) -> str:
    if "封面" in title:
        return f"《{course_title}》\n音乐课堂"
    if "目标" in title:
        return "听一听\n唱一唱\n动一动\n说一说"
    if "小结" in title or "总结" in title:
        return "今天我学会了……\n音乐让我们看见更大的世界"
    if "初听" in title or "聆听" in title:
        return "听完后说一说：\n这首歌给你什么感觉？"
    if "节奏" in title:
        return "跟着节拍读一读\n拍手 / 拍腿 / 跺脚"
    if "旋律" in title or "学唱" in title:
        return "轻声模唱\n分句学唱\n完整演唱"
    if "律动" in title or "合作" in title or "展示" in title:
        return "小组合作\n演唱 + 律动 + 表现"
    return "观察画面\n聆听音乐\n参与课堂活动"


def _visual_prompt_for(title: str, course_title: str, style: str, screen_text: str) -> str:
    return (
        f"16:9 小学音乐课 PPT 背景画面，主题《{course_title}》，页面环节：{title}。"
        f"视觉风格：{style or '儿童友好、明亮清晰、课堂可用'}。"
        "画面要有音乐课堂氛围，可以包含音符、节奏线、舞台灯光、教室互动、地域文化元素等；"
        "构图留出大面积干净区域方便后期放置标题和课堂文字；"
        "不要生成任何文字、汉字、英文字母、数字、水印、logo；"
        "画面清晰、温暖、适合公开课课件，不要商业路演风。"
        f"这一页后期会叠加的屏幕文字是：{screen_text.replace(chr(10), ' / ')}。"
    )


def build_script_pages(lesson_text: str, title: str = "", style: str = "") -> list[dict]:
    course_title = title.strip() or infer_title(lesson_text)
    stage_titles = extract_stage_titles(lesson_text)
    titles = ["封面导入", "学习目标"]
    titles.extend(stage_titles or DEFAULT_SLIDE_TITLES[2:9])
    if not any("小结" in item or "总结" in item for item in titles):
        titles.append("课堂小结")
    titles = titles[:12]

    pages: list[dict] = []
    for index, page_title in enumerate(titles, start=1):
        screen_text = _screen_text_for(page_title, course_title)
        pages.append(
            {
                "index": index,
                "title": page_title,
                "screen_text": screen_text,
                "visual_prompt": _visual_prompt_for(page_title, course_title, style, screen_text),
                "image_status": "not_started",
                "image_file": "",
                "task_id": "",
                "error": "",
            }
        )
    return pages


def script_to_markdown(project: dict) -> str:
    lines = [
        f"# 《{project.get('title') or '音乐课'}》PPT 脚本",
        "",
        f"- 视觉风格：{project.get('style') or '未填写'}",
        "",
    ]
    for page in project.get("script_pages") or []:
        lines.extend(
            [
                f"## 第 {page.get('index')} 页｜{page.get('title')}",
                "",
                "### 屏幕文字",
                str(page.get("screen_text") or ""),
                "",
                "### 即梦画面提示词",
                str(page.get("visual_prompt") or ""),
                "",
                f"### 图片状态：{page.get('image_status') or 'not_started'}",
                "",
            ]
        )
    return "\n".join(lines)


def parse_full_page_design(design_text: str, global_style: str = "") -> list[dict]:
    blocks = _split_page_blocks(design_text)
    pages: list[dict] = []
    for index, block in enumerate(blocks, start=1):
        title = _page_title(block, index)
        pages.append(
            {
                "index": index,
                "title": title,
                "raw_design": block.strip(),
                "prompt": full_page_prompt(block, global_style),
                "image_status": "not_started",
                "image_file": "",
                "task_id": "",
                "error": "",
            }
        )
    return pages


def _split_page_blocks(design_text: str) -> list[str]:
    text = design_text.strip()
    if not text:
        return []
    marker = r"(?:#{1,4}\s*)?(?:P\s*\d+|第\s*\d+\s*页)[｜|:：\s]"
    pattern = re.compile(
        rf"(?=^\s*{marker})",
        re.MULTILINE | re.IGNORECASE,
    )
    blocks = [block.strip() for block in pattern.split(text) if block.strip()]
    if blocks and not re.match(rf"^\s*{marker}", blocks[0], flags=re.IGNORECASE):
        blocks = blocks[1:]
    if len(blocks) > 1:
        return blocks

    return [text]


def _page_title(block: str, index: int) -> str:
    first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")
    first_line = re.sub(r"^\s*#{1,4}\s*", "", first_line)
    first_line = re.sub(r"^\s*P\s*\d+\s*[｜|:：-]?\s*", "", first_line, flags=re.IGNORECASE)
    first_line = re.sub(r"^\s*第\s*\d+\s*页\s*[｜|:：-]?\s*", "", first_line)
    return first_line[:30] or f"第{index}页"


def full_page_prompt(page_design: str, global_style: str = "") -> str:
    style_line = f"整体风格：{global_style.strip()}。" if global_style.strip() else ""
    return (
        "请生成一张完整的 16:9 PPT 页面成品图，适合小学/中学音乐公开课。"
        "页面里的中文标题和正文必须准确、清晰、美观，排版要像优秀课件封面/页面设计，"
        "不要乱码、错字、英文占位、无意义符号、水印或 logo。"
        "整体画面要高级、干净、课堂投影可读，后续会放进 WPS 并用图片转可编辑能力继续修改。"
        f"{style_line}\n\n页面设计稿：\n{page_design.strip()}"
    )
