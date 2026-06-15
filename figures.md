# TikZ/PGFPlots 配图系统

> 本文件按需加载——仅在用户启用 `--figures` 或询问配图相关问题时读入上下文。

## 概述

`--figures` 开关（默认关闭）让题目/解答/讲义内嵌 TikZ/PGFPlots 矢量图。

## 设计要点

### 默认关闭、行为等价
不传 `--figures` 时，所发 prompt 与题目/答案内容与无图版逐字节一致（仅导言区多加载了 tikz/pgfplots 包，未使用、无副作用）。

### 按科目授权
`--figures` 只对 `conventions/<subject>.md` 里定义了 `<!-- FIGURE_POLICY_START/END -->` 块的科目生效。目前仅以下三科支持配图：
- **概率论与数理统计** (`probability`)
- **高等数学** (`calculus`)
- **大学物理** (`university-physics`)

**工程制图没有该块**，即便误传 `--figures` 也是 no-op，严格无图政策原样保留。对未授权科目传 `--figures`，脚本会在 stderr 打印「按无图处理」提示。

### 纯内联、零外部依赖
硬性禁止 `\includegraphics`、外部图片/数据文件、`\write18`/shell-escape。图必须是可独立编译的 TikZ/PGFPlots 代码。

### 导言区已加载的库
- **TikZ 库**：`calc`, `arrows.meta`, `angles`, `quotes`, `patterns`, `intersections`, `positioning`, `decorations.pathmorphing`, `decorations.markings`, `bending`, `backgrounds`, `shapes.geometric`, `shapes.misc`, `fit`
- **PGFPlots 库**：`fillbetween`, `groupplots`, `polar`, `statistics`（缺包静默跳过，不阻断编译）

### 配图降级策略
图只是辅助，不该拖垮正文。当某题的图无法修好时：
1. P1 微编译阶段：先剥图保文（保留题干+解答正文，去掉 TikZ 代码）
2. P2 整卷编译阶段：同样先剥图再占位
3. 只有剥图后仍编不过的题才退回红框占位

### 编译超时兜底
每次 xelatex 调用有墙钟超时（默认 90s，环境变量 `COURSEWARE_COMPILE_TIMEOUT` 调整），防止 TikZ/PGFPlots 遇坐标特异点、过大 `samples` 或非终止绘制时挂死整条流水线。

## 配图政策来源

- 通用硬规则：`gen_sections.py` 的 `_FIGURE_POLICY_BASE`
- 每科特定规则：`conventions/<subject>.md` 的 `FIGURE_POLICY` 块
- 启用 `--figures` 且科有 FIGURE_POLICY 时，`PROMPT_EXTRA` 中「不要作图」一条自动被覆盖

## 使用方法

```bash
# 单科：加 --figures，用 --figures-per-section 控制图量
python scripts/gen_sections.py --subject probability --mode exam \
  --sections "条件概率" --total 5 --figures --figures-per-section 2 --build

# 多科：tasks.json 中用 "figures": true 和 "figures_per_section": N
```
