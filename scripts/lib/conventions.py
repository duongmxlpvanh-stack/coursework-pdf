# -*- coding: utf-8 -*-
"""约定文件解析 + 章节展开。零内部依赖（标准库）。"""
import functools
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
CONV_DIR = SKILL_ROOT / "conventions"

_file_cache: dict[str, str] = {}


def _read_cached(p: Path) -> str:
    """读取文件内容并缓存，避免多 task 并发时重复读盘。"""
    key = str(p.resolve())
    if key not in _file_cache:
        _file_cache[key] = p.read_text(encoding="utf-8")
    return _file_cache[key]


def extract_block(text: str, name: str) -> str:
    m = re.search(
        rf"<!--\s*{name}_START\s*-->(.*?)<!--\s*{name}_END\s*-->",
        text, flags=re.DOTALL,
    )
    return m.group(1).strip() if m else ""


@functools.lru_cache(maxsize=None)
def load_convention(subject: str) -> tuple[str, str]:
    path = CONV_DIR / f"{subject}.md"
    if not path.is_file():
        raise RuntimeError(
            f"[错误] 找不到约定文件 {path}。\n"
            f"      新科目请先复制 conventions/_template.md 为 conventions/{subject}.md 并填好标记块。"
        )
    text = path.read_text(encoding="utf-8")
    sym = extract_block(text, "SYMBOL_BLOCK")
    extra = extract_block(text, "PROMPT_EXTRA")
    if not sym:
        raise RuntimeError(f"[错误] {path} 缺少 SYMBOL_BLOCK 标记块。")
    return sym, extra


@functools.lru_cache(maxsize=None)
def load_figure_policy(subject: str) -> str:
    """读取该科目可选的 FIGURE_POLICY 标记块。未定义返回空串（no-op）。"""
    path = CONV_DIR / f"{subject}.md"
    if not path.is_file():
        return ""
    return extract_block(_read_cached(path), "FIGURE_POLICY")


def load_syllabus(subject: str) -> list[str]:
    """从 SYLLABUS 标记块读取完整章节清单（一行一节）。"""
    path = CONV_DIR / f"{subject}.md"
    if not path.is_file():
        raise RuntimeError(f"[错误] 找不到约定文件 {path}。")
    block = extract_block(_read_cached(path), "SYLLABUS")
    if not block:
        raise RuntimeError(
            f"[错误] {path} 缺少 SYLLABUS 标记块，无法用 --sections all 展开。\n"
            f"      请在该文件中补一个 <!-- SYLLABUS_START --> ... <!-- SYLLABUS_END --> 块。"
        )
    sections: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.lstrip("-*•").strip()
        if line:
            sections.append(line)
    if not sections:
        raise RuntimeError(f"[错误] {path} 的 SYLLABUS 块为空。")
    return sections


def resolve_sections(subject: str, raw: str, tag: str = "") -> list[str]:
    """'all' / '全部' -> 从 SYLLABUS 展开；否则按逗号切分。"""
    raw = (raw or "").strip()
    if raw.lower() == "all" or raw == "全部":
        sections = load_syllabus(subject)
        print(f"{tag}[展开] --sections all -> {len(sections)} 节：{'、'.join(sections)}",
              file=sys.stderr)
        return sections
    return [s.strip() for s in raw.split(",") if s.strip()]
