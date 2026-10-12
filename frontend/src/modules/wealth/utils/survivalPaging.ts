/**
 * 生存资源 · 分页判据（唯一实现）
 *
 * 2026-10-10 起，本模块的**四个**列表都分了页：
 *     物品清单（v3.60.24）· 实盘盘点记录 · 生存时长快照 · 库存流水（v3.60.26）
 *
 * 四处各写一份「每页几条、分页栏什么时候出现」，迟早会分叉 ——
 * 而分叉是**静默**的：用户只看到「这一块的行为和别处不一样」，
 * 没有任何一处会报错。⇒ 常量与判据收在这里，组件只做参数适配。
 *
 * ⚠️ 这里**只有**「切哪一段」的算术，没有「切完之后别的东西怎么办」——
 *    后者是本类最容易错的地方，判据各写在各组件里：
 *      · **结果集 / 计数 / 列渲染判据仍读全量**，切片只喂给 `el-table`
 *      · **先排全量、再切片**（切片后排序只排当前页，而表头箭头照常高亮）
 *      · **筛选一变回第 1 页**
 *      · 「行合并表」的边界必须落在**记录之间**（见盘正面板的注释）
 */

/**
 * 每页条数的可选项。**第一个是最小值**，分页栏的显示条件要用它。
 *
 * ⚠️ 别写成 `as const` —— 那会得到 readonly 元组，而 `el-pagination` 的
 *    `page-sizes` 收 `number[]`，传 readonly 会在类型检查里直接红。
 */
export const MIN_PAGE_SIZE = 10

export const PAGE_SIZE_OPTIONS: number[] = [MIN_PAGE_SIZE, 20, 50, 100]

/** 默认每页条数 —— 四个列表一致，用户不必记「哪块默认多少」 */
export const DEFAULT_PAGE_SIZE = 20

/**
 * 分页栏该不该出现。
 *
 * 🔴 判据是「**存在**能让它分页的每页条数」，**不是**「当前每页条数下有多页」。
 *    写成后者：用户选一次「100 条/页」⇒ `50 > 100` 为假 ⇒ **分页栏连同每页条数
 *    选择器一起消失**，他再也调不回 20（除非数据继续增长）——
 *    而选 100 是「一屏看全部」的正常用法，不是误操作。
 *
 *    ⇒ **出口不能自己关掉自己。**
 */
export function shouldShowPager(total: number): boolean {
  return total > MIN_PAGE_SIZE
}

/** 总页数（至少 1 —— 「一页都没有」不是一个可展示的状态） */
export function pageCountOf(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize))
}

/**
 * 把页码夹回合法范围。
 *
 * ⚠️ 什么时候会越界：删掉当前页最后一条、改筛选后结果变少、翻页期间别处写入。
 *    不夹的后果是停在一张**空表**上 —— 而它读作「我的数据没了」，
 *    不是「页码超了」。
 */
export function clampPage(page: number, total: number, pageSize: number): number {
  return Math.min(Math.max(1, page), pageCountOf(total, pageSize))
}

/** 当前页在**原始数组**上的切片区间 `[start, end)` */
export function pageSlice(page: number, pageSize: number): [number, number] {
  const start = (Math.max(1, page) - 1) * pageSize
  return [start, start + pageSize]
}
