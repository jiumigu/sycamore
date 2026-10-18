import type { WorkCapture } from '../types/workTypes'

/** 只认真正的省略号（U+2026）—— 别用 `\.`：
 *  标题里本来就有的句号会被误当成「这里省略了」，然后去比对出错误的公共前缀。 */
const ELLIPSIS_TAIL = /…$/

function flat(s: string | null | undefined): string {
  return (s ?? '').replace(/\s+/g, ' ').trim()
}

/**
 * 一条捕获在列表里该怎么显示 —— **收口台与待提炼明细共用这一份**。
 *
 * 🔴 为什么需要它：**标题与摘要是同一段话**。
 *    摘录 / AI 问答这两类，打勾那一刻写下的「标题」就是正文的开头
 *    （见 `QuoteManager` / `AskLibrary` 的 `capture()` 调用），
 *    而「摘要」是正文全文。原样并排摆出来 = **同一句话连着出现两遍**，
 *    那是用两行说一行的事，比只显示一行更糟：人会以为自己看错了。
 *
 *    ⇒ 只把「摘要比标题多出来的那一段」当补充正文，并带一个「…」说明是接续。
 *
 * ⚠️ 这是**显示层归一化，不动存量数据** ——
 *    标题是打勾那一刻写下的，改它等于改写历史（项目铁律）。
 */
export function captureText(c: WorkCapture): { title: string; body: string } {
  const title = flat(c.title)
  const excerpt = flat(c.excerpt)

  if (!excerpt) return { title, body: '' }
  if (!title) return { title: excerpt, body: '' }
  if (excerpt === title) return { title, body: '' }

  // 标题以「…」收尾时，比对的应是不带省略号的那截
  const head = title.replace(ELLIPSIS_TAIL, '')
  if (head && excerpt.startsWith(head)) {
    const rest = excerpt.slice(head.length).trim()
    if (!rest) return { title, body: '' }
    // 标题自己已经带着「…」了，就不必再补一个（否则写成「…情，有哪些…」）
    return { title, body: (ELLIPSIS_TAIL.test(title) ? '' : '…') + rest }
  }

  return { title, body: excerpt }
}
