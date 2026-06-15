# PowerShell 基础 约定

`--subject powershell`

## 给生成模型的符号约定块

<!-- SYMBOL_BLOCK_START -->
- 行内命令/Cmdlet 用 \texttt{Verb-Noun} 格式，如 \texttt{Get-ChildItem}、\texttt{Set-Location}。
- 参数用 \texttt{-参数名}，如 \texttt{-Path}、\texttt{-Recurse}；参数值与参数名之间用空格分隔。
- 变量用 \texttt{\$变量名}，如 \texttt{\$path}、\texttt{\$count}。
- 短代码片段（1-2 行）用 \verb|...| 或 \texttt{...} 行内排版。
- 多行代码块统一用 \begin{verbatim}...\end{verbatim}（verbatim 环境，无需额外包，原样输出，禁止在其中使用 LaTeX 命令）。
- 输出示例（命令执行结果）同样放在 \begin{verbatim}...\end{verbatim} 中，并在其前加一行 \textbf{输出示例：}。
- 重要术语/关键词首次出现时用 \textbf{...} 加粗（如 \textbf{管道}、\textbf{对象}）。
- 不使用数学环境（$...$ / \[...\]）——本科目无数学公式。
- 不要使用 \usepackage、\documentclass 等导言区命令，只输出正文片段。
<!-- SYMBOL_BLOCK_END -->

## 给生成模型的提示补充块

<!-- PROMPT_EXTRA_START -->
- 本科目是 PowerShell 编程入门，面向零基础大学生，语言风格简洁易懂。
- 每个知识点先给出简短定义/说明，再给出 1-2 个具体命令示例（含参数），最后说明常见用法场景。
- 代码示例必须是合法的 PowerShell 命令，可直接在终端粘贴运行；不要编造不存在的 Cmdlet。
- 代码块一律用 \begin{verbatim}...\end{verbatim}，不要用 markdown 代码围栏（``` ）。
- verbatim 环境内禁止出现任何 LaTeX 命令（\texttt、\$ 等），直接原样写 PowerShell 代码（包括 $variable），verbatim 会自动处理特殊字符。
- 正文段落（非 verbatim）中出现 $ 符号时，必须写成 \$（加反斜杠），否则 LaTeX 会将 $ 解释为数学模式的开始标志，导致编译错误。例如：正文中写 \texttt{\$name}，而不是 \texttt{$name}。
- 切勿在正文/\texttt 中直接写裸 $（未转义），这是最常见的编译错误来源。
- \pitfall{...} 的内容写 PowerShell 初学者常犯的错误或容易混淆的点（如变量不加 $、路径用斜杠还是反斜杠、单引号与双引号的区别等）。
- 本科目讲义不含数学公式，禁止使用 $...$ 数学环境。
- 配套例题的「题目」描述一个具体的操作任务（如「请用 PowerShell 命令列出 C:\Users 下所有 .txt 文件」），「解答」给出命令并逐行解释，最终答案用 \boxedans{\text{...命令...}} 框出（因无数学，用 \text{} 包裹命令文本）。
<!-- PROMPT_EXTRA_END -->

## 章节清单（`--sections all` 的展开来源）

<!-- SYLLABUS_START -->
PowerShell 简介与帮助系统（Get-Help、Get-Command、Get-Member）
文件系统导航（Set-Location、Get-Location、Get-ChildItem、Push/Pop-Location）
文件与目录操作（New-Item、Remove-Item、Copy-Item、Move-Item、Rename-Item）
文件内容读写（Get-Content、Set-Content、Add-Content、Out-File）
变量与数据类型（字符串、整数、布尔、数组、哈希表）
运算符（算术、比较、逻辑、赋值运算符）
字符串处理（格式化字符串、-replace、-split、-join）
管道与对象过滤（|、Where-Object、Select-Object、Sort-Object、ForEach-Object）
条件判断（if/elseif/else、switch）
循环（for、foreach、while、do-while、ForEach-Object）
函数定义与调用（function、参数、返回值、作用域）
错误处理（try/catch/finally、-ErrorAction、\$Error）
<!-- SYLLABUS_END -->
