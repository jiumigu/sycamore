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

/** 回顾视图里的一个主题（主题级聚合，不含回答正文 —— 点进去再拉 detail） */
export interface AskReviewTopicItem {
  id: number
  title: string
  question: string
  answer_count: number
  accepted_count: number
  noted_count: number
  /** 采纳 + 有备注 的条数，即「已有结论的回答数」 */
  concluded_count: number
  /** 距该主题最后一次变动过了多少天 —— 零迁移下「最该回顾」的代理指标 */
  days_idle: number
  updated_at: string
}

export interface AskReviewGroup {
  /** null = 未分类 */
  scene_id: number | null
  scene_name: string
  topics: AskReviewTopicItem[]
}

export interface AskReviewStats {
  topics: number
  answers: number
  /** 已标结论（采纳 或 写了备注）的回答数 */
  marked: number
  /** 还是「原料」、没标过结论的回答数 */
  unmarked: number
}

export interface AskReviewData {
  groups: AskReviewGroup[]
  stats: AskReviewStats
}

/** 汇总总览「一条旧结论」卡的数据；`null` = 库里还没有任何结论 */
export interface AskConclusionItem {
  id: number
  topic_id: number
  topic_title: string
  question: string
  scene_name: string
  ai: string
  verdict: '' | '采纳' | '备用' | '不采用'
  conclusion: string
  /** `note` = 这句是**你自己写的备注**；`answer` = AI 回答的片段（卡片上要能说清） */
  conclusion_source: 'note' | 'answer'
  /**
   * AI 回答的摘要（开头 120 字）。
   * `note` 型下它是**判断依据** —— 你的结论可能只有几个字，没有这段就读不出当时在判断什么；
   * ⚠️ `answer` 型下它与 `conclusion` 是**同一段文字**，渲染时别把两块都画出来。
   */
  ai_excerpt: string
  /**
   * `ai_excerpt` 是否被截断 —— **由后端判，前端不按长度推算**。
   * 库里回答原文常在 1000~2700 字，卡上只放得下 120 字；不标出来就会被读成「AI 就说了这么点」。
   */
  ai_excerpt_truncated: boolean
  /** AI 回答原文总字数（截断提示里念出来的那个数） */
  answer_len: number
  /** 池子里一共几条能进这张卡 —— 「换一条」总转回同两条时，界面上要能说出为什么 */
  pool_size: number
  asked_at: string
  days_ago: number
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

/**
 * 回顾视图数据：按场景分组 + 组内「最久没动」排前（供「回顾」页**浏览**）。
 *
 * 与 `getAskAcceptedSummary` 的分工：
 * - `getAskAcceptedSummary` = **导出用**：只吐采纳回答，产出物是 .md 文件
 * - 本接口 = **浏览用**：含全部主题（包括一条结论都还没标的），
 *   点进去才有东西可标 —— 这是「标记动作从录入时搬到回顾时」的落点
 */
export function getAskReview() {
  return request({ url: '/toolkit/ask-topics/review/', method: 'get' })
}

/**
 * 取一条「有结论的」问答（供汇总总览「一条旧结论」卡）。
 *
 * 「有结论」= 标了采纳 **或** 写了备注；没标记的是「原料」不是「结论」，不会被推。
 * 后端在「最久没动的主题」前 5 条候选里随机挑一条，刷新即轮转（无需推送记录字段）。
 * ⚠️ 库里还没有任何结论时返回 **200 + null**（不是 204）—— 调用方要能区分
 * 「确实还没有结论」与「请求失败」，前者给引导文案，不能静默空白。
 */
export function getNextConclusion() {
  return request({ url: '/toolkit/ask-topics/next-conclusion/', method: 'get' })
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
