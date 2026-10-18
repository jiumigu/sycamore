/** 「值得留」这一勾 —— 七个入口共享的状态机
 *
 * 🔴 为什么抽出来：这一勾在**七个页面**上出现（里程碑 / 收件箱 / 读书 /
 *    日记 / 摘录 / AI 问答 / 档案馆）。各写一份的话，七份迟早对不上 ——
 *    而且对不上**不报错**，只是某个页面上的勾「点了没反应」。
 *
 * ⚠️ **再加入口时本文件零改动** —— 来源是构造参数（`useWorkKeep('treasure')`），
 *    要改的只有两处：后端 `CAPTURE_SOURCE_CHOICES` 与前端 `SOURCE_SHORT`
 *    （后者是 `Record<CaptureSource, string>`，漏了会编译报错）。
 *    若哪天发现「加一个入口得动这里」，说明有东西漏在外面了。
 *
 * 🔴 三态，不是布尔：
 *    - 没勾过 ⇒ 可以勾；
 *    - `pending`（待提炼）⇒ 再点一下取消；
 *    - `used`（已收进某件作品）⇒ **不能在这里取消** —— 那会让作品凭空少一个
 *      来源。界面必须说清「去哪儿处理」，而不是点了报错。
 *      （后端 `uncapture` 对 `used` 直接 400，所以不能靠「试一下」发现。）
 *
 * ⚠️ 读不到（作品库还没迁移）时**整个标记不渲染** ——
 *    这是附加动作，不该在六个列表页上各喊一遍「我坏了」；
 *    而显示成「未勾」是**说谎**（用户以为没勾，其实是读不到）。
 *    解释只发生在主视图那两处（作品页 / 本周状态扁条）。
 *
 * ⚠️ 一行一个请求地查、还是整页查一次：这里选**整页一次**
 *    （`load()` 拉该来源的全部捕获，之后 `entryOf` 本地查）。
 *    逐行查在 20 行的列表上就是 20 个请求，且每行都要有自己的 loading 态。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

import { capture as apiCapture, getCaptures, uncapture as apiUncapture } from '../api/workApi'
import type { CaptureSource, WorkCapture } from '../types/workTypes'

export function useWorkKeep(sourceType: CaptureSource) {
  /** 该来源的全部捕获（含 `pending` / `used`）—— 本地查，不逐行发请求 */
  const rows = ref<WorkCapture[]>([])
  /** 成功读到过（**没读到就别渲染标记**，见文件头） */
  const ready = ref(false)
  /** 正在提交的那些 id（防连点） */
  const busy = ref<Set<number>>(new Set())

  async function load() {
    try {
      const res = await getCaptures({ source_type: sourceType })
      rows.value = res.data ?? []
      ready.value = true
    } catch {
      // ⚠️ 不设 ready —— 标记整个不渲染（主视图负责解释为什么）
      ready.value = false
    }
  }

  /** 某个来源的捕获；`undefined` = 没勾过。 */
  function entryOf(sourceId: number): WorkCapture | undefined {
    return rows.value.find((r) => r.source_id === sourceId)
  }

  function markBusy(sourceId: number, on: boolean) {
    const next = new Set(busy.value)
    if (on) next.add(sourceId)
    else next.delete(sourceId)
    busy.value = next
  }

  /** 打勾（幂等）。返回是否真的写成功了。 */
  async function keep(sourceId: number, title: string, excerpt = '') {
    busy.value = new Set(busy.value).add(sourceId)
    try {
      const res = await apiCapture({
        source_type: sourceType, source_id: sourceId, title, excerpt,
      })
      const row = res.data?.capture
      if (row) {
        const idx = rows.value.findIndex((r) => r.id === row.id)
        if (idx >= 0) rows.value.splice(idx, 1, row)
        else rows.value.unshift(row)
      }
      return true
    } catch {
      ElMessage.warning('「值得留」没标上 —— 稍后再试')
      return false
    } finally {
      markBusy(sourceId, false)
    }
  }

  /** 取消勾。已收进作品的不动（只提示去哪儿处理）。 */
  async function unkeep(sourceId: number) {
    const cur = entryOf(sourceId)
    if (!cur) return

    if (cur.status === 'used') {
      ElMessage.info(
        `这条已经收进《${cur.work_name || '某件作品'}》了 —— 要拆开请在「作品」页里处理`,
      )
      return
    }
    markBusy(sourceId, true)
    try {
      await apiUncapture(cur.id)
      rows.value = rows.value.filter((r) => r.id !== cur.id)
    } catch {
      ElMessage.warning('取消标记没成功 —— 稍后再试')
    } finally {
      markBusy(sourceId, false)
    }
  }

  /** 行内点击：没勾就勾、勾了就取消。 */
  async function toggle(sourceId: number, title: string, excerpt = '') {
    if (busy.value.has(sourceId)) return
    if (entryOf(sourceId)) await unkeep(sourceId)
    else await keep(sourceId, title, excerpt)
  }

  return { rows, ready, busy, load, entryOf, keep, unkeep, toggle }
}
