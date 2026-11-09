/**
 * 展厅 · 类型
 *
 * 🔴 前端不写第二份枚举文案（技能熟练度三级）—— 它由 `/showroom/meta/` 下发。
 */
import type { MediaItem } from '@/shared/types/media'

export interface ShowroomProfile {
  id: number | null
  ip_name: string
  tagline: string
  positioning: string
  bio: string
  email: string
  wechat: string
  other_contact: string
  updated_at: string | null
}

/** 展示媒体：type 由后端上传接口按扩展名判定，前端不写第二份判据 */
export type ShowroomMedia = MediaItem

export interface ShowroomCase {
  id: number
  title: string
  client: string
  time_label: string
  problem: string
  result: string
  skill_tags: string[]
  media: ShowroomMedia[]
  source_module: string
  source_id: number | null
  is_visible: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ShowroomSkill {
  id: number
  name: string
  level: string
  level_display?: string
  is_visible: boolean
  sort_order: number
}

export interface ShowroomWork {
  id: number
  work: number | null
  work_name: string | null
  work_summary: string
  work_kind: string
  work_kind_display: string
  title_snapshot: string
  curator_note: string
  media: ShowroomMedia[]
  is_visible: boolean
  sort_order: number
  created_at: string
}

export interface SkillLevelOption {
  value: string
  label: string
}

export interface ShowroomMeta {
  skill_levels: SkillLevelOption[]
}

export interface ShowroomPreview {
  profile: ShowroomProfile
  cases: ShowroomCase[]
  skills: ShowroomSkill[]
  works: ShowroomWork[]
}

/** 作品库候选（选作品进馆用的列表项，来自 works 模块的 /works/items/） */
export interface WorkCandidate {
  id: number
  name: string
  summary: string
  kind: string
  kind_display?: string
}
