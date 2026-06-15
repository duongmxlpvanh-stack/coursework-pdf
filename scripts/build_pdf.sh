#!/usr/bin/env bash
# build_pdf.sh —— 两遍 XeLaTeX 编译
# 用法：bash scripts/build_pdf.sh <path/to/main.tex>
# hyperref 的题↔答交叉引用必须编译两遍，否则跳转链接全为 ??。

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法：bash build_pdf.sh <path/to/main.tex>" >&2
  exit 1
fi

TEX_PATH="$1"
if [ ! -f "$TEX_PATH" ]; then
  echo "[错误] 找不到文件：$TEX_PATH" >&2
  exit 1
fi

TEX_DIR="$(cd "$(dirname "$TEX_PATH")" && pwd)"
TEX_FILE="$(basename "$TEX_PATH")"
BASE="${TEX_FILE%.tex}"

cd "$TEX_DIR"

run_xelatex() {
  xelatex -interaction=nonstopmode -halt-on-error "$TEX_FILE" >/dev/null 2>&1 || {
    echo "[错误] XeLaTeX 编译失败，请查看 $TEX_DIR/$BASE.log 中的报错行。" >&2
    exit 1
  }
}

echo "[编译] 第一遍 …" >&2
run_xelatex
echo "[编译] 第二遍（解析交叉引用）…" >&2
run_xelatex

# 清理中间文件
rm -f "$BASE.aux" "$BASE.out" "$BASE.toc" "$BASE.log"

echo "[完成] PDF -> $TEX_DIR/$BASE.pdf" >&2
echo "$TEX_DIR/$BASE.pdf"
