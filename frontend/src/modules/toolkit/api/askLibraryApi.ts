import request from '@/shared/utils/request'
import type { SystemPreset } from '@/shared/api/coreApi'
import { getPresets } from '@/shared/api/coreApi'

export interface AskSceneItem {
  id: number
  name: string
  description: string
  sort: number
  topic_count?: number
  created_at: string
  updated_at: string
}

export interface AskAnswerItem {
  id: number
  topic: number
  /** 追问自哪条回答（首轮为 null） */
  parent: number | null
  /** 本轮提问文本（追问必填；首轮留空沿用主题 question） */
  question: string
  ai: string
  session: string
  answer: string
  asked_at: string
  verdict: '' | '采纳' | '备用' | '不采用'
  note: string
  created_at: string
}

export interface AskTopicItem {
  id: number
  /** 所属业务场景 id（null = 未分类） */
  scene: number | null
  scene_name?: string
  title: string
  question: string
  background: string
  tags: string[]
  answers?: AskAnswerItem[]
  answer_count?: number
  latest_asked_at?: string | null
  accepted_count?: number
  created_at: string
  updated_at: string
}

export interface AskTopicQuery {
  search?: string
  tag?: string
  ai?: string
  /** 场景 id；'none' = 未分类 */
  scene?: string
  /** '1' = 只返回含 ✅采纳 回答的主题 */
  has_accepted?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

/** summary 汇总中的单条采纳回答 */
export interface AskAcceptedItem {
  ai: string
  session: string
  /** 追问节点：该轮追问文本；首轮为空串 */
  question: string
  asked_at: string
  answer: string
  note: string
}

/** summary 汇总中的主题（含其全部采纳回答） */
export interface AskSummaryTopic {
  id: number
  title: string
  question: string
  scene_name: string
  created_at: string
  accepted: AskAcceptedItem[]
}

/** 系统预设中的 AI 问答库标签（ask_tags） */
export async function fetchAskTagPresets(): Promise<string[]> {
  try {
    const res = await getPresets()
    const presets = (res.data?.results || []) as SystemPreset[]
    return presets.find((p) => p.preset_type === 'ask_tags')?.values || []
  } catch {
    return []
  }
}

export function getAskTopics(params?: AskTopicQuery) {
  return request({ url: '/toolkit/ask-topics/', method: 'get', params })
}

/** 采纳结论汇总：?scene=<id>|none|空=全部 → { topics: AskSummaryTopic[] } */
export function getAskAcceptedSummary(scene?: string) {
  return request({ url: '/toolkit/ask-topics/summary/', method: 'get', params: scene ? { scene } : {} })
}

export function getAskTopic(id: number) {
  return request({ url: `/toolkit/ask-topics/${id}/`, method: 'get' })
}

export function createAskTopic(data: Partial<AskTopicItem>) {
  return request({ url: '/toolkit/ask-topics/', method: 'post', data })
}

export function updateAskTopic(id: number, data: Partial<AskTopicItem>) {
  return request({ url: `/toolkit/ask-topics/${id}/`, method: 'patch', data })
}

export function deleteAskTopic(id: number) {
  return request({ url: `/toolkit/ask-topics/${id}/`, method: 'delete' })
}

export function createAskAnswer(data: Partial<AskAnswerItem>) {
  return request({ url: '/toolkit/ask-answers/', method: 'post', data })
}

export function updateAskAnswer(id: number, data: Partial<AskAnswerItem>) {
  return request({ url: `/toolkit/ask-answers/${id}/`, method: 'patch', data })
}

export function deleteAskAnswer(id: number) {
  return request({ url: `/toolkit/ask-answers/${id}/`, method: 'delete' })
}

// ─── 业务场景容器 ───
export function getAskScenes() {
  return request({ url: '/toolkit/ask-scenes/', method: 'get' })
}

export function createAskScene(data: Partial<AskSceneItem>) {
  return request({ url: '/toolkit/ask-scenes/', method: 'post', data })
}

export function updateAskScene(id: number, data: Partial<AskSceneItem>) {
  return request({ url: `/toolkit/ask-scenes/${id}/`, method: 'patch', data })
}

export function deleteAskScene(id: number) {
  return request({ url: `/toolkit/ask-scenes/${id}/`, method: 'delete' })
}
