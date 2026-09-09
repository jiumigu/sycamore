import request from '@/shared/utils/request'
import type { SystemPreset } from '@/shared/api/coreApi'
import { getPresets } from '@/shared/api/coreApi'

export interface AskAnswerItem {
  id: number
  topic: number
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
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
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
