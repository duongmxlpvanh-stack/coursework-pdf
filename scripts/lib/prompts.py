# -*- coding: utf-8 -*-
"""System/User Prompt 构建。零内部依赖（纯字符串拼接 + 解析）。"""

_DIFF_STARS: dict[str, str] = {
    "基础": "★☆☆", "简单": "★☆☆", "平时": "★☆☆",
    "中等": "★★☆", "期末": "★★☆",
    "难": "★★★", "竞赛": "★★★", "困难": "★★★",
}

_FIGURE_POLICY_BASE = (
    "\n【配图政策（已启用 TikZ/PGFPlots 配图）】\n"
    "- 当且仅当一张图能显著帮助理解时才配图；纯计算题不要硬塞图。可在题目、解答或讲义正文中"
    "嵌入自包含的 \\begin{tikzpicture}...\\end{tikzpicture}，函数图像/坐标图用 pgfplots 的 "
    "\\begin{axis}...\\end{axis}（已加载 tikz、pgfplots 及 calc/arrows.meta/angles/quotes/patterns/"
    "intersections/positioning/decorations.pathmorphing 库，compat=1.18）。\n"
    "- 硬规则：绝不使用 \\includegraphics、绝不引用任何外部图片/数据文件、绝不使用 \\write18 或任何 "
    "shell-escape 特性、绝不 \\input 外部文件——图必须是纯内联、可独立编译的 TikZ/PGFPlots 代码。\n"
    "- 图要小而清晰：tikzpicture 建议加 [scale=...] 或显式坐标范围控制尺寸，避免超出页宽；"
    "用 \\begin{center}...\\end{center} 居中。务必保证 \\begin/\\end、坐标括号、{} 全部配对。\n"
    "- 题目（PROBLEM）里只在「图本身是题目已知条件」时配图（如给定电路/几何构型/已知曲线），"
    "绝不通过图泄漏解题思路、中间步骤或答案；提示性、解释性的图一律放进解答（SOLUTION）。\n"
    "- 图中文字标签可用中文（位于 node 文本/text 模式，合法）；图内数学仍用 $...$。\n"
)


