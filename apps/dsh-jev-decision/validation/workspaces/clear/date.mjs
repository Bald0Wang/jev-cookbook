// 空字符串返回 null；其他输入保持原有 Date 行为。
export function parseDate(input) {
  if (typeof input === 'string' && input.trim() === '') {
    return null;
  }
  return new Date(input);
}
