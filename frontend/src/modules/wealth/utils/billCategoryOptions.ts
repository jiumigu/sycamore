/**
 * 记账表单的「分类 → 子分类」联动 —— 唯一实现。
 *
 * 🔴 为什么抽出来：`QuickBillForm`（月度页的记一笔弹窗）与
 *    `QuickBillInlineForm`（页头快速记录的记账页签）都要这份联动。
 *    两处各写一遍 = 同一事实两把尺子 —— 改了一处忘了另一处，
 *    表现出来的症状是「同一个分类，两个入口给出的子分类候选不一样」，
 *    而且不报错、不白屏，只有用户觉得「怎么这里选不到」。
 *
 * ⚠️ 候选**只有一个来源**：后端 `GET /wealth/classify/bill-options/`。
 *    本模块只做「选哪个桶」，不持有任何分类常量、不排序、不去重。
 */
import type { BillCategoryOption, BillCategoryOptions } from '../types/wealthTypes'

/**
 * 子分类候选：选了分类就只给该分类下的，没选（或该分类还没历史）就给全局。
 *
 * ⚠️ **该分类没有历史时必须回退全局**，不能给空列表：分类可以在口径配置里先行
 *    登记（那时账本里一条记录都没有），此时若只给空列表，用户会觉得
 *    「刚建好的分类一个子分类都选不了」。
 *
 * 🔴 回退用的是后端下发的 `subcategories_all`，**不是**把 `subcategories` 自己拍平 ——
 *    拍平就得在前端再决定一次顺序，那又是一份局部口径（第一版就踩了：
 *    按各分类键序拼接，把「早午晚餐（3026 笔）」排到了「公交（134 笔）」后面）。
 */
export function pickSubcategoryOptions(
  options: BillCategoryOptions | null | undefined,
  category: string,
): BillCategoryOption[] {
  if (!options) return []

  if (category) {
    const grouped = options.subcategories?.[category]
    if (grouped && grouped.length) return grouped
  }

  return options.subcategories_all ?? []
}

/**
 * 未选分类时说明「这是全部子分类」，省得有人以为候选丢了。
 *
 * ⚠️ 两个表单的可用宽度不同，文案也不同：宽表单（弹窗）说「可选（全部）」，
 *    窄表单（页头面板，半宽约 190px）只留「全部」，否则会被省略号吃掉。
 */
export function subcategoryPlaceholder(category: string, narrow = false): string {
  if (category) return '可选'
  return narrow ? '全部' : '可选（全部）'
}
