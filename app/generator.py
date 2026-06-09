from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .llm import LLMNotConfigured, chat_completion
from .prompts import LESSON_SYSTEM_PROMPT, SLIDE_SYSTEM_PROMPT, lesson_user_prompt, slide_user_prompt


DEFAULT_STAGES = [
    ("情境导入", 5, "创设音乐与文化情境，激发学习兴趣。", "图片/视频/人物导入素材"),
    ("初听歌曲", 4, "整体感受歌曲情绪、速度和风格。", "原唱音频、播放提示"),
    ("复听歌曲", 4, "关注曲式、反复记号、重点节奏或旋律。", "曲谱、标注图示"),
    ("节奏与歌词", 5, "用声势动作读歌词，建立 2/4 拍律动。", "歌词、节奏图谱、动作提示"),
    ("发声练习", 4, "围绕重点旋律进行声音准备。", "发声练习谱、钢琴/示范音频"),
    ("学唱歌曲", 10, "分句学唱，解决音准、节奏和情绪表现。", "曲谱、伴奏、范唱"),
    ("律动表现", 5, "加入舞蹈、身体律动或乐器伴奏。", "舞步视频、动作分解图"),
    ("合作展示", 3, "分组完成演唱、律动、伴奏合作。", "分组任务卡、伴奏音频"),
    ("课堂小结", 2, "回顾音乐要素和文化理解。", "关键词、结束页背景"),
]


def _upload_summary(uploads: list[dict]) -> str:
    if not uploads:
        return ""
    lines = []
    for item in uploads:
        size_kb = int(item.get("size", 0)) // 1024
        lines.append(f"- {item.get('filename')}（{item.get('kind')}，{size_kb} KB）")
    return "\n".join(lines)


def _reference_text(uploads: list[dict]) -> str:
    chunks = []
    for item in uploads:
        preview = str(item.get("text_preview") or "").strip()
        if preview:
            chunks.append(f"### {item.get('filename')}\n{preview}")
    return "\n\n".join(chunks)


def fallback_lesson(payload: dict, uploads: list[dict], reason: str = "") -> str:
    title = payload.get("title") or "音乐课"
    grade = payload.get("grade") or "小学音乐"
    minutes = payload.get("lesson_minutes") or "40"
    style = payload.get("style") or "活泼、清晰、儿童友好"
    upload_summary = _upload_summary(uploads)
    reference_text = _reference_text(uploads)
    if "教学目标" in reference_text and "教学过程" in reference_text:
        note = f"\n> 本草稿由上传资料整理生成，原因：{reason}\n" if reason else ""
        return f"""# 《{title}》配套教案
{note}
## 基本信息
- 课题：{title}
- 年级/学段：{grade}
- 课时：{minutes} 分钟
- 课件风格：{style}

## 上传资料整理
以下内容来自你上传的参考资料，已作为人工审核的教案草稿起点。建议先检查课题名、教材版本、师生对话、音频/视频提示和课堂时间分配。

{reference_text[:18000]}

## 待确认事项
- 是否需要补充学情分析、评价方式、板书设计。
- 是否需要把“师生对话”进一步拆成 PPT 页面动作。
- 是否需要加入音频、视频、曲谱、舞蹈动作、乐器伴奏等素材状态。
"""
    stage_lines = []
    for index, (name, duration, purpose, media) in enumerate(DEFAULT_STAGES, start=1):
        stage_lines.append(
            f"### {index}. {name}（约 {duration} 分钟）\n"
            f"- 教师活动：围绕“{title}”组织{name}，引导学生{purpose}\n"
            f"- 学生活动：聆听、观察、模唱、律动或小组交流，完成对应课堂任务。\n"
            f"- 课件提示：准备{media}。\n"
        )
    note = f"\n> 本草稿由本地模板生成，原因：{reason}\n" if reason else ""
    return f"""# 《{title}》配套教案
{note}
## 一、基本信息
- 课题：{title}
- 年级/学段：{grade}
- 课时：{minutes} 分钟
- 课件风格：{style}

## 二、教材分析
《{title}》音乐课应围绕歌曲/作品的节奏、旋律、情绪和文化背景展开。课堂需要通过聆听、模唱、节奏体验、律动表现和合作展示，让学生从“听见音乐”走向“表现音乐”。

## 三、学情分析
学生对形象化、互动式、带动作和声音参与的音乐活动接受度高。课件应减少大段文字，增加音频、视频、曲谱标注、节奏图谱和课堂提问。

## 四、教学目标
1. 审美感知：感受作品的情绪、速度、节拍和音乐风格。
2. 艺术表现：能够用自然、准确、有表现力的声音或动作参与音乐表现。
3. 创意实践：通过节奏、律动、乐器或分组展示创造性表现音乐。
4. 文化理解：了解作品相关地域、民族、生活场景或文化内涵。

## 五、教学重难点
- 重点：准确感受并表现歌曲/作品的情绪、节奏和主要旋律。
- 难点：把音准、节奏、声音状态和动作表现结合起来。

## 六、教学准备
{upload_summary or "- 需准备：歌曲音频、伴奏、曲谱、相关图片/视频、课堂互动素材。"}

## 七、教学过程
{chr(10).join(stage_lines)}
## 八、板书设计
《{title}》：情绪 / 速度 / 节拍 / 重点旋律 / 表现方式 / 文化关键词

## 九、评价方式
- 过程评价：学生是否积极参与聆听、模唱、律动和合作。
- 表现评价：演唱或律动是否准确、自然、有情绪。
- 文化评价：能否说出本课作品的文化背景或音乐特点。

## 十、待确认事项
- 是否有指定教材版本、歌曲谱例、歌词、原唱/伴奏文件。
- 是否需要加入舞蹈动作、乐器伴奏、视频播放或课堂小游戏。
"""


