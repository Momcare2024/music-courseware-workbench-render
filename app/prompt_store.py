from __future__ import annotations

from pathlib import Path

from .settings import get_settings


DEFAULT_LESSON_PROMPT = """请生成一份适合真实音乐课堂使用的详细教案。

要求：
1. 面向一线音乐教师，语言自然，可直接用于课堂。
2. 先分析教材、学情、教学目标、重难点，再设计教学过程。
3. 教学过程要有清晰的师生活动、课件提示、素材提示和时间分配。
4. 必须体现音乐课特点：聆听、节奏、演唱、律动/舞蹈、合作表现、文化理解。
5. 不要写空泛套话，要写具体课堂话术和学生任务。
6. 如果涉及歌曲，要关注情绪、速度、节拍、旋律难点、歌词理解、发声练习和表现方式。
"""


def lesson_prompt_path() -> Path:
    path = get_settings().workbench_data_dir / "prompts" / "lesson_prompt.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_lesson_prompt() -> str:
    path = lesson_prompt_path()
    if not path.exists():
        path.write_text(DEFAULT_LESSON_PROMPT, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def write_lesson_prompt(content: str) -> str:
    text = content.strip() or DEFAULT_LESSON_PROMPT
    lesson_prompt_path().write_text(text, encoding="utf-8")
    return text
