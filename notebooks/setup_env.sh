#!/usr/bin/env bash
# 一键创建《TypeSafe 架构模式实验》本地运行环境（Python >= 3.10 + 全部依赖）
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv

# 官方 SDK 要求 Python >= 3.10；macOS 系统自带 python3 是 3.9 装不上。
# 优先用 uv（能自动下载所需 Python 版本，brew install uv）；
# 否则寻找本机已有的 3.10+ 解释器。
if command -v uv >/dev/null 2>&1; then
  echo "▸ 用 uv 创建虚拟环境 ($VENV)…"
  uv venv "$VENV" --python 3.12
  uv pip install --python "$VENV/bin/python" -r requirements.txt
  uv pip install --python "$VENV/bin/python" pip   # uv venv 默认不带 pip，而笔记本里的 %pip 需要它
else
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
  done
  if [ -z "$PY" ]; then
    echo "✗ 未找到 Python >= 3.10。请先安装 uv：  brew install uv   然后重跑本脚本。" >&2
    exit 1
  fi
  echo "▸ 用 $PY 创建虚拟环境 ($VENV)…"
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -q -U pip
  "$VENV/bin/pip" install -q -r requirements.txt
fi

echo
PYVER=$("$VENV/bin/python" -c 'import sys; print(sys.version.split()[0])')
echo "✅ 环境就绪：notebooks/${VENV}（Python ${PYVER}）"
echo
echo "运行笔记本："
echo "  export TYPESAFE_API_KEY=你的key"
echo "  ${VENV}/bin/jupyter lab patterns_experiments.ipynb"
