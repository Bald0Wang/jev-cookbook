# 从查询到可运行学生：执行手册

这里给出当前代码的完整依赖顺序。研究结论分别看 [V2 结果](pipeline_v2_report_zh.md) 和 [V3 结果](navigation_v3_report_zh.md)；算法选择及未采用方案见 [实施计划](implementation_plan_zh.md)。已有实验目录是冻结产物，重新实验请换输出目录，不能覆盖旧结果。

## 1. 先定义题目，再找教师

训练样本是 `(state, question, candidate_set, target_distribution)`。问题是明确的输入；不能省去 question 后假设模型知道应该判断什么。例如：

```json
{
  "states": [{
    "id": "home_example",
    "state": "客厅温度29度，目标24度，窗户关闭，有人在家。可控制空调、窗户和灯。",
    "questions": {
      "action": {
        "type": "choice",
        "instructions": "请选择最直接降低室内温度的操作。",
        "criteria": {
          "cool": "开启空调制冷",
          "light": "打开照明",
          "wait": "维持当前状态"
        }
      },
      "occupied": {"type": "boolean", "instructions": "现在有人在家吗？"},
      "heat": {
        "type": "score",
        "instructions": "按当前温度与目标温度的差值分档。",
        "criteria": ["低于或等于目标", "超过目标但不超过3度", "超过目标3度以上"]
      }
    }
  }]
}
```

这是接口示例，不附造出的模型答案。三个问题不依赖彼此输出，因此可和其他状态的问题一起前向。如果下一题确实需要上一题结果，应由外部程序启动下一轮；并行不消除任务本身的依赖。

当前查询来自自写生成器，不是让 Jev 凭空生成输入分布：支持/退款规则、智能家居、候选目录查找、可解析概率事件、井字棋和网格导航。生成器先建立事实或环境，再写 question 和合法候选。规则真值、条件事件分布和专家动作策略是三种不同 target，分别标记。改写、坐标变换和同一地图的不同起点继承整个源组的 split。

## 2. 数据构建与两种监督来源

以下命令在项目根目录执行。生成器只需要 Python；付费标注另需锁定的 Node 依赖以及本机 `.env` 中的 `AI_GATEWAY_API_KEY`。

```bash
python3 scripts/build_toy_decisions.py --output-dir research/private_toy --seed 17
python3 scripts/build_workflow_decisions.py --output-dir research/private_workflows_v2 --seed 20260917
python3 scripts/build_game_decisions.py --output-dir research/private_games_v2 --seed 17
python3 - <<'PY'
from pathlib import Path
for name in ('private_toy', 'private_workflows_v2'):
    d = Path('research') / name
    parts = [d / f'{s}.jsonl' for s in ('train', 'dev', 'calibration', 'test', 'ood')]
    (d / 'all.jsonl').write_text(''.join(p.read_text() for p in parts))
PY
```

**无需 API 的完整 V2 程序监督路径：** 为汇总器建立一个明确为空的教师文件，保留全部程序真值。此路径不需要 Jev 标签。

```bash
python3 -c 'from pathlib import Path; Path("research/empty_teacher.jsonl").write_text("")'
python3 scripts/assemble_pipeline_dataset.py \
  --workflows research/private_workflows_v2/all.jsonl \
  --games-raw research/private_games_v2/all.jsonl \
  --games-labels research/empty_teacher.jsonl \
  --toy research/private_toy/all.jsonl \
  --output-dir research/private_pipeline_gold_rebuild --freeze
python3 scripts/train_pipeline_decisions.py \
  --input research/private_pipeline_gold_rebuild/merged.jsonl --validate-only
```

**Jev 教师路径：** 使用生成器的相同输入，额外采集完整候选概率。费用参数是每次运行分配上限；总预算还须核对网关余额与已有支出。失败请求不自动重试，日志保留，失败不能用学生预测补标签。

```bash
npm ci
node --env-file=.env scripts/label_decision_dataset.mjs \
  --input-dir research/private_toy --budget-usd 0.25 --concurrency 3 --max-failures 20
node --env-file=.env scripts/label_decision_dataset.mjs \
  --input-dir research/private_workflows_v2 --budget-usd 3 --concurrency 8 --max-failures 20
node --env-file=.env scripts/label_decision_dataset.mjs \
  --input-dir research/private_games_v2 --budget-usd 3 --concurrency 3 --max-failures 20
python3 scripts/assemble_pipeline_dataset.py \
  --workflows research/private_workflows_v2/labeled.jsonl \
  --games-raw research/private_games_v2/all.jsonl \
  --games-labels research/private_games_v2/labeled.jsonl \
  --toy research/private_toy/labeled.jsonl \
  --output-dir research/private_pipeline_v2 --freeze
```

