# LaTeX 语法规则 约定

`--subject latex`

## 给生成模型的符号约定块

<!-- SYMBOL_BLOCK_START -->
- 命令（宏）统一用 \texttt{\textbackslash commandname} 形式展示，参数写成 \texttt{\{arg\}} 或 \texttt{[opt]}。
- 代码示例放在 \texttt{verbatim} 或 \lstlisting 环境里，保证等宽字体显示。
- 环境名用 \texttt{环境名} 表示，如 \texttt{tabular}、\texttt{figure}、\texttt{equation}。
- 宏包名用 \textsf{宏包名} 表示，如 \textsf{amsmath}、\textsf{graphicx}。
- 键值对选项写成 \texttt{key=value} 形式。
- 示例代码与实际输出效果均需给出，帮助读者对照理解。
<!-- SYMBOL_BLOCK_END -->

## 给生成模型的提示补充块

<!-- PROMPT_EXTRA_START -->
- 本科目是 LaTeX 语法教学讲义，面向零基础入门读者，语言清晰易懂，循序渐进。
- 每个语法点必须给出完整可运行的最小示例代码（用 \texttt{verbatim} 或 lstlisting 环境展示），并说明代码的输出效果。
- 讲解时先给出"最简用法"，再介绍常用选项与进阶用法，避免一开始就堆砌所有参数。
- 对于容易出错的地方（如数学模式、特殊字符转义、浮动体定位），要在「注意」或「常见错误」小节特别标出。
- 所有代码示例必须是合法的 XeLaTeX 代码，不要用过时命令（如 \bf、\it 等旧式字体命令）。
- 不要作图；排版效果用文字描述。
- 讲义按"是什么 → 怎么用 → 示例 → 注意事项"的结构组织每个知识点。
<!-- PROMPT_EXTRA_END -->

## 章节清单（`--sections all` 的展开来源）

<!-- SYLLABUS_START -->
基本文档结构（文档类、导言区、正文区、编译流程）
常用宏包（amsmath、graphicx、geometry、hyperref 等核心宏包介绍）
文字排版（字体、字号、字形、段落格式、页面布局）
数学公式（行内公式、行间公式、常用数学符号与命令）
表格（tabular 环境、列格式、合并单元格、booktabs 三线表）
图片插入（includegraphics、figure 浮动体、图片路径与格式）
列表环境（itemize、enumerate、description 及嵌套列表）
交叉引用（label 与 ref、图表编号、超链接 hyperref）
参考文献（thebibliography 环境、BibTeX/BibLaTeX 使用方法）
<!-- SYLLABUS_END -->
