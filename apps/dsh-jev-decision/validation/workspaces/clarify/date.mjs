// 空字符串返回 null；其余输入保持原有的 Date 解析行为。
export function parseDate(input) {
  if (input === '') {
    return null;
  }
  return new Date(input);
}
