export interface Quote {
  id: number
  content: string
  author: string
  language: string
  category: string
  is_paragraph: boolean
  short_title: string
  source: string
  is_favorite: boolean
  review_count: number
  tags: string
  created_at: string
  /** 正文字数 —— **后端算好下发**，前端不自己数（判断依据要与池子取数同一把尺子） */
  content_len: number
  /** 是否在「每日金句」的可取范围内；`null` = 后端没给上限（当作「不知道」，不是「不进池」） */
  in_golden_pool: boolean | null
}

/** `/toolkit/quotes/stats/` 返回体 */
export interface QuoteStats {
  total: number
  paragraphs: number
  shorts: number
  /** ⚠️ 语义 = **被推送到首页卡的次数总和**，不是「用户主动回顾次数」 */
  total_reviews: number
  /** 当前生效的池上限（来自系统设置） */
  pool_max_len: number
  /** 不进池（因超长）的条数 */
  out_pool: number
  /** 能进池的条数 */
  in_pool: number
}

export interface QuoteFormData {
  content: string
  author: string
  language: string
  category: string
  is_paragraph: boolean
  short_title: string
  source: string
  tags: string
}

export const LANGUAGE_OPTIONS = [
  { value: '中文', label: '🇨🇳 中文' },
  { value: '英语', label: '🇬🇧 英语' },
  { value: '日语', label: '🇯🇵 日语' },
  { value: '德语', label: '🇩🇪 德语' },
  { value: '法语', label: '🇫🇷 法语' },
  { value: '韩语', label: '🇰🇷 韩语' },
  { value: '其他', label: '🌐 其他' },
]
