# Gridloop · Jev 贪吃蛇

一个可以直接打开的贪吃蛇小游戏。点击“Jev 自动驾驶”后，Jev 会读取当前棋盘、蛇身、食物和合法方向，通过 TypeSafe 的 Choice 结构化输出直接决定下一步移动。

## 运行

```bash
npm start
```

然后打开 <http://localhost:4173>。

## 启用 Jev

在项目根目录创建 `.env` 文件，也就是 `D:\AI\jev\.env`，内容如下：

```env
TYPESAFE_API_KEY=你的 TypeSafe API key
```

也可以只在当前 PowerShell 会话里设置：

```bash
# PowerShell 临时设置
$env:TYPESAFE_API_KEY = "你的 TypeSafe API key"
npm start
```

页面中的输入框是开发调试入口，会把 key 仅放在当前页面内存中，再由服务端代理请求。正式使用时推荐 `.env` 或系统环境变量，不要把 key 写进 `index.html`。

Jev 请求使用 `POST https://api.typesafe.ai/v1/systemone`、模型 `jev-latest`，并行返回一个方向 Choice 和一个危险度 Noul。客户端还会把最近轨迹和一个安全 BFS 路线交给 Jev；若 Jev 置信度低、危险度高或检测到短周期循环，会优先采用安全路线。没有有效 key 时，自动驾驶会停止并提示配置问题，避免把本地规则误称为 Jev 决策。
