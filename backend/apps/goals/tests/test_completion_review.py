"""里程碑「完成必须有批阅」—— 两条人手入口 + 一条系统入口的边界

来源：2026-11-18 的那笔账 —— 131 条已完成里程碑里只有 41 条有批阅。
根因不是没人写，是**两个完成入口只有一个要求写**：
目标页的完成弹窗必填 `self_review`，而「今天」四格与 `toggle_milestone`
都是直接 PATCH / POST 状态，从不问一句。

本文件钉四类事：
  ① 判据本身（纯函数的四边界）；
  ② 两条人手入口**同口径** —— 缺批阅一律 400，且库里不改一个字；
  ③ 已写下的批阅**可以改、不能抹掉** —— 否则「先随便写一句完成、再删空」
     会让 ② 变成一次性闸门；
  ④ **系统入口不受牵连** —— 打卡推进里程碑不该逼人补批阅。
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.goals.models import Action, Goal, Milestone
from apps.goals.services import (
    COMPLETION_REVIEW_KEEP_REQUIRED,
    COMPLETION_REVIEW_REQUIRED,
    completion_review_clear_issue,
    completion_review_issue,
)

# 文件级：本文件的 fixture 直接建库行（判据那两条是纯函数，连带用库也无害）
pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════
# ① 判据本身
# ══════════════════════════════════════════════════════════════

def test_issue_requires_review_only_on_new_completion():
    """缺批阅才算问题；已完成的再编辑、改回 pending 都不是。"""
    assert completion_review_issue(before='pending', after='completed', review='') \
        == COMPLETION_REVIEW_REQUIRED
    # 已完成 → 已完成：普通编辑，不追溯历史
    assert completion_review_issue(before='completed', after='completed', review='') is None
    # 取消完成：不需要理由（理由在别处，不在这一步）
    assert completion_review_issue(before='completed', after='pending', review='') is None
    # 进行中：与完成无关
    assert completion_review_issue(before='pending', after='in-progress', review='') is None


def test_issue_accepts_any_non_blank_review():
    assert completion_review_issue(before='pending', after='completed', review='做完了') is None
    # 空白串不算写了 —— 前端 `inputValidator` 与这里必须同一个判据
    assert completion_review_issue(before='pending', after='completed', review='   ') is not None
    # None = 没带这个字段，调用方应传实例现值
    assert completion_review_issue(before='pending', after='completed', review=None) is not None


# ══════════════════════════════════════════════════════════════
# ② 两条人手入口
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def goal() -> Goal:
    return Goal.objects.create(
        title='测试目标',
        category='year',
        life_dimension='学习成长',
        status='in-progress',
        enable_reward=False,
        reward_value=Decimal('0'),
        goal_completion_bonus=Decimal('0'),
    )


@pytest.fixture
def milestone(goal: Goal) -> Milestone:
    return Milestone.objects.create(goal=goal, title='里程碑A', status='pending')


def test_patch_completed_without_review_is_rejected(milestone: Milestone) -> None:
    """PATCH 缺批阅 ⇒ 400，且**状态未变**（不能先写再报错）。"""
    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/', {'status': 'completed'}, format='json',
    )

    assert r.status_code == 400
    assert 'self_review' in r.json()
    milestone.refresh_from_db()
    assert milestone.status == 'pending'


def test_patch_completed_with_blank_review_is_rejected(milestone: Milestone) -> None:
    """`allow_blank=True` 让空串过得了字段校验 —— 挡住它的是判据里的 `strip()`。"""
    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/',
        {'status': 'completed', 'self_review': '   '},
        format='json',
    )

    assert r.status_code == 400
    milestone.refresh_from_db()
    assert milestone.status == 'pending'


def test_patch_completed_with_review_succeeds(milestone: Milestone) -> None:
    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/',
        {'status': 'completed', 'self_review': '比预想的快，因为先写好了清单'},
        format='json',
    )

    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.status == 'completed'
    assert milestone.self_review == '比预想的快，因为先写好了清单'


def test_editing_a_finished_milestone_needs_no_review(milestone: Milestone) -> None:
    """历史条目不追溯：已完成的老数据（90 条没批阅）改标题不该被拦。"""
    milestone.status = 'completed'
    milestone.save(update_fields=['status'])

    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/', {'title': '改个名字'}, format='json',
    )

    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.title == '改个名字'


def test_reopening_then_completing_again_keeps_old_review(milestone: Milestone) -> None:
    """之前写过批阅 → 改回 pending → 再次完成（不带字段）⇒ 放行，不逼重写一遍。"""
    milestone.status = 'completed'
    milestone.self_review = '第一次写完时的批阅'
    milestone.save(update_fields=['status', 'self_review'])

    client = APIClient()
    assert client.patch(
        f'/api/goals/milestones/{milestone.id}/', {'status': 'pending'}, format='json',
    ).status_code == 200

    r = client.patch(
        f'/api/goals/milestones/{milestone.id}/', {'status': 'completed'}, format='json',
    )

    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.status == 'completed'
    assert milestone.self_review == '第一次写完时的批阅'


def test_toggle_endpoint_shares_the_same_rule(goal: Goal, milestone: Milestone) -> None:
    """`POST /goals/goals/{pk}/toggle_milestone/` 是同一件事的另一个入口 —— 口径必须一样。

    只堵 PATCH 的话，用户会绕到勾选框去完成，而页面上看不出两个入口的差别。
    ⚠️ 路径里的 `goals/goals` 不是笔误：本 app 的 include 前缀是 `api/goals/`，
       router 又注册了 `goals`（前端 `goalApi.ts` 同此）。
    """
    client = APIClient()

    r = client.post(
        f'/api/goals/goals/{goal.id}/toggle_milestone/',
        {'milestone_id': milestone.id, 'status': 'completed'},
        format='json',
    )
    assert r.status_code == 400
    assert 'self_review' in r.json()
    milestone.refresh_from_db()
    assert milestone.status == 'pending'

    r = client.post(
        f'/api/goals/goals/{goal.id}/toggle_milestone/',
        {'milestone_id': milestone.id, 'status': 'completed', 'self_review': '勾上去了'},
        format='json',
    )
    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.status == 'completed'


# ══════════════════════════════════════════════════════════════
# ③ 已写下的批阅：可以改，不能抹掉（v3.64.85）
# ══════════════════════════════════════════════════════════════
#
# 为什么要有这一节：③ 那道闸只拦「完成时没写」。写完之后进编辑把内容删空，
# 库里又变回「完成了、但没批阅」—— 与九十多条历史数据、与打卡推进的完成
# 再也分不开，而界面上完全看不出来。缺口会以另一种方式长回来。

def test_clear_issue_only_when_there_was_something() -> None:
    """判据是「有过的不能变没有」，不是「已完成的一定要有」。"""
    # 有 → 抹掉：拦
    assert completion_review_clear_issue(
        before='completed', after='completed', before_review='写过一句', review='',
    ) == COMPLETION_REVIEW_KEEP_REQUIRED
    assert completion_review_clear_issue(
        before='completed', after='completed', before_review='写过一句', review='   ',
    ) is not None
    # 有 → 改成另一句：放行（改是修订自己的判断）
    assert completion_review_clear_issue(
        before='completed', after='completed', before_review='写过一句', review='换个说法',
    ) is None
    # 本来就没有 → 传空串：放行（九十多条历史条目，不能追溯）
    assert completion_review_clear_issue(
        before='completed', after='completed', before_review='', review='',
    ) is None
    # 没带这个字段（只改标题）：放行
    assert completion_review_clear_issue(
        before='completed', after='completed', before_review='写过一句', review=None,
    ) is None
    # 撤销完成：批阅随完成作废是合理的
    assert completion_review_clear_issue(
        before='completed', after='pending', before_review='写过一句', review='',
    ) is None


def test_patch_cannot_blank_a_written_review(milestone: Milestone) -> None:
    """已完成 + 原本有批阅 + 这次要清空 ⇒ 400，且**库里一个字都没改**。"""
    milestone.status = 'completed'
    milestone.self_review = '第一次写完时的批阅'
    milestone.save(update_fields=['status', 'self_review'])

    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/',
        {'self_review': ''},
        format='json',
    )

    assert r.status_code == 400
    assert 'self_review' in r.json()
    milestone.refresh_from_db()
    assert milestone.self_review == '第一次写完时的批阅'


def test_patch_can_rewrite_a_written_review(milestone: Milestone) -> None:
    milestone.status = 'completed'
    milestone.self_review = '第一次写完时的批阅'
    milestone.save(update_fields=['status', 'self_review'])

    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/',
        {'self_review': '过了两天再看，其实难在开头那半天'},
        format='json',
    )

    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.self_review == '过了两天再看，其实难在开头那半天'


def test_patch_can_blank_a_review_that_never_existed(milestone: Milestone) -> None:
    """历史条目（已完成但没批阅）改标题时，前端会把空串一起提交 —— 不能因此拦住。

    这条是最容易写错的地方：判据写成「已完成就必须有批阅」，
    九十多条历史数据会让任何人改个错别字都收到 400。
    """
    milestone.status = 'completed'
    milestone.save(update_fields=['status'])

    r = APIClient().patch(
        f'/api/goals/milestones/{milestone.id}/',
        {'title': '改个名字', 'self_review': ''},
        format='json',
    )

    assert r.status_code == 200
    milestone.refresh_from_db()
    assert milestone.title == '改个名字'


def test_toggle_endpoint_also_refuses_to_blank(goal: Goal, milestone: Milestone) -> None:
    """勾选框那条路同样不能抹掉 —— 否则等于给清空留了后门。"""
    milestone.status = 'completed'
    milestone.self_review = '写过一句'
    milestone.save(update_fields=['status', 'self_review'])

    r = APIClient().post(
        f'/api/goals/goals/{goal.id}/toggle_milestone/',
        {'milestone_id': milestone.id, 'status': 'completed', 'self_review': ''},
        format='json',
    )

    assert r.status_code == 400
    assert 'self_review' in r.json()
    milestone.refresh_from_db()
    assert milestone.self_review == '写过一句'


# ══════════════════════════════════════════════════════════════
# ④ 系统入口不受牵连
# ══════════════════════════════════════════════════════════════

def test_checkin_still_completes_without_review(goal: Goal) -> None:
    """打卡推进里程碑是「日子到了」的系统判定，不是人的宣告 —— 不该要批阅。

    这条是反向守卫：如果哪天把校验塞进模型层 / save() 里，它就会红。
    """
    action = Action.objects.create(goal=goal, name='每天读 20 分钟', completion_log={})
    m = Milestone.objects.create(goal=goal, title='第 1 天', order_num=1, status='pending')

    r = APIClient().post(f'/api/goals/actions/{action.id}/checkin/', {}, format='json')

    assert r.status_code == 200
    assert r.json()['milestone_completed'] is True
    m.refresh_from_db()
    assert m.status == 'completed'
    assert m.self_review == ''
