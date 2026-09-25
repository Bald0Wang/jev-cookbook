#!/usr/bin/env python3
"""生成 DSH × Jev 学习案例；运行时不把凭据写入 Notebook。"""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / 'main/generators/templates/tutorial.ipynb'
nb = nbf.read(TEMPLATE, as_version=4) if TEMPLATE.exists() else nbf.v4.new_notebook()
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip()))
def code(s): cells.append(nbf.v4.new_code_cell(s.strip()))

md('''# DSH × Jev：从结构化判断到决策协作

这是一个有真实成功与失败记录的工程学习案例：DeepSeek Harness（DSH）负责聊天与工具执行，Jev 负责狭窄判断，插件中的代码组合答案，主模型再决定如何推进任务。

**适合读者**：会运行终端命令、了解 JSON 和基本 Python，希望学习 Agent 工具集成的人。
**学完可以做到**：解释三种原语；追踪判断到建议的代码路径；区分接口成功、行为成功与业务准确率；复现安装和澄清实验。

| 步骤 | 要回答的问题 |
|---|---|
| 0. 准备 | 用实时请求，还是重读已保存证据？ |
| 1. 三种原语 | 一次请求怎样返回三种形状？ |
| 2. 分流 | 概率怎样变成 proceed / clarify / review？ |
| 3. 完整任务 | Jev 返回以后，主模型真的照做了吗？ |
| 4. 失败复盘 | 旧版为什么跳过了澄清？ |
| 5. 练习与验收 | 下一位读者怎样证明自己复现成功？ |

工程入口：[安装与运行](../apps/dsh-jev-decision/README.md) · [案例讲解](../apps/dsh-jev-decision/docs/LEARNING-CASE.md) · [证据说明](../apps/dsh-jev-decision/validation/README.md)
''')
md('''## 0. 准备：先选证据来源

需要 Python ≥3.10、Node.js 24。在仓库根目录先执行：

```bash
cd apps/dsh-jev-decision
npm ci --ignore-scripts
npm run build
```

本 Notebook 默认 `DSH_JEV_RUN_MODE=live`，通过**同一插件的 DSH ToolRuntime**发起至多 4 次 TypeSafe 请求，不启动聊天主模型，不改动练习源码。凭据只读环境变量 `TYPESAFE_API_KEY`；缺失或失败立即停止，不自动回退。

无密钥阅读可以在启动 Jupyter 前明确设置 `DSH_JEV_RUN_MODE=recorded`。此模式重读 2026-09-24 的真实响应，**没有发出新请求，也不是人工 mock**。第 3、4 节始终分析归档会话；重新跑完整 DSH 会话需要另一套 `DEEPSEEK_API_KEY`，见工程说明。API 调用会消耗相应账户额度。
''')
code('''import os, json, shutil, subprocess, tempfile
from pathlib import Path

CANDIDATES = [Path.cwd(), *Path.cwd().parents]
ROOT = next(p for p in CANDIDATES if (p / "apps/dsh-jev-decision/package.json").exists())
APP = ROOT / "apps/dsh-jev-decision"
EVIDENCE = APP / "validation"
MODE = os.getenv("DSH_JEV_RUN_MODE", "live")
assert MODE in {"live", "recorded"}, "请选择 live 或 recorded"
NODE = shutil.which("node")
assert NODE, "请先安装 Node.js 24 并加入 PATH"
assert (APP / "dist/router.js").exists(), "先在工程目录执行 npm ci 与 npm run build"
if MODE == "live":
    assert os.getenv("TYPESAFE_API_KEY"), "live 模式需要 TYPESAFE_API_KEY 环境变量"
print("本次原语与分流来源：", "实时 API" if MODE == "live" else "已保存的真实记录（未发新请求）")''')
md('''下面的助手只负责选择数据来源。实时模式复用工程的请求、校验、错误处理与报告脚本；临时报告只在本机存在。Notebook 不会读取 `.env`，也不会把密钥作为命令行参数。''')
code('''def load_record(name):
    return json.loads((EVIDENCE / name).read_text())

def run_suite(routes=False):
    name = "live-routes-20260924-01.json" if routes else "live-primitives-20260924-02.json"
    if MODE == "recorded":
        return load_record(name)
    with tempfile.TemporaryDirectory(prefix="dsh-jev-notebook-") as tmp:
        report = Path(tmp) / "result.json"
        args = [NODE, "scripts/check-live.mjs", "--output", str(report)]
        if routes:
            args.append("--routes")
        proc = subprocess.run(args, cwd=APP, capture_output=True, text=True, timeout=100)
        result = json.loads(report.read_text()) if report.exists() else {"status": "error"}
        if proc.returncode or result["status"] != "ok":
            raise RuntimeError("本次实时检查失败，已停止；未自动重试或替换为归档结果。")
        return result''')
