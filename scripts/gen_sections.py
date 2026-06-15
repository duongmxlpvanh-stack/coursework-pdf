#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_sections.py —— 无状态分节生成器（编排层）

按科目读取约定文件，对 --sections 里的每一节做一次独立（无状态）的 LLM 调用，
每次都注入同一份符号约定块，以对抗多章节长上下文质量退化。生成内容填入 XeLaTeX
模板，产出自包含的 .tex。

用法示例：
  python scripts/gen_sections.py --subject probability --mode exam \
      --sections "矩估计,极大似然估计" --total 3 --difficulty 期末 \
      --title "参数估计专项练习" --course "概率论与数理统计" --out ./out/main.tex

不调用 API 先验证流水线：加 --mock。
查看全部参数：python scripts/gen_sections.py -h
"""
import argparse
import datetime as _dt
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lib.config import resolve_provider
from lib.conventions import load_convention, load_figure_policy, resolve_sections
from lib.prompts import (build_system_prompt, parse_types, parse_difficulty_mix,
                          user_prompt_exam, user_prompt_study)
from lib.llm import section_call
from lib.sanitize import sanitize_fragment, fragment_issues
from lib.validate import validate_fragments
from lib.compile import (fill_template, split_out_paths, parse_exam_items,
                          build_with_repair, compile_pdf, _HYPERLINKS_PREAMBLE_ON,
                          _HYPERLINKS_PREAMBLE_OFF, _STUDY_TOC_PREAMBLE)
from lib.cache import CACHE_DIR

SKILL_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-pro"


def _gen_section_exam(system, sec, args, api_key):
    types = getattr(args, "types_parsed", None) or None
    difficulty_mix = getattr(args, "difficulty_mix_parsed", None) or None
    figures = bool(getattr(args, "figures_effective", False))
    fps = int(getattr(args, "figures_per_section", 0) or 0)
    raw = section_call(
        system,
        user_prompt_exam(sec, args.count, args.difficulty, types, difficulty_mix, figures, fps),
        args=args, api_key=api_key, section=sec, mode="exam",
    )
    return sec, parse_exam_items(raw)


def _gen_section_study(system, sec, args, api_key):
    with_examples = getattr(args, "with_examples", 0)
    figures = bool(getattr(args, "figures_effective", False))
    fps = int(getattr(args, "figures_per_section", 0) or 0)
    raw = section_call(
        system,
        user_prompt_study(sec, with_examples, figures, fps),
        args=args, api_key=api_key, section=sec, mode="study",
    )
    return sec, raw


def run(args, executor: ThreadPoolExecutor | None = None, label: str = "") -> tuple[list[Path], str]:
    """生成单科 .tex。返回 (out_paths, summary)。"""
    tag = f"[{label}] " if label else ""
    if not hasattr(args, "types_parsed"):
        args.types_parsed = parse_types(getattr(args, "types", None))
    if not hasattr(args, "difficulty_mix_parsed"):
        args.difficulty_mix_parsed = parse_difficulty_mix(getattr(args, "difficulty_mix", None))
    symbol_block, prompt_extra = load_convention(args.subject)
    figure_policy = load_figure_policy(args.subject) if getattr(args, "figures", False) else ""
    args.figures_effective = bool(figure_policy)
    if getattr(args, "figures", False) and not figure_policy:
        print(f"{tag}[提示] --figures 已传入，但「{args.subject}」未定义 FIGURE_POLICY，按无图处理。",
              file=sys.stderr)
    elif args.figures_effective:
        print(f"{tag}[配图] 已为「{args.subject}」启用 TikZ/PGFPlots 配图。", file=sys.stderr)
    system = build_system_prompt(symbol_block, prompt_extra, figure_policy)
    api_key = resolve_provider(args)

    sections = resolve_sections(args.subject, args.sections, tag)
    if not sections:
        raise RuntimeError("[错误] sections 为空。")

    total = getattr(args, "total", None)
    if total is not None and args.mode == "exam":
        per_section = max(1, round(total / len(sections)))
        print(f"{tag}[分配] 总题数 {total} ÷ {len(sections)} 节 = 每节约 {per_section} 题", file=sys.stderr)
        args.count = per_section

    date = args.date or _dt.date.today().isoformat()

    if args.mode == "study":
        hyperlinks_preamble = _STUDY_TOC_PREAMBLE
    else:
        combined = getattr(args, "combined", False)
        want_hyperlinks = args.hyperlinks and not (args.mode == "exam" and not combined)
        if args.hyperlinks and not want_hyperlinks:
            print(f"{tag}[提示] exam 分卷模式下 --hyperlinks 不适用，已忽略。", file=sys.stderr)
        hyperlinks_preamble = _HYPERLINKS_PREAMBLE_ON if want_hyperlinks else _HYPERLINKS_PREAMBLE_OFF

    use_parallel = bool(getattr(args, "parallel_sections", False))
    owned_executor: ThreadPoolExecutor | None = None
    if use_parallel and executor is None:
        owned_executor = ThreadPoolExecutor(max_workers=max(1, min(len(sections), 3)))
        executor = owned_executor

    worker = _gen_section_exam if args.mode == "exam" else _gen_section_study

    try:
        if use_parallel:
            futures = [executor.submit(worker, system, sec, args, api_key) for sec in sections]
            results = []
            for sec, fut in zip(sections, futures):
                print(f"{tag}[生成] 第「{sec}」节（并发）…", file=sys.stderr)
                results.append(fut.result())
        else:
            results = []
            for sec in sections:
                print(f"{tag}[生成] 第「{sec}」节 …", file=sys.stderr)
                results.append(worker(system, sec, args, api_key))
    finally:
        if owned_executor is not None:
            owned_executor.shutdown(wait=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    to_write: list[tuple[Path, str]] = []

    validate = bool(getattr(args, "validate", True))

    if args.mode == "exam":
        collected: list[tuple[int, str, str, str]] = []
        n = 0
        for sec, items in results:
            if not items:
                print(f"{tag}[警告] 「{sec}」未解析出题目，已跳过。", file=sys.stderr)
            for prob, sol in items:
                n += 1
                prob = sanitize_fragment(prob)
                sol = sanitize_fragment(sol)
                for who, frag in (("题", prob), ("答", sol)):
                    for msg in fragment_issues(frag):
                        print(f"{tag}[告警] 第 {n} {who}：{msg}（已尽力清洗，待微编译校验）", file=sys.stderr)
                collected.append((n, sec, prob, sol))
        if n == 0:
            raise RuntimeError("[错误] 未生成任何题目。")

        ph = 0
        if validate:
            frag_tasks = []
            for m, sec, prob, sol in collected:
                frag_tasks.append({"key": (m, "prob"), "kind": "prob", "section": sec, "frag": prob})
                frag_tasks.append({"key": (m, "ans"), "kind": "ans", "section": sec, "frag": sol})
            fixed, stats = validate_fragments(frag_tasks, system=system, args=args,
                                              api_key=api_key, tag=tag)
            if stats:
                rep = sum(1 for _, s in stats if s.startswith("repaired"))
                ph = sum(1 for _, s in stats if s == "placeholder")
                strip = sum(1 for _, s in stats if s == "figure_stripped")
                strip_note = f"，剥图保文 {strip}" if strip else ""
                print(f"{tag}[校验] 完成：{len(stats)} 个片段，修复 {rep}，占位 {ph}{strip_note}。", file=sys.stderr)
            problems = [f"\\probitem{{{m}}}{{{fixed[(m, 'prob')]}}}" for m, _, _, _ in collected]
            answers = [f"\\ansitem{{{m}}}{{{fixed[(m, 'ans')]}}}" for m, _, _, _ in collected]
        else:
            problems = [f"\\probitem{{{m}}}{{{prob}}}" for m, _, prob, _ in collected]
            answers = [f"\\ansitem{{{m}}}{{{sol}}}" for m, _, _, sol in collected]
        ph_note = f"，{ph} 题占位" if ph else ""
        common = {
            "TITLE": args.title, "COURSE": args.course, "DATE": date,
            "HYPERLINKS_PREAMBLE": hyperlinks_preamble,
        }
        combined = getattr(args, "combined", False)
        if combined:
            content = fill_template("exam.tex", {
                **common,
                "PROBLEMS": "\n".join(problems), "ANSWERS": "\n".join(answers),
            })
            to_write.append((out, content))
            summary = f"{len(sections)} 节，共 {n} 题（合订单 PDF）{ph_note}"
        else:
            prob_out, ans_out = split_out_paths(out)
            to_write.append((prob_out, fill_template("exam-problems.tex", {
                **common, "PROBLEMS": "\n".join(problems),
            })))
            to_write.append((ans_out, fill_template("exam-answers.tex", {
                **common, "ANSWERS": "\n".join(answers),
            })))
            summary = f"{len(sections)} 节，共 {n} 题（题目卷 + 答案卷）{ph_note}"
    else:
        items_st: list[tuple[str, str]] = []
        for sec, text in results:
            text = sanitize_fragment(text)
            for msg in fragment_issues(text):
                print(f"{tag}[告警] 「{sec}」：{msg}（已尽力清洗，待微编译校验）", file=sys.stderr)
            items_st.append((sec, text))
        ph = 0
        if validate:
            frag_tasks = [{"key": i, "kind": "study", "section": sec, "frag": text}
                          for i, (sec, text) in enumerate(items_st)]
            fixed, stats = validate_fragments(frag_tasks, system=system, args=args,
                                              api_key=api_key, tag=tag)
            if stats:
                rep = sum(1 for _, s in stats if s.startswith("repaired"))
                ph = sum(1 for _, s in stats if s == "placeholder")
                strip = sum(1 for _, s in stats if s == "figure_stripped")
                strip_note = f"，剥图保文 {strip}" if strip else ""
                print(f"{tag}[校验] 完成：{len(stats)} 节，修复 {rep}，占位 {ph}{strip_note}。", file=sys.stderr)
            items_st = [(sec, fixed[i]) for i, (sec, _) in enumerate(items_st)]
        blocks = [f"\\section{{{sec}}}\n{text}" for sec, text in items_st]
        content = fill_template("study-guide.tex", {
            "TITLE": args.title, "COURSE": args.course, "DATE": date,
            "KNOWLEDGE": "\n\n".join(blocks),
            "HYPERLINKS_PREAMBLE": hyperlinks_preamble,
        })
        to_write.append((out, content))
        ph_note = f"，{ph} 节占位" if ph else ""
        summary = f"{len(sections)} 个知识点小节{ph_note}"

    out_paths: list[Path] = []
    for path, content in to_write:
        path.write_text(content, encoding="utf-8")
        out_paths.append(path)
    print(f"{tag}[完成] {summary} -> {', '.join(str(p) for p in out_paths)}", file=sys.stderr)
    return out_paths, summary


def main():
    ap = argparse.ArgumentParser(description="无状态分节生成器（任意 OpenAI-compatible LLM + XeLaTeX）")
    ap.add_argument("--subject", default=None, help="科目（生成时必填）")
    ap.add_argument("--mode", choices=["exam", "study"], default="exam")
    ap.add_argument("--sections", default=None, help="逗号分隔；all 从 SYLLABUS 展开全部章节")
    ap.add_argument("--list-sections", action="store_true", default=False, help="打印章节清单后退出")
    ap.add_argument("--count", type=int, default=3, help="每节题数（被 --total 覆盖时忽略）")
    ap.add_argument("--total", type=int, default=None, help="总题数，自动均分到各节")
    ap.add_argument("--difficulty", default="期末")
    ap.add_argument("--types", default=None, help="题型分配，如 '选择:2,填空:2,计算:3'")
    ap.add_argument("--difficulty-mix", default=None, dest="difficulty_mix", help="梯度难度分配")
    ap.add_argument("--with-examples", type=int, default=0, dest="with_examples")
    ap.add_argument("--figures", action="store_true", default=False, help="启用 TikZ/PGFPlots 配图")
    ap.add_argument("--figures-per-section", type=int, default=0, dest="figures_per_section",
                    help="每节目标配图数")
    ap.add_argument("--title", default="练习")
    ap.add_argument("--course", default="")
    ap.add_argument("--date", default=None)
    ap.add_argument("--out", default="./main.tex")
    ap.add_argument("--hyperlinks", action="store_true", default=False)
    ap.add_argument("--combined", action="store_true", default=False)
    ap.add_argument("--parallel-sections", action="store_true", default=True)
    ap.add_argument("--no-validate", dest="validate", action="store_false", default=True)
    ap.add_argument("--tex-only", action="store_true", default=False,
                    help="仅生成 .tex 文件，跳过编译校验和 PDF 编译")
    ap.add_argument("--repair-attempts", type=int, default=2)
    ap.add_argument("--build", action="store_true", default=False)
    ap.add_argument("--pdf-engine", default="xelatex", choices=["xelatex", "tectonic", "online"],
                    help="PDF 编译引擎：xelatex（本地）/ tectonic（自动下载，推荐）/ online（在线备用）")
    ap.add_argument("--max-build-repairs", type=int, default=6)
    ap.add_argument("--cache", action="store_true", default=False)
    ap.add_argument("--refresh-cache", action="store_true", default=False)
    ap.add_argument("--clear-cache", action="store_true", default=False)
    ap.add_argument("--model", default=None, help=f"默认 {DEFAULT_MODEL}")
    ap.add_argument("--base-url", default=None, help=f"默认 {DEFAULT_BASE_URL}")
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--env", default=None, help="指定 .env 路径")
    ap.add_argument("--mock", action="store_true", help="不调用 API，用样例内容验证流水线")
    args = ap.parse_args()

    if args.tex_only:
        args.validate = False
        args.build = False

    if args.clear_cache:
        if CACHE_DIR.is_dir():
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
            print(f"[缓存] 已清空 {CACHE_DIR}", file=sys.stderr)
        else:
            print(f"[缓存] 无缓存目录 {CACHE_DIR}，无需清理。", file=sys.stderr)
        return

    if not args.subject:
        ap.error("缺少 --subject")

    if args.list_sections:
        from lib.conventions import load_syllabus
        try:
            for s in load_syllabus(args.subject):
                print(s)
        except RuntimeError as e:
            sys.exit(str(e))
        return

    if not args.sections:
        ap.error("缺少 --sections")

    try:
        outs, _ = run(args)
    except RuntimeError as e:
        sys.exit(str(e))

    if args.build and not args.mock:
        engine = getattr(args, "pdf_engine", "xelatex")
        built = []
        with ThreadPoolExecutor(max_workers=len(outs)) as pool:
            futs = [pool.submit(compile_pdf, o, engine=engine,
                                max_repairs=args.max_build_repairs)
                    for o in outs]
            for fut in futs:
                try:
                    built.append(fut.result())
                except RuntimeError as e:
                    sys.exit(str(e))
        outs = built
    for o in outs:
        print(str(o))


if __name__ == "__main__":
    main()