def fallback_slide_design(payload: dict, lesson_markdown: str, uploads: list[dict], reason: str = "") -> str:
    title = payload.get("title") or "音乐课"
    image_model = payload.get("image_model") or "未指定"
    slide_style_prompt = payload.get("slide_style_prompt") or "儿童友好、音乐课堂、清晰留白、避免商业汇报风。"
    page_blocks = []
    page_templates = [
        ("封面", "建立课堂主题和音乐氛围", ["课题", "年级/课程主题"], "大背景图 + 标题 + 音乐元素装饰"),
        ("情境导入", "引出作品背景，建立文化情境", ["观察画面，说说你看到了什么"], "人物/地域图片 + 课堂问题"),
        ("初听歌曲", "整体感受情绪和速度", ["这首歌曲的情绪是怎样的？", "速度是快还是慢？"], "播放按钮 + 情绪词卡"),
        ("复听歌曲", "关注音乐记号和演唱顺序", ["找到反复记号", "说出演唱顺序"], "曲谱局部 + 标注圈选"),
        ("跟节奏读歌词", "建立节拍和歌词韵律", ["跟着 2/4 拍读歌词"], "歌词分行 + 拍手/拍腿图示"),
        ("发声练习", "准备声音状态，突破难点旋律", ["li / la 发声练习"], "简谱/五线谱片段 + 声音提示"),
        ("学唱歌曲", "分句学习旋律和歌词", ["第一乐句", "第二乐句", "完整演唱"], "曲谱分块 + 难点高亮"),
        ("律动表现", "加入身体动作或舞蹈表现", ["学习基本舞步", "跟音乐律动"], "动作分解图/视频占位"),
        ("合作表演", "组织演唱、律动、伴奏合作", ["演唱组", "舞蹈组", "乐器组"], "三组任务卡 + 舞台感布局"),
        ("课堂小结", "回顾音乐与文化收获", ["今天我学会了……"], "关键词云 + 温暖收束画面"),
    ]
    for index, (page_title, purpose, screen_text, layout) in enumerate(page_templates, start=1):
        text_lines = "\n".join(f"  - {item}" for item in screen_text)
        page_blocks.append(
            f"## 第 {index} 页｜{page_title}\n"
            f"- 教学意图：{purpose}。\n"
            f"- 屏幕文字：\n{text_lines}\n"
            f"- 画面布局：{layout}。\n"
            f"- 媒体/素材：根据上传素材优先匹配；不足时使用 {image_model} 生成无文字配图。\n"
            f"- 动画交互：标题淡入，关键问题逐条出现，音频/视频图标保留点击提示。\n"
            f"- 教师提示：该页服务“{page_title}”环节，不堆文字，重点留给课堂互动。\n"
            f"- 生成建议：{slide_style_prompt}\n"
        )
    upload_summary = _upload_summary(uploads)
    note = f"\n> 本设计稿由本地模板生成，原因：{reason}\n" if reason else ""
    return f"""# 《{title}》PPT 逐页设计稿
{note}
## 设计总则
- 课件定位：音乐课堂演示课件，不是普通汇报 PPT。
- 视觉方向：儿童友好、干净明亮、适度民族/音乐元素、课堂可读。
- 用户风格要求：{slide_style_prompt}
- 媒体原则：音频、视频、曲谱、歌词、节奏、舞蹈动作都要明确服务教学环节。
- 图片原则：AI 图片不放文字，页面文字由 PPT 单独排版，方便后期修改。

{chr(10).join(page_blocks)}

## 素材清单
{upload_summary or "- 暂无上传素材。"}
- 需确认：原唱、伴奏、曲谱、歌词、动作示范视频、地域/文化图片。
- 可生成：封面背景、导入人物、课堂总结背景、节奏/互动装饰图。

## 下一步人工审核
1. 检查页数是否符合课堂节奏。
2. 检查每页是否有明确教学动作。
3. 标注哪些素材已有，哪些需要生成或补传。
4. 确认后再进入 PPTX 生成阶段。
"""


