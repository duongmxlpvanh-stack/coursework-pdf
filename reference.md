# coursework-pdf CLI 参数速查手册

> 本文件按需加载——仅在用户查询高级参数或遇到编译问题时读入上下文。

## gen_sections.py 全部参数

### 核心参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--subject` | str | 必填 | 科目，对应 `conventions/<subject>.md` |
| `--mode` | exam/study | exam | exam=出题（题目+答案分卷），study=知识点讲义 |
| `--sections` | str | 必填 | 逗号分隔章节；`all` 从本科目 SYLLABUS 块展开 |
| `--list-sections` | flag | false | 只打印该科章节清单后退出（配合 --subject） |
| `--out` | path | ./main.tex | 输出基名（exam 分卷自动派生 `_题目` / `_答案`） |
| `--tex-only` | flag | false | **新增**：仅生成 .tex，跳过编译校验和 PDF 编译 |

### 题量控制（exam 模式）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--count` | int | 3 | 每节题数（被 --total 覆盖时忽略） |
| `--total` | int | None | 总题数，自动均分到各节，覆盖 --count |
| `--difficulty` | str | 期末 | 难度：平时/期末/竞赛 |
| `--types` | str | None | 题型分配，如 `"选择:2,填空:2,计算:3"` |
| `--difficulty-mix` | str | None | 梯度难度，如 `"基础:1,期末:2,竞赛:1"` |

### 配图（--figures）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--figures` | flag | false | 启用 TikZ/PGFPlots 矢量配图（仅概率论/高数/物理） |
| `--figures-per-section` | int | 0 | 每节图数：0=按需，1=精简，2=适中，3=丰富 |

### study 模式

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--with-examples` | int | 0 | 每节讲义末尾附配套例题数 |

### 编译与校验

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--build` | flag | false | 生成后直接编译成 PDF（含整卷修复） |
| `--max-build-repairs` | int | 6 | 整卷编译最大占位修复次数 |
| `--no-validate` | flag | false | 关闭逐题微编译校验（需要 xelatex） |
| `--repair-attempts` | int | 2 | 单片段校验失败最大再生成次数 |
| `--tex-only` | flag | false | 仅生成 .tex，跳过校验和编译 |

### 超链接与分卷

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--hyperlinks` | flag | false | 启用题↔答超链接（仅 --combined 有效） |
| `--combined` | flag | false | exam 合订单 PDF（默认分卷：题目卷 + 答案卷） |

### 缓存（调试用）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--cache` | flag | false | 启用分节缓存 |
| `--refresh-cache` | flag | false | 强制重生成并写回缓存 |
| `--clear-cache` | flag | false | 清空 `.sectioncache/` 后退出 |

### 供应商切换

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--model` | str | from .env / deepseek/deepseek-v4-pro | 模型名 |
| `--base-url` | str | from .env / https://openrouter.ai/api/v1 | API 基址 |
| `--temperature` | float | 0.6 | 温度（kimi-k2 自动强制 1.0） |
| `--env` | path | None | 指定 .env 路径 |
| `--mock` | flag | false | 不调 API，用样例验证流水线 |

## gen_multi.py 编排器参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--config` | path | 必填 | tasks.json 路径 |
| `--workers` | int | 3 | 全局 ThreadPool 大小 |
| `--no-build` | flag | false | 只生成 .tex，跳过编译 |
| `--sequential-sections` | flag | false | 禁用单科 section 并发 |

## tasks.json 字段参考

```json
{
  "tasks": [{
    "subject": "probability",        // 必填
    "sections": "矩估计,极大似然估计",  // 必填，"all"=全部章节
    "out": "./output.tex",           // 必填
    "mode": "exam",                  // 可选，默认 exam
    "total": 15,                     // 可选，总题数
    "count": 3,                      // 可选，每节题数（被 total 覆盖）
    "difficulty": "期末",             // 可选
    "title": "练习标题",              // 可选
    "course": "课程名",              // 可选
    "combined": false,               // 可选，合订单文件
    "hyperlinks": false,             // 可选，超链接导航
    "figures": false,                // 可选，启用配图
    "figures_per_section": 0,        // 可选，每节配图数
    "types": null,                   // 可选，题型分配
    "difficulty_mix": null,          // 可选，梯度难度
    "validate": true,                // 可选，微编译校验
    "repair_attempts": 2,            // 可选，修复次数
    "cache": false,                  // 可选，分节缓存
    "refresh_cache": false,          // 可选，强制刷新缓存
    "model": null,                   // 可选，覆盖模型
    "base_url": null,                // 可选，覆盖 API 基址
    "temperature": 0.6               // 可选
  }]
}
```

## 编译错误处理参考

### P0 自动清洗（sanitize_fragment）
按顺序执行：去代码围栏 → 去 `\boxedans` 外多余 display → 规整 `\boxedans` 参数 → 数学模式内中文包 `\text{}` → 去 markdown → 转义裸 `%`

结构性隐患（`$`/`\[\]`/括号/`\left\right`/`\begin\end` 不配对）打印 `[告警]` 但不自动修复。

### P1 逐题微编译校验（默认开启）
1. 分块批量编译（每 8 片段一批，通过则全过）
2. 整块未过 → 逐题回退编译
3. 单题失败 → 提取 `.log` → 回喂 LLM 修复（最多 `--repair-attempts` 次）
4. 修复失败 → 剥离图再试 → 仍失败 → 占位框
5. stderr 打印 `[校验] 完成：N 个片段，修复 X，占位 Y`

### P2 整卷编译修复（--build 触发）
1. 两遍 xelatex 编译
2. 失败 → 解析 `.log` 的 `l.NNN` → 定位出错题号
3. 该题占位/剥图 → 重编（最多 `--max-build-repairs` 次）
4. 占位后 PDF 必出；stderr 打印 `[整卷修复] 第 N 题…已占位`

### 编译超时兜底
xelatex 调用墙钟超时默认 90s（环境变量 `COURSEWARE_COMPILE_TIMEOUT` 覆盖），防止 TikZ 挂死。
