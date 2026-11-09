import request from '@/shared/utils/request'
import type {
  TimerRunningData, TimerStartData, TimerStopData,
} from '@/shared/types/timer'

/**
 * 实时计时接口。
 *
 * 放在 `shared/api/` 而不是 `modules/temporal/api/`：顶栏的便捷入口也要用，
 * 它不应反向依赖某个业务模块。
 */

export function getRunning() {
  return request<TimerRunningData>({ url: '/temporal/timer/running/', method: 'get' })
}

export function startTimer(taskName: string) {
  return request<TimerStartData>({
    url: '/temporal/timer/start/',
    method: 'post',
    data: { task_name: taskName },
  })
}

/**
 * 停止并入账。
 * @param allowLong 会话超过 4 小时时必须显式传 true —— 后端用 409 拦，
 *                  前端不能靠"按钮点两次"绕过。
 */
export function stopTimer(sessionId: number, notes = '', allowLong = false) {
  return request<TimerStopData>({
    url: '/temporal/timer/stop/',
    method: 'post',
    data: { session_id: sessionId, notes, allow_long: allowLong },
  })
}

export function discardTimer(sessionId: number) {
  return request<TimerStopData>({
    url: '/temporal/timer/discard/',
    method: 'post',
    data: { session_id: sessionId },
  })
}
