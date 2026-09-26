# Jev Games Lab · React 统一入口实验报告

## 1. 这是什么

三个游戏 + 两组对比实验的 React + TypeScript + Vite 统一入口（`/` 总览、`/games/snake`、`/games/minesweeper`、`/compare/*`），把页面、游戏、trace 与 Jev 适配层统一到一个项目。

## 2. 实验意义

三本独立 notebook 各自能跑之后，"同一时间轴上的对比"才可能：贪吃蛇对比页在**同一个时间轴**上并排原始 Jev 与约束后 Jev 的真实 trace，扫雷对比页比较两种信息传递方式的结果——统一入口让"控制变量"成为产品功能而不是手动操作。

## 3. 要回答的问题

1. 构建产物是否完整可用（npm install → build → 静态托管）？
2. 总览页四个入口与路由是否正常？

## 4. 实验怎么做的

`npm install && npm run build`（Vite 构建到 `dist/`），`dist` 起静态服务后用浏览器打开总览页截图（`figures/overview.png`）。

## 5. Jev 每一步怎么工作

入口本身不做判断；`/games/*` 页面复用各游戏的 Jev 适配层（与独立版相同的 systemone 调用），`/compare/*` 读取 trace 做时间轴对齐。

## 6. 实验结果与说明

- 构建 **501ms** 完成：`dist/assets/index-*.js` 298.96 kB（gzip 95.43 kB）+ CSS 15.75 kB；
- 总览页正常渲染：主标语「先把问题交代完整，再让模型做决定」，四个入口卡片（贪吃蛇/扫雷/贪吃蛇对比/扫雷对比）全部可点。

## 7. 成本与耗时

npm install + build 约 40 秒（本机网络）；静态托管零成本。运行时成本与各游戏相同。

## 8. 结论与后续

React 迁移可用，构建产物 299KB 在正常范围。后续：把 trace 对比接上真实对局数据；统一三个游戏的 Jev 适配层版本。
