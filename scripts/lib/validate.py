# -*- coding: utf-8 -*-
"""P1 微编译校验 + 失败再生成/占位。依赖 llm + sanitize。"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 延迟导入避免循环
def _get_sanitize():
    from . import sanitize as _s
    return _s

def _get_llm():
    from . import llm as _l
    return _l

_COMPILE_TIMEOUT = int(os.environ.get("COURSEWARE_COMPILE_TIMEOUT", "90"))
_BATCH_SIZE = 8

_PROB_PLACEHOLDER = r"\textcolor{red}{\textbf{（本题自动校验未通过，已占位——请人工补题或重跑该节）}}"
_ANS_PLACEHOLDER = r"\textcolor{red}{\textbf{（本题解答自动校验未通过，已占位——请人工补全或重跑该节）}}"
_STUDY_PLACEHOLDER = r"\textcolor{red}{\textbf{（本节内容自动校验未通过，已占位——请重跑该节）}}"

_KIND_META = {
    "prob": ("题目", lambda f: r"\probitem{0}{" + f + "}", _PROB_PLACEHOLDER),
    "ans": ("解答", lambda f: r"\ansitem{0}{" + f + "}", _ANS_PLACEHOLDER),
    "study": ("知识点", lambda f: f, _STUDY_PLACEHOLDER),
}

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

SKILL_ROOT = Path(__file__).resolve().parents[2]
TPL_DIR = SKILL_ROOT / "templates"

_file_cache: dict[str, str] = {}

def _read_cached(p: Path) -> str:
    key = str(p.resolve())
    if key not in _file_cache:
        _file_cache[key] = p.read_text(encoding="utf-8")
    return _file_cache[key]


def _validation_preamble() -> str:
    pre = _read_cached(TPL_DIR / "preamble.tex")
    return pre.replace("<<<HYPERLINKS_PREAMBLE>>>", _HYPERLINKS_PREAMBLE_OFF)


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


def _micro_compile(body: str, preamble: str, workdir: Path, jobname: str) -> tuple[bool, str]:
    doc = (
        "\\documentclass[11pt]{ctexart}\n" + preamble
        + "\n\\begin{document}\n" + body + "\n\\end{document}\n"
    )
    tex = workdir / (jobname + ".tex")
    tex.write_text(doc, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "-no-pdf", tex.name],
            cwd=str(workdir), capture_output=True, timeout=_COMPILE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, (f"(xelatex 微编译超时 >{_COMPILE_TIMEOUT}s——可能是 TikZ/PGFPlots 图陷入"
                       f"过大 samples、坐标特异点或非终止绘制；请简化或移除该图。)")
    except Exception as e:
        return False, f"(xelatex 调用异常：{e})"
    if proc.returncode == 0:
        return True, ""
    log = tex.with_suffix(".log")
    err = _extract_tex_error(log.read_text(encoding="utf-8", errors="replace")) if log.is_file() else ""
    return False, err or "(编译失败但无 .log)"


def _regen_fragment(system: str, broken: str, err: str, label: str, section: str,
                    args, api_key: str) -> str:
    s = _get_sanitize()
    has_fig = s.has_figure(broken)
    fig_clause = (
        f"该片段含 TikZ/PGFPlots 图，请重点检查 \\begin{{tikzpicture}}\\end{{tikzpicture}}、"
        f"\\begin{{axis}}\\end{{axis}}、坐标括号是否配对，是否误用 \\includegraphics/外部文件/"
        f"shell-escape，pgfplots 的 samples 是否过大、domain 是否含特异点、fill between 前是否已"
        f"用 name path 命名两条曲线。\n"
        f"【重要】图只是辅助：若该图无法在几处小改内修好，请直接删除整张图，"
        f"**保留题干/解答的全部文字与公式**——绝不要为保住图而牺牲正文。\n"
        if has_fig else ""
    )
    user = (
        f"下面是为「{section}」生成的一段 XeLaTeX {label}片段，用 xelatex(ctexart) 编译报错。\n"
        f"请只修正导致编译失败的 LaTeX 语法问题（花括号/数学定界符 $ 与 \\[ \\]/环境 \\begin\\end 配对、"
        f"\\left\\right 配对、非法字符、数学模式内的裸中文），保持{label}的实质内容不变。\n"
        f"{fig_clause}"
        f"只输出修正后的{label}片段本身：不要编号、不要 \\probitem/\\ansitem 包裹、不要解释、不要代码围栏。\n"
        f"【编译错误摘要】\n{err}\n\n【原片段】\n{broken}"
    )
    llm = _get_llm()
    return llm.call_llm(system, user, api_key=api_key, base_url=args.base_url,
                        model=args.model, temperature=args.temperature, mock=args.mock)


def _validate_one(task: dict, preamble: str, system: str, args, api_key: str,
                  workdir: Path, tag: str) -> tuple:
    s = _get_sanitize()
    key, kind, section, frag = task["key"], task["kind"], task["section"], task["frag"]
    label, wrap, placeholder = _KIND_META[kind]
    job = "v_" + re.sub(r"\W+", "_", str(key)) + "_" + kind
    ok, err = _micro_compile(wrap(frag), preamble, workdir, job)
    if ok:
        return key, frag, "ok"
    attempts = max(0, int(getattr(args, "repair_attempts", 2)))
    for a in range(attempts):
        print(f"{tag}[校验] {label} {key} 编译失败，第 {a + 1}/{attempts} 次尝试修复…", file=sys.stderr)
        try:
            fixed = s.sanitize_fragment(_regen_fragment(system, frag, err, label, section, args, api_key))
        except Exception as e:
            print(f"{tag}[校验] {label} {key} 修复调用失败：{e}", file=sys.stderr)
            break
        ok, err = _micro_compile(wrap(fixed), preamble, workdir, job)
        if ok:
            print(f"{tag}[校验] {label} {key} 第 {a + 1} 次修复成功。", file=sys.stderr)
            return key, fixed, f"repaired@{a + 1}"
        frag = fixed
    if s.has_figure(frag):
        stripped = s.strip_figures(frag)
        if stripped and stripped != frag:
            ok, _ = _micro_compile(wrap(stripped), preamble, workdir, job)
            if ok:
                print(f"{tag}[校验] {label} {key} 图无法修复，已剥离图保留正文。", file=sys.stderr)
                return key, stripped, "figure_stripped"
    print(f"{tag}[校验] {label} {key} 修复未果，使用占位。", file=sys.stderr)
    return key, placeholder, "placeholder"


def _batch_compile(tasks: list[dict], preamble: str, workdir: Path, jobname: str) -> bool:
    bodies = [_KIND_META[t["kind"]][1](t["frag"]) for t in tasks]
    ok, _ = _micro_compile("\n\n".join(bodies), preamble, workdir, jobname)
    return ok


def validate_fragments(frag_tasks: list[dict], *, system: str, args, api_key: str,
                       tag: str = "") -> tuple[dict, list[tuple]]:
    """两段式微编译校验：分块批量 -> 未过回退逐题修复。返回 (key->最终片段, [(key,状态)])。"""
    if not frag_tasks:
        return {}, []
    if getattr(args, "mock", False):
        return {t["key"]: t["frag"] for t in frag_tasks}, []
    if shutil.which("xelatex") is None:
        print(f"{tag}[校验] 未找到 xelatex，跳过逐题微编译校验。", file=sys.stderr)
        return {t["key"]: t["frag"] for t in frag_tasks}, []

    preamble = _validation_preamble()
    results: dict = {}
    stats: list[tuple] = []
    chunks = [frag_tasks[i:i + _BATCH_SIZE] for i in range(0, len(frag_tasks), _BATCH_SIZE)]
    with tempfile.TemporaryDirectory(prefix="cw_validate_") as td:
        workdir = Path(td)
        bw = max(1, min(len(chunks), (os.cpu_count() or 4), 8))
        failed: list[dict] = []
        with ThreadPoolExecutor(max_workers=bw) as pool:
            batch_futs = [(chunk, pool.submit(_batch_compile, chunk, preamble, workdir, f"batch_{i}"))
                          for i, chunk in enumerate(chunks)]
            for chunk, fut in batch_futs:
                try:
                    ok = fut.result()
                except Exception:
                    ok = False
                if ok:
                    for t in chunk:
                        results[t["key"]] = t["frag"]
                        stats.append((t["key"], "ok"))
                else:
                    failed.extend(chunk)
        if failed:
            print(f"{tag}[校验] {len(chunks)} 块中部分未过，回退逐题校验 {len(failed)} 个片段…",
                  file=sys.stderr)
            iw = max(1, min(len(failed), (os.cpu_count() or 4), 8))
            with ThreadPoolExecutor(max_workers=iw) as pool:
                indiv_futs = [pool.submit(_validate_one, t, preamble, system, args, api_key, workdir, tag)
                              for t in failed]
                for fut in indiv_futs:
                    key, frag, status = fut.result()
                    results[key] = frag
                    stats.append((key, status))
    return results, stats
