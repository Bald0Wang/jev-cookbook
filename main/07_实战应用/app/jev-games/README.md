# Mini Games

这里集中管理小游戏，每个游戏放在 `games/<game-name>/` 目录中，彼此独立运行。

## React 统一入口

React + TypeScript + Vite 项目位于 `apps/web/`，提供统一路由：

```text
/                    总览
/games/snake         贪吃蛇
/games/minesweeper   扫雷
/compare/snake       贪吃蛇对比
/compare/minesweeper 扫雷对比
```

启动前端：

```powershell
cd apps/web
npm run dev
```

## 当前游戏

- [Gridloop · Jev 贪吃蛇](games/gridloop/README.md)
- [Minesweeper · Jev 扫雷](games/minesweeper/README.md)
- [Jev Games Lab · 决策复盘](showcase/jev-games/README.md)
- [Werewolf · Jev 狼人杀](games/werewolf/README.md)
- [Poker · Jev 德州扑克](games/poker/README.md)

## 目录约定

```text
games/
  gridloop/
    index.html
    server.mjs
    package.json
    README.md
    .env              # 本地 key，不提交
```

以后新增游戏时，继续在 `games/` 下创建独立目录即可。
