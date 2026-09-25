# 原始 Qwen3-0.6B 原生词表强基线

基线使用固定 revision `c1899de289a04d12100db370d81485cdf75e47ca` 的原始 Qwen3-0.6B 及其原生 LM 输出头。它已有上游训练，但未做本项目微调；没有随机新决策头。

每个状态的输入包含完整 coords 地图、action 问题及全部合法候选。候选按 action ID 字典序映射 A–D；实际 tokenizer 将四个字母映射为单 token 32–35。沿用官方 chat template 并设置 `enable_thinking=False`，在最后一个提示位置用原生 LM 词表头读取 next-token logits。没有调用 generate，没有生成推理或任何输出 token。

各 active states 合在一次前向中；只对当前提供的候选字母归一化。完整轨迹同时保存原词表中这些字母的概率质量，因此条件分布不应解释成完整词表输出概率或任务成功概率。此基线每state只计算action题，训练后的决策模型还输出Boolean/Score辅助题；两者输入组织与输出头不同。

| 控制器 | test 成功 | OOD 成功 | batch 前向数 | 推理秒 |
|---|---:|---:|---:|---:|
| greedy | 6/20 | 1/20 | 72 | 8.344 |
| sample | 7/20 | 3/20 | 72 | 7.154 |

总运行（含模型加载与审计哈希）20.12秒，最大allocated显存3.029GB。40个初局、seed、horizon、合法候选与V3完全一致；greedy/sample保留全部成功和失败，没有oracle纠错。

这是固定的一种提示与候选别名方案，没有根据测试结果搜索提示。A–D别名及条件归一化会影响表现，不能据此断言未微调Qwen的所有使用方式都具有同等水平。逐步状态变换、原生logit条件softmax、候选映射和采样RNG均已复核。

文件：`navigation_v3_native_qwen_greedy.json`、`navigation_v3_native_qwen_sample.json`、`navigation_v3_native_qwen_summary.json`、`navigation_v3_native_qwen_preflight.json`、`navigation_v3_native_qwen_audit.json`。所有环境均为自写合成数据，无API教师输出或凭证。

## 新用户重新运行

公开仓库提供代码与记录，不附原始 Qwen 缓存、项目学生权重或研究目录中的私有文件。此入口也刻意不自动联网下载模型。需要先在兼容的 Python/CUDA 环境安装 [运行依赖](../requirements-toy.txt)，并显式缓存指定版本；实际完整基线使用单张 A100、BF16。下面均从仓库根目录运行。

先用自写生成器重建相同数据分区，不需要 Jev API 或教师标签。第二步必须使用第一步完整 V2 游戏地图列表，以保持 V3 排除规则及固定 40 个评估初局一致：

```bash
python3 scripts/build_game_decisions.py \
  --output-dir data/native_rebuild_v2_games --seed 17
python3 scripts/build_navigation_v3.py \
  --v2-input data/native_rebuild_v2_games/all.jsonl \
  --output-dir data/native_rebuild_v3 --seed 20260918
```

接下来显式下载公开底座的固定 revision。仅这一步访问模型仓库；后续基线入口使用 `local_files_only=True`，缺少完整缓存时会报错，而不会选择其他版本：

```bash
python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3-0.6B",
    revision="c1899de289a04d12100db370d81485cdf75e47ca",
)
PY
```

先执行不加载 GPU 模型的分词/schema 预检，再运行两个固定控制器。显式传 `--data-dir`，不依赖脚本默认的研究私有路径；输出到新目录，不覆盖仓库内已有证据：

```bash
python scripts/evaluate_native_qwen_navigation.py \
  --data-dir data/native_rebuild_v3 \
  --output-dir artifacts/native_qwen_rebuild \
  --preflight-only

CUDA_VISIBLE_DEVICES=0 python scripts/evaluate_native_qwen_navigation.py \
  --data-dir data/native_rebuild_v3 \
  --output-dir artifacts/native_qwen_rebuild \
  --precision bf16
```

输出目录允许保留刚生成的 preflight 文件，但若已有完整 greedy/sample 轨迹，程序拒绝覆盖；再次运行应换一个新输出目录。`--disable-native-triton` 仅在原实验所遇的 PyTorch 原生 Triton 宿主兼容问题出现时显式追加，不是通用安装步骤。FP32 可作为数值参照，但本报告中的成绩来自已记录的 BF16 配置；不同硬件、版本及精度不保证逐位相同。
