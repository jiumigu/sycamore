export function smartTruncate(text: string, maxLength: number = 8): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}
