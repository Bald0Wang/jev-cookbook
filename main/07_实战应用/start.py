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

# 只能命令行跑的实验（不占端口，菜单里给命令）
CLI_EXPERIMENTS = [
    ("browser-use live smoke", "cd app/browser-use && PYTHONPATH=. ../../../../main/.venv/bin/python scripts/smoke.py --max-actions 6",
     "真 Jev 驱动浏览器完成 Lisbon 目标（6 决策 5 动作），需 Chrome", "app/browser-use/EXPERIMENT.md"),
    ("browser-use 守卫回归", "cd app/browser-use && PYTHONPATH=. ../../../../main/.venv/bin/python scripts/check_guards.py",
     "21 项浏览器守卫回归，零模型调用", "app/browser-use/EXPERIMENT.md"),
    ("maze 测试套件", "cd app/maze/scripts && ../../../../main/.venv/bin/python -m pytest test_unified_grid_envs.py test_scaled_maze.py test_composed_maze.py -q",
     "35 通过 / 4 因训练侧依赖缺失（详见报告）", "app/maze/EXPERIMENT.md"),
    ("predict_position 测试套件", "cd app/predict_position/scripts && ../../../../main/.venv/bin/python -m pytest test_unified_doom_env.py test_build_predict_position_demo.py test_build_shooting_demo.py -q",
     "28 项全过；完整评估需 ViZDoom", "app/predict_position/EXPERIMENT.md"),
    ("sudoku 数独评测", "cd app/sudoku && ../../../../main/.venv/bin/python jev_sudoku.py --episodes 10 --holes 40",
     "本地裁判解 10 局；--judge jev 切真 Jev", "app/sudoku/EXPERIMENT.md"),
]

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


def menu_page() -> str:
    rows = []
    for name, title, port, path, tip, report in SERVICES:
        up = alive(port)
        dot = "🟢 运行中" if up else "⚪ 未启动"
        rows.append(f"""<div class="card">
  <div class="head"><span class="dot {'on' if up else 'off'}"></span><b>{title}</b>
  <span class="state">{dot}</span></div>
  <p>{tip}</p>
  <div class="links"><a class="btn" href="http://127.0.0.1:{port}{path}">打开实验 →</a>
  <a class="doc" href="/{report}">实验报告</a></div>
</div>""")
    cli = "".join(f"""<tr><td><code>{cmd}</code></td><td>{tip}</td>
      <td><a href="/{rep}">报告</a></td></tr>"""
                  for _, cmd, tip, rep in CLI_EXPERIMENTS)
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
<p class="sub">全部服务已拉起并停在就绪位 —— 点「打开实验」逐个实践；观察要点已写在每张卡片上。</p>
<div class="grid">{''.join(rows)}</div>
<h2>命令行实验（复制运行）</h2>
<table>{cli}</table>
<p class="foot">密钥从 main/07_实战应用/.env 读取（已 gitignore）· 全部实测数据与八节报告见各卡片「实验报告」 · 本页由 start.py 生成，每 15s 自动刷新状态
<meta http-equiv="refresh" content="15"></p>"""


class MenuHandler:
    pass


def serve_menu() -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/app/"):
                # 让菜单能直接打开各项目里的实验报告 md
                target = HERE / self.path.lstrip("/")
                if target.exists():
                    body = target.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
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
