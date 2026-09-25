import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const gameRoot = join(root, 'games', 'gridloop');
const output = join(root, 'showcase', 'jev-games', 'traces', 'snake-baseline-live.json');
const envText = await readFile(join(gameRoot, '.env'), 'utf8');
for (const line of envText.split(/\r?\n/)) { const match = line.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/); if (match && !process.env[match[1]]) process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, ''); }

const grid = 20;
let snake = [{x: 9, y: 10}, {x: 8, y: 10}, {x: 7, y: 10}];
let food = {x: 14, y: 10};
let direction = {x: 1, y: 0};
let score = 0;
const trace = [];
const vector = {up:{x:0,y:-1},down:{x:0,y:1},left:{x:-1,y:0},right:{x:1,y:0}};
const foods = [{x:14,y:10},{x:10,y:5},{x:3,y:15},{x:16,y:4}];
function legalMoves() { return Object.entries(vector).filter(([,next]) => { if (next.x === -direction.x && next.y === -direction.y) return false; const head = {x:snake[0].x + next.x,y:snake[0].y + next.y}; return head.x >= 0 && head.x < grid && head.y >= 0 && head.y < grid && !snake.some(part => part.x === head.x && part.y === head.y); }).map(([name]) => name); }
async function askJev(state) {
  const criteria = Object.fromEntries(state.legalMoves.map(move => [move, `Move the snake ${move}. Keep the head inside the board and approach the food.`]));
  const response = await fetch('https://api.typesafe.ai/v1/systemone', {method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${process.env.TYPESAFE_API_KEY}`},body:JSON.stringify({state,model:'jev-latest',questions:{move:{type:'choice',instructions:'Choose exactly one next direction from legalMoves. Use only the current board state and do not assume any hidden history.',criteria}}})});
  if (!response.ok) throw new Error(`TypeSafe ${response.status}`);
  return response.json();
}
for (let step=0; step<155; step++) {
  const state = {grid, snake:JSON.parse(JSON.stringify(snake)), food:{...food}, direction:{...direction}, score, legalMoves:legalMoves()};
  if (!state.legalMoves.length) { trace.push({step:step+1,state,answer:null,selected:null,scoreAfter:score,status:'game_over'}); break; }
  const answer = await askJev(state);
  const selected = answer?.answers?.move?.choice;
  if (!selected || !state.legalMoves.includes(selected)) { trace.push({step:step+1,state,answer,selected,status:'invalid'}); break; }
  const next = vector[selected];
  const head = {x:snake[0].x + next.x,y:snake[0].y + next.y};
  direction = next;
  snake.unshift(head);
  if (head.x === food.x && head.y === food.y) { score++; food = foods[score % foods.length]; } else snake.pop();
  const status = snake.some((part,index)=>index>0&&part.x===head.x&&part.y===head.y) ? 'game_over' : 'playing';
  trace.push({step:step+1,state,answer,selected,scoreAfter:score,status,timestamp:new Date().toISOString()});
  if (status === 'game_over') break;
}
await writeFile(output, JSON.stringify(trace));
console.log(JSON.stringify({steps:trace.length,score,output}));
