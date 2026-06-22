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
