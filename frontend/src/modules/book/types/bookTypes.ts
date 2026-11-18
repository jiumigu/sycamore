export interface Book {
  bid: number
  years: string | null
  btitle: string
  author: string | null
  original_title: string | null
  btype: string | null
  btype_display?: string
  status: string | null
  status_display?: string
  recommend: number
  recommend_display?: string
  reading_depth: number
  reading_depth_display?: string
  readDate: string | null
  created_at: string | null
  updated_at: string
  tags: string | null
  abandon_reason: string | null
  closedop: string | null
  openop: string | null
  action_item?: string
  user_id?: number | null
}

export interface BookListParams {
  page?: number
  page_size?: number
  years?: string
  btype?: string
  status?: string
  recommend?: number
  recommend_min?: number
  recommend_max?: number
  reading_depth?: number
  search?: string
  ordering?: string
  tag?: string
}

export interface BookStats {
  total_count: number
  completed_count: number
  reading_count: number
  abandoned_count: number
  planned_count: number
  month_count: number
  year_count: number
  avg_recommend: number
  status_stats: Array<{ status: string; count: number }>
  type_stats: Array<{ btype: string; count: number; avg_recommend: number }>
  year_stats: Array<{ years: string; count: number }>
  recommend_stats: Array<{ recommend: number; count: number }>
  depth_stats: Array<{ reading_depth: number; count: number }>
}

export const BTYPE_OPTIONS = [
  '基础学科', '哲学智慧', '心理健康', '财富创造', '幸福科学',
  '认知提升类', '技能工具类', '文学滋养类', '休闲放松类', '个人成长类', '能量消耗类',
]

/** 阅读状态：**6 个值，只说「这一步」**。读法（多细）看 `reading_depth`。
 *
 *  🔴 这是后端 `Book.STATUS_CHOICES` 的**副本**（枚举不是接口下发），
 *  改后端必须同步改这里 —— 不一致时的表现是：下拉里少一项（静默少选项），
 *  或者选了之后 400（`无效的选择`），两种都不容易一眼看出原因。
 *
 *  为什么不再是 8 个：`精读 / 通读 / 消遣` 说的是**读法**，和「计划 / 在读 / 读完」
 *  不是同一个维度。它们并排在一个下拉里时，「在读」这个词同时指三种东西。
 */
export type BookStatus =
  | 'to_read' | 'reading' | 'rereading' | 'finished' | 'shelved' | 'abandoned'

export const STATUS_OPTIONS: BookStatus[] = [
  'to_read', 'reading', 'rereading', 'finished', 'shelved', 'abandoned',
]

/** 状态的中文词。列表、下拉、批量工具条都从这里取，不再各写一份。 */
export const STATUS_LABELS: Record<BookStatus, string> = {
  to_read: '待读',
  reading: '在读',
  rereading: '在读二刷',
  finished: '已读完',
  shelved: '搁置',
  abandoned: '弃读',
}

/** 状态 → el-tag 颜色。🔴 一个元素只承载一个量：
 *  颜色答「还能不能推进」，文字答「第几遍」—— 所以二刷与在读同色（都是蓝）。
 *  搁置橙、弃读红：前者能捡回来，后者是终止。 */
export const STATUS_TAG_TYPE: Record<
  BookStatus, 'info' | 'primary' | 'success' | 'warning' | 'danger'
> = {
  to_read: 'info',
  reading: 'primary',
  rereading: 'primary',
  finished: 'success',
  shelved: 'warning',
  abandoned: 'danger',
}

/** 批量工具条里能选的状态 = 全部状态 − 「弃读」。
 *
 *  🔴 弃读在后端是**逐本必填原因**的（`BookCreateUpdateSerializer.validate`），
 *  批量给一个统一原因会把「为什么弃」写成假话 ⇒ 那条路只走单本编辑。
 *  后端 `BookBulkUpdateSerializer` 用**同一口径**（它的 `BULK_STATUS_CHOICES`
 *  也是这么筛的），所以这里即使多加一项，也只会拿到 400，不会静默写脏。 */
export const BULK_STATUS_OPTIONS = STATUS_OPTIONS.filter(s => s !== 'abandoned')

export const READING_DEPTH_OPTIONS = [
  { value: 1, label: '速读浏览' },
  { value: 2, label: '重点阅读' },
  { value: 3, label: '精读细品' },
  { value: 4, label: '反复研读' },
  { value: 5, label: '践行内化' },
]

export const RECOMMEND_TEXTS = ['不推荐', '一般', '推荐', '宝藏', '人生必读']

/** 换书时给旧书的结论。三选一，与后端 `ReadingFocusService.CLOSE_CHOICES` 逐字对应。 */
export type ReadingFocusCloseMode = 'finished' | 'abandoned' | 'later'

/** 「当前这本」横条上要显示的那几列 —— 不是整本 `Book`。
 *
 *  后端 `ReadingFocusBookSerializer` 只下发这些；别按 `Book` 取 `closedop` 之类，
 *  取不到不是「空」，是根本没发。 */
export interface ReadingFocusBook {
  bid: number
  btitle: string
  author: string | null
  btype: string | null
  btype_display: string
  status: string | null
  status_display: string
  reading_depth: number
  reading_depth_display: string
  readDate: string | null
  recommend: number
  tags: string | null
}

/** `GET /api/books/reading-focus/`
 *
 *  🔴 三个字段要么同时有值、要么同时为 `null`：
 *  `book === null` 就是「还没指定当前这本」，不能只判 `days`。 */
export interface ReadingFocus {
  book: ReadingFocusBook | null
  started_on: string | null
  days: number | null
}

/** `POST /api/books/reading-focus/switch/` 的出参 = `ReadingFocus` + 写了哪些表 */
export interface ReadingFocusSwitchResult extends ReadingFocus {
  written: { book_read_list: number; book_reading_focus: number }
}

