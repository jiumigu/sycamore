import { marked } from 'marked'

/**
 * 把 Markdown 文本渲染成 HTML 片段。
 *
 * **唯一实现** —— 需要渲染 Markdown 的地方一律走这里，不要在组件里各写一遍
 * `marked.parse(...)`（同一条规则散成三份，早晚分叉；项目里已经有过
 * privacy / format 两份实现打架的教训）。
 *
 * 两个选项都是刻意的：
 * - `breaks: true`：单个换行就成行。中文手记与 AI 回答普遍是「一行一句」，
 *   不这么设的话整段会被粘成一大坨，读起来完全不是作者写的样子。
 * - `gfm: true`：表格 / 任务列表 / 删除线这些日常写法要能认出来。
 *
 * ⚠️ 返回值是 **HTML 片段**，调用方必须用 `v-html` 渲染，并配 `:deep()` 样式 ——
 * scoped 样式打不进 `v-html` 运行时产生的节点。
 *
 * ⚠️ 不做 HTML 转义（marked 默认放行原始 HTML）。数据源是自用系统的自有内容，
 * 与既有渲染点（AskAnswerNode / LogseqViewer）保持一致；**若将来接入外部文本，
 * 必须在这里补消毒，不要在调用点各补一遍**。
 */
export function renderMarkdown(text: string | null | undefined): string {
  if (!text) return ''
  // 显式 async:false —— 否则 marked 的重载吐 `string | Promise<string>`，
  // 而这里要的就是同步结果（调用点是 computed，不能 await）
  return marked.parse(normalize(text), { breaks: true, gfm: true, async: false })
}

/**
 * 行首 `###` 后面直接跟文字时补一个空格。
 *
 * CommonMark 要求标题标记后必须有空格，`###1. 每天记录三件事` **不算标题**，
 * 会被整行原样吐出来 —— 界面上就是一行带 `###` 的裸符号。
 * 手写金句 / AI 生成的回答普遍漏这个空格，所以统一在这里补，不要求数据源守规矩。
 *
 * ⚠️ 断言必须是 `(?=[^\s#])` 而不是 `(?=\S)`：
 * `#{1,6}` 是贪婪的，用 `(?=\S)` 时 `## 正常标题` 会回溯成只匹配一个 `#`
 * （因为 `#` 也算非空白），替换后变成 `# # 正常标题`，**渲染成一堆坏掉的 h1**。
 * 要求后一个字符「非空白**且非 `#`**」，回溯路径才全部被堵死。
 *
 * 只锚行首，正文里的 `C#`、`第#1名` 不受影响。
 */
function normalize(text: string): string {
  return text.replace(/^(#{1,6})(?=[^\s#])/gm, '$1 ')
}
