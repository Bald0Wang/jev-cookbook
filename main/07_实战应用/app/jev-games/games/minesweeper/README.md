# Minesweeper · Jev 扫雷

第二个小游戏。点击“Jev 自动扫雷”后，Jev 会直接选择翻开格子或插旗，并读取当前可见棋盘、确定安全格和疑似雷区。棋盘为 14×14，包含 20 颗雷，给 Jev 更多连续推理和猜测空间。自动驾驶会先处理单格约束和子集约束推导出的确定雷，再处理安全格或风险猜测。它遵循标准扫雷规则，选中雷格时会正常结束整局。

## 运行

```powershell
cd D:\AI\jev\games\minesweeper
npm start
```

打开 <http://localhost:4174>。

`.env` 需要包含 `TYPESAFE_API_KEY`。如果已经在 `games/gridloop/.env` 配置过，可以复制一份到当前目录。API key 不会被提交到 Git。
