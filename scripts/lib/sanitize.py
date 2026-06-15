# -*- coding: utf-8 -*-
"""P0 清洗层：自动修复 + 结构性隐患检测 + 配图剥离。零内部依赖（纯文本 regex）。"""
import re

_PREFIX = "\\boxedans{"
_CJK_RE = re.compile(r"[　-〿一-鿿＀-￯]+")

_FIGURE_ENV_RE = re.compile(
    r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}"
    r"|\\begin\{axis\}.*?\\end\{axis\}",
    re.DOTALL,
)
_EMPTY_CENTER_RE = re.compile(r"\\begin\{center\}\s*\\end\{center\}")


# ---- 辅助函数 ----
def _match_brace(text: str, open_idx: int) -> int:
    """给定 `{` 后第一个字符的下标 open_idx，返回与之匹配的 `}` 之后的下标。"""
    depth = 1
    k = open_idx
    while k < len(text) and depth > 0:
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
        k += 1
    return k


# ---- 清洗函数 ----
def strip_fences(s: str) -> str:
    s = re.sub(r"```[a-zA-Z]*", "", s)
    return s.replace("```", "").strip()


def strip_display_around_boxedans(text: str) -> str:
    r"""移除紧邻包裹 \boxedans{...} 的多余 display 数学环境 \[ ... \]"""
    out: list[str] = []
    while True:
        idx = text.find(_PREFIX, 0)
        if idx == -1:
            out.append(text)
            break
        k = _match_brace(text, idx + len(_PREFIX))
        before, box, after = text[:idx], text[idx:k], text[k:]
        m_before = re.search(r"\\\[\s*$", before)
        m_after = re.match(r"\s*\.?\s*\\\]", after)
        if m_before and m_after:
            out.append(before[: m_before.start()])
            out.append(box)
            text = after[m_after.end():]
        else:
            out.append(before)
            out.append(box)
            text = after
    return "".join(out)


def clean_boxedans(text: str) -> str:
    r"""规整 \boxedans{...} 参数：删内部 $，中文包 \text{}。"""
    result: list[str] = []
    i = 0
    while True:
        idx = text.find(_PREFIX, i)
        if idx == -1:
            result.append(text[i:])
            break
        result.append(text[i:idx])
        j = idx + len(_PREFIX)
        k = _match_brace(text, j)
        inner = text[j : k - 1]
        inner = inner.replace("$", "")
        inner = _CJK_RE.sub(lambda m: r"\text{" + m.group(0) + "}", inner)
        result.append(_PREFIX + inner + "}")
        i = k
    return "".join(result)


def _wrap_cjk_runs(inner: str) -> str:
    return _CJK_RE.sub(lambda m: r"\text{" + m.group(0) + "}", inner)


def wrap_cjk_in_math(text: str) -> str:
    r"""数学模式内的中文/全角字符用 \text{} 包裹。"""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith(r"\[", i):
            j = text.find(r"\]", i + 2)
            if j == -1:
                out.append(text[i:]); break
            out.append(r"\[" + _wrap_cjk_runs(text[i + 2:j]) + r"\]")
            i = j + 2
        elif text.startswith(r"\(", i):
            j = text.find(r"\)", i + 2)
            if j == -1:
                out.append(text[i:]); break
            out.append(r"\(" + _wrap_cjk_runs(text[i + 2:j]) + r"\)")
            i = j + 2
        elif text.startswith("$$", i):
            j = text.find("$$", i + 2)
            if j == -1:
                out.append(text[i:]); break
            out.append("$$" + _wrap_cjk_runs(text[i + 2:j]) + "$$")
            i = j + 2
        elif text[i] == "$":
            j = text.find("$", i + 1)
            if j == -1:
                out.append(text[i:]); break
            out.append("$" + _wrap_cjk_runs(text[i + 1:j]) + "$")
            i = j + 1
        else:
            nxts = [p for p in (text.find("$", i), text.find(r"\[", i), text.find(r"\(", i)) if p != -1]
            if not nxts:
                out.append(text[i:]); break
            k = min(nxts)
            out.append(text[i:k])
            i = k
    return "".join(out)


def _strip_markdown(s: str) -> str:
    s = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", s)
    s = s.replace("**", "")
    return s


def _escape_stray_percent(s: str) -> str:
    return re.sub(r"(?<!\\)%", r"\\%", s)


# ---- 公共 API ----
def sanitize_fragment(s: str) -> str:
    r"""P0 清洗主入口。顺序：去围栏 -> 去多余 display -> 规整 \boxedans -> CJK 包裹 -> 去 markdown -> 转义 %"""
    s = strip_fences(s)
    s = strip_display_around_boxedans(s)
    s = clean_boxedans(s)
    s = wrap_cjk_in_math(s)
    s = _strip_markdown(s)
    s = _escape_stray_percent(s)
    return s.strip()


def fragment_issues(s: str) -> list[str]:
    r"""检查结构性隐患（$/\[\]/括号/\left\right/\begin\end 不配对），返回告警列表。"""
    issues: list[str] = []
    if s.count("$") % 2 != 0:
        issues.append("行内 $ 数量为奇数（数学环境可能未闭合）")
    if s.count(r"\[") != s.count(r"\]"):
        issues.append(r"\[ 与 \] 数量不配对")
    if s.count(r"\(") != s.count(r"\)"):
        issues.append(r"\( 与 \) 数量不配对")
    opens = len(re.findall(r"(?<!\\)\{", s))
    closes = len(re.findall(r"(?<!\\)\}", s))
    if opens != closes:
        issues.append(f"花括号不配对（{{={opens}, }}={closes}）")
    if len(re.findall(r"\\left(?![a-zA-Z])", s)) != len(re.findall(r"\\right(?![a-zA-Z])", s)):
        issues.append(r"\left 与 \right 数量不配对")
    if len(re.findall(r"\\begin\{", s)) != len(re.findall(r"\\end\{", s)):
        issues.append(r"\begin 与 \end 数量不配对")
    return issues


def has_figure(s: str) -> bool:
    return "tikzpicture" in s or r"\begin{axis}" in s


def strip_figures(s: str) -> str:
    r"""删除所有 TikZ/PGFPlots 图环境，保留纯文本。"""
    s = _FIGURE_ENV_RE.sub("", s)
    s = _EMPTY_CENTER_RE.sub("", s)
    return s.strip()