md('''## 1. 📖 理论：让 Jev 回答小问题

System One 适合在已给上下文上做“一秒钟能判断”的小题。`state` 放事实，`questions` 放判断标准；问题共享同一 state、独立评估，不能让第二题依赖同一次请求中尚未得到的第一题答案。ID 用于对应结果，不发送给模型，所以判断条件应写在 `instructions` 中。

- **Choice**：在无序选项中选择；返回 choice、probabilities、confidence。
- **Score**：沿有序等级给概率加权期望，可以是小数；返回 score、legend、probabilities、confidence。
- **Noul**：给“是”的概率，0.5 表示不确定，不代表中等复杂度，也没有单独 confidence。

来源：[System One 原文](https://docs.typesafe.ai/concepts/system-one) / [中文](../content/concepts/system-one.md)、[State 原文](https://docs.typesafe.ai/concepts/state) / [中文](../content/concepts/state.md)、[原语原文](https://docs.typesafe.ai/primitives) / [中文](../content/primitives.md)。
''')
md('''### 1.1 看清发出了什么

任务是把会议纪要整理成行动清单。纪要中的人物任务是材料；插件不会替他们执行。先看工程里的实际请求，再单独运行它。''')
code('''REQUEST = json.loads((APP / "examples/three-primitives.json").read_text())
print(json.dumps(REQUEST, ensure_ascii=False, indent=2))''')
code('''PRIMITIVES = run_suite()
RESULT = PRIMITIVES["results"][0]["result"]
print("采集时间：", PRIMITIVES["created_at"])
print("模型：", RESULT["model"], "耗时毫秒：", RESULT["duration_ms"])
print(json.dumps(RESULT["answers"], ensure_ascii=False, indent=2))''')
md('''### 1.2 观察 Score 和 Noul

归档响应把任务归为 writing；`is_actionable.noul=0.91`，复杂度 Score 为 0.24。实时重跑可能变化，应以本次输出为准。
Score 是等级索引的加权期望。下面自行计算，允许服务端四舍五入误差。Noul 不增加虚构的 confidence 字段。''')
code('''ANSWERS = RESULT["answers"]
SCORE = ANSWERS["complexity"]
EXPECTED = sum(int(level) * probability for level, probability in SCORE["probabilities"].items())
print("按分布计算：", round(EXPECTED, 4), "服务端 Score：", SCORE["score"])
assert abs(EXPECTED - SCORE["score"]) < 0.03
assert "confidence" not in ANSWERS["is_actionable"]
print("Noul 只有概率；检查通过。")''')
md('''## 2. 📖 理论：代码组合概率，模式引导行动

`jev_route_task` 提出三道题：类别 Choice、必要澄清 Noul、复杂度 Score。插件在本地按顺序应用规则：

| 优先级 | 条件 | 建议 |
|---|---|---|
| 1 | 澄清 Noul ≥0.8 | clarify，提出具体问题并等待回答 |
| 2 | Noul >0.2，或类别 confidence <0.8，或类别为 other | review，先检查已有材料 |
| 3 | 其余 | proceed，推进工作 |

Score 仅用于展示规划信号。阈值是教学起点，未经过业务标注集校准。

**confidence 不是最大选项概率**：它概括分布形状。Choice 低 confidence 往往表示类别难分；Score 低 confidence 可能表示各等级分散或两端都有支持，应结合分布阅读。校准在成组预测上衡量，不能保证某一次正确。

来源：[置信度原文](https://docs.typesafe.ai/confidence) / [中文](../content/confidence.md)。
''')
md('''### 2.1 三个固定样本

这一步最多调用 3 次 Jev。教学预期不发送给模型，不会为凑齐分支而重试。输出不同也是应记录的观察。''')
code('''ROUTES = run_suite(routes=True)
print("采集时间：", ROUTES["created_at"])
for row in ROUTES["results"]:
    result = row["result"]
    category = result["answers"]["category"]
    noul = result["answers"]["needs_clarification"]["noul"]
    print(row["id"], "→", result["recommendation"]["action"],
          "类别=", category["choice"], "confidence=", category["confidence"],
          "Noul=", noul, "预期一致=", row["matches_intended_action"])''')
