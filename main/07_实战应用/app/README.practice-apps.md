# Jev 应用实验

用 Jev 做闭环控制的三个应用项目——不是教程笔记本，而是可直接运行的代码工程。

> 作者：[Fyuan0206](https://github.com/Fyuan0206)（经 [PR #3](https://github.com/datawhalechina/jev-cookbook/pull/3) 收录）。迷宫与移动靶共用同一个 NanoJev checkpoint 思路，浏览器智能体来自 [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)（MIT）。
实验笔记本在 [`../notebooks/`](../notebooks/)；这里放的是**完整可复现的应用代码**。

从 [NanoJev](https://github.com/TianyuCodings/NanoJev) 仓库提取的两个游戏的**主要代码**，以及 browser-use 的 Jev Ultrafast 完整代码，按项目分文件夹。每个文件夹保持各自原有布局（`scripts/` + `configs/` + `docs/`），因此测试里的相对路径和文档里的命令示例都能直接用。

| 文件夹 | 项目 | 环境 | 模型看到/控制什么 | 成绩 |
|---|---|---|---|---|
| [`maze/`](maze/) | 迷宫（8×8 ~ 50×50） | `unified_grid_envs.py` / `scaled_maze.py`，纯 Python | 5×5 局部窗口 + 已观测边图的紧凑掩码；只给未试过的方向 | 统一 checkpoint 225 次尝试到达 50×50 出口（Jev 2,738） |
| [`predict_position/`](predict_position/) | ViZDoom Predict Position（移动靶） | `unified_doom_env.py`，headless ViZDoom | 可见物体标签框 + 血量/弹药/姿态 + 最近 4 帧；4 个动作 left/right/shoot/noop | 27/128 命中（Jev 11/128） |
| [`browser-use/`](browser-use/) | Jev Ultrafast 浏览器智能体 | Browser Harness + CDP，真实 Chrome | 目标 + 页面 URL/标题/可见文本 + 带索引的元素表 + 最近 10 步；一次往返定「操作 + 目标」 | Google Flights 7.073 s（原版中位 9.450 s，−25%） |

前两个游戏共用同一个 NanoJev checkpoint（`unified-games-v1` / `hard_lr1e5` step-400），但代码路径、数据构造和评估方式完全不同。第三个文件夹是另一个仓库（[browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)，MIT）的完整代码，用远程的 TypeSafe Jev API 而非本地 checkpoint，与前两个无共享代码。

## 试验目的与意义

三个任务都在回答同一件事：System One 模型（Jev）在**有限候选上做结构化判断**时，能不能支撑可复现的闭环控制，而不是生成开放文本。

| 项目 | 试验目的 | 意义 | 本仓库最终态 |
|---|---|---|---|
| 迷宫 | 模型只看 5×5 局部窗口，判断四个方向通不通；路线由同一套探索代码完成 | 把「几何判断」和「规划」拆开，单独衡量感知能力；50×50 上 Jev 2738 次到达，对照局部精确几何约 133 次、统一 checkpoint 约 225 次 | [`maze/final.html`](maze/final.html) |
| 位置预测 | 在移动靶上从 left / right / shoot / noop 中选动作，成功以真实击杀为准 | 暴露「过早开火、很少转身」的失败模式；完整测试集 Jev 11/128，演示局 seed 9300720 在 1.40 s 开火打偏 | [`predict_position/final.html`](predict_position/final.html) |
| 浏览器 | 一次往返同时决定操作与目标元素，输出永远是元素索引 | 把网页控制从「写脚本」改成「在可见动作里选择」，便于限权与校验；正式对照 Google Flights 中位约 7.1 秒 | [`browser-use/final.html`](browser-use/final.html) |

三个 `final.html` 是**可播放的动态回放**：打开后默认自动播放，可用时间轴/速度/暂停控制。迷宫轨迹内嵌在页面里；位置预测读取同目录下的 `frames/`；浏览器用本地夹具三步动画。都不调用 API。加 `?autoplay=0` 可关闭自动播放。

## 打开页面

### 动态回放（可直接打开）

- 迷宫：双击 [`maze/final.html`](maze/final.html)
- 位置预测：双击 [`predict_position/final.html`](predict_position/final.html)（需保留 `predict_position/frames/`）
- 浏览器：双击 [`browser-use/final.html`](browser-use/final.html)

### 浏览器实机（需 TypeSafe API）

本机 inspector 会调用 TypeSafe API。先在 `browser-use` 目录配置环境变量，再启动：
```powershell
cd browser-use
$env:TYPESAFE_API_KEY = "<密钥>"
$env:TYPESAFE_MODEL = "jev-latest"
python -m jev_ultrafast.demo
```

打开 http://127.0.0.1:8766 。本机 Chrome 如果没有打开远程调试，先用单独的用户目录启动，并设置 `BU_CDP_URL=http://127.0.0.1:9333`：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9333 --user-data-dir="$env:TEMP\jev-chrome-profile" --no-first-run about:blank
```

需要往输入框里打字时，还要配置 `TEXT_MODEL_API_KEY`。只点击的本地夹具不需要。

## 运行测试

三个文件夹的测试都从**文件夹根目录**执行。NanoJev 的两个游戏有部分跨游戏共享的引擎（训练器、推理器、采集管线），没有复制两份，因此需要把原仓库的 `scripts/` 加到 `PYTHONPATH`：

```bash
# 迷宫：74 个测试全部通过（2 个跳过）
cd maze
PYTHONPATH="/c/Users/24019/Desktop/NanoJev-main/scripts" \
  python -m unittest discover -s scripts -p 'test_*.py'

# 位置预测：79 个测试，4 个 error（原因见 predict_position/README.md）
cd predict_position
PYTHONPATH="/c/Users/24019/Desktop/NanoJev-main/scripts" \
  python -m unittest discover -s scripts -p 'test_*.py'
```

Windows 下把 `PYTHONPATH` 换成 `C:\Users\24019\Desktop\NanoJev-main\scripts`。NanoJev 的测试不加载权重、不调 API、不需要 GPU；`test_unified_doom_env.py --real` 会额外跑一次真实 ViZDoom（需装 `vizdoom`）。

`browser-use/` 本提取未带 `tests/`；实机运行需 `pip install browser-harness==0.1.13`，简体中文 Windows 建议 `PYTHONUTF8=1`。详见 [`browser-use/README.md`](browser-use/README.md)。

## 为什么不是完全自包含

`predict_position` 的监督数据准备代码直接依赖统一游戏的训练器（`train_unified_games.py`、`train_pipeline_decisions.py`）和推理器（`predict_toy_decisions.py`）。把这些复制进来会引发连锁导入，把文件夹膨胀成接近整个仓库，而且和原仓库产生两份会漂移的副本。因此这里只放**该游戏自己的代码**，共享部分用 `PYTHONPATH` 指向原仓库。各文件夹的 README 列出了确切需要哪些共享模块。

`browser-use/` 则相反——它是独立完整的一份，只依赖 PyPI 上的 `browser-harness`。

## 未包含的内容

- NanoJev 原版三模型对比页与 `web/dev/media/*.webp` 图集未复制；本仓库用各项目根目录的 `final.html` 做 Jev 动态回放，位置预测画面按录制动作在本机 ViZDoom 重放生成后放在 `predict_position/frames/`
- `browser-use` 的大型二进制媒体（`demo.gif` / `demo.mp4` / `inspector.png` / `flights-result.png`）与上游 `docs/`、`tests/`、`pyproject.toml` 未纳入本提取
- 共享引擎：`predict_toy_decisions.py`、`train_pipeline_decisions.py`、`train_unified_games.py`、`calibrated_objectives.py`
- 其他游戏（Snake、ViZDoom Basic、APPO 实验）的代码；`maze/` 里的 `snake_game.py` 和 `unified_grid_envs.py` 的 Snake 部分是因为迷宫环境依赖它们而一并复制的
