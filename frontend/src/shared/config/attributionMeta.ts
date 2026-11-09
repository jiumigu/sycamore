/** 六类归因的**标签配色**（`color` 文字色 + `bg` 浅底，成对使用）
 *
 * 词表真源是 `backend/apps/temporal/constants.py` 的 `ATTRIBUTION_CHOICES` ——
 * 这里**只有配色，没有词表**。加一个 L1 词时后端那份先动，这里补一格；
 * 漏补不会报错，只会让那个词在用到它的格子里**静默**落到 `|| 兜底` 的灰。
 *
 * ⚠️ 与 temporal 侧的 `ATTRIBUTION_COLOR_MAP`（单色填充、给热力格用）**用途不同**，
 *    刻意不同色，别去「统一」它们 —— 那不是漂移。
 *
 * 📌 v3.64.19 从 `modules/redemption/types/redemptionTypes.ts` 搬到这里：
 *    阶段账本（selfrun）要用同一份，而赎回期模块第 4 轮就下线了。
 *    留在原处的话，两个模块会各存一张配色表，删模块时这张表**跟着被删**，
 *    而账本那边还在用 —— 那时才发现，就是一片灰。
 * ✅ v3.64.20 赎回期已下线，现在它是**唯一一份**：temporal（热力格）、
 *    selfrun 账本、时间统计页都从这里取。redemption 模块里那个 re-export
 *    会随页面文件一起被人工删除，删之前不要先去改它。
 */
export const ATTRIBUTION_META: Record<string, { color: string; bg: string }> = {
  成长: { color: '#7C3AED', bg: '#F3E8FF' },
  体验: { color: '#EA580C', bg: '#FFEDD5' },
  关系: { color: '#0D9488', bg: '#CCFBF1' },
  维持: { color: '#2563EB', bg: '#DBEAFE' },
  谋生: { color: '#D97706', bg: '#FEF3C7' },
  流失: { color: '#DC2626', bg: '#FEE2E2' },
}

/** 取一格配色；词表里有、这里没有时给中性灰（**不抛错** —— 少一格配色不该白屏） */
export function attrMeta(key: string): { color: string; bg: string } {
  return ATTRIBUTION_META[key] ?? { color: '#6B7280', bg: '#F3F4F6' }
}