md('''归档样本依次触发 proceed / clarify / review，仅证明这些输入和接口路径曾经跑通。3 条样本不足以报告“准确率 100%”。下一步直接调用工程里的 `recommend()`，核对建议来自确定性代码，不在 Notebook 另写一个容易漂移的路由器。''')
code('''def recommend_from_code(answers):
    js = """import {recommend} from './dist/router.js';
let raw = ''; for await (const chunk of process.stdin) raw += chunk;
console.log(JSON.stringify(recommend({answers: JSON.parse(raw)})));"""
    proc = subprocess.run([NODE, "--input-type=module", "-e", js], cwd=APP,
                          input=json.dumps(answers), capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)

for row in ROUTES["results"]:
    computed = recommend_from_code(row["result"]["answers"])
    assert computed == row["result"]["recommendation"]
print("本次全部建议均与工程 recommend() 一致。")''')
md('''## 3. 从判断走到真实任务

三种架构的控制权不同：传统软件由确定性规则分支；LLM Agent 自行选择工具；AI 驱动软件把原子判断交给模型、由代码控制工作流。本案例是混合形式：**分流建议由代码确定，后续执行仍由 DSH 主模型选择**。“Jev 决策协作”提示词不是强制权限网关，proceed 不授予工具权限。

来源：[如何构建原文](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) / [中文](../content/concepts/how-to-build-with-system-one.md)。

下面分析 0.1.2 的真实 DSH 核心会话归档。脚本显式挂载与界面相同的预设；不是完整网页操作记录。澄清答案由测试脚本在实际提问后提供，不能写成“现场用户回答”。
''')
md('''### 3.1 先核对工具顺序

明确任务的首个 Jev 结果实际是 review，随后模型阅读文件并修复。它与第 2 节固定样本的 context 不同，不能把归档改写为 proceed。下面同时显示工具名和 Jev 建议。''')
code('''CLEAR = load_record("chat-clear-20260924-02.json")
CLARIFY = load_record("chat-clarify-20260924-03.json")

def show_trace(record):
    for event in record["trace"]:
        if event["type"] == "tool/call":
            print(event["seq"], "调用", event["name"])
        elif event["type"] == "tool/result" and event["name"] == "jev_route_task":
            result = event["result"]
            print(event["seq"], "Jev →", result.get("recommendation", {}).get("action", result["status"]))

show_trace(CLEAR)''')
md('''### 3.2 澄清必须发生在修改之前

旧版失败的关键不是“Jev 没识别到歧义”，而是主模型得到 clarify 后继续猜了目标。新版要求首次单独分流；clarify 后先提问并等待答案；不能把示例 README 中的可能任务当作用户的真实目标。''')
code('''show_trace(CLARIFY)
FIRST_CALL = next(e for e in CLARIFY["trace"] if e["type"] == "tool/call")
assert FIRST_CALL["name"] == "jev_route_task"
assert CLARIFY["scripted_answers"]
assert all(not item["source_changed_before_answer"] for item in CLARIFY["scripted_answers"])
print("归档确认：出现实际提问，脚本回答前 date.mjs 未改变。")
print("预设回答：", CLARIFY["scripted_answers"][0]["answer"])''')
md('''这条断言只覆盖脚本当时观测的 `date.mjs`，不是对所有副作用的通用证明。还要检查最终产物与测试：归档保存了两个完成后的练习目录，下格只在本机重跑其测试，不调用模型，不重新执行聊天。明确任务样本还把纯空白字符串视为空输入，这个行为扩展值得业务审阅。''')
code('''for case in ["clear", "clarify"]:
    folder = EVIDENCE / "workspaces" / case
    proc = subprocess.run([NODE, "--test", "--test-reporter=tap", "date.test.mjs"], cwd=folder,
                          capture_output=True, text=True, check=True)
    summary = [line for line in proc.stdout.splitlines() if line.startswith(("# tests", "# pass", "# fail"))]
    print(case, "；".join(summary))''')
