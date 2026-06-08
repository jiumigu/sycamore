export interface RewardPool {
  balance: number
  total_earned: number
  total_withdrawn: number
}

export interface RewardTransaction {
  id: number
  source_id: number | null
  source_type: string | null
  amount: number
  transaction_type: string
  transaction_type_display?: string
  balance_before: number
  balance_after: number
  description: string | null
  created_at: string
}

export interface RewardTransactionList {
  items: RewardTransaction[]
  total: number
  page: number
  page_size: number
}

export type GiftStatus = 'pending' | 'waiting' | 'redeemed' | 'cancelled'
export type GiftCategory = 'physical' | 'experience' | 'virtual' | 'other'

export interface GiftList {
  id: number
  name: string
  expected_reward: number
  actual_reward: number | null
  status: GiftStatus
  status_display?: string
  category: GiftCategory | null
  category_display?: string | null
  priority: number
  image_url: string | null
  link_url: string | null
  notes: string | null
  progress: number
  needed: number
  can_redeem: boolean
  redeemed_at: string | null
  created_at: string
  updated_at: string
}

export interface GiftStats {
  total: number
  pending: number
  waiting: number
  redeemed: number
  cancelled: number
  total_expected: number
  total_redeemed: number
}

export const GIFT_CATEGORY_OPTIONS = [
  { value: 'physical', label: '实物', icon: '📚' },
  { value: 'experience', label: '体验', icon: '✈️' },
  { value: 'virtual', label: '虚拟', icon: '🎫' },
  { value: 'other', label: '其他', icon: '🎁' },
]

export const GIFT_STATUS_MAP: Record<string, { label: string; type: string; icon: string }> = {
  pending: { label: '待兑换', type: 'info', icon: '⏳' },
  waiting: { label: '可兑换', type: 'success', icon: '🎉' },
  redeemed: { label: '已兑换', type: 'primary', icon: '✅' },
  cancelled: { label: '已取消', type: 'danger', icon: '❌' },
}

export interface RewardSourceStats {
  sugar: number
  milestone: number
  total: number
  milestone_detail: Array<{
    source_id: number
    amount: number
    description: string
    created_at: string
  }>
}
