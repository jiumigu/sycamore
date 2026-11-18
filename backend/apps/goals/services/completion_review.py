"""里程碑「完成必须有批阅」——**唯一判据**

🔴 这个模块存在的唯一理由：里程碑的完成有**两条**人手入口

    · `PATCH /goals/milestones/{pk}/`（目标页的完成弹窗 / 「今天」四格的完成按钮）
    · `POST /goals/goals/{pk}/toggle_milestone/`（目标卡片上的勾选）

    ⚠️ 那个 `goals/goals` 不是笔误：本 app 的 include 前缀是 `api/goals/`，
       router 里又注册了 `goals`。

    两处各写一遍判据，就是「目标页要求批阅、今天页不要」这种分叉的来源 ——
    而分叉不会报错，只会让 131 条完成里只有 41 条有批阅。

⚠️ **不覆盖**「按日程打卡」（`GoalViewSet.checkin`）：那里把里程碑标完成，
   是「日子到了」的系统判定，不是人的宣告 —— 它不该逼人补一句话，
   否则打卡会在一个用户没有开口的时刻弹出输入框（且当前是静默失败）。
   判据：这条完成**是否由人宣布**。是 ⇒ 要批阅；否 ⇒ 不要。

⚠️ 两条判据，都只针对「人的宣告」，都不追溯历史：

    · `completion_review_issue`：**从非完成 → 完成**、手里又没有批阅 ⇒ 拦；
    · `completion_review_clear_issue`：**已完成、原本有批阅、这一笔要把它清空** ⇒ 拦。
      判据是「有过的不能变没有」，不是「已完成的一定要有」—— 后者会把 90 条
      历史数据全部判成违规，任何人改个错别字都会被要求补写。

⚠️ 已完成的历史条目改标题 / 日期 / 备注，一概不追溯 —— 那是既成事实，不是这轮要清的账。
"""
from __future__ import annotations

COMPLETED = 'completed'

# 文案只此一份。前端不另写（写死的第二份迟早和后端不一致）。
COMPLETION_REVIEW_REQUIRED = '写一句批阅再算完成 —— 这句只写给你自己看'
COMPLETION_REVIEW_KEEP_REQUIRED = '已经写下的批阅不能删空 —— 可以改，但不能抹掉'


def completion_review_issue(*, before: str, after: str, review: str | None) -> str | None:
    """这一笔「改成完成」是否缺批阅。

    返回错误文案；不需要批阅时返回 `None`。

    `review` 为 `None` 表示请求里没带这个字段 —— 此时调用方应传**实例现值**，
    而不是空串：之前填过又改回 pending 的条目，再次完成不必重写一遍。
    """
    if after != COMPLETED:
        return None
    # 已经是完成态 ⇒ 这是一次普通的编辑，不是一次新的完成
    if before == COMPLETED:
        return None
    if (review or '').strip():
        return None
    return COMPLETION_REVIEW_REQUIRED


def completion_review_clear_issue(
    *,
    before: str,
    after: str,
    before_review: str | None,
    review: str | None,
) -> str | None:
    """已写下的批阅：**可以改，不能抹掉**。返回错误文案或 `None`。

    `review is None` = 这一笔请求没碰这个字段（只改标题 / 日期 / 备注）⇒ 不判。

    🔴 判据是「**有过的不能变没有**」，不是「已完成的一定要有」：
       93 条历史完成本来就没有批阅，按后者写，任何人改个错别字都会被要求补写 ——
       那正是这一轮想避免的追溯。所以先看 `before_review`。

    🔴 为什么需要这一条：完成时那句批阅是「有没有人写过」的唯一证据。
       被清空之后，库里就是一条「完成了、但没批阅」——
       与历史数据、与打卡推进的完成再也分不开，而界面上完全看不出来。
       「改」是修订自己的判断，「抹掉」是让那条记录退回到从没写过。
    """
    if before != COMPLETED or after != COMPLETED:
        # 改回 pending = 撤销这次完成，批阅随之作废是合理的
        return None
    if review is None:
        return None
    if not (before_review or '').strip():
        # 本来就没有，谈不上抹掉
        return None
    if (review or '').strip():
        return None
    return COMPLETION_REVIEW_KEEP_REQUIRED
