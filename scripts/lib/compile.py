# -*- coding: utf-8 -*-
"""P2 整卷编译 + 失败定位/占位 + 模板填充 + 在线编译。依赖 sanitize。"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path

_COMPILE_TIMEOUT = int(os.environ.get("COURSEWARE_COMPILE_TIMEOUT", "90"))

SKILL_ROOT = Path(__file__).resolve().parents[2]
TPL_DIR = SKILL_ROOT / "templates"

_FILE_CACHE: dict[str, str] = {}

def _read_cached(p: Path) -> str:
    key = str(p.resolve())
    if key not in _FILE_CACHE:
        _FILE_CACHE[key] = p.read_text(encoding="utf-8")
    return _FILE_CACHE[key]


def _get_sanitize():
    from . import sanitize as _s
    return _s


_HYPERLINKS_PREAMBLE_ON = (
    r"% hyperref 超链接导航（--hyperlinks 已启用）" + "\n"
    r"\usepackage[colorlinks=true,linkcolor=blue!60!black,urlcolor=blue!60!black,citecolor=blue!60!black]{hyperref}" + "\n\n"
    r"\newcommand{\probitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \hypertarget{prob:#1}{}%" + "\n"
    r"  \noindent\textbf{#1.}\quad #2%" + "\n"
    r"  \hfill{\small\hyperlink{ans:#1}{[查看答案]}}\par%" + "\n"
    r"}" + "\n\n"
    r"\newcommand{\ansitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \hypertarget{ans:#1}{}%" + "\n"
    r"  \noindent\textbf{#1.}\quad{\small\hyperlink{prob:#1}{[返回题目]}}\par%" + "\n"
    r"  \nopagebreak\noindent #2\par%" + "\n"
    r"}"
)

_HYPERLINKS_PREAMBLE_OFF = (
    r"\newcommand{\probitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \noindent\textbf{#1.}\quad #2\par%" + "\n"
    r"}" + "\n\n"
    r"\newcommand{\ansitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \noindent\textbf{#1.}\par%" + "\n"
    r"  \nopagebreak\noindent #2\par%" + "\n"
    r"}"
)

_STUDY_TOC_PREAMBLE = (
    r"% hyperref 书签与目录超链接（study 模式默认开启）" + "\n"
    r"\usepackage[colorlinks=true,linkcolor=blue!60!black,"
    r"urlcolor=blue!60!black,bookmarks=true,bookmarksopen=true]{hyperref}" + "\n\n"
    r"% study 模式不调用 \probitem/\ansitem，保留无链接版定义保证 preamble 完整" + "\n"
    r"\newcommand{\probitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \noindent\textbf{#1.}\quad #2\par%" + "\n"
    r"}" + "\n\n"
    r"\newcommand{\ansitem}[2]{%" + "\n"
    r"  \par\medskip%" + "\n"
    r"  \noindent\textbf{#1.}\par%" + "\n"
    r"  \nopagebreak\noindent #2\par%" + "\n"
    r"}"
)

_ITEM_LOCATE_RE = re.compile(r"\\(probitem|ansitem)\{(\d+)\}")
_PROB_PLACEHOLDER = r"\textcolor{red}{\textbf{（本题自动校验未通过，已占位——请人工补题或重跑该节）}}"
_ANS_PLACEHOLDER = r"\textcolor{red}{\textbf{（本题解答自动校验未通过，已占位——请人工补全或重跑该节）}}"


def fill_template(tpl_name: str, mapping: dict) -> str:
    tpl = _read_cached(TPL_DIR / tpl_name)
    preamble = _read_cached(TPL_DIR / "preamble.tex")
    out = tpl.replace("<<<PREAMBLE>>>", preamble)
    for k, v in mapping.items():
        out = out.replace(f"<<<{k}>>>", v)
    return out


def split_out_paths(out: Path) -> tuple[Path, Path]:
    suffix = out.suffix or ".tex"
    return (
        out.with_name(out.stem + "_题目" + suffix),
        out.with_name(out.stem + "_答案" + suffix),
    )


def parse_exam_items(raw: str) -> list[tuple[str, str]]:
    s = _get_sanitize()
    raw = s.strip_fences(raw)
    items = []
    for chunk in raw.split("===ITEM==="):
        chunk = chunk.strip()
        if "[SOLUTION]" not in chunk:
            continue
        prob_part, sol_part = chunk.split("[SOLUTION]", 1)
        prob = prob_part.replace("[PROBLEM]", "").strip()
        sol = sol_part.strip()
        if prob:
            items.append((prob, sol))
    return items


def _extract_tex_error(log_text: str) -> str:
    lines = log_text.splitlines()
    bang = next((i for i, ln in enumerate(lines) if ln.startswith("! ")), None)
    if bang is None:
        return "(未能从 .log 提取具体错误，可能为字体/包加载问题)"
    out = lines[bang : bang + 6]
    lnum = next((j for j in range(bang, min(bang + 25, len(lines)))
                 if lines[j].startswith("l.")), None)
    if lnum is not None and lnum >= bang + 6:
        out += ["...", lines[lnum]]
        if lnum + 1 < len(lines):
            out.append(lines[lnum + 1])
    text = "\n".join(out).strip()
    return text or "(未能从 .log 提取具体错误，可能为字体/包加载问题)"


def _match_brace(text: str, open_idx: int) -> int:
    depth = 1
    k = open_idx
    while k < len(text) and depth > 0:
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
        k += 1
    return k


def _compile_full_once(p: Path, extra: list[str] | None = None) -> tuple[bool, str]:
    cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error"]
    if extra:
        cmd += extra
    cmd.append(p.name)
    try:
        proc = subprocess.run(cmd, cwd=str(p.parent), capture_output=True,
                              timeout=_COMPILE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log = p.with_suffix(".log")
        partial = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        return False, partial
    except Exception as e:
        return False, f"(xelatex 调用异常：{e})"
    if proc.returncode == 0:
        return True, ""
    log = p.with_suffix(".log")
    return False, (log.read_text(encoding="utf-8", errors="replace") if log.is_file() else "")


def _locate_failed_item(p: Path, log_text: str) -> tuple[str, str] | None:
    m = re.search(r"(?m)^l\.(\d+)", log_text)
    if not m:
        return None
    err_line = int(m.group(1))
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for i in range(min(err_line, len(lines)) - 1, -1, -1):
        mm = _ITEM_LOCATE_RE.search(lines[i])
        if mm:
            return mm.group(1), mm.group(2)
    return None


def _placeholder_item(tex: str, kind_cmd: str, n: str) -> tuple[str, bool]:
    placeholder = _PROB_PLACEHOLDER if kind_cmd == "probitem" else _ANS_PLACEHOLDER
    prefix = f"\\{kind_cmd}{{{n}}}{{"
    idx = tex.find(prefix)
    if idx == -1:
        return tex, False
    end = _match_brace(tex, idx + len(prefix))
    return tex[:idx] + f"\\{kind_cmd}{{{n}}}{{{placeholder}}}" + tex[end:], True


def _strip_item_figures(tex: str, kind_cmd: str, n: str) -> tuple[str, bool]:
    s = _get_sanitize()
    prefix = f"\\{kind_cmd}{{{n}}}{{"
    idx = tex.find(prefix)
    if idx == -1:
        return tex, False
    body_start = idx + len(prefix)
    end = _match_brace(tex, body_start)
    body = tex[body_start : end - 1]
    if not s.has_figure(body):
        return tex, False
    new_body = s.strip_figures(body)
    if new_body == body:
        return tex, False
    return tex[: body_start] + new_body + tex[end - 1 :], True


def build_with_repair(tex_path, label: str = "", max_repairs: int = 6) -> str:
    """编译 .tex → 整卷失败时自动定位+占位+重编 → 返回 PDF 路径。"""
    p = Path(tex_path)
    tag = f"[{label}] " if label else ""
    print(f"{tag}[编译] {p.name} …", file=sys.stderr)

    def _finish(placeholdered: list[str]) -> str:
        for ext in (".aux", ".out", ".toc", ".log", ".xdv"):
            try:
                p.with_suffix(ext).unlink()
            except FileNotFoundError:
                pass
        pdf = str(p.with_suffix(".pdf"))
        if placeholdered:
            print(f"{tag}[整卷修复] 共占位 {len(placeholdered)} 处：{', '.join(placeholdered)}。"
                  f"PDF 已生成，请人工补题或重跑对应节。", file=sys.stderr)
        print(f"{tag}[完成] PDF -> {pdf}", file=sys.stderr)
        return pdf

    ok, log_text = _compile_full_once(p)
    if ok:
        ok2, log2 = _compile_full_once(p)
        if not ok2:
            raise RuntimeError(
                f"PDF 生成阶段第 2 遍失败，见 {p.with_suffix('.log')}。\n"
                f"错误摘要：\n{_extract_tex_error(log2)}"
            )
        return _finish([])

    placeholdered: list[str] = []
    stripped_done: set[tuple[str, str]] = set()
    for attempt in range(max_repairs):
        loc = _locate_failed_item(p, log_text)
        if loc is None:
            raise RuntimeError(
                f"整卷编译失败且无法定位到具体题号（可能为导言区/字体/包问题），见 "
                f"{p.with_suffix('.log')}。\n错误摘要：\n{_extract_tex_error(log_text)}"
            )
        kind_cmd, n = loc
        label_cn = "题目" if kind_cmd == "probitem" else "解答"
        if (kind_cmd, n) not in stripped_done:
            tex_s, stripped = _strip_item_figures(p.read_text(encoding="utf-8"), kind_cmd, n)
            if stripped:
                stripped_done.add((kind_cmd, n))
                p.write_text(tex_s, encoding="utf-8")
                print(f"{tag}[整卷修复] 第 {n} {label_cn}的图在整卷中编译失败，已剥离图保留正文"
                      f"（第 {attempt + 1}/{max_repairs} 次）。", file=sys.stderr)
                ok, log_text = _compile_full_once(p, extra=["-no-pdf"])
                if ok:
                    break
                continue
        tex2, replaced = _placeholder_item(p.read_text(encoding="utf-8"), kind_cmd, n)
        if not replaced:
            raise RuntimeError(
                f"整卷编译失败，定位到 \\{kind_cmd}{{{n}}} 但无法替换占位，见 {p.with_suffix('.log')}。"
            )
        p.write_text(tex2, encoding="utf-8")
        placeholdered.append(f"{n}{label_cn[0]}")
        print(f"{tag}[整卷修复] 第 {n} {label_cn}在整卷中编译失败，已占位（第 {attempt + 1}/{max_repairs} 次）。",
              file=sys.stderr)
        ok, log_text = _compile_full_once(p, extra=["-no-pdf"])
        if ok:
            break
    else:
        raise RuntimeError(
            f"整卷编译在 {max_repairs} 次占位修复后仍失败，见 {p.with_suffix('.log')}。"
        )

    for i in range(2):
        ok, log_text = _compile_full_once(p)
        if not ok:
            raise RuntimeError(
                f"PDF 生成阶段第 {i + 1} 遍失败（修复后 -no-pdf 已通过），见 "
                f"{p.with_suffix('.log')}。\n错误摘要：\n{_extract_tex_error(log_text)}"
            )
    return _finish(placeholdered)


# ---------- Tectonic 编译（无需本地 LaTeX 安装） ----------
# Tectonic 是单文件 LaTeX 引擎，自动下载所需宏包，支持中文 ctex。
# 首次运行自动从 GitHub 下载二进制（~11MB），缓存到 skill 根目录。

_TECTONIC_URL = (
    "https://github.com/tectonic-typesetting/tectonic/releases/download/"
    "tectonic%400.16.9/tectonic-0.16.9-x86_64-pc-windows-msvc.zip"
)
_TECTONIC_CACHE = SKILL_ROOT / ".tectonic"


def _get_tectonic() -> Path:
    """获取 tectonic 二进制路径；不存在则自动下载。"""
    if sys.platform == "win32":
        exe = _TECTONIC_CACHE / "tectonic.exe"
    else:
        exe = _TECTONIC_CACHE / "tectonic"
    if exe.is_file():
        return exe

    print("[tectonic] 首次使用，正在下载 tectonic LaTeX 引擎（~11MB）…", file=sys.stderr)
    _TECTONIC_CACHE.mkdir(parents=True, exist_ok=True)

    import zipfile
    import io

    try:
        with urllib.request.urlopen(_TECTONIC_URL, timeout=120) as r:
            data = r.read()
    except Exception as e:
        raise RuntimeError(
            f"[错误] 下载 tectonic 失败：{e}\n"
            f"      请手动安装 xelatex（MiKTeX/TeX Live）或 tectonic 后重试。"
        ) from e

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extract("tectonic.exe" if sys.platform == "win32" else "tectonic",
                   path=_TECTONIC_CACHE)
    exe.chmod(0o755)
    print(f"[tectonic] 下载完成：{exe}", file=sys.stderr)
    return exe


def compile_with_tectonic(tex_path, label: str = "") -> str:
    """使用 tectonic 编译 .tex 为 PDF（自动下载宏包，无需配置）。

    返回 PDF 路径。编译失败抛 RuntimeError。
    """
    p = Path(tex_path)
    tag = f"[{label}] " if label else ""
    exe = _get_tectonic()

    print(f"{tag}[tectonic] 编译 {p.name}（首次需下载宏包，请耐心等待）…", file=sys.stderr)
    try:
        # tectonic 自动处理 ctex/中文/交叉引用，只需跑一遍
        proc = subprocess.run(
            [str(exe), p.name],
            cwd=str(p.parent),
            capture_output=True,
            timeout=900,  # 首次需下载宏包（~50MB），从国内可能较慢
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"[错误] tectonic 编译超时（首次运行需下载宏包，请重试）。")
    except Exception as e:
        raise RuntimeError(f"[错误] tectonic 调用异常：{e}")

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")
        stdout = proc.stdout.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"[错误] tectonic 编译失败：\n{stderr[-800:]}\n{stdout[-800:]}"
        )

    pdf = p.with_suffix(".pdf")
    # tectonic 把 PDF 放在当前工作目录或 tex 所在目录
    alt = Path(p.parent) / p.stem
    if not pdf.is_file() and alt.with_suffix(".pdf").is_file():
        import shutil as _shutil
        _shutil.move(str(alt.with_suffix(".pdf")), str(pdf))
    if not pdf.is_file():
        raise RuntimeError(f"[错误] tectonic 编译完成但未找到 PDF：{pdf}")

    print(f"{tag}[完成] PDF -> {pdf}", file=sys.stderr)
    return str(pdf)


# ---------- 在线编译（无需本地 LaTeX 安装） ----------
# 以下在线服务作为 tectonic 的备用方案。


def compile_pdf(tex_path, engine: str = "xelatex", label: str = "",
                max_repairs: int = 6, timeout: int = 120) -> str:
    """根据指定的引擎编译 .tex → PDF。

    引擎:
      - xelatex (默认): 本地编译，含自动修复/占位（需安装 TeX Live/MiKTeX）
      - tectonic: 自动下载 tectonic 二进制后编译（无需安装，推荐无 LaTeX 环境时使用）
      - online: 在线编译（备用）

    若 xelatex 不可用，自动回退到 tectonic。
    返回 PDF 文件路径。
    """
    if engine == "online":
        return compile_with_tectonic(tex_path, label=label)  # 在线服务不稳定，统一回退 tectonic

    if engine == "xelatex":
        if shutil.which("xelatex"):
            return build_with_repair(tex_path, label=label, max_repairs=max_repairs)
        # xelatex 不可用，回退到 tectonic
        print(f"[{'[' + label + '] ' if label else ''}提示] 未找到 xelatex，使用 tectonic 编译。",
              file=sys.stderr)
        return compile_with_tectonic(tex_path, label=label)

    if engine == "tectonic":
        return compile_with_tectonic(tex_path, label=label)

    raise ValueError(f"未知的 PDF 引擎：{engine!r}。可选值：xelatex, tectonic, online")
