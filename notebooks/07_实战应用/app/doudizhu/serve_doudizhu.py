"""Dou Dizhu (斗地主) spectator server: three reference-policy seats, CSS playing cards.

Pure standard library for the local judge; the same questions go to the real Jev with
``--judge jev`` and ``TYPESAFE_API_KEY`` (needs ``pip install typesafe-sdk``).

Run:  python3 serve_doudizhu.py --port 8801 --host 0.0.0.0
Then open http://127.0.0.1:8801
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import doudizhu_game as D


class DoudizhuSession:
    def __init__(self, judge, pace: float) -> None:
        self.lock = threading.Lock()
        self.judge = judge
        self.pace = pace
        self.state = D.make_doudizhu(seed=1)
        self.last_question: dict | None = None
        self.last_answer: str | None = None
        self.last_probabilities: dict = {}
        self.score = {'landlord_win': 0, 'peasants_win': 0}
        self.episode = 0
        self.alive = True

    def run(self) -> None:
        while self.alive:
            if self.state['done']:
                time.sleep(2.5)
                if not self.alive:
                    return
                self.episode += 1
                self.state = D.make_doudizhu(seed=1 + self.episode)
                with self.lock:
                    self.last_question = None
                    self.last_answer = None
                continue
            with self.lock:
                request = D.render_request(self.state)
                record = D.make_record(self.state, 'dev')
                self.last_question = request
                self.last_probabilities = record['gold_probs']['move']
            time.sleep(self.pace)
            if not self.alive:
                return
            answer = self.judge(request)
            moves = {f"m{i}": m for i, m in enumerate(
                D.gen_moves(self.state['hands'][self.state['turn']], self.state['trick']))}
            move = moves.get(answer.get('move'))
            if move is None:
                move = {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0}
            with self.lock:
                self.last_answer = answer.get('move')
            try:
                self.state = D.step(self.state, move)
            except ValueError:
                self.state = D.step(self.state, {'type': 'pass', 'cards': [], 'rank': -1, 'length': 0})
            if self.state['done']:
                with self.lock:
                    self.score[self.state['outcome']] += 1

    def snapshot(self) -> dict:
        with self.lock:
            state = self.state
            seats = []
            for seat in range(3):
                on_turn = seat == state['turn'] and not state['done']
                last_play = None
                for entry in reversed(state['history']):
                    if entry['seat'] == seat:
                        last_play = {
                            'name': D.move_name(entry),
                            'cards': [D.card_name(c) for c in entry['cards']],
                            'is_bomb': entry['type'] in ('bomb', 'rocket'),
                        }
                        break
                seats.append({
                    'seat': seat,
                    'role': 'landlord' if seat == state['landlord'] else 'peasant',
                    'cards': [D.card_name(c) for c in sorted(state['hands'][seat], key=D.rank_of)]
                    if on_turn else [],
                    'card_count': len(state['hands'][seat]),
                    'on_turn': on_turn,
                    'last_play': last_play,
                })
            trick = state['trick']
            return {
                'seats': seats,
                'turn': state['turn'],
                'landlord': state['landlord'],
                'done': state['done'],
                'outcome': state['outcome'],
                'multiplier': state['multiplier'],
                'episode': self.episode,
                'score': self.score,
                'trick': {'name': D.move_name(trick),
                          'cards': [D.card_name(c) for c in trick['cards']],
                          'owner': trick['owner'], 'is_bomb': trick['type'] in ('bomb', 'rocket')}
                if trick else None,
                'question': {
                    'state': self.last_question['state'] if self.last_question else None,
                    'moves': self.last_question['moves'] if self.last_question else [],
                },
                'answer': self.last_answer,
                'probabilities': self.last_probabilities,
            }


def local_judge(request: dict) -> dict:
    """Stand-in judge reading only the published move list.

    Leading: unload the biggest non-explosive combination.  Following: the smallest
    sufficient play, else pass.  Never spends bombs — that is where a stronger judge
    (Jev) could shine.
    """
    moves = request['moves']
    passing = [m for m in moves if m['type'] == 'pass']
    plays = [m for m in moves if m['type'] != 'pass']
    if passing:  # following
        plain = [m for m in plays if m['type'] not in ('bomb', 'rocket')]
        if not plain:
            return {'move': passing[0]['id']}
        best = min(plain, key=lambda m: (max(m['cards']), len(m['cards'])))
        return {'move': best['id']}
    pool = [m for m in plays if m['type'] not in ('bomb', 'rocket')] or plays
    best = max(pool, key=lambda m: (len(m['cards']), -max(m['cards'])))
    return {'move': best['id']}


def make_judge(kind: str):
    if kind == 'local':
        return local_judge
    import typesafe_sdk

    client = typesafe_sdk.TypeSafeClient()

    def jev_judge(request: dict) -> dict:
        response = client.system_one(state=request['state'], questions=request['questions'])
        return {'move': str(response.answers['move'].choice)}

    return jev_judge


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>斗地主 — Jev 牌桌</title>
<style>
  :root { --canvas:#0b1013; --felt:#0e5c36; --felt2:#0a4a2c; --surface:#16191f;
    --line:#303640; --text:#eceff3; --muted:#8d96a3; --gold:#e6c26a; }
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
    border:10px solid #5a3a22; border-radius:22px; padding:20px; min-height:560px;
    box-shadow:inset 0 0 60px rgba(0,0,0,.45); }
  .card { display:inline-flex; flex-direction:column; justify-content:space-between;
    width:52px; height:74px; background:#fdfdf8; border-radius:6px; padding:3px 5px;
    margin-right:-18px; box-shadow:1px 2px 5px rgba(0,0,0,.45);
    font:700 13px/1 ui-monospace,Menlo,monospace; color:#1a1a1e;
    border:1px solid #c9c9c2; position:relative; }
  .card .mid { position:absolute; inset:0; display:flex; align-items:center;
    justify-content:center; font-size:22px; opacity:.85; }
  .card.red { color:#c0392b; }
  .card.back { background:repeating-linear-gradient(45deg,#274b8f,#274b8f 6px,#1d3a70 6px,#1d3a70 12px);
    border-color:#152a52; }
  .card.back .mid { color:rgba(255,255,255,.35); font-size:16px; }
  .hand { display:flex; padding-left:18px; min-height:78px; flex-wrap:wrap; }
  .seat { margin:14px 0; padding:10px 12px; border-radius:12px;
    background:rgba(0,0,0,.28); border:1px solid rgba(255,255,255,.08); }
  .seat.on { border-color:var(--gold); box-shadow:0 0 18px rgba(230,194,106,.35); }
  .seat .head { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
  .badge { font-size:12px; color:var(--muted); }
  .crown { font-size:16px; }
  .played { min-height:80px; padding:6px 4px; }
  .played .msg { color:#cfe8d8; font-size:13px; }
  .played .msg.bomb { color:#ffb3a7; font-weight:700; animation:shake .4s; }
  .tablecenter { text-align:center; padding:16px 0; min-height:100px;
    border-top:1px dashed rgba(255,255,255,.18);
    border-bottom:1px dashed rgba(255,255,255,.18); }
  .big { font-size:17px; font-weight:600; }
  .panel { background:var(--surface); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin-bottom:14px; }
  .label { color:var(--muted); font-size:12px; text-transform:uppercase;
    letter-spacing:.7px; margin-bottom:8px; }
  pre { margin:0; white-space:pre-wrap; font:11.5px/1.5 ui-monospace,Menlo,monospace;
    color:var(--muted); max-height:220px; overflow:auto; }
  .mv { display:flex; justify-content:space-between; font-size:12.5px; padding:2px 0; }
  .mv .bar { height:6px; background:var(--accent,#89a6c1); border-radius:3px; }
  .scoreline { display:flex; gap:16px; font-size:14px; }
  .scoreline b { font-size:18px; }
  .banner.win { position:fixed; inset:auto 0 0 0; text-align:center; padding:14px;
    background:rgba(99,176,106,.92); color:#06220c; font-size:19px; font-weight:700;
    animation:rise .35s; }
  @keyframes shake { 0%,100%{transform:translateX(0)} 20%{transform:translateX(-6px)}
    40%{transform:translateX(6px)} 60%{transform:translateX(-4px)} 80%{transform:translateX(4px)} }
  @keyframes rise { from{transform:translateY(100%)} to{transform:translateY(0)} }
  .hint { color:var(--muted); font-size:12.5px; }
</style>
</head>
<body>
<header><div class="brand">🃏 斗地主 — Jev 牌桌</div>
  <div style="flex:1"></div><div class="hint">裁判：本地规则替身（非真实 Jev）</div></header>
<div class="banner">模型应答来自本地规则替身。54 张牌由 SplitMix64 确定性发牌；裁判只读公开事实（自己的手牌、别家张数、桌面牌型），看不到任何暗牌。</div>
<main><section class="table" id="table"></section><aside id="side"></aside></main>
<script>
const suitClass = n => (n.includes('♥') || n.includes('♦')) ? 'card red' : 'card';
const cardHTML = n => `<div class="${suitClass(n)}"><span>${n.replace(/♠|♥|♣|♦/,'')}</span><span class="mid">${n.match(/♠|♥|♣|♦/)?.[0] ?? '🃏'}</span></div>`;
const cardBack = `<div class="card back"><span></span><span class="mid">✦</span></div>`;
let lastTrickKey = '';

function panel(title, body) {
  return `<div class="panel"><div class="label">${title}</div>${body}</div>`;
}

async function tick() {
  try {
    const s = await (await fetch('/state.json', {cache:'no-store'})).json();
    const table = document.getElementById('table');
    const side = document.getElementById('side');
    const seats = s.seats.map(seat => {
      const crown = seat.role === 'landlord' ? '<span class="crown">👑</span>' : '<span class="crown">🧑</span>';
      const cards = seat.cards.length
        ? '<div class="hand">' + seat.cards.map(cardHTML).join('') + '</div>'
        : '<div class="hand">' + cardBack.repeat(Math.min(seat.card_count, 12)) + '</div>';
      const played = seat.last_play
        ? `<div class="played"><div class="msg ${seat.last_play.is_bomb?'bomb':''}">${seat.last_play.is_bomb?'💥 ':''}${seat.last_play.name}</div></div>`
        : '<div class="played"><div class="msg" style="opacity:.4">—</div></div>';
      return `<div class="seat ${seat.on_turn?'on':''}">
        <div class="head">${crown}<b>座位 ${seat.seat}</b>
          <span class="badge">${seat.role==='landlord'?'地主':'农民'} · 剩 ${seat.card_count} 张</span>
          ${seat.on_turn?'<span class="badge" style="color:var(--gold)">◆ 决策中</span>':''}</div>
        ${cards}${played}</div>`;
    }).join('');
    const trickHTML = s.trick
      ? `<div class="trick">${s.trick.cards.map(cardHTML).join('')}<div class="msg">桌面：${s.trick.name}</div></div>`
      : '<div class="msg" style="opacity:.5">无有效出牌 —— 重新领出</div>';
    table.innerHTML = seats +
      `<div class="tablecenter"><div class="big">倍率 ×${s.multiplier}</div><div class="trick" id="trick">${trickHTML}</div></div>` +
      (s.done ? `<div class="banner win">🎉 ${s.outcome==='landlord_win'?'地主胜利':'农民胜利'} · 第 ${s.episode+1} 局结束，即将开局</div>` : '');
    const moves = (s.question.moves || []).map(m => {
      const p = ((s.probabilities || {})[m.id] || 0) * 100;
      const chosen = s.answer === m.id;
      return `<div class="mv"><span>${chosen?'▶ ':''}${m.name}</span><span>${p.toFixed(0)}%</span></div>
        <div class="bar" style="width:${p}%; margin-bottom:4px;"></div>`;
    }).join('');
    side.innerHTML =
      panel('比分', `<div class="scoreline"><span>👑 地主胜 <b>${s.score.landlord_win}</b></span>
        <span>🧑 农民胜 <b>${s.score.peasants_win}</b></span><span>第 <b>${s.episode+1}</b> 局</span></div>`) +
      panel('裁判刚回答', `<div class="big">${s.answer ?? '—'}</div>`) +
      panel('模型被问到的问题 · move', `<pre>${s.question.state || '—'}</pre>`) +
      panel('合法动作与参考概率', moves || '—');
    const trickEl = document.getElementById('trick');
    const key = JSON.stringify(s.trick);
    if (trickEl && s.trick && key !== lastTrickKey && s.trick.is_bomb) {
      table.style.animation = 'shake .4s';
      setTimeout(() => table.style.animation = '', 450);
    }
    lastTrickKey = key;
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
    session: DoudizhuSession

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
        if path in ("/", "/index.html", "/doudizhu"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode())
        elif path == "/state.json":
            self._send(200, "application/json", json.dumps(self.session.snapshot()).encode())
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8801)
    parser.add_argument("--pace", type=float, default=0.7, help="seconds between moves")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--judge", choices=("local", "jev"), default="local")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    session = DoudizhuSession(make_judge(args.judge), pace=args.pace)
    session.state = D.make_doudizhu(seed=args.seed)
    Handler.session = session
    threading.Thread(target=session.run, daemon=True).start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}/"
    print("斗地主 — Jev 牌桌")
    print(f"  地址   {url}")
    print(f"  裁判   {args.judge}" + ("（本地规则替身）" if args.judge == "local" else "（真实 TypeSafe API）"))
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
