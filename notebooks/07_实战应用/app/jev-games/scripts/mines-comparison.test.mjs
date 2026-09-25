import test from 'node:test';
import assert from 'node:assert/strict';
import { makeBoard, initialGame, applyAction, makeRequest, deduce, neighbors } from './mines-comparison-core.mjs';

test('both runs start on identical reproducible board and do not mutate each other', () => {
  const board = makeBoard(20260922), a = initialGame(board), b = initialGame(board);
  assert.deepEqual(board, makeBoard(20260922)); assert.deepEqual(a,b);
  assert.equal(board.mines.length,20); assert.ok(!board.mines.includes(0));
  applyAction(a,board,{kind:'flag',cell:a.visible.indexOf('#')}); assert.notDeepEqual(a,b);
});
test('baseline offers reveal and flag; request contains no hidden mine map', () => {
  const initial = initialGame(makeBoard(20260922));
  for (const variant of ['baseline','shaped']) {
    const request = makeRequest(initial,variant);
    assert.deepEqual(request.payload.state.board.flat(), initial.visible);
    assert.equal(request.payload.state.minePositions,undefined);
    for (const q of Object.values(request.payload.questions)) if(q.type==='choice') assert.ok(Object.keys(q.criteria).length<=255);
  }
  assert.ok(makeRequest(initial,'baseline').kinds.includes('flag'));
});
test('deductions are supported by visible clues on 20 reproducible boards', () => {
  for (let seed=1;seed<=20;seed++) {
    const board=makeBoard(seed),game=initialGame(board),d=deduce(game.visible);
    for(const i of d.safe) assert.ok(!board.mines.includes(i));
    for(const i of d.mines) assert.ok(board.mines.includes(i));
  }
});
test('a mine ends either policy under the same rules; flags never reveal hidden mines', () => {
  const board=makeBoard(1), game=initialGame(board), mine=board.mines[0];
  applyAction(game,board,{kind:'reveal',cell:mine}); assert.equal(game.status,'lost'); assert.equal(game.visible[mine],'M');
  assert.throws(()=>applyAction(game,board,{kind:'flag',cell:1}));
});