md('''## 4. 失败也是学习材料

0.1.1 曾返回 clarify，但主模型没有实际提问就读文件、改源码；0.1.2 增加了执行顺序与等待规则。新样本成功只能说明这次改善，不能证明提示词从此保证每次遵守。

另一次 0.1.2 材料任务出现 network_error，没有有效建议，也没有修改源码。保留失败证据；本案例暂不追查网络原因，不把失败当作 review 或“通过”。''')
code('''OLD = load_record("chat-clarify-20260924-01.json")
FAILED = load_record("chat-review-20260924-02.json")
for label, record in [("旧版澄清案例", OLD), ("网络失败案例", FAILED)]:
    print(label, "版本", record.get("plugin_version", "旧报告未记录"), "记录状态", record["status"],
          "观察到澄清", record.get("clarification_observed", "旧报告无此字段，请读轨迹"),
          "源码变化", record["source_changed"])
    decisions = [e["result"] for e in record["trace"]
                 if e["type"] == "tool/result" and e["name"] == "jev_route_task"]
    for result in decisions:
        print("  Jev：", result["status"], result.get("recommendation", {}).get("action"),
              result.get("error", {}).get("code"))''')
md('''`status: captured` 表示会话证据已保存，不表示任务成功。验收至少需要：工具顺序、实际答案、结束原因、文件差异、独立测试。默认 headless 入口未自动挂载模式的早期尝试也不算通过；复现请使用工程提供的显式挂载脚本。
''')
md('''## 5. 练习：先预测边界，再运行代码

复制一份分流答案，把类别固定为 coding、confidence 固定为 0.8，然后改变澄清 Noul：0.2、0.2001、0.8。预测三个分支。再把复杂度从 0 改为 2，分支会变化吗？

下格是答案骨架与可执行验证。**这些改写数据仅用于测试规则边界，不是新的 Jev 预测。**''')
code('''from copy import deepcopy
BASE = deepcopy(ROUTES["results"][0]["result"]["answers"])
BASE["category"].update(choice="coding", confidence=0.8,
                        probabilities={"coding": 1.0, "research": 0.0, "writing": 0.0, "other": 0.0})
for noul, expected in [(0.2, "proceed"), (0.2001, "review"), (0.8, "clarify")]:
    actions = []
    for score in [0, 2]:
        sample = deepcopy(BASE)
        sample["needs_clarification"]["noul"] = noul
        sample["complexity"].update(score=score, probabilities={str(score): 1.0}, confidence=1.0)
        actions.append(recommend_from_code(sample)["action"])
    assert actions == [expected, expected]
    print("人工边界输入：Noul=", noul, "；Score 0/2 →", actions)''')
md('''### 复现与下一步

工程中的 `npm test` 验证协议与逻辑，`npm run test:install` 在临时 home 走官方安装流程；两者不调用付费模型。完整会话需按 [真实联调记录](../apps/dsh-jev-decision/docs/LIVE-VALIDATION-20260924.md) 创建隔离目录并显式挂载预设。

阅读 [学习案例与待办](../apps/dsh-jev-decision/docs/LEARNING-CASE.md) 后，在另一台机器记录 Node/DSH 版本、安装命令、原始响应、源码差异及测试结果。网页完整交互、跨机器验证、标注集评估仍需补齐；本案例没有给出生产可用或准确率保证。

可选扩展：收集有人工标签的任务集，区分“应澄清”“可先读材料”“直接执行”，划分调参与留出集，测量误放行、过度询问、失败率和延迟。若需要强制阻止修改，应在 DSH 执行层增加可验证的状态与权限控制，不能只继续加提示词。
''')

nb.cells = cells
for i, cell in enumerate(nb.cells): cell.id = f'dsh-jev-{i:02d}'
nb.metadata = {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
               'language_info': {'name': 'python', 'version': '3.12.0'}}
out = ROOT / 'main/09_Agent集成/02_DSH决策协作.ipynb'
nbf.validate(nb)
nbf.write(nb, out)
print(f'已生成 {out.name}：{len(cells)} 格')
