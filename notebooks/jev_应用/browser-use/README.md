# Jev Ultrafast（Browser Use × TypeSafe）

从 [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) 提取的完整代码。这是一个**浏览器智能体**：给它一个自然语言目标，TypeSafe 的 Jev 每次只做「选哪个操作 + 选哪个元素」两个判断，只有操作是 `TYPE_TEXT` 时才调用小 LLM 生成文本。

**苏黎世 → 伦敦，Google Flights，7.1 秒。** 一次自然语言目标，包含真实的文本生成和加载等待。

> 上游仓库 12,748 star / 792 fork，MIT 许可，Python 3.12+，最后推送 2026-09-18。

## 模型看到什么、控制什么

- **看到**：一次请求里同时给出目标、当前页面的 `{url, title, text}`、**带索引的元素表**（`[1] button Change ticket type · Round trip`）、以及最近 10 步动作历史。
- **控制**：两个 `choice` 问题共一次网络往返——`operation`（`CLICK` / `TYPE_TEXT` / `SELECT` / `SCROLL_UP` / `SCROLL_DOWN` / `WAIT` / `DONE` / `BLOCKED`）和一个**只对该操作有效**的目标头（`click_target` / `type_text_target` / `select_target`）。执行器只消费被选中的那个目标头。
- **目标问题是推测式的**：`click_target` 无法读到 `operation` 的答案，所以它的前提里显式写明了「假设下一步是 CLICK」。两个决策、一次往返。
- **不生成代码**：模型输出永远是元素索引。选择器、坐标、shell 命令、可执行 JavaScript 都不允许出现。文本助手必须返回只含一个 `text` 键的 JSON 才允许输入。
- **成功判定**：`DONE` 选择本身不算成功，必须由独立校验（如 `examples/flights.py` 的 `verify()`）确认最终结果。

## 文件清单

### 核心库（`jev_ultrafast/`）

| 文件 | 作用 |
|---|---|
| `agent.py` | 完整智能体循环：`observe → predict → act`，以及文本助手的交接与缓存 |
| `model.py` | 动态操作/目标头的构造与响应校验；`TYPE_TEXT` 的文本生成 |
| `questions.py` | 模型指令（`NEXT_ACTION` / `TARGET` / `TEXT_VALUE`）与动作预算 `MAX_STEPS = 60` |
| `browser.py` | 经 Browser Harness 的浏览器连接、几何读取与执行；`StalePage` 判定 |
| `snapshot.js` | **原子化 DOM 快照**：一次浏览器调用读出可见控件、名称、值、文本，并用 WeakMap 给真实节点一个代码自有的身份 |
| `demo.py` | 本地 inspector（`jev` 命令入口），loopback-only，带 Host/Origin/本地 token 校验 |
| `static/` | inspector 前端（`index.html` / `app.js` / `style.css`）+ 本地测试夹具 `fixture.html` |

### 脚本（`scripts/`）

| 文件 | 作用 |
|---|---|
| `check_guards.py` | 本地浏览器下的新鲜度/执行回归，**不发模型请求、不访问外部网站** |
| `measure_flights.py` | 一次真实的航班搜索计时，冻结源码以便跨版本比较 |
| `record_flights.py` | 带连续 CDP 录屏的实测运行，保留原始时间戳 |
| `render_demo.py` | 按 1× 原始速度渲染录屏，不加速 |
| `render_fixture.py` | 按原始时间戳渲染录制的夹具帧 |
| `smoke.py` | 显式live冒烟：本地夹具 + 付费 API，**pytest 不跑它** |

### 示例（`examples/`）

`flights.py`（跑航班搜索并独立校验路线/日期/结果，保存 trace；不订票）、`run.py`（任意 URL + 目标）。

### 本仓库回放与配置

| 路径 | 作用 |
|---|---|
| `final.html` | 本地 travel 夹具三步动态回放（不调 API，可双击打开） |
| `.env.example` | TypeSafe / 文本模型密钥模板 |

本提取未纳入上游的 `docs/`、`tests/`、`pyproject.toml`、`uv.lock`、`LICENSE`、`AGENTS.md` 以及大型二进制媒体。

## 语法检查

```bash
cd browser-use
node --check jev_ultrafast/snapshot.js
node --check jev_ultrafast/static/app.js
```

### Windows 注意

`jev_ultrafast/browser.py` 用 `Path(...).read_text()` 读 `snapshot.js` 未指定编码；`snapshot.js` 含 `→`。在简体中文 Windows（GBK）上请设 `PYTHONUTF8=1`，否则可能 `UnicodeDecodeError`。

## 未包含的内容

上游大型二进制与文档/测试未复制，例如 `docs/demo.gif`、`docs/inspector.png`、`docs/demo.mp4`、`docs/flights-result.png`，以及完整 `docs/`、`tests/`。

## 典型用法

```bash
# 1) 装依赖并配置凭据（.env 已被 .gitignore 忽略，不要提交）
uv sync                      # 或 pip install browser-harness==0.1.13
cp .env.example .env         # 填 TYPESAFE_API_KEY 和 TEXT_MODEL_API_KEY

# 2) 跑一个真实任务（付费 API 调用）
uv run --env-file .env python examples/run.py \
  --url https://en.wikipedia.org/wiki/Main_Page \
  --goal 'Find and open the Wikipedia article about Gödel’s incompleteness theorems.'

# 3) 作为库使用
python - <<'PY'
from jev_ultrafast import Agent

with Agent(
    "https://www.google.com/travel/flights?hl=en",
    "Find one-way flights from Zurich to London on September 20, 2026, "
    "for one adult in economy. Stop when matching flight options are visible.",
) as agent:
    for state in agent.run():
        print(state["elapsed_ms"], state["status"])
PY

# 4) 本地 inspector（不访问外部网站）
uv run --env-file .env jev
```

## 溯源

- 上游仓库：`browser-use/jev-ultrafast`，分支 `main`
- 提交：`1231850a0bf1a0c0341fe408ef1668dbbfdfac46`（2026-09-18，作者 Gregor Žunič）
- 提取方式：GitHub API（`api.github.com`；`github.com` 与 `raw.githubusercontent.com` 在本机被网络层阻断，`git clone` 不可用）
- 完整性：36/36 个文件与上游 git blob 的 SHA-1 **逐字节一致**；4 个大型二进制媒体文件按上述说明有意跳过
