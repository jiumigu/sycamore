/**
 * 实时计时（Timer）· 类型
 *
 * 🔴 阈值（30 秒 / 4 小时）与「已流逝秒数」都由后端下发：
 *    前端不写第二份判据，否则改口径时两边会静默不一致。
 */

export interface TimerSession {
  id: number
  task_name: string
  start_time: string
  end_time: string | null
  notes: string
  status: 'running' | 'done' | 'discarded'
  task_id: number | null
  /** 后端算好的已流逝秒数（前端只用它当锚点） */
  elapsed_seconds: number
  created_at: string
}

/** 上一个会话被自动收尾时的结果（点新任务触发） */
export interface TimerPrevResult {
  outcome: 'saved' | 'too_short' | 'too_long_dropped'
  task_name?: string
  task_id?: number
  elapsed_seconds: number
  duration_hours?: number
  min_seconds?: number
  long_seconds?: number
}

/** 停止 / 丢弃的结果 —— 前端按 outcome 分支提示，不解析文案 */
export interface TimerStopResult {
  outcome: 'saved' | 'too_short' | 'discarded' | 'already_closed'
  status?: string
  task_name?: string
  task_id?: number | null
  elapsed_seconds: number
  duration_hours?: number
  min_seconds?: number
  long_seconds?: number
}

export interface TimerRunningData {
  session: TimerSession | null
  elapsed_seconds: number
  min_seconds: number
  long_seconds: number
}

export interface TimerStartData extends TimerRunningData {
  prev: TimerPrevResult | null
}

export interface TimerStopData {
  session: TimerSession
  result: TimerStopResult
}
