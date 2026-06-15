#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_multi.py —— 多科并行编排器

读 JSON 任务清单，按 task 调用 gen_sections.run()；所有 section 调用扁平化
提交到共享的 ThreadPoolExecutor，由 --workers 控制全局并发上限（默认 50）。
默认生成完毕后并行调用 gen_sections.build_with_repair 编译每个 .tex（纯 Python，
整卷失败时自动定位+占位+重编，不依赖 bash/WSL）；加 --no-build 跳过。

用法示例：
  python scripts/gen_multi.py --config tasks.json
  python scripts/gen_multi.py --config tasks.json --workers 100 --no-build

JSON 配置格式：
  {
    "tasks": [
      {
        "subject": "probability",   # 必填，对应 conventions/<subject>.md
        "sections": "矩估计,极大似然估计",  # 必填
        "out": "./probability_exam.tex",    # 必填
        "mode": "exam",             # 可选，默认 exam
        "count": 3,                 # 可选（exam 模式题数）
        "difficulty": "期末",
        "title": "参数估计专项练习",
        "course": "概率论与数理统计",
        "date": null,
        "hyperlinks": false,
        "model": null,            # 留空则由 .env(MODEL) 或内置默认解析；写则覆盖
        "base_url": null,         # 留空则由 .env(BASE_URL) 解析，支持任意 OpenAI-compatible 供应商
        "temperature": 0.6,       # kimi-k2 系列自动强制为 1.0；也可在 .env 中设置 TEMPERATURE=
        "env": null,
        "mock": false
        # 其余可选字段（与 CLI 同名，下划线写法）见 TASK_DEFAULTS：
        #   total / types / difficulty_mix / with_examples / figures / figures_per_section /
        #   combined / validate / repair_attempts / cache / refresh_cache
      },
      ...
    ]
  }
