"""Blackjack (21点) spectator server: basic-strategy player, CSS playing cards.

Pure standard library for the local judge; the same questions go to the real Jev with
``--judge jev`` and ``TYPESAFE_API_KEY`` (needs ``pip install typesafe-sdk``).

Run:  python3 serve_blackjack.py --port 8802 --host 0.0.0.0
Then open http://127.0.0.1:8802
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blackjack_game as B


class BlackjackSession:
    def __init__(self, judge, pace: float, seed: int) -> None:
        self.lock = threading.Lock()
        self.judge = judge
        self.pace = pace
        self.state = B.make_blackjack(seed=seed)
        self.base_seed = seed
        self.last_question: dict | None = None
        self.last_answer: str | None = None
        self.episodes = 1
        self.alive = True

    def run(self) -> None:
        while self.alive:
            if self.state['done']:
                time.sleep(3.0)
                if not self.alive:
                    return
                self.episodes += 1
                self.state = B.make_blackjack(seed=self.base_seed + self.episodes * 100)
                with self.lock:
                    self.last_question = None
                    self.last_answer = None
                continue
            if self.state['phase'] != 'player':
                time.sleep(self.pace)
                continue
            with self.lock:
                request = B.render_request(self.state)
                self.last_question = request
            time.sleep(self.pace)
            if not self.alive:
                return
            answer = self.judge(request)
            action = answer.get('action')
            if action not in B.legal_actions(self.state):
                action = 'stand'
            with self.lock:
                self.last_answer = action
            self.state = B.step(self.state, action)

    def snapshot(self) -> dict:
        with self.lock:
            state = self.state
            return {
                'player': [B.card_name(c) for c in state['player']],
                'dealer': [B.card_name(c) for c in state['dealer']],
                'player_value': B.hand_value(state['player'])[0],
                'dealer_value': B.hand_value(state['dealer'])[0],
                'hole_hidden': state['phase'] == 'player' and len(state['dealer']) >= 2,
                'phase': state['phase'],
                'outcome': state['outcome'],
                'bank': state['bank'],
                'bet': state['bet'],
                'round': state['round'],
                'done': state['done'],
                'episodes': self.episodes,
                'history': state['history'][-12:],
                'question': {
                    'state': self.last_question['state'] if self.last_question else None,
                    'legal': self.last_question['legal'] if self.last_question else [],
                    'bust': self.last_question['bust_probability'] if self.last_question else None,
                },
                'answer': self.last_answer,
            }


def local_judge(request: dict) -> dict:
    """Basic strategy, parsed back out of the published facts (hand value, upcard)."""
    match = re.search(r'Your hand: .* = (\d+)', request['state'])
    soft = ' (soft)' in request['state']
    up_match = re.search(r'Dealer shows .* \(value (\d+)\)', request['state'])
    total = int(match.group(1))
    upcard = int(up_match.group(1))
    can_double = 'double' in request['legal']
    if soft:
        if total >= 19:
            return {'action': 'stand'}
        if total == 18:
            if 3 <= upcard <= 6 and can_double:
                return {'action': 'double'}
            return {'action': 'stand' if upcard <= 8 else 'hit'}
        if total == 17 and 3 <= upcard <= 6 and can_double:
            return {'action': 'double'}
        if total in (15, 16) and 4 <= upcard <= 6 and can_double:
            return {'action': 'double'}
        if total in (13, 14) and 5 <= upcard <= 6 and can_double:
            return {'action': 'double'}
        return {'action': 'hit'}
    if total >= 17:
        return {'action': 'stand'}
    if total >= 13:
        return {'action': 'stand' if upcard <= 6 else 'hit'}
    if total == 12:
        return {'action': 'stand' if 4 <= upcard <= 6 else 'hit'}
    if total == 11:
        return {'action': 'double' if (upcard <= 10 and can_double) else 'hit'}
    if total == 10:
        return {'action': 'double' if (upcard <= 9 and can_double) else 'hit'}
    if total == 9:
        return {'action': 'double' if (3 <= upcard <= 6 and can_double) else 'hit'}
    return {'action': 'hit'}


def make_judge(kind: str):
    if kind == 'local':
        return local_judge
    import typesafe_sdk

    client = typesafe_sdk.TypeSafeClient()

    def jev_judge(request: dict) -> dict:
        response = client.system_one(state=request['state'], questions=request['questions'])
        return {'action': str(response.answers['action'].choice)}

    return jev_judge


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>21点 — Jev 牌桌</title>
<style>
  :root { --canvas:#0b1013; --felt:#0e5c36; --felt2:#0a4a2c; --surface:#16191f;
    --line:#303640; --text:#eceff3; --muted:#8d96a3; --gold:#e6c26a;
    --danger:#c77065; --ok:#63b06a; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--canvas); color:var(--text);
    font:14px/1.5 -apple-system,"Segoe UI","PingFang SC",sans-serif; }
  header { display:flex; align-items:center; gap:16px; padding:10px 20px;
    background:var(--surface); border-bottom:1px solid var(--line); }
  .brand { font-weight:600; font-size:17px; }
  .banner { padding:8px 20px; font-size:12.5px; color:#d2a764;
    background:rgba(210,167,100,.08); border-bottom:1px solid var(--line); }
  main { padding:18px 22px; display:grid; grid-template-columns:minmax(0,1fr) 400px; gap:18px; }
  @media (max-width:1100px) { main { grid-template-columns:1fr; } }
  .table { background:radial-gradient(ellipse at center, var(--felt) 0%, var(--felt2) 75%);
    border:10px solid #5a3a22; border-radius:22px; padding:24px; min-height:480px;
    box-shadow:inset 0 0 60px rgba(0,0,0,.45); }
  .card { display:inline-flex; flex-direction:column; justify-content:space-between;
    width:64px; height:92px; background:#fdfdf8; border-radius:7px; padding:4px 6px;
    margin-right:8px; box-shadow:1px 3px 6px rgba(0,0,0,.45);
    font:700 15px/1.2 ui-monospace,Menlo,monospace; color:#1a1a1e;
    border:1px solid #c9c9c2; position:relative; }
  .card .mid { position:absolute; inset:0; display:flex; align-items:center;
    justify-content:center; font-size:30px; opacity:.85; }
  .card.red { color:#c0392b; }
  .card.back { background:repeating-linear-gradient(45deg,#274b8f,#274b8f 6px,#1d3a70 6px,#1d3a70 12px);
    border-color:#152a52; }
  .card.back .mid { color:rgba(255,255,255,.35); font-size:18px; }
  .hand { display:flex; min-height:96px; }
  .bjrow { display:flex; align-items:center; gap:14px; margin:14px 0; }
  .bjrow .who { width:70px; color:var(--muted); font-size:13.5px; }
  .badge { font-size:13px; color:var(--muted); }
  .tablecenter { text-align:center; padding:22px 0; min-height:70px;
    border-top:1px dashed rgba(255,255,255,.18);
    border-bottom:1px dashed rgba(255,255,255,.18); }
  .big { font-size:18px; font-weight:600; }
  .panel { background:var(--surface); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-bottom:14px; }
  .label { color:var(--muted); font-size:12px; text-transform:uppercase;
    letter-spacing:.7px; margin-bottom:8px; }
  pre { margin:0; white-space:pre-wrap; font:11.5px/1.5 ui-monospace,Menlo,monospace;
    color:var(--muted); max-height:220px; overflow:auto; }
  .chips { color:var(--gold); font-weight:700; font-size:18px; }
  .hist { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
  .chip { padding:2px 9px; border-radius:10px; font-size:12px; background:var(--canvas);
    border:1px solid var(--line); }
  .chip.win { border-color:var(--ok); color:var(--ok); }
  .chip.lose { border-color:var(--danger); color:var(--danger); }
  .hint { color:var(--muted); font-size:12.5px; }
</style>
</head>
<body>
<header><div class="brand">🎯 21点 — Jev 牌桌</div>
  <div style="flex:1"></div><div class="hint">裁判：基本策略替身（非真实 Jev）</div></header>
<div class="banner">模型应答来自本地基本策略替身。单副牌低于 15 张自动重洗（SplitMix64 确定性）；BJ 赔 3:2，庄家全 17 停；模型看到手牌价值、庄家明牌、鞋组成与爆牌概率，看不到暗牌与鞋序。</div>
<main><section class="table" id="table"></section><aside id="side"></aside></main>
<script>
const suitClass = n => (n.includes('♥') || n.includes('♦')) ? 'card red' : 'card';
const cardHTML = n => `<div class="${suitClass(n)}"><span>${n.replace(/♠|♥|♣|♦/,'')}</span><span class="mid">${n.match(/♠|♥|♣|♦/)?.[0] ?? ''}</span></div>`;
const cardBack = `<div class="card back"><span></span><span class="mid">✦</span></div>`;

function panel(title, body) {
  return `<div class="panel"><div class="label">${title}</div>${body}</div>`;
}

async function tick() {
  try {
    const s = await (await fetch('/state.json', {cache:'no-store'})).json();
    const table = document.getElementById('table');
    const side = document.getElementById('side');
    const hideHole = s.hole_hidden && s.dealer.length === 2;
    const dealerCards = s.dealer.map((n, i) =>
      (i === 0 && hideHole) ? cardBack : cardHTML(n)).join('');
    table.innerHTML = `
      <div class="bjrow"><div class="who">🎩 庄家</div><div class="hand">${dealerCards}</div>
        <span class="badge">价值 ${hideHole ? '?' : s.dealer_value}</span></div>
      <div class="tablecenter"><div class="big">${s.phase==='player'?'轮到你决策':(s.outcome ?? s.phase)}</div></div>
      <div class="bjrow"><div class="who">🧑 玩家</div><div class="hand">${s.player.map(cardHTML).join('')}</div>
        <span class="badge">价值 <b>${s.player_value}</b></span></div>`;
    const chips = `<span class="chips">💰 ${s.bank}</span> <span class="badge">注 ${s.bet}</span>
      <span class="badge">第 ${s.round} 轮 · 第 ${s.episodes} 副</span>`;
    const hist = (s.history||[]).slice().reverse().map(h =>
      `<span class="chip ${h.delta>0?'win':(h.delta<0?'lose':'')}">${h.outcome} ${h.delta>=0?'+':''}${h.delta}</span>`).join('');
    side.innerHTML =
      panel('资金', `<div class="scoreline">${chips}</div><div class="hist">${hist}</div>`) +
      panel('裁判刚回答', `<div class="big">${s.answer ?? '—'}</div>`) +
      panel('模型被问到的问题 · action', `<pre>${s.question.state || '—'}</pre>`) +
      panel('合法动作', (s.question.legal||[]).join(' · ') || '—') +
      panel('此刻爆牌概率', `<div class="big">${s.question.bust===null||s.question.bust===undefined?'—':(s.question.bust*100).toFixed(1)+'%'}</div>`);
  } catch (e) {}
  setTimeout(tick, 450);
}

tick();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    session: BlackjackSession

    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/blackjack"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode())
        elif path == "/state.json":
            self._send(200, "application/json", json.dumps(self.session.snapshot()).encode())
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8802)
    parser.add_argument("--pace", type=float, default=0.7, help="seconds between actions")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--judge", choices=("local", "jev"), default="local")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    session = BlackjackSession(make_judge(args.judge), pace=args.pace, seed=args.seed)
    Handler.session = session
    threading.Thread(target=session.run, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}/"
    print("21点 — Jev 牌桌")
    print(f"  地址   {url}")
    print(f"  裁判   {args.judge}" + ("（本地基本策略替身）" if args.judge == "local" else "（真实 TypeSafe API）"))
    print("  Ctrl+C 结束")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        session.alive = False
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
