#!/usr/bin/env bash
# 一键跑 jevbench_intro.ipynb：先 load .env（如果存在），再 nbconvert --execute。
#
# 用法：
#   ./scripts/run_notebook.sh             # 用 .env 里的 key 真跑（无 key 时全 skip，零成本）
#   ./scripts/run_notebook.sh --mock      # 强制走 mock（不管 .env），零成本验证流程
#   ./scripts/run_notebook.sh --help      # 看帮助
#
# 跑完后：
#   - notebooks/jevbench_intro_executed.ipynb  （含所有 cell 输出）
#   - runs/notebook-demo/real/<provider>/summary.json
#   - runs/notebook-demo/multi/charts/14_main_score.png
#   - runs/notebook-demo/multi/charts/14_4dim_compare.png
#
# 安全：
#   - .env 已被 .gitignore 排除，不会 commit
#   - raw/ 目录（每家模型请求体）已 .gitignore 排除
#   - 但 Authorization header 仍会出现在 raw/ 里，需要 mavis-trash 时单独处理

set -e

NOTEBOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NOTEBOOK="$NOTEBOOK_DIR/notebooks/jevbench_intro.ipynb"
OUTPUT="$NOTEBOOK_DIR/notebooks/jevbench_intro_executed.ipynb"
TIMEOUT=600

usage() {
    head -16 "$0" | tail -15
    exit 0
}

# Parse args
MOCK_ONLY=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock) MOCK_ONLY=1; shift ;;
        --help|-h) usage ;;
        *) echo "unknown arg: $1"; usage ;;
    esac
done

cd "$NOTEBOOK_DIR"

# Load .env if exists; never fail if missing
if [ -f ".env" ]; then
    echo "=== loading .env ==="
    # 只 export "KEY=VALUE" 形式的行，跳过注释
    set -a
    while IFS='=' read -r key val; do
        # 跳过注释/空行
        case "$key" in ''|\#*) continue ;; esac
        # 去掉 val 前后空白
        val="${val#"${val%%[![:space:]]*}"}"
        val="${val%"${val##*[![:space:]]}"}"
        # 把真实 key 写入 environment；不 echo
        export "$key=$val"
    done < .env
    set +a
    echo "    keys loaded (not echoed):"
    env | grep -E "^(TYPESAFE|DEEPSEEK|DASHSCOPE|ZHIPU|MOONSHOT|ARK|STEPFUN|XIAOMI)_API_KEY" | sed 's/=.*/=***/' | sed 's/^/      /'
else
    echo "=== no .env file, all providers will skip (zero-cost mode) ==="
fi

if [ "$MOCK_ONLY" = "1" ]; then
    echo
    echo "=== --mock: unsetting all *_API_KEY to force skip ==="
    unset TYPESAFE_API_KEY DEEPSEEK_API_KEY DASHSCOPE_API_KEY ZHIPU_API_KEY
    unset MOONSHOT_API_KEY ARK_API_KEY STEPFUN_API_KEY XIAOMI_API_KEY
fi

echo
echo "=== running notebook ==="
echo "    notebook: $NOTEBOOK"
echo "    output:   $OUTPUT"
echo "    timeout:  ${TIMEOUT}s"
echo

# 真正执行
.venv/bin/jupyter nbconvert --to notebook --execute "$NOTEBOOK" \
    --output "$OUTPUT" \
    --ExecutePreprocessor.timeout="$TIMEOUT" \
    2>&1 | tail -8

echo
echo "=== done ==="
echo
echo "产物："
echo "  - $OUTPUT"
echo "  - runs/notebook-demo/real/<provider>/summary.json"
echo "  - runs/notebook-demo/multi/charts/14_main_score.png"
echo "  - runs/notebook-demo/multi/charts/14_4dim_compare.png"
echo
echo "看 main-score 图："
echo "  open runs/notebook-demo/multi/charts/14_main_score.png"
echo
echo "看 4 维横评图："
echo "  open runs/notebook-demo/multi/charts/14_4dim_compare.png"