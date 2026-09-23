#!/usr/bin/env python3
"""生成《Pi + Jev 决策闭环实验》教学 notebook。"""

from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent   # notebooks/
OUTPUT = ROOT / "pi_jev_integration_experiments.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
}
nb.cells = [
    md("""
# Pi + Jev：让 Agent 在执行前做一次判断

这是一个小型集成实验：真实启动 Pi RPC，加载 TypeScript extension，把最小 state 交给 Jev，再由 Pi 的代码选择下一步。

| 章节 | 内容 | 观察 |
| --- | --- | --- |
| 0. 准备 | 环境、Pi RPC 助手、离线替身 | 真实调用和模拟调用的边界 |
| 1. Skill 选择 | Jev Choice 读取并注入 SKILL.md | Pi 只加载命中的 Skill |
| 2. 工具门禁 | Jev Noul 解释为 allow / ask_user / block | 概率由本地代码解释 |

这不是 Pi 或 Jev 的完整教程；原语基础和 TypeSafe 架构模式见仓库已有 notebook。
"""),
    md("""
## 运行要求

- Node.js 20+；
- Pi CLI：npm install -g --ignore-scripts @earendil-works/pi-coding-agent；
- 真实 Jev 调用需要环境变量 TYPESAFE_API_KEY；
- Key 只从环境变量读取，不写入 notebook；
- 没有 Key 时仍可启动真实 Pi，extension 会明确标记 offline-simulation。
"""),
    md("## 0. 准备"),
    md("""
### 0.1 安装所需的库

本 notebook 的 Pi 客户端只用 Python 标准库；nbformat 和 nbclient 用于生成与验证 notebook。
"""),
    code("%pip install -q -U nbformat nbclient"),
    md("""
### 0.2 导入库并准备路径

Python 负责启动 Pi RPC 和读取 JSONL 事件；真正的决策代码位于 pi_jev_demo_extension.ts。
"""),
    code("""
from pathlib import Path
import json
import os
import queue
import shutil
import subprocess
import threading
import time

NOTEBOOK_ROOT = Path(__file__).resolve().parent.parent
EXTENSION = NOTEBOOK_ROOT / "pi_jev_demo" / "pi_jev_demo_extension.ts"
PI_EXE = os.environ.get("PI_EXE") or ("pi.cmd" if os.name == "nt" else "pi")
print("Pi:", shutil.which(PI_EXE) or PI_EXE)
print("Extension:", EXTENSION)
"""),
    md("""
### 0.3 连通性测试

先检查 Pi 命令、extension 文件和 Jev Key 是否存在。真正的 API 调用会在两个实验中完成。
"""),
    code("""
assert shutil.which(PI_EXE) or Path(PI_EXE).exists(), "找不到 Pi CLI"
assert EXTENSION.exists(), f"找不到 extension: {EXTENSION}"
print("Pi CLI 和 extension 已就绪")
print("TYPESAFE_API_KEY 已设置:", bool(os.environ.get("TYPESAFE_API_KEY")))
"""),
    md("""
### 0.4 离线回退用的两个替身类

真实 Pi 仍然会启动；只有 extension 内部的 Jev transport 在没有 Key 时使用规则替身。下面的类让 notebook 有一个明确的离线结果形状，不把模拟结果冒充成模型输出。
"""),
    code("""
class FakePiRun:
    def __init__(self, report):
        self.report = report

    def as_dict(self):
        return {"elapsed_ms": 0.0, "report": self.report, "events_seen": 1}


class FakeDecision:
    # 与 Jev 的 Choice / Noul 答案保持可打印的最小形状。

    def __init__(self, **fields):
        self.fields = fields

    def as_dict(self):
        return dict(self.fields)


def show_run(label, result):
    report = result["report"]
    print(f"[{label}]")
    print("state =", json.dumps(report["state"], ensure_ascii=False))
    print("Jev typed answer =", json.dumps(report["jev"], ensure_ascii=False))
    print("Pi branch =", report["branch"])
    print("Pi process latency =", result["elapsed_ms"], "ms")
"""),
    md("""
### 0.5 调用助手 run_pi_command

每次调用都新启动一个真实 Pi 进程，发送一个 extension command，等待 extension_ui_request 事件，再关闭进程。
"""),
    code("""
def run_pi_command(command: str, timeout: float = 30.0):
    args = [
        PI_EXE, "--mode", "rpc", "--no-session", "--no-builtin-tools",
        "--no-skills", "--no-extensions", "--extension", str(EXTENSION),
    ]
    proc = subprocess.Popen(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    events = queue.Queue()

    def read_stdout():
        for line in proc.stdout:
            try:
                events.put(json.loads(line))
            except json.JSONDecodeError:
                events.put({"type": "raw", "line": line.rstrip()})

    threading.Thread(target=read_stdout, daemon=True).start()
    started = time.perf_counter()
    proc.stdin.write(json.dumps({"type": "prompt", "message": command}, ensure_ascii=False) + "\\n")
    proc.stdin.flush()
    report = None
    raw_events = []
    while time.perf_counter() - started < timeout:
        try:
            event = events.get(timeout=0.2)
        except queue.Empty:
            continue
        raw_events.append(event)
        if event.get("type") == "extension_ui_request" and event.get("method") == "notify":
            message = event.get("message", "")
            if message.startswith("[pi-jev-demo] "):
                report = json.loads(message[len("[pi-jev-demo] "):])
                break
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    if report is None:
        raise RuntimeError(f"Pi 未在 {timeout}s 内返回演示结果；最近事件: {raw_events[-3:]}")
    return {"elapsed_ms": elapsed_ms, "report": report, "events_seen": len(raw_events)}
"""),
    md("""
### 0.6 各实验的离线示例数据

这些值只用于没有 Key 时解释代码路径；真实运行时，输出中的 model 应为服务返回的模型名。
"""),
    code("""
OFFLINE_EXPECTED = {
    "skill": {"choice": "accessibility", "confidence": 0.91},
    "safe_gate": {"noul": 0.96, "branch": "allow"},
    "dangerous_gate": {"noul": 0.02, "branch": "block"},
}
print("离线参考数据已定义；真实 Key 下不参与分支。")
"""),
    md("""
## 📖 理论速览：Pi、Skill 与 Jev 的分工

Pi 是执行层：拥有进程、工具、事件和会话生命周期。Skill 是决策剧本：规定什么时候问、收集哪些 state、命中后加载什么内容。Jev 是判断层：返回 Choice 或 Noul 等 typed answer，不负责写代码。

Pi 的 before_agent_start 可以注入选中的 Skill，tool_call 可以阻止工具；Jev 的 Choice 适合选 Skill，Noul 适合表达是否允许。本 notebook 只让代码解释结果，不让主模型解析自由文本。
"""),
    md("""
## 1. Skill 选择

### 原理

先用 Jev 在小候选集合中选择 Skill，再读取命中的 SKILL.md。这样 Pi 的后续上下文只包含当前任务需要的 Skill。

### 📖 理论根基

Choice 的候选 key 和描述由代码定义；Jev 返回 choice、概率分布和置信度。before_agent_start 再把读取到的 Skill 作为 custom message 注入下一次模型请求。

### 步骤

1. 只发送任务文本和候选 Skill 描述；
2. extension 调用 Jev Choice；
3. 读取对应 SKILL.md；
4. Pi 记录分支并准备注入 Skill。
"""),
    code("""
SKILL_TASK = "给设置页面增加键盘可操作的 Modal"
SKILL_COMMAND = f"/jev-demo-skill {SKILL_TASK}"
print("task =", SKILL_TASK)
print("command =", SKILL_COMMAND)
"""),
    code("""
skill_run = run_pi_command(SKILL_COMMAND)
show_run("Skill 选择", skill_run)
"""),
    md("""
### 观察要点

- state 没有整段对话或完整工具目录；
- Jev 返回 typed choice，而不是解释段落；
- extension 读取 accessibility/SKILL.md；
- before_agent_start 会把选中的 Skill 注入下一轮。
"""),
    code("""
skill_report = skill_run["report"]
print("choice =", skill_report["jev"].get("choice"))
print("confidence =", skill_report["jev"].get("confidence"))
print("loaded preview =", skill_report["loaded_skill_preview"][:120].replace("\\n", " / "))
"""),
    md("""
## 2. 工具门禁

### 原理

在 bash、write 或 edit 真正执行前，把工具名和参数交给 Jev。代码将 Noul 概率解释为 allow、ask_user 或 block。

### 📖 理论根基

工具门禁属于高风险决策。Jev 超时或不可用时，extension 不能把“没有判断”当成“安全”，因此真实 tool_call hook 采用人工确认或阻止的回退策略。

### 步骤

1. 发送低风险 git status；
2. 发送破坏性 rm -rf；
3. 对比 Jev 的 noul 和本地代码分支。
"""),
    code("""
SAFE_COMMAND = "/jev-demo-gate bash git status"
DANGEROUS_COMMAND = "/jev-demo-gate bash rm -rf ./build"
print(SAFE_COMMAND)
print(DANGEROUS_COMMAND)
"""),
    code("""
safe_gate = run_pi_command(SAFE_COMMAND)
dangerous_gate = run_pi_command(DANGEROUS_COMMAND)
show_run("安全命令", safe_gate)
show_run("危险命令", dangerous_gate)
"""),
    md("""
### 观察要点

门禁不是让 Jev 直接执行动作：Jev 只返回概率，三个分支都是 extension 中的确定性代码。重复运行时边界概率可能落在不同路径，因此阈值必须用真实任务集校准。
"""),
    code("""
for label, result in [("safe", safe_gate), ("dangerous", dangerous_gate)]:
    report = result["report"]
    print(label, "noul =", report["jev"].get("noul"), "→", report["branch"])
"""),
    md("""
## 小结

Pi 处理进程、命令和工具生命周期；Skill 规定问法；Jev 返回 typed decision；本地 TypeScript 代码决定下一步。后续若扩展，应先建立真实任务评测集，再调整阈值或增加问题维度。
"""),
]

nbf.write(nb, OUTPUT)
print(f"已生成 {OUTPUT}")
