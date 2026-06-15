---
name: coursework-pdf
description: 生成大学课程的试题与知识点 PDF。基于 OpenAI-compatible API（默认 deepseek/deepseek-v4-pro，可通过 .env 自定义）分节出题 + XeLaTeX 编译，exam 模式默认产出「题目卷」与「答案卷」两个可打印 PDF（可加 --combined 改回合订单 PDF）。支持 --figures 为概率论/高等数学/大学物理内嵌 TikZ/PGFPlots 矢量配图。当用户要求出题、出练习题、出例题、生成试题、整理知识点、生成复习讲义/习题PDF，或提到概率论、高等数学、大学物理、工程制图等课程需要练习材料或知识点文档时，务必使用本技能——即使用户没有明确说"用 skill"或"生成 PDF"。
---

# coursework-pdf

把「出题 / 整理知识点」做成一条确定性流水线：按科目读取约定文件 → 调 LLM（任意 OpenAI-compatible API，默认 DeepSeek）分节生成 → 套 XeLaTeX 模板 → 编译成可打印 PDF。目标是消除手动排版与手动拼装，你只需决定科目、章节范围和数量。

## 适用判断

- 用户说「出题 / 练习题 / 例题 / 生成试题 / 习题PDF」→ `exam` 模式（题目 + 答案分卷）。
- 用户说「整理知识点 / 复习讲义 / 知识点PDF / study guide」→ `study` 模式（说明性讲义）。
- 单纯在对话里问一道题、要一个概念解释，不要触发本技能；本技能用于成批、成文、要出 PDF 的场景。

## 不可违反的规则

1. **题目区只给题干**。绝不在题目里夹带提示、思路、提纲或答案。提示/解析一律放进答案区。
2. **答案区分步解析**，最终答案用 `\boxedans{...}` 框出，并在每题末尾给「常见陷阱」一行。
3. **题目与答案分卷（默认）**：exam 模式默认产出两个独立 PDF——「题目卷」与「答案卷」，题号一一对应。仅当用户明确要求「合订 / 题答一份」时才加 `--combined`。
4. **「全部章节」必须用 `--sections all`，禁止手列**。当用户要求覆盖整门课时，一律传 `--sections all`（或 `全部`），由脚本从该科 `conventions/<subject>.md` 的 SYLLABUS 块确定性展开——绝不凭记忆手敲章节列表。只有用户明确指定部分章节时才显式逗号列出。
5. **禁用 OCG 图层**（`ocgx2` 等），用户的阅读器不支持。
6. **中文 XeLaTeX**（`ctexart`），不要改成 pdfLaTeX。

## TikZ/PGFPlots 配图

`--figures` 开关（默认关闭）让题目/解答/讲义内嵌自包含的 TikZ/PGFPlots 矢量图。仅对概率论/高等数学/大学物理三科生效（需科 conventions 定义了 FIGURE_POLICY 块）。工程制图无该块，误传 `--figures` 也是 no-op。

配图有完善降级策略：图编译失败时自动剥图保文 → 仍失败才占位，正文不受影响。详见 `figures.md`。

## 工作流程

### 0. 统一选项式参数收集

在开始后续步骤前，先识别用户请求中已明确与未明确的参数，对所有未明确的参数必须用 `AskUserQuestion` 工具批量询问——绝不改用纯文字让用户手打。每次最多 4 个问题，按以下规则分批：

**第一批（最先询问）**：

| 参数 | 选项 | 询问条件 |
| --- | --- | --- |
| **科目** | 概率论与数理统计 / 高等数学 / 大学物理 / 工程制图 / Other（新科目） | 用户未指定科目 |
| **模式** | exam（出题，题目卷＋答案卷）/ study（知识点讲义） | 用户未指定模式 |

科目与模式确认后，再发**第二批**：

| 参数 | 选项 | 询问条件 |
| --- | --- | --- |
| **章节范围** | 全部章节（`all`）/ Other（手动输入，逗号分隔） | 用户未指定章节 |
| **难度**（exam 专用） | 期末 ★★☆（推荐）/ 基础 ★☆☆ / 竞赛 ★★★ / 混合梯度 | exam 模式且未指定难度 |
| **总题数**（exam 专用） | 15 题（推荐）/ 10 题 / 20 题 / 30 题 | exam 模式且未指定题数 |
| **输出文件名** | 默认 `<subject>_<mode>`（推荐）/ Other（自定义） | 始终询问 |

科目为概率论 / 高等数学 / 大学物理三科之一时，再发**第三批（配图）**：

| 参数 | 选项 | 询问条件 |
| --- | --- | --- |
| **是否配图** | 否（推荐，纯文字）/ 是（内嵌 TikZ/PGFPlots 矢量图） | 科目属上述三科且用户未表态 |
| **图片数量** | 按需自动（推荐）/ 精简（~1张）/ 适中（~2张）/ 丰富（~3张） | 仅当「是否配图」选了「是」 |

补充规则：
- 用户消息中已明确的参数不再重复询问。
- 第一批若两项都已知，直接进入第二批。
- 第三批仅对三个授权科目发起。工程制图不问配图、也不传 `--figures`。
- 收集完所有参数后再进入 Step 1，不要边问边做。

### 1. 确定科目，定位约定文件

| 科目 | `--subject` 值 | 文件 |
| --- | --- | --- |
| 概率论与数理统计 | `probability` | `conventions/probability.md` |
| 高等数学 | `calculus` | `conventions/calculus.md` |
| 大学物理 | `university-physics` | `conventions/university-physics.md` |
| 工程制图 | `engineering-drawing` | `conventions/engineering-drawing.md` |

