export type SampleType = 'acquaintance' | 'online' | 'historical' | 'celebrity' | 'fictional'

export type SampleStatus = 'collected' | 'verified' | 'reviewed'

export type SampleRelevance = 'high' | 'reference' | 'knowledge'

export const SampleTypeLabels: Record<SampleType, string> = {
  acquaintance: '熟人',
  online: '网友',
  historical: '历史人物',
  celebrity: '知名人士',
  fictional: '虚构人物',
}

export const SampleTypeIcons: Record<SampleType, string> = {
  acquaintance: '👤',
  online: '🌐',
  historical: '📜',
  celebrity: '🧑',
  fictional: '🎭',
}

export const StatusConfig: Record<SampleStatus, { label: string; icon: string; color: string }> = {
  collected: { label: '已收集', icon: '📥', color: '#909399' },
  verified: { label: '已核实', icon: '🔍', color: '#409EFF' },
  reviewed: { label: '已审阅', icon: '✅', color: '#67C23A' },
}

export const RelevanceConfig: Record<SampleRelevance, { label: string; icon: string; color: string }> = {
  high: { label: '高度借鉴', icon: '🔥', color: '#E6A23C' },
  reference: { label: '参考', icon: '📖', color: '#409EFF' },
  knowledge: { label: '了解', icon: '👀', color: '#909399' },
}

export interface LifeSample {
  id: number
  name: string
  alias: string
  sample_type: SampleType
  tags: string[]
  summary: string
  obsidian_path: string
  obsidian_full_path: string
  my_note: string
  related_goals: number[]
  related_diary: number[]
  status: SampleStatus
  status_label: string
  verified_at: string | null
  reviewed_at: string | null
  relevance: SampleRelevance
  relevance_label: string
  relevance_reason: string
  created_at: string
  updated_at: string
}

export interface LifeSampleForm {
  name: string
  alias: string
  sample_type: SampleType
  tags: string[]
  summary: string
  obsidian_path: string
  my_note: string
  status: SampleStatus
  relevance: SampleRelevance
  relevance_reason: string
}

export interface ObsidianConfig {
  id: number
  enabled: boolean
  vault_path: string
  samples_folder: string
  updated_at: string
}

export interface ScanResult {
  name: string
  alias: string
  era: string
  region: string
  birth_year: number | null
  death_year: number | null
  type: string
  tags: string[]
  summary: string
  path: string
  filename: string
  modified_at: string
  exists: boolean
}

export interface SyncMigration {
  name: string
  old_path: string
  new_path: string
}

export interface SyncResult {
  success: boolean
  message: string
  created: string[]
  updated: string[]
  migrated?: SyncMigration[]
  skipped: string[]
  total: number
}

export interface Stats {
  total: number
  synced: number
  pending: number
  obsidian_files: number
  status: Record<SampleStatus, number>
  relevance: Record<SampleRelevance, number>
}