"""
import argparse
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
import gen_sections  # noqa: E402
from lib.compile import build_with_repair  # noqa: E402

REQUIRED_FIELDS = ("subject", "sections", "out")

TASK_DEFAULTS = {
    "mode": "exam",
    "count": 3,
    "difficulty": "期末",
    "title": "练习",
    "course": "",
    "date": None,
    "hyperlinks": False,
    "combined": False,
    "types": None,
    "difficulty_mix": None,
    "with_examples": 0,
    "figures": False,
    "figures_per_section": 0,
    "total": None,
    "validate": True,
    "repair_attempts": 2,
    "cache": False,
    "refresh_cache": False,
    # model / base_url 默认 None：留空则由 gen_sections._resolve_provider 从 .env
    # （MODEL / BASE_URL）或内置默认解析，从而支持任意 OpenAI-compatible 供应商。
    # task 里显式写则以显式值为准。
    # temperature：0.6 为通用默认；kimi-k2 系列在 _resolve_provider 中自动强制为 1.0；
    #   也可在 .env 中设 TEMPERATURE=1 全局覆盖，或在每个 task 里显式写 "temperature": 1。
    "model": None,
    "base_url": None,
    "temperature": 0.6,
    "env": None,
    "mock": False,
}


def normalize_task(raw: dict, parallel_sections: bool) -> SimpleNamespace:
    for k in REQUIRED_FIELDS:
        if not raw.get(k):
            raise ValueError(f"task 缺少必填字段 `{k}`：{raw}")
    merged = {**TASK_DEFAULTS, **raw}
    merged["parallel_sections"] = parallel_sections
    return SimpleNamespace(**merged)


def task_label(task: SimpleNamespace) -> str:
    name = Path(task.out).stem or task.subject
    return f"{task.subject}:{name}"


def run_one_task(task: SimpleNamespace, executor: ThreadPoolExecutor, label: str) -> list[Path]:
    print(f"[{label}] 启动 …", file=sys.stderr)
    outs, summary = gen_sections.run(task, executor=executor, label=label)
    print(f"[{label}] 生成完成：{summary}", file=sys.stderr)
    return outs


def build_one(tex_path: Path, label: str) -> str:
    """编译单个 .tex（跨平台纯 Python，不依赖 bash/WSL）。

    走 gen_sections.build_with_repair：整卷编译失败时自动从 .log 定位出错题号并占位后重编，
    保证「整卷必出 PDF」，不再把编译错误抛回人工 debug。两遍编译补全 hyperref 交叉引用、
    清理中间文件均已内置。
    """
    return build_with_repair(tex_path, label=label)


def main():
    ap = argparse.ArgumentParser(description="多科并行编排器（gen_sections + build_pdf）")
    ap.add_argument("--config", required=True, help="任务清单 JSON 路径")
    ap.add_argument("--workers", type=int, default=3,
                    help="全局 ThreadPool 大小（所有 section 调用共享，默认 3；Kimi API 并发上限为 3，超出无益）")
    ap.add_argument("--no-build", action="store_true", help="只生成 .tex，跳过 xelatex 编译")
    ap.add_argument("--sequential-sections", action="store_true",
                    help="禁用单科内 section 并发（每科 section 顺序执行）")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        sys.exit(f"[错误] 找不到配置文件：{cfg_path}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    raw_tasks = cfg.get("tasks") or []
    if not raw_tasks:
        sys.exit("[错误] 配置中未找到 tasks。")

    parallel_sections = not args.sequential_sections
    tasks: list[SimpleNamespace] = []
    for raw in raw_tasks:
        try:
            tasks.append(normalize_task(raw, parallel_sections))
        except ValueError as e:
            sys.exit(f"[错误] {e}")

    labels = [task_label(t) for t in tasks]

    # 检查 out 路径不冲突
    out_paths = [str(Path(t.out).resolve()) for t in tasks]
    if len(set(out_paths)) != len(out_paths):
        sys.exit("[错误] 多个 task 的 `out` 指向同一文件，请使用不同输出路径。")

    # ---- 生成阶段 ----
    # 一个共享的 section 池：所有 task 的 section future 都丢进这里，由 --workers 统一限流。
    # 另一个 task 驱动池：只负责协程化每个 task.run（task.run 内部等自己的 section futures），不限流。
    results: dict[str, dict] = {lbl: {"texs": [], "gen_error": None, "pdfs": [], "build_error": None}
                                for lbl in labels}
    with ThreadPoolExecutor(max_workers=args.workers, thread_name_prefix="section") as section_pool, \
            ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix="task") as task_pool:
        gen_futs = {
            task_pool.submit(run_one_task, t, section_pool, lbl): lbl
            for t, lbl in zip(tasks, labels)
        }
        for fut in as_completed(gen_futs):
            lbl = gen_futs[fut]
            try:
                results[lbl]["texs"] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[lbl]["gen_error"] = str(e)
                print(f"[{lbl}] 生成失败：{e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    # ---- 编译阶段 ----
    # 一个 task 可能产出多个 .tex（exam 分卷：题目卷 + 答案卷），逐个编译。
    if not args.no_build:
        to_build = [(lbl, tex) for lbl, r in results.items() for tex in r["texs"]]
        if to_build:
            with ThreadPoolExecutor(max_workers=min(len(to_build), 8),
                                    thread_name_prefix="build") as bpool:
                build_futs = {bpool.submit(build_one, tex, lbl): (lbl, tex) for lbl, tex in to_build}
                for fut in as_completed(build_futs):
                    lbl, tex = build_futs[fut]
                    try:
                        results[lbl]["pdfs"].append(fut.result())
                    except Exception as e:  # noqa: BLE001
                        results[lbl]["build_error"] = str(e)
                        print(f"[{lbl}] 编译失败（{Path(tex).name}）：{e}", file=sys.stderr)

    # ---- 汇总 ----
    print("\n========== 汇总 ==========", file=sys.stderr)
    all_ok = True
    pdfs: list[str] = []
    for lbl in labels:
        r = results[lbl]
        if r["gen_error"]:
            print(f"  [{lbl}] FAIL（生成） — {r['gen_error'].splitlines()[0]}", file=sys.stderr)
            all_ok = False
        elif r["build_error"]:
            print(f"  [{lbl}] FAIL（编译） — TEX={', '.join(str(t) for t in r['texs'])}", file=sys.stderr)
            all_ok = False
        elif r["pdfs"]:
            print(f"  [{lbl}] OK — PDF={', '.join(r['pdfs'])}", file=sys.stderr)
            pdfs.extend(r["pdfs"])
        elif r["texs"]:
            print(f"  [{lbl}] OK — TEX={', '.join(str(t) for t in r['texs'])}（未编译）", file=sys.stderr)
            pdfs.extend(str(t) for t in r["texs"])

    # stdout: 每行一个产物路径，便于脚本下游消费
    for p in pdfs:
        print(p)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