原始 V2 使用早期 toy 标注器得到其冻结标签；上面统一标注器用于重新采集，不能保证服务响应与历史完全相同。若 workflows/toy 有未完成标签，先处理并审计完整覆盖再冻结；汇总器的固定 2,312 条检查会阻止静默缺数。游戏缺失标签由 raw+labels 合并保留原记录。

Jev 数值记录为舍入概率，不叫 logits。当前训练仅使用完整、有限、非负、候选完全匹配且和为 1 的教师向量；不合格目标隔离，原记录仍可用于 gold 分支。普通 LLM 可以换作标签来源，但其 JSON 自报百分比不能伪装为原生概率。

## 3. 模型与确切更新规则

直接初始化 `Qwen/Qwen3-0.6B`，没有先训练 yes/no reranker。每个候选路径包含 state、question、当前候选语义和读出位置。一次 backbone 前向编码批内全部路径；Choice 使用共享标量头与无位置编码的集合注意力头输出该题 K 个 logits，再做 masked softmax。Boolean 使用单路径 sigmoid；Score 绕过集合注意力，输出完整等级分布及其期望。

对完整一题：

```text
p = softmax(z)
L(q, p) = -sum_i q_i log p_i
dL/dz_i = p_i - q_i
```

`q` 可以是 Jev 分布、解析条件概率或程序专家策略。每题等权；完整候选集合一起计算分母，不能把 20 个候选拆成 20 个独立二分类 loss。训练 microbatch 只拆完整问题，梯度累积后再更新。推理没有输出 token 解码；当前 flat 路径重复计算前缀，尚未实现生产级共享前缀内核。

安装本次记录的 [依赖](../requirements-toy.txt)，在 CUDA 机器运行：

```bash
python scripts/train_pipeline_decisions.py \
  --input research/private_pipeline_v2/merged.jsonl \
  --output-dir runs/v2_teacher_seed17 \
  --model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --objective teacher --seed 17 --head-steps 12 --steps 600 \
  --batch-questions 12 --microbatch-questions 4 --max-microbatch-tokens 6000 \
  --max-length 512 --eval-every 50 --precision bf16 --disable-native-triton
```

纯程序监督将 input 改为上述 gold_rebuild 包、objective 改为 `gold_distribution`、output-dir 改为新目录。V2 实际两目标各跑 seed 17/18/19；0.6B 在一张 80GB 卡上全参训练，8 卡用于独立对照，未把一个小模型无必要地切到 8 卡。`--disable-native-triton` 是本次宿主环境的兼容回退，不是所有环境必需参数。

只在 dev 选择 checkpoint，calibration 不参与参数训练，test/OOD 不选择超参。实际 `config.json`、权重 SHA、数据 SHA、训练日志和逐题预测共同定义一个实验。

## 4. V3：表示与覆盖的受控导航扩展

```bash
python3 scripts/build_navigation_v3.py \
  --v2-input research/private_games_v2/all.jsonl \
  --output-dir research/private_navigation_v3 --seed 20260918
node --env-file=.env scripts/label_decision_dataset.mjs \
  --input-dir research/private_navigation_v3 --budget-usd 3 \
  --max-requests 3100 --concurrency 8 --max-failures 20
python3 scripts/assemble_navigation_v3_views.py
```

V3 排除全部 V2 地图后生成 500 张新地图、3,000 状态、9,000 题；训练为相同 300 张地图，每图 8 个曝光槽。四组比较 ASCII/坐标 × 单起点/多起点；另加 coords_multi 的 Jev 监督。单起点原始位置 300 个、多起点 1,874 个；D4 变换不冒充新的独立地图。每组加入相同 984 条旧 nongrid train replay。教师标签失效仅影响 teacher 分支覆盖。

以下是预先指定主组的实际配置；其余四组只按冻结协议切换 input/目标/输出名：

```bash
python scripts/train_pipeline_decisions.py \
  --input research/private_navigation_v3/views/coords_multi.jsonl \
  --init-checkpoint runs/v2_teacher_seed17 \
  --output-dir runs/v3_gold_coords_multi_seed17 \
  --objective gold_distribution --seed 17 --head-steps 0 --steps 1200 \
  --batch-questions 12 --microbatch-questions 4 --max-microbatch-tokens 6000 \
  --max-length 512 --eval-every 50 --precision bf16 --disable-native-triton
```

V3 实际五组都从同一个 V2 teacher checkpoint 继续训练，优化器重新初始化。因此这里的 gold 指 V3 更新目标，**不表示权重谱系从未用过教师**。纯开源、零 API 的新实验需要同时使用无教师的组装来源和 gold checkpoint；不能只改初始化路径：

```bash
python3 scripts/assemble_navigation_v3_views.py \
  --canonical research/private_navigation_v3/all.jsonl \
  --labels research/private_navigation_v3/all.jsonl \
  --replay research/private_pipeline_gold_rebuild/merged.jsonl \
  --output-dir research/private_navigation_v3/gold_rebuild_views
```

