# 高等数学（多元微积分、积分定理） 约定

`--subject calculus`

## 给生成模型的符号约定块

<!-- SYMBOL_BLOCK_START -->
- 向量用粗体 $\mathbf{r}, \mathbf{F}, \mathbf{n}$；向量场分量 $\mathbf{F}=P\mathbf{i}+Q\mathbf{j}+R\mathbf{k}=(P,Q,R)$。
- 偏导数 $\dfrac{\partial f}{\partial x}$ 或 $f_x$；梯度 $\nabla f=\operatorname{grad} f$；方向导数 $\dfrac{\partial f}{\partial \mathbf{l}}$。
- 散度 $\operatorname{div}\mathbf{F}=\nabla\cdot\mathbf{F}$；旋度 $\operatorname{rot}\mathbf{F}=\nabla\times\mathbf{F}$。
- 平面区域 $D$，其边界曲线 $\partial D$ 或 $L$，正向（逆时针）记为 $L^+$。
- 空间区域 $\Omega$，其边界曲面 $\partial\Omega$ 或 $\Sigma$，外侧记为 $\Sigma^+$，单位外法向量 $\mathbf{n}$。
- 第一类（对弧长/面积）：$\displaystyle\int_L f\,\mathrm{d}s$，$\displaystyle\iint_\Sigma f\,\mathrm{d}S$。
- 第二类（对坐标）：$\displaystyle\int_L P\,\mathrm{d}x+Q\,\mathrm{d}y$，$\displaystyle\iint_\Sigma P\,\mathrm{d}y\,\mathrm{d}z+Q\,\mathrm{d}z\,\mathrm{d}x+R\,\mathrm{d}x\,\mathrm{d}y$。
- 闭曲线/闭曲面积分用 $\oint$、$\oiint$。
- 微分一律用 $\mathrm{d}$（直立体），不用斜体 $d$。
<!-- SYMBOL_BLOCK_END -->

## 给生成模型的提示补充块

<!-- PROMPT_EXTRA_START -->
- 涉及格林公式、高斯公式、斯托克斯公式时，解答中先验证适用条件（区域是否单连通、曲面是否分片光滑、是否封闭、定向是否一致），再套用公式。
- 曲线、曲面积分题写清积分类型（第一类/第二类）与定向。
- 不要作图；曲线、曲面、区域用方程与文字描述其范围与边界。
- 题目可涉及参数化、换元、对称性化简等技巧，解答中点明所用技巧。
<!-- PROMPT_EXTRA_END -->

## 配图政策块（仅 `--figures` 启用时注入；测试版新增）

<!-- FIGURE_POLICY_START -->
- 启用配图后，上方补充要求中「不要作图」一条对本科目不再适用，可按需配图。
- 适合配图的场景：二重积分的平面积分区域 $D$（画出边界曲线与积分次序示意）、一元/二元函数图像、空间曲面或区域的二维示意、向量场方向示意、格林/高斯/斯托克斯公式中区域与定向的示意。
- 平面区域、函数曲线优先用 pgfplots 的 `axis`（标注坐标轴、积分上下限、交点）；定向箭头、法向量用 tikz 的 `arrows.meta`。
- 三维场景只画清晰的二维投影示意即可，不要追求真实三维渲染；复杂曲面用文字+方程描述为主、配图为辅。
<!-- FIGURE_POLICY_END -->

## 章节清单（`--sections all` 的展开来源）

下面标记块是本科目的权威章节清单，一行一节（小节级）。`--sections all`（或 `全部`）会**原样读取**它逐节出题，从机制上杜绝漏章。改动课程范围时只改这里，不要在别处手列。

> 注：当前清单覆盖本约定文件已声明的范围（多元微积分 + 积分定理 + 向量代数与空间解析几何）。若你的高数期末还含**无穷级数 / 微分方程 / 傅里叶级数**，在块内对应位置补行即可。

<!-- SYLLABUS_START -->
向量代数（向量的线性运算、数量积、向量积、混合积）
空间平面与直线（平面方程、直线方程、点线面相对位置）
曲面与空间曲线（旋转曲面、柱面、二次曲面、空间曲线及其投影）
多元函数的极限与连续
偏导数与全微分
多元复合函数与隐函数的求导
方向导数与梯度
多元函数的极值与条件极值（拉格朗日乘数法）
二重积分（直角坐标与极坐标）
三重积分（直角坐标、柱面坐标、球面坐标）
重积分的应用（曲面面积、质心、转动惯量）
第一类曲线积分（对弧长）
第二类曲线积分（对坐标）
格林公式及曲线积分与路径无关
第一类曲面积分（对面积）
第二类曲面积分（对坐标）
高斯公式与散度
斯托克斯公式与旋度
<!-- SYLLABUS_END -->
