import { Link } from 'react-router-dom';

const cards = [
  { path: '/games/snake', title: '贪吃蛇', text: '让 Jev 自己控制蛇，观察它如何从局部判断走向轨迹和反馈闭环。', kind: '实时游戏' },
  { path: '/games/minesweeper', title: '扫雷', text: '让 Jev 选择翻格或插旗，比较直接猜测和确定性线索优先。', kind: '实时游戏' },
  { path: '/compare/snake', title: '贪吃蛇对比', text: '同一个时间轴，左边原始 Jev，右边约束后的真实 trace。', kind: '对比实验' },
  { path: '/compare/minesweeper', title: '扫雷对比', text: '同一张雷盘，比较两种不同信息传递方式造成的结果。', kind: '对比实验' },
];

export default function HomePage() {
  return <div className="home-page">
    <section className="home-hero"><div><p className="eyebrow">JEV GAMES / REACT MIGRATION</p><h1>先把问题交代完整，<em>再让模型做决定。</em></h1></div><p>这是一个用小游戏观察结构化 AI 决策的实验场。页面、游戏、trace 和 Jev 适配层正在统一到同一个 React 项目中。</p></section>
    <section className="home-section"><div className="section-kicker">四个入口</div><div className="route-grid">{cards.map(card => <Link className="route-card" to={card.path} key={card.path}><span>{card.kind}</span><h2>{card.title}</h2><p>{card.text}</p><b>打开页面 →</b></Link>)}</div></section>
    <section className="principles"><div><b>状态</b><span>模型看到了什么？</span></div><div><b>动作</b><span>模型可以选择什么？</span></div><div><b>反馈</b><span>上一轮发生了什么？</span></div></section>
  </div>;
}
