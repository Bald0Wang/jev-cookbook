#!/usr/bin/env python3
"""Jev Cookbook · 第七章实战应用 —— 一键启动菜单。

用法：
    python3 start.py          # 拉起全部服务并打开总控菜单（http://127.0.0.1:4200）
    python3 start.py stop     # 停止本章全部服务
    python3 start.py status   # 只看状态

所有服务启动后停在各自的「就绪/暂停」界面，等你逐个实践；
总控菜单显示每个实验的运行状态、入口链接、观察要点和对应实验报告。
密钥从本目录 .env 读取（不入库），或继承启动前的环境变量。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE / "logs"
MENU_PORT = 4200

# 密钥：目录级 .env → 环境变量
env_file = HERE / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

# 服务清单：名称 → (启动命令, 端口, 入口路径, 观察要点, 报告链接)
SERVICES = [
    ("gridloop", "Jev 贪吃蛇", 4173, "/",
     "点「开始游戏」再点「Jev 自动驾驶」——看 Jev 逐帧选方向，面板实时解释每个决策（朝食物/避风险）",
     "app/jev-games/games/gridloop/EXPERIMENT.md"),
    ("minesweeper", "Jev 扫雷", 4174, "/",
     "点「Jev 自动扫雷」——观察它优先翻逻辑确定安全的格子、按数字线索插旗、无解时诚实停止",
     "app/jev-games/games/minesweeper/EXPERIMENT.md"),
    ("werewolf", "Jev 狼人杀", 4175, "/",
     "点「新局」再连点「推进一步」——你是村民，5 个 Jev 玩家会发言/查验/刀人/投票；重点看投票置信度分层和跨轮一致性检查",
     "app/jev-games/games/werewolf/EXPERIMENT.md"),
    ("smart-home", "智能家居 3D 演练场", 8812, "/",
     "打字或点麦克风下指令——追踪面板显示 Jev 一次调用的完整概率分布；试「先开客厅灯再关掉」看串行栈",
     "app/smart-home/EXPERIMENT.md"),
    ("web-lab", "Jev Games Lab（React 总览）", 4180, "/",
     "三个游戏 + 两组对比实验的统一入口；对比页在同一时间轴并排两种 Jev 的真实 trace",
     "app/jev-games/apps/web/EXPERIMENT.md"),
    ("doudizhu", "斗地主自动对局", 8801, "/",
     "三座位自动出牌观战——本地裁判与 Jev 判断可切换，CSS 扑克实时渲染",
     "app/doudizhu/EXPERIMENT.md"),
    ("blackjack", "21 点对局", 8802, "/",
     "基本策略 gold vs 凭直觉打法的资金曲线对照——长期必输的游戏里衡量策略差距",
     "app/blackjack/EXPERIMENT.md"),
]
# 回放实验：无端口，由菜单服务器托管 final.html（本地录制回放，不调 API）
REPLAYS = [
    ("maze-replay", "迷宫 · 终局回放", "/app/maze/final.html",
     "50×50 通关录制的本地回放——观察 5×5 局部判断如何拼出全局路线",
     "app/maze/EXPERIMENT.md"),
    ("pp-replay", "移动靶 · 终局回放", "/app/predict_position/final.html",
     "seed 9300720 演示局回放——看「过早开火」失败模式的实况",
     "app/predict_position/EXPERIMENT.md"),
    ("bu-replay", "浏览器 · 夹具回放", "/app/browser-use/final.html",
     "travel 夹具三步动态回放——对比 live smoke 的决策序列",
     "app/browser-use/EXPERIMENT.md"),
]

# 可一键运行的实验（slug → 标题 / bash 命令 / 说明 / 报告路径）
RUNNABLES = {
    "sudoku": ("数独评测（本地裁判解 10 局，40 洞）",
               "cd app/sudoku && \"$PY\" jev_sudoku.py --episodes 10 --holes 40",
               "MRV 选格 + 约束推理裁判；加 --judge jev 可切真 Jev",
               "app/sudoku/EXPERIMENT.md"),
    "maze-tests": ("迷宫测试套件（3 模块）",
               "cd app/maze/scripts && \"$PY\" -m pytest test_unified_grid_envs.py test_scaled_maze.py test_composed_maze.py -q",
               "35 过 / 4 失败均因训练侧依赖缺失（详见报告）",
               "app/maze/EXPERIMENT.md"),
    "pp-tests": ("移动靶测试套件（3 模块）",
               "cd app/predict_position/scripts && \"$PY\" -m pytest test_unified_doom_env.py test_build_predict_position_demo.py test_build_shooting_demo.py -q",
               "28 项全过；完整评估需 ViZDoom",
               "app/predict_position/EXPERIMENT.md"),
    "browser-guards": ("浏览器守卫回归（21 项）",
               "cd app/browser-use && \"$PY\" scripts/check_guards.py",
               "零模型调用的确定性回归",
               "app/browser-use/EXPERIMENT.md"),
    "browser-smoke": ("浏览器 live smoke（真 Jev）",
               "cd app/browser-use && \"$PY\" -m jev_ultrafast.demo & DPID=$!; sleep 1.5; PYTHONPATH=app/browser-use \"$PY\" app/browser-use/scripts/smoke.py --max-actions 6; kill $DPID 2>/dev/null; true",
               "真 Jev 驱动浏览器完成 Lisbon 目标（约 6 决策 5 动作）",
               "app/browser-use/EXPERIMENT.md"),
}

PROCS: dict[str, subprocess.Popen] = {}


def spawn(name: str, cmd: list[str], cwd: Path) -> None:
    LOGS.mkdir(exist_ok=True)
    log = open(LOGS / f"{name}.log", "w")
    env = dict(os.environ)
    env.setdefault("TYPESAFE_API_KEY", "")
    env.setdefault("STEPFUN_API_KEY", "")
    PROCS[name] = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, env=env)


def alive(port: int) -> bool:
    try:
        return urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1.5).status == 200
    except Exception:
        return False


def start_all() -> None:
    cmds = {
        "gridloop": (["node", "server.mjs"], HERE / "app/jev-games/games/gridloop"),
        "minesweeper": (["node", "server.mjs"], HERE / "app/jev-games/games/minesweeper"),
        "werewolf": (["node", "server.mjs"], HERE / "app/jev-games/games/werewolf"),
        "smart-home": ([sys.executable, "serve_smart_home.py", "--port", "8812", "--no-open"],
                       HERE / "app/smart-home"),
        "doudizhu": ([sys.executable, "serve_doudizhu.py", "--port", "8801", "--judge", "local"],
                     HERE / "app/doudizhu"),
        "blackjack": ([sys.executable, "serve_blackjack.py", "--port", "8802", "--judge", "local"],
                      HERE / "app/blackjack"),
        "web-lab": ([sys.executable, "-m", "http.server", "4180", "--bind", "127.0.0.1"],
                    HERE / "app/jev-games/apps/web/dist"),
    }
    for name, (cmd, cwd) in cmds.items():
        if alive(next(p for n, _, p, *_ in SERVICES if n == name)):
            print(f"  = {name} 已在运行（复用）")
            continue
        spawn(name, cmd, cwd)
        print(f"  ▶ {name} 已启动")


def stop_all() -> None:
    """按端点精确停掉本章服务（不动其他进程）。"""
    killed = 0
    try:
        out = subprocess.run(["lsof", "-tiTCP:4173,4174,4175,4180,4200,8801,8802,8812,8766",
                              "-sTCP:LISTEN"], capture_output=True, text=True).stdout
        pids = {p for p in out.split() if p}
        for pid in pids:
            try:
                os.kill(int(pid), 15)
                killed += 1
            except ProcessLookupError:
                pass
    except FileNotFoundError:
        pass
    print(f"已停止 {killed} 个进程")


MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
        ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webm": "video/webm",
        ".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8",
        ".jsonl": "text/plain; charset=utf-8"}

RESULTS: dict[str, tuple[float, str]] = {}


def _serve_file(self, rel: str) -> None:
    target = (HERE / rel).resolve()
    if not str(target).startswith(str(HERE.resolve())) or not target.is_file():
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return
    body = target.read_bytes()
    self.send_response(200)
    self.send_header("Content-Type", MIME.get(target.suffix, "application/octet-stream"))
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def _runnable_page(self, slug: str) -> None:
    if slug not in RUNNABLES:
        self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
    title, cmd_tpl, tip, rep = RUNNABLES[slug]
    if slug not in RESULTS:
        cmd = cmd_tpl.replace('\"$PY\"', sys.executable)
        try:
            t0 = time.time()
            proc = subprocess.run(["bash", "-c", cmd], cwd=HERE, capture_output=True,
                                  text=True, timeout=300,
                                  env={**os.environ, "TERM": "dumb"})
            out = f"$ {cmd}\n\n" + (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
            out += f"\n\n[exit {proc.returncode} · {time.time()-t0:.1f}s]"
        except subprocess.TimeoutExpired:
            out = f"$ {cmd}\n\n超时（300s）——实验仍在后台意义不大，请回菜单重试并缩小范围。"
        RESULTS[slug] = (time.time(), out)
    _, out = RESULTS[slug]
    body = (f"<!doctype html><meta charset=\"utf-8\"><title>{title}</title>"
            "<style>body{background:#0d1117;color:#c9d1d9;font:13px/1.6 Menlo,monospace;padding:26px}"
            "h1{font-size:15px;color:#58a6ff}a{color:#7aa2f7}pre{white-space:pre-wrap}</style>"
            f"<h1>{title}</h1><p>{tip} · <a href='/'>← 返回菜单</a> · <a href='/run/{slug}'>重新运行</a></p>"
            f"<pre>{out}</pre>").encode()
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)


def menu_page() -> str:
    rows = []
    for name, title, port, path, tip, report in SERVICES:
        up = alive(port)
        rows.append(_card(title, f"http://127.0.0.1:{port}{path}", tip, report, up, f":{port}"))
    for name, title, path, tip, report in REPLAYS:
        rows.append(_card(title + "（回放）", path, tip, report, True, "本地录制 · 不调 API"))
    # Mario：上游 venv 存在则给实况服务，否则给报告
    mario_py = None
    for cand in (HERE / "app/typesafe-mario/.venv/bin/python",
                 Path("/Volumes/拓展/workspace/jev cookbook/typesafe-mario/.venv/bin/python")):
        if cand.exists():
            mario_py = cand
            break
    if mario_py and alive(8770):
        rows.append(_card("马里奥实况（模拟器）", "http://127.0.0.1:8770/",
                          "NES 模拟器实时画面：本地替身驾驶员 + 每步决策遥测（页面自带黄色「非 Jev」横幅）",
                          "app/typesafe-mario-repro/REPORT.md", True, ":8770"))
    else:
        rows.append(f"""<div class="card"><div class="head"><b>马里奥（typesafe-mario 复现）</b>