这里的 `--labels` 读取无教师字段的同一份程序数据，不生成伪教师概率。训练 input 改用新 view、init 改用对应 V2 gold checkpoint，output-dir 也换名；这属于不同实验，需要另报结果。

## 5. Benchmark 与运行中的游戏

离线评测分别回答三件事：教师 KL/TV 测“像不像 Jev”；独立真值上的 NLL/Brier/ECE 测正确性和概率可靠性；已知条件分布上的 KL/TV 测是否恢复概率机制。专家动作分布只是策略约定，不能用其 ECE 冒充游戏获胜率校准。

```bash
python scripts/evaluate_pipeline_decisions.py \
  --input runs/v3_gold_coords_multi_seed17/predictions_test.jsonl \
  --output runs/v3_gold_coords_multi_seed17/test_metrics.json
python scripts/evaluate_navigation_v3.py \
  --data-dir research/private_navigation_v3 \
  --checkpoint-dir runs/v3_gold_coords_multi_seed17 \
  --policy greedy --representation coords --precision bf16 --disable-native-triton \
  --name v3_gold_coords_multi_seed17_greedy \
  --output research/navigation_v3_v3_gold_coords_multi_seed17_greedy.json
```

再用 `--policy sample` 运行原始概率的 T=1 采样并保存不同文件；`--policy random`、`oracle` 不需要 checkpoint。固定 20 张 test 和 20 张 OOD 地图、每局独立 RNG、步数上限 `2×size²`；每个时间步将仍在运行的不同状态汇成一次模型前向。记录到达率、失败、路径效率、重访、原始概率、实际抽中动作及 forced moves。

运行时只提供坐标、墙、目标、合法转移等原始环境信息。BFS/minimax 用于数据标签、单列 oracle 和离线评分；不能把答案特征或动作纠错混进学生输入/控制器。游戏受 [官方文字状态 Doom/Wikiracing](https://typesafe.ai/blog/introducing-system-one-models-and-jev) 启发，当前实现是独立网格与井字棋。

```bash
python scripts/serve_decisions.py \
  --checkpoint-dir runs/v3_gold_coords_multi_seed17 \
  --web-root web --port 8765 --disable-native-triton
```

此服务加载一次本地学生，可多次调用，且不调用教师。静态回放另用 `npm run demo:replay`。完整回放、实时接口与运行成本必须分开显示，不能把保存的轨迹当作现场模型输出。

把已完成的对局写入回放页，例如以下两个真实结果文件；若缺失或不完整，组装器会报错，不生成替代轨迹：

```bash
python3 scripts/build_demo_artifact.py \
  --models research/navigation_v3_v3_gold_coords_multi_seed17_greedy.json \
           research/navigation_v3_v3_gold_coords_multi_seed17_sample.json \
  --output web/demo_results.json
```

交付版本另外收录全部对照和 V2 失败，具体完整清单以包内数据为准。`scripts/summarize_pipeline_v2.py` 与 `scripts/summarize_navigation_v3.py` 对应两轮固定实验汇总；它们读取既定 run 的轻量产物及全部对照，不用于把任意部分重跑自动宣称为完整实验。

## 6. RLCD 与交付范围

[官方全称](https://docs.typesafe.ai/introduction/machine-learning-primer) 是 Reinforcement Learning for Calibrated Decisions。本轮一手核查没有取得其 reward、网络或训练数据配方。现在实现的是可验证的分布监督和程序监督；没有把普通 CE 改名为 RLCD。需要研究 RL 时，应在相同底座/数据/计算预算下比较 proper log loss、精确 Brier 和明确推导的 policy-gradient 估计，参见 [数学分析](rlcd_theory_zh.md)。

源码、生成器、训练/推理/评估脚本、真实网页回放可以独立审阅。已有权重在用户服务器 `capyubara-0:/home/rwang/openjev_codex_20260917/runs/`；NanoJev 的 Git 仓库不包含这些权重或私有教师训练标签。可发布内容及包内复现边界见 [交付范围](release_scope_zh.md)。

## 7. NanoJev 三方演示

新三方对照固定使用 V3 中使用 Jev 分布监督训练的学生、真实 Jev API 与原始 Qwen3-0.6B，完整协议与真实轨迹见 [比较协议](nanojev_comparison_protocol_zh.md)。与早期默认程序监督服务不同，README 视频使用 `v3_teacher_coords_multi_seed17`，没有更改 V3 主实验选择。原始 Qwen 的离线权重准备与复跑说明见 [基线文档](navigation_v3_native_qwen_zh.md)。使用 Node.js ≥22 执行锁定 AI SDK 7 依赖；无需 API/GPU 的视频和交互回放已随仓库提供。
