"""摘录「金句池」测试 — 长度上限（可配置）· 冷落优先轮转 · 收藏同档插队 · 池内外可见

对应 `QuoteViewSet.next / stats / ?pool=`（v3.60.11 起，v3.60.12 改为配置项）。

背景两句话：
- v3.60.11：汇总总览的「每日金句」从 `random/`（全池等概率随机，1600 字整段问答也会被抽中、
  卡片只截 200 字 ⇒ 显示成读不完的断句）切到 `next/`（池子 + 冷落优先轮转）。
- v3.60.12：池的长度上限由硬编码常量（200）改为 `UserProfile.quote_pool_max_len`，
  在「系统管理 → 系统设置」里可调。

⚠️ 因此本文件**不依赖默认值是多少** —— 凡涉及边界的用例都先 `_set_pool_max_len()` 显式设定，
否则改一次默认值就要来改一批用例（这正是「判据写进代码而非写进测试」的做法）。
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import DEFAULT_QUOTE_POOL_MAX_LEN, UserProfile
from apps.toolkit.models import Quote
from apps.toolkit.services import resolve_quote_pool_max_len

QUOTES_URL = '/api/toolkit/quotes/'
NEXT_URL = '/api/toolkit/quotes/next/'
STATS_URL = '/api/toolkit/quotes/stats/'


def _create_quote(content: str, **kw) -> dict:
    payload = {'content': content, 'is_paragraph': False, 'language': '中文'}
    payload.update(kw)
    resp = APIClient().post(QUOTES_URL, payload, format='json')
    assert resp.status_code == 201, resp.data
    return resp.data


def _set_pool_max_len(n: int) -> None:
    """把当前生效的池上限设成 n（测试库内，用例结束随事务回滚）。

    ⚠️ 直接写模型而不是走 `/core/profile/` 接口：本文件测的是**池子的取数行为**，
    配置接口自己的读写/校验由 `apps/core/tests.py` 负责。两件事别混在一个文件里。
    """
    UserProfile.objects.update_or_create(user_id=1, defaults={'quote_pool_max_len': n})


# ─── 池的取数口径 ───

@pytest.mark.django_db
def test_next_only_picks_quotes_within_configured_limit() -> None:
    """超限（> 上限）不进池：连抽 20 次只会命中那条短句"""
    _set_pool_max_len(200)
    short = _create_quote('我语言的边界，就是我世界的边界。')
    _create_quote('长' * 201)
    c = APIClient()
    seen = {c.get(NEXT_URL).data['id'] for _ in range(20)}
    assert seen == {short['id']}


@pytest.mark.django_db
def test_pool_filters_by_length_not_paragraph_flag() -> None:
    """池判据是**长度**，不是 `is_paragraph`

    开发库实测：段落型 14 条全部 >200 字（平均 1267 字），与长文完全重合 ——
    也就是说「排除段落型」在当前数据上与「排除长文」同结果，纯属冗余条件。
    但它会误挡**将来**一条长度合格的短段落，所以池只用长度把关。
    本用例钉住这一点，防后人「顺手补一个 is_paragraph=False」。
    """
    _set_pool_max_len(200)
    para_short = _create_quote('短文' * 60, is_paragraph=True)  # 120 字，段落型
    c = APIClient()
    assert {c.get(NEXT_URL).data['id'] for _ in range(5)} == {para_short['id']}


@pytest.mark.django_db
def test_pool_boundary_follows_configured_value() -> None:
    """边界钉死：**上限本身在池内、上限 +1 出池**（防后人把 <= 改成 <）

    这里刻意把上限设成 300（**不用默认值**）—— 若实现里还留着写死的数字，
    本用例立刻会红，从而证明「池真的读配置」。
    """
    _set_pool_max_len(300)
    at_limit = _create_quote('短' * 300)
    _create_quote('长' * 301)
    c = APIClient()
    seen = {c.get(NEXT_URL).data['id'] for _ in range(6)}
    assert seen == {at_limit['id']}


@pytest.mark.django_db
def test_pool_limit_takes_effect_immediately() -> None:
    """改配置**即刻生效、零迁移**：同一条摘录「先出池、后进池」

    配置项不是快照 —— 池口径是运行时时算的，所以调完值不需要重算任何存量数据
    （与「派生值不落库」同一条判据）。
    """
    _set_pool_max_len(100)
    mid = _create_quote('中' * 150)
    c = APIClient()
    assert c.get(NEXT_URL).status_code == 204       # 150 > 100 ⇒ 池里没东西

    _set_pool_max_len(200)
    assert c.get(NEXT_URL).data['id'] == mid['id']  # 150 <= 200 ⇒ 立刻取得到


@pytest.mark.django_db
def test_pool_limit_falls_back_to_model_default() -> None:
    """没有任何 UserProfile 行时，回落到**模型字段的 default**（默认值只有一份）

    ⚠️ 这条例外会被静默忽略：若读取端自己写死一个兜底数字，
    改模型默认值时两处就不一致了，而界面上完全看不出来。
    """
    # 测试库内、用例事务内；结束自动回滚（不动任何真实数据）
    UserProfile.objects.filter(user_id=1).delete()
    assert not UserProfile.objects.filter(user_id=1).exists()
    assert resolve_quote_pool_max_len() == DEFAULT_QUOTE_POOL_MAX_LEN
    assert UserProfile._meta.get_field('quote_pool_max_len').default == DEFAULT_QUOTE_POOL_MAX_LEN


# ─── 轮转与收藏（与上限无关，但都显式设定上限避免受默认值影响） ───

@pytest.mark.django_db
def test_next_rotates_by_review_count() -> None:
    """冷落优先：连抽 3 次应恰好覆盖 3 条 review_count=0 的，不重复抽同一条"""
    _set_pool_max_len(500)
    ids = {_create_quote(f'第 {i} 句')['id'] for i in range(3)}
    c = APIClient()
    got = [c.get(NEXT_URL).data['id'] for _ in range(3)]
    assert sorted(got) == sorted(ids)
    for q in Quote.objects.filter(id__in=ids):
        assert q.review_count == 1  # 推一次记一次（本接口下这是「被推送次数」）


@pytest.mark.django_db
def test_favorite_wins_within_same_tier() -> None:
    """收藏只做「同档插队」：两条同为 0 次时收藏的先出，但不会霸占第二次

    若把收藏写成绝对置顶（`order_by('-is_favorite', ...)`），这条收藏会被无限反复推送、
    池里其余条目永远轮不到 —— 这正是本用例要防的回归。
    """
    _set_pool_max_len(500)
    plain = _create_quote('普通的一句')
    fav = _create_quote('收藏的一句', is_favorite=True)
    c = APIClient()
    assert c.get(NEXT_URL).data['id'] == fav['id']
    assert c.get(NEXT_URL).data['id'] == plain['id']


@pytest.mark.django_db
def test_next_returns_204_when_pool_empty() -> None:
    """池里没有合格条目 → 204（前端读作「暂无金句」，别把空串当对象用）"""
    _set_pool_max_len(200)
    _create_quote('长' * 300)
    assert APIClient().get(NEXT_URL).status_code == 204


# ─── 池内外「被看见」：序列化字段 · 筛选 · 统计 ───

@pytest.mark.django_db
def test_serializer_exposes_pool_state_and_len() -> None:
    """列表下发 `content_len` 与 `in_golden_pool` —— 前端只查表，不自己比长度

    用户诉求「在摘录管理里面的都要被看见」：超长条目必须在列表里**被标出来**，
    否则它们混在 69 条里，只有翻到才看得见，等于没有出口。
    ⚠️ 判断必须与池子取数用同一把尺子，所以这两个字段由后端算好下发。
    """
    _set_pool_max_len(200)
    inside = _create_quote('短' * 120)
    outside = _create_quote('长' * 250)
    rows = {r['id']: r for r in APIClient().get(QUOTES_URL).data['results']}
    assert rows[inside['id']]['content_len'] == 120
    assert rows[inside['id']]['in_golden_pool'] is True
    assert rows[outside['id']]['content_len'] == 250
    assert rows[outside['id']]['in_golden_pool'] is False


@pytest.mark.django_db
def test_pool_query_param_splits_in_and_out() -> None:
    """`?pool=in|out` 能把池外条目单独筛出来（这是「被看见」的实际手段）"""
    _set_pool_max_len(200)
    inside = _create_quote('短' * 120)
    outside = _create_quote('长' * 250)
    c = APIClient()
    in_ids = {r['id'] for r in c.get(f'{QUOTES_URL}?pool=in').data['results']}
    out_ids = {r['id'] for r in c.get(f'{QUOTES_URL}?pool=out').data['results']}
    assert in_ids == {inside['id']}
    assert out_ids == {outside['id']}
    # 不传 pool 时两拨都在（默认行为不变）
    all_ids = {r['id'] for r in c.get(QUOTES_URL).data['results']}
    assert all_ids == {inside['id'], outside['id']}


@pytest.mark.django_db
def test_pool_query_param_reads_current_limit() -> None:
    """筛选的边界同样跟着配置走：同一条摘录在两个上限下归属相反的两侧"""
    row = _create_quote('中' * 150)
    c = APIClient()

    _set_pool_max_len(100)
    assert [r['id'] for r in c.get(f'{QUOTES_URL}?pool=out').data['results']] == [row['id']]

    _set_pool_max_len(200)
    assert [r['id'] for r in c.get(f'{QUOTES_URL}?pool=in').data['results']] == [row['id']]


@pytest.mark.django_db
def test_stats_reports_pool_distribution() -> None:
    """stats 念出「池内 / 池外」两拨的条数，并回传当前生效的上限

    ⚠️ 键名清单用例：新增的 `pool_max_len` / `in_pool` / `out_pool` 三个键
    如果名字写错，前端会「取不到就静默不渲染」—— 在界面上看不出来。
    """
    _set_pool_max_len(200)
    _create_quote('短' * 120)
    _create_quote('短' * 180)
    _create_quote('长' * 250)
    data = APIClient().get(STATS_URL).data
    assert data['pool_max_len'] == 200
    assert data['in_pool'] == 2
    assert data['out_pool'] == 1
    assert data['total'] == 3
    assert data['in_pool'] + data['out_pool'] == data['total']
    # 旧键仍在（向后兼容，别顺手删）
    assert {'paragraphs', 'shorts', 'total_reviews'} <= set(data)


# ─── 兼容守卫 ───

@pytest.mark.django_db
def test_random_still_serves_long_quotes() -> None:
    """兼容守卫：`random/` 的**口径未被改动**，长文仍在它的池里

    它不再被首页使用（v3.60.11 已切到 next/），但保留作向后兼容 ——
    改 next/ 时别顺手把 random/ 一起改了。
    """
    _set_pool_max_len(200)
    long_one = _create_quote('长' * 300)
    c = APIClient()
    for _ in range(5):
        assert c.get(f'{QUOTES_URL}random/').data['id'] == long_one['id']