def asset_checklist(project: dict) -> str:
    uploads = project.get("uploads") or []
    lesson = project.get("lesson") or {}
    slide = project.get("slide_design") or {}
    lines = [
        f"# 《{project.get('title') or '音乐课'}》素材清单",
        "",
        "## 已上传素材",
    ]
    if uploads:
        for item in uploads:
            lines.append(f"- {item.get('filename')}｜{item.get('kind')}｜{item.get('suffix')}")
    else:
        lines.append("- 暂无")
    lines.extend([
        "",
        "## 建议补充素材",
        "- 原唱音频",
        "- 伴奏音频",
        "- 曲谱图片或可编辑谱例",
        "- 歌词文本",
        "- 舞蹈/律动示范视频",
        "- 课堂导入图片或视频",
        "- 文化背景图片",
        "",
        "## 状态",
        f"- 教案状态：{lesson.get('status', 'draft')}",
        f"- PPT设计稿状态：{slide.get('status', 'not_started')}",
    ])
    return "\n".join(lines)


async def generate_lesson(payload: dict, uploads: list[dict]) -> tuple[str, str]:
    use_ai = payload.get("use_ai", True)
    if not use_ai:
        return fallback_lesson(payload, uploads, "未启用 AI 生成"), "fallback"
    try:
        content = await chat_completion(
            LESSON_SYSTEM_PROMPT,
            lesson_user_prompt(payload, _reference_text(uploads), _upload_summary(uploads)),
            model=payload.get("text_model"),
            timeout_seconds=90,
        )
        if _looks_like_non_answer(content):
            return fallback_lesson(payload, uploads, f"AI 没有直接输出教案正文，而是返回：{content[:160]}"), "fallback_error"
        return content, "ai"
    except LLMNotConfigured as exc:
        return fallback_lesson(payload, uploads, str(exc)), "fallback"
    except Exception as exc:
        return fallback_lesson(payload, uploads, f"AI 生成失败：{exc}"), "fallback_error"


async def generate_slide_design(
    payload: dict,
    lesson_markdown: str,
    uploads: list[dict],
    style_reference_image_paths: Sequence[Path] | None = None,
) -> tuple[str, str]:
    use_ai = payload.get("use_ai", True)
    if not use_ai:
        return fallback_slide_design(payload, lesson_markdown, uploads, "未启用 AI 生成"), "fallback"
    try:
        user_prompt = slide_user_prompt(payload, lesson_markdown, _upload_summary(uploads))
        try:
            content = await chat_completion(
                SLIDE_SYSTEM_PROMPT,
                user_prompt,
                model=payload.get("text_model"),
                timeout_seconds=90,
                image_paths=style_reference_image_paths,
            )
        except Exception as image_exc:
            if not style_reference_image_paths:
                raise
            retry_prompt = (
                "本次用户上传了风格参考图，但代理网关处理视觉图片失败。"
                "请不要放弃生成，请根据用户填写的 PPT 视觉风格要求、上传图片文件名和课程信息生成设计稿。"
                f"\n\n视觉请求失败原因：{image_exc}\n\n"
                f"{user_prompt}"
            )
            content = await chat_completion(
                SLIDE_SYSTEM_PROMPT,
                retry_prompt,
                model=payload.get("text_model"),
                timeout_seconds=90,
            )
            return content, "ai_text_only_after_image_error"
        return content, "ai"
    except LLMNotConfigured as exc:
        return fallback_slide_design(payload, lesson_markdown, uploads, str(exc)), "fallback"
    except Exception as exc:
        return fallback_slide_design(payload, lesson_markdown, uploads, f"AI 生成失败：{exc}"), "fallback_error"


def _looks_like_non_answer(content: str) -> bool:
    stripped = content.strip()
    if len(stripped) < 40:
        return True
    bad_starts = (
        "我先查看",
        "我需要先",
        "请上传",
        "无法",
        "抱歉",
    )
    return any(stripped.startswith(prefix) for prefix in bad_starts)
