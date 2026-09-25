import { NavLink, Route, Routes } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SnakeComparePage from './pages/SnakeComparePage';
import MinesweeperComparePage from './pages/MinesweeperComparePage';
import SnakeGamePage from './pages/SnakeGamePage';
import MinesweeperGamePage from './pages/MinesweeperGamePage';

const routes = [
  { to: '/', label: '总览' },
  { to: '/games/snake', label: '贪吃蛇' },
  { to: '/games/minesweeper', label: '扫雷' },
  { to: '/compare/snake', label: '贪吃蛇对比' },
  { to: '/compare/minesweeper', label: '扫雷对比' },
];

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-nav">
        <NavLink className="app-brand" to="/">
          <span className="app-mark">J</span>
          <span><b>Jev Games</b><small>structured decisions in play</small></span>
        </NavLink>
        <nav>{routes.map(route => <NavLink key={route.to} to={route.to}>{route.label}</NavLink>)}</nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/games/snake" element={<SnakeGamePage />} />
          <Route path="/games/minesweeper" element={<MinesweeperGamePage />} />
          <Route path="/compare/snake" element={<SnakeComparePage />} />
          <Route path="/compare/minesweeper" element={<MinesweeperComparePage />} />
        </Routes>
      </main>
    </div>
  );
}