<span class="state">⚪ 需上游 venv</span></div>
<p>NES 模拟器实况需上游 typesafe-mario/.venv（nes-py 等重依赖）。先看报告与截图：
<a href="/app/typesafe-mario-repro/REPORT.md">REPORT.md</a> ·
<a href="/app/typesafe-mario-repro/images/viz.png">viz.png</a> ·
<a href="/app/typesafe-mario-repro/images/terminal.png">terminal.png</a></p>
<div class="links"><span class="doc">手动启动：viz_server.py --port 8770（上游 venv）</span></div></div>""")
    cli = ""
    for slug, (title, cmd_tpl, tip, rep) in RUNNABLES.items():
        n = "（已运行，可重跑）" if slug in RESULTS else ""
        cli += f"""<tr><td><a href="/run/{slug}" style="color:#7dd3fc">▶ {title}</a>{n}</td>
<td>{tip}</td><td><a href="/{rep}">报告</a></td></tr>"""
    return f"""<!doctype html><meta charset="utf-8"><title>Jev Cookbook · 第七章启动菜单</title>
<style>
body{{background:#0b0f1a;color:#dbe4f0;font:14px/1.65 -apple-system,'PingFang SC',sans-serif;margin:0;padding:34px}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#7c8db0;margin:0 0 22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}}
.card{{background:#131a2b;border:1px solid #24304d;border-radius:12px;padding:14px 16px}}
.card b{{font-size:15px}} .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}}
.dot.on{{background:#34d399;box-shadow:0 0 6px #34d39988}} .dot.off{{background:#4b5876}}
.state{{float:right;font-size:12px;color:#8fa0c0}}
.card p{{color:#9fb0cd;font-size:12.5px;margin:8px 0 10px;min-height:52px}}
.links{{display:flex;gap:10px;align-items:center}}
.btn{{background:#2563eb;color:#fff;text-decoration:none;padding:6px 12px;border-radius:8px;font-size:13px}}
.doc{{color:#7aa2f7;font-size:12.5px;text-decoration:none}}
h2{{font-size:16px;margin:26px 0 10px}} table{{border-collapse:collapse;width:100%;font-size:12.5px}}
td{{border-top:1px solid #24304d;padding:8px 6px;vertical-align:top;color:#9fb0cd}}
code{{background:#1b2337;padding:2px 6px;border-radius:6px;color:#7dd3fc;font-size:11.5px}}
.foot{{color:#5c6c8e;font-size:12px;margin-top:24px}}
</style>
<h1>Jev Cookbook · 第七章 实战应用</h1>
<p class="sub">全部服务已拉起并停在就绪位 —— 点「打开实验」逐个实践；观察要点已写在每张卡片上。回放卡不调 API，随时可看。</p>
<div class="grid">{''.join(rows)}</div>
<h2>一键运行实验（点击即跑，输出就地显示）</h2>
<table>{cli}</table>
<p class="foot">密钥从 main/07_实战应用/.env 读取（已 gitignore）· 八节报告见各卡片「实验报告」 · 状态每 15s 自动刷新
<meta http-equiv="refresh" content="15"></p>"""


def _card(title, href, tip, report, up, state):
    return f"""<div class="card">
  <div class="head"><span class="dot {'on' if up else 'off'}"></span><b>{title}</b>
  <span class="state">{('🟢 ' + state) if up else ('⚪ ' + state)}</span></div>
  <p>{tip}</p>
  <div class="links"><a class="btn" href="{href}">打开实验 →</a>
  <a class="doc" href="/{report}">实验报告</a></div>
</div>"""


def serve_menu() -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith("/run/"):
                return _runnable_page(self, path[len("/run/"):])
            if path.startswith("/app/"):
                return _serve_file(self, path.lstrip("/"))
            if path == "/healthz":
                self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok"); return
            body = menu_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    ThreadingHTTPServer(("127.0.0.1", MENU_PORT), H).serve_forever()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_all()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        for name, title, port, *_ in SERVICES:
            print(f"  {'🟢' if alive(port) else '⚪'} {port}  {title}")
        return
    print("启动第七章全部服务…")
    start_all()
    time.sleep(1.5)
    # Mario 实况（有上游 venv 就拉起）
    mario_py = next((c for c in (HERE / "app/typesafe-mario/.venv/bin/python",
                                 Path("/Volumes/拓展/workspace/jev cookbook/typesafe-mario/.venv/bin/python")) if c.exists()), None)
    if mario_py and not alive(8770):
        spawn("mario", [str(mario_py), "viz_server.py", "--port", "8770"],
              HERE / "app/typesafe-mario-repro")
        print("  ▶ mario 实况已启动（:8770，本地替身驾驶员）")
    print(f"总控菜单: http://127.0.0.1:{MENU_PORT}")
    import threading
    threading.Thread(target=serve_menu, daemon=True).start()
    webbrowser.open(f"http://127.0.0.1:{MENU_PORT}")
    print("Ctrl+C 退出本脚本（服务继续在后台运行；python3 start.py stop 可全部停止）")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n菜单已退出，服务仍在运行——python3 start.py stop 全部停止")


if __name__ == "__main__":
    main()