新科目：复制 `conventions/_template.md`，填好 SYMBOL_BLOCK / PROMPT_EXTRA / SYLLABUS 三个标记块。

### 2. 读约定文件

读一遍 `conventions/<subject>.md`，了解符号规则。脚本自动注入 SYMBOL_BLOCK 和 PROMPT_EXTRA 到每次 LLM 调用。用 `python scripts/gen_sections.py --subject <subject> --list-sections` 预览章节清单。

### 3. .env 配置（直接跳过，报错时再排查）

脚本自动读取 `.env`。仅在脚本报错（401/Connection refused/No API key）时才排查：
- API key 优先级：`API_KEY` → `LLM_API_KEY` → `OPENAI_API_KEY` → `DEEPSEEK_API_KEY`
- 默认 BASE_URL：`https://openrouter.ai/api/v1`，默认 MODEL：`deepseek/deepseek-v4-pro`
- 可通过 `.env` 切换到任意 OpenAI-compatible API。用户可通过 `.env` 的 `BASE_URL` / `MODEL` 切换到任意 OpenAI-compatible API。
- **绝不**把 key 写进 skill 文件。

### 4. 确认输出文件名

文件名已在 Step 0 收集（默认 `<subject>_<mode>`）。所有文件保存在当前工作目录，通过 `--out ./<filename>.tex` 指定。

### 5. 生成内容（分节、无状态）

```bash
python scripts/gen_sections.py \
  --subject probability \
  --mode exam \
  --sections "矩估计,极大似然估计" \
  --total 15 \
  --difficulty 期末 \
  --title "参数估计专项练习" \
  --course "概率论与数理统计" \
  --out ./<filename>.tex
```

要点：
- `--sections` 每节是一次独立 LLM 调用，对抗长上下文质量退化。
- 全部章节：`--sections all`（从 SYLLABUS 展开），**绝不手敲**。
- `--total` 总题数，自动均分到各节。
- exam 默认分卷（`_题目.tex` + `_答案.tex`）；加 `--combined` 回合订单文件。
- study 模式默认开启目录超链接与 PDF 书签。
- `--tex-only` 仅生成 `.tex` 跳过编译（无需 xelatex 时使用）。
- `--build` 生成后直接编译出 PDF（推荐）。

**完整参数参考**：见 `reference.md`。**配图系统详情**：见 `figures.md`。

### 6. 审查 .tex

扫一眼产出的 `.tex`（exam 分卷有两个文件）。重点查：题目卷是否纯净、答案卷是否有 `\boxedans` 和「常见陷阱」、题号对应、记号合规。

脚本内置三层鲁棒性（详见 `reference.md`）：
- **P0**：自动清洗（去围栏、规整 `\boxedans`、数学模式中文包 `\text{}` 等）
- **P1**：逐题微编译校验 + 失败再生成（默认开启，`--no-validate` 关闭）
- **P2**：整卷编译 + 失败自动定位/占位（`--build` 触发）

### 7. 编译

推荐直接用 `--build` 让脚本编译（含整卷自动修复）：

```bash
python scripts/gen_sections.py --subject ... --out ./<filename>.tex --build
```

或手动两遍编译（无 `--build` 时）：

```powershell
xelatex -interaction=nonstopmode -halt-on-error "<filename>_题目.tex"
xelatex -interaction=nonstopmode -halt-on-error "<filename>_题目.tex"
xelatex -interaction=nonstopmode -halt-on-error "<filename>_答案.tex"
xelatex -interaction=nonstopmode -halt-on-error "<filename>_答案.tex"
```

### 8. 上传到 Google Drive

编译成功后检查 Google Drive Desktop 挂载：

```powershell
Test-Path '<GDRIVE_MOUNT>'
```

若 `True`：按科目→模式→子文件夹复制 PDF。默认执行上传，用户说「不用上传」则跳过。
若 `False`：跳过，交付时提示 PDF 仅保存在本地。

> 不要使用 `mcp__claude_ai_Google_Drive__*` 工具——PDF 体积超出 MCP base64 参数上限。

### 9. 处理编译错误

用 `--build` 时 P2 层已自动定位+占位+重编，整卷必出 PDF。按 stderr 的 `[整卷修复] 第 N 题…已占位` 去补对应题号即可。仅当脚本抛错说无法定位到题号时才需手工处理 `.log`。

### 10. 交付

用 `present_files` 把 PDF 交给用户。exam 分卷模式把题目卷与答案卷两个 PDF 一并交付。

## 并行生成多科

用户一次性要求 2+ 门课程时：

1. 对每门课按 Step 0 收集参数（每科 `out` 必须各不相同）
2. 在当前工作目录写 `tasks.json`（字段参考见 `reference.md`）
3. 运行 `python scripts/gen_multi.py --config tasks.json`
4. 处理结果：失败的 task 不影响其他 task；编译成功的 PDF 执行 Google Drive 上传

## 资源说明

- `conventions/` — 各科约定（SYMBOL_BLOCK / PROMPT_EXTRA / SYLLABUS）
- `templates/` — LaTeX 模板（exam 分卷 / combined / study）
- `scripts/gen_sections.py` — 无状态分节生成器（主入口）
- `scripts/gen_multi.py` — 多科并行编排器
- `scripts/build_pdf.sh` — XeLaTeX 编译脚本（Linux/macOS 可选）
- `reference.md` — CLI 参数速查手册（按需加载）
- `figures.md` — 配图系统说明（按需加载）
