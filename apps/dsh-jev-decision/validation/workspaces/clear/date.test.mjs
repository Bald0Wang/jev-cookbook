import test from 'node:test';
import assert from 'node:assert/strict';
import { parseDate } from './date.mjs';

test('ISO 日期解析保留原有行为', () => {
  assert.equal(parseDate('2026-09-23T00:00:00Z').toISOString(), '2026-09-23T00:00:00.000Z');
});

test('空字符串返回 null 而不是 Invalid Date', () => {
  assert.equal(parseDate(''), null);
});

test('仅含空白字符的字符串返回 null', () => {
  assert.equal(parseDate('   '), null);
});

test('无法解析的字符串仍返回 Invalid Date，不受空字符串分支影响', () => {
  assert.ok(Number.isNaN(parseDate('not-a-date').getTime()));
});
