# coursework-pdf 

> 大学课程试题与知识点 PDF 生成器 —— LLM 出题 + XeLaTeX 排版，一站式流水线

把「出题 / 整理知识点」变成一条命令：按科目读取约定文件 → 调 LLM 分节生成 → 套 XeLaTeX 模板 → 编译成可打印 PDF。目标是**消除手动排版与手动拼装**，你只需决定科目、章节范围和题数。

##  特性

-  **exam 模式**：出题 + 答案分卷 PDF，题号一一对应
-  **study 模式**：知识点复习讲义，带目录超链接和 PDF 书签
-  **三层鲁棒性**：P0 自动清洗 → P1 逐题编译校验+自动修复 → P2 整卷失败自动占位，**PDF 必出**
-  **TikZ/PGFPlots 配图**：概率论/高数/物理三科支持内嵌矢量图（函数图像、受力分析、积分区域等）
-  **零安装编译**：`--pdf-engine tectonic` 自动下载 tectonic 引擎，无需安装 TeX Live
-  **多科并发**：一次生成多门课材料
-  **灵活控制**：题型配比、难度梯度、章节范围全可控

##  支持科目

| 科目 | `--subject` | 配图 |
|------|-------------|:----:|
| 概率论与数理统计 | `probability` | ✅ |
| 高等数学（多元微积分） | `calculus` | ✅ |
| 大学物理 | `university-physics` | ✅ |
| 工程制图 | `engineering-drawing` | ❌（纯文字） |
| 人工智能的数学思维 | `ai-math-thinking` | ❌（概念题为主） |

> 新科目只需复制 `conventions/_template.md` 填写三个标记块即可接入，无需改代码。

##  快速开始

### 1. 配置 API Key

```bash
# 在 skill 根目录创建 .env
echo "API_KEY=sk-your-key-here" > .env
echo "BASE_URL=https://api.deepseek.com/v1" >> .env
echo "MODEL=deepseek-chat" >> .env
```

支持任意 OpenAI-compatible API（DeepSeek / OpenAI / OpenRouter / 通义千问 / 本地 vLLM 等）。

### 2. 出题 (exam 模式)

```bash
python scripts/gen_sections.py \
  --subject probability \
  --mode exam \
  --sections "矩估计,极大似然估计" \
  --total 15 \
  --difficulty 期末 \
  --title "参数估计专项练习" \
  --course "概率论与数理统计" \
  --out ./output.tex \
  --build --pdf-engine tectonic
```

产出：`output_题目.pdf` + `output_答案.pdf`（题号一一对应）

### 3. 复习讲义 (study 模式)

```bash
python scripts/gen_sections.py \
  --subject calculus \
  --mode study \
  --sections all \
  --title "高等数学复习讲义" \
  --course "高等数学" \
  --out ./study_guide.tex \
  --build --pdf-engine tectonic
```

### 4. 章节管理

```bash
# 查看某科全部章节
python scripts/gen_sections.py --subject probability --list-sections

# 只出指定章节
--sections "条件概率,贝叶斯公式"

# 全部章节一次性覆盖
--sections all
```

## 📖 参数速查

### 核心参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--subject` | 科目 | 必填 |
| `--mode` | `exam` / `study` | `exam` |
| `--sections` | 章节，逗号分隔 / `all` | 必填 |
| `--total` | 总题数（exam） | — |
| `--difficulty` | 平时 / 期末 / 竞赛 | `期末` |
| `--out` | 输出路径 | `./main.tex` |
| `--build` | 生成后编译 PDF | 否 |
| `--pdf-engine` | `xelatex` / `tectonic` / `online` | `xelatex` |

### 高级参数

| 参数 | 说明 |
|------|------|
| `--types` | 题型分配，如 `"选择:2,填空:2,计算:3"` |
| `--difficulty-mix` | 梯度难度，如 `"基础:1,期末:2,竞赛:1"` |
| `--figures` | 启用 TikZ/PGFPlots 配图（仅三科） |
| `--figures-per-section` | 每节图数（0=按需，1-3） |
| `--tex-only` | 仅生成 .tex，跳过编译 |
| `--mock` | 不调 API，验证流水线 |
| `--cache` | 启用分节缓存（改一节重跑不重调 API） |

> 完整参数见 [`reference.md`](reference.md)，配图系统见 [`figures.md`](figures.md)

##  架构

```
SKILL.md (入口) ──→ Step 0-10 工作流

scripts/
├── gen_sections.py      # 主入口 + 编排层
├── gen_multi.py          # 多科并行编排器
├── build_pdf.sh          # Linux/macOS 编译脚本
└── lib/
    ├── config.py         # 环境变量 + API 供应商
    ├── conventions.py    # 约定解析 + 章节展开
    ├── prompts.py        # System/User Prompt 构建
    ├── llm.py            # LLM 调用 + session + mock
    ├── cache.py          # 分节缓存
    ├── sanitize.py       # P0 清洗层
    ├── validate.py       # P1 微编译校验 + 再生成
    └── compile.py        # P2 整卷编译 + 修复/占位

conventions/              # 各科约定文件
templates/                # XeLaTeX 模板
```

### 鲁棒性层

```
P0  自动清洗
  ├─ 去代码围栏、规整 \boxedans、数学模式 CJK 包裹
  └─ 结构性隐患告警（$ / \[\ ] / 括号不配对）

P1  逐题微编译校验（默认开启）
  ├─ 分块批量编译（8 片段/批）→ 未过回退逐题
  ├─ 失败 → 回喂 .log 让 LLM 修复（最多 N 次）
  └─ 修复失败 → 剥图保文 → 仍失败 → 占位框

P2  整卷编译修复（--build 触发）
  ├─ 失败 → 解析 l.NNN 定位出错题号
  └─ 占位/剥图 → 重编 → 保证 PDF 必出
```

##  依赖

- **Python 3.10+** + `requests`
- **PDF 编译**（三选一）：
  - `xelatex`（TeX Live / MiKTeX，含 `ctex`）
  - `tectonic`（自动下载，无需安装）
  - 在线服务（备用）

##  许可

MIT License

---

 由 Claude Code + DeepSeek 驱动 | built with ❤️