def parse_types(raw: str | None) -> list[tuple[str, int]]:
    """'选择:2,填空:2,计算:3' -> [('选择题',2),('填空题',2),('计算题',3)]"""
    if not raw:
        return []
    result: list[tuple[str, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        name, n = part.rsplit(":", 1)
        name = name.strip()
        if not name.endswith("题"):
            name += "题"
        try:
            result.append((name, int(n.strip())))
        except ValueError:
            pass
    return result


def parse_difficulty_mix(raw: str | None) -> list[tuple[str, int]]:
    """'基础:1,期末:2,竞赛:1' -> [('基础',1),('期末',2),('竞赛',1)]"""
    if not raw:
        return []
    result: list[tuple[str, int]] = []
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        name, n = part.rsplit(":", 1)
        try:
            result.append((name.strip(), int(n.strip())))
        except ValueError:
            pass
    return result


def build_system_prompt(symbol_block: str, prompt_extra: str,
                        figure_policy: str = "") -> str:
    base = (
        "你是中国大学课程的命题与解题助手，为 XeLaTeX (ctexart) 文档生成内容。\n"
        "严格遵守以下规则：\n"
        "- 只输出 LaTeX 正文片段：不要 \\documentclass、不要导言区、不要 \\begin{document}、"
        "不要 markdown 代码围栏（``` ）、不要任何解释性旁白。\n"
        "- 中文用普通文本，数学用 $...$ 或 \\[...\\]；确保所有数学环境、括号、\\left\\right 都配对。\n"
        "- 题目（PROBLEM）只含题干，绝不包含任何提示、思路、提纲或答案。\n"
        "- 解答（SOLUTION）分步详解，最终答案用 \\boxedans{...} 框出（\\boxedans 已自动提供数学模式，参数内不要加 $...$）。\n"
        "- \\boxedans 本身已是 display 数学环境，禁止在其外再套 \\[ \\] 或 $$；直接写 \\boxedans{...} 即可。\n"
        "- \\boxedans 参数内若含中文，必须用 \\text{...} 包裹，例如 \\boxedans{\\text{最小值为} 27a^3}。\n"
        "- 务必保证花括号严格配对：\\boxedans{...} 只用一个 } 收尾，不要在行末附加多余的 }。\n"
        "- 不要自行编号，编号由外部程序统一添加。\n"
    )
    parts = [base, "\n【符号约定（务必遵守）】\n" + symbol_block]
    if prompt_extra:
        parts.append("\n【本科目补充要求】\n" + prompt_extra)
    if figure_policy:
        parts.append(_FIGURE_POLICY_BASE + "【本科目配图约定】\n" + figure_policy)
    return "\n".join(parts)


def _fig_count_hint(figures: bool, per_section: int, where: str) -> str:
    """根据是否配图与每节目标配图数，生成注入 prompt 的配图数量提示。"""
    if not figures:
        return ""
    if per_section and per_section > 0:
        return (
            f"本节请配约 {per_section} 张自包含的 tikzpicture / pgfplots 图（可按需浮动 ±1，"
            f"只在最能帮助理解处配，绝不为凑数硬塞），可分布在{where}。\n"
        )
    return (
        f"若配图有助于理解，可按系统提示中的配图政策在{where}嵌入自包含的 "
        "tikzpicture / pgfplots 图。\n"
    )


def user_prompt_exam(section: str, count: int, difficulty: str,
                     types: list | None = None,
                     difficulty_mix: list | None = None,
                     figures: bool = False,
                     figures_per_section: int = 0) -> str:
    if difficulty_mix:
        total = sum(n for _, n in difficulty_mix)
    elif types:
        total = sum(n for _, n in types)
    else:
        total = count

    constraints: list[str] = []
    if types:
        type_desc = "、".join(f"{tn} {n} 道" for tn, n in types)
        constraints.append(
            f"按题型分配（{type_desc}），在每道题目开头用「（题型）」标注，例如「（计算题）」"
        )
    if difficulty_mix:
        diff_desc = "、".join(
            f"{dn}难度（{_DIFF_STARS.get(dn, '★★☆')}）{n} 道" for dn, n in difficulty_mix
        )
        constraints.append(
            f"按难度分配（{diff_desc}），在每道题目开头用星级标注，例如「★★☆ 」"
        )
    if not constraints:
        constraints.append(f"出 {total} 道{difficulty}难度的题")

    requirement = "，".join(constraints)
    fig_hint = _fig_count_hint(figures, figures_per_section, "题目或解答中")
    return (
        f"请就「{section}」这一主题，{requirement}，每题给出题目与完整解答。\n"
        f"{fig_hint}"
        f"严格按以下格式输出，共 {total} 段，不要有多余文字：\n"
        "===ITEM===\n[PROBLEM]\n（题目的 LaTeX 正文）\n[SOLUTION]\n（解答的 LaTeX 正文，含 \\boxedans）\n"
    )


def user_prompt_study(section: str, with_examples: int = 0,
                      figures: bool = False,
                      figures_per_section: int = 0) -> str:
    base = (
        f"请就「{section}」这一主题，撰写一段知识点复习讲义的 LaTeX 正文，"
        "涵盖核心定义、定理、公式与典型方法要点。只输出正文片段，不要小节标题（外部会添加），不要代码围栏。"
    )
    if figures:
        if figures_per_section and figures_per_section > 0:
            base += (
                f"本节请配约 {figures_per_section} 张自包含的 tikzpicture / pgfplots 图"
                "（按需浮动 ±1，只在确有助于理解处配，如函数图像、几何/受力示意、密度曲线，"
                "绝不为凑数硬塞）。"
            )
        else:
            base += (
                "若配图有助于理解（如函数图像、几何/受力示意、密度曲线），"
                "可按系统提示中的配图政策嵌入自包含的 tikzpicture / pgfplots 图。"
            )
    if with_examples > 0:
        base += (
            f"\n讲义正文末尾另起 \\subsection*{{配套例题}} 小节，"
            f"出 {with_examples} 道配套例题（含完整解答）。"
            "每道例题用 \\textbf{例~N.}（顺序编号）引出，"
            "解答紧跟题后用 \\textbf{解：} 引导，"
            "最终答案用 \\boxedans{...} 给出。"
            "各例题间用 \\medskip 分隔，不要代码围栏。"
        )
    return base
