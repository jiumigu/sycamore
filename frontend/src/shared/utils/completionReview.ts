/**
 * 「完成里程碑前留一句」——**唯一交互实现**
 *
 * 里程碑的完成有三条人手入口（目标页完成弹窗、行为追踪卡的完成切换、
 * 「今天」四格的完成按钮）。后两处都是「点一下就走」，于是它们必须
 * 在最少的步骤里拿到那句批阅 —— 三处各写一份 prompt，文案与校验迟早分叉，
 * 而那分叉不会报错，只会让人在某一处随手写「1」蒙过去。
 *
 * 后端判据在 `apps/goals/services/completion_review.py`：
 * trim 后非空。这里的 `inputValidator` 用同一条，**先在本地挡住**，
 * 而不是发出去换一个 400 回来（那读起来像「按钮坏了」）。
 *
 * 返回值：
 *   · 非空字符串 = 用户写的那句话
 *   · `null`      = 用户自己取消 —— 调用方应当**什么都不做**（不报错、不改状态）
 *
 * ⚠️ 别把 `null` 当成「没写」然后补一句默认批阅：那等于替用户编一句他没说过的话，
 *    而且会永久污染「这句话是谁说的」。
 */
import { ElMessageBox } from 'element-plus'

export async function promptCompletionReview(question: string): Promise<string | null> {
  try {
    const { value } = await ElMessageBox.prompt(question, '完成 · 留一句', {
      confirmButtonText: '完成',
      cancelButtonText: '还没做完',
      inputType: 'textarea',
      inputPlaceholder: '一句话就够',
      inputValidator: (v: string) => (v && v.trim() ? true : '留一句再完成'),
    })
    return (value || '').trim()
  } catch {
    return null
  }
}
