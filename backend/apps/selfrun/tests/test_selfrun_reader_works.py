"""自我运转 · `works_count` 取数器 —— 7 条（v3.62.0 口径变更）

🔴 这一组钉住两件事：

① **口径换源**：`output_count` / `content_output` 两条模板从
   「数日记流 MIGU 条数」改成「数作品库件数」；
② **`0` 是 `0`，不是 `None`** —— 「这周一件都没留」是事实，
   与「系统取不到」（比如某个取数器算不出来）是两件相反的事。

⚠️ 2026-11-02 起 `module_value` 的 `redemption.runway` **不再**是「取不到」的例子：
   它已经能真算（余额 ÷ 日均净支出 ÷ 30）。本文件原先拿它当反例，只是举例，
   性质上与本文件测的 `works_count` 无关，故改为泛指。
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.selfrun import templates as tpl
from apps.selfrun.constants import READER_KEYS, READER_WHERE_KEYS, STALE_RULES
from apps.selfrun.readers import READERS, run_reader, works_count
from apps.works.models import Work

pytestmark = pytest.mark.django_db


class _FakeMetric:
    """`works_count` 只看区间与 `source_config.where`，其余字段一个都不读。

    ⚠️ `where` 用 `None` 区分「没给」与「给了空字典」：两者都等于不过滤，
       但测试要能明确表达「这条 KPI 就是没配类型」。
    """

    def __init__(self, where=None):
        self.source_config = {'kind': 'works_count'}
        if where is not None:
            self.source_config['where'] = where
        self.pk = None


def _mk(name, when, kind='other'):
    """建一件作品并把 `created_at` 挪到指定时刻（`auto_now_add` 挡不住 update）。"""
    work = Work.objects.create(name=name, kind=kind)
    Work.objects.filter(id=work.id).update(
        created_at=timezone.make_aware(dt.datetime.combine(when, dt.time(12, 0))),
    )
    return work


class TestWorksCountReader:

    def test_counts_inside_half_open_range(self):
        today = timezone.localdate()
        start, end, _ = _week(today)
        _mk('范围内的', start + dt.timedelta(days=1))
        _mk('下周一那件', end)          # 半开区间 ⇒ **不算**

        out = works_count(_FakeMetric(), start, end)
        assert out['value'] == 1.0
        assert out['breakdown'][0]['label'] == '范围内的'

    def test_zero_is_zero_not_none(self):
        """🔴 一件都没有 ⇒ `0`（真 0），不是 `None`（取不到）。"""
        start, end, _ = _week(timezone.localdate())
        out = works_count(_FakeMetric(), start, end)
        assert out['value'] == 0.0
        assert out['value'] is not None
        assert out['count'] == 0

    def test_breakdown_carries_work_identity(self):
        start, end, _ = _week(timezone.localdate())
        work = _mk('一件有名字的', timezone.localdate())
        work.summary = '一句话'
        work.channel = '公众号'
        work.save()

        out = works_count(_FakeMetric(), start, end)
        extra = out['breakdown'][0]['extra']
        assert extra['id'] == work.id
        assert extra['summary'] == '一句话'
        assert extra['channel'] == '公众号'

    def test_run_reader_dispatches(self):
        start, end, _ = _week(timezone.localdate())
        assert run_reader(_FakeMetric(), start, end)['value'] == 0.0

    def test_registry_matches_constants(self):
        assert set(READERS) == set(READER_KEYS)
        # v3.64.30 起可按作品类型过滤（「这月画了几张」）
        assert READER_WHERE_KEYS['works_count'] == 'work_kind'

    def test_filter_by_work_kind(self):
        """🔴 按类型过滤 —— 月度「画 ≥2 张」自动溯源就走这条路。"""
        start, end, _ = _week(timezone.localdate())
        day = start + dt.timedelta(days=1)
        _mk('一张画', day, kind='drawing')
        _mk('一件绣', day, kind='embroidery')
        _mk('一篇文章', day, kind='article')

        out = works_count(_FakeMetric(where={'work_kind': 'drawing'}), start, end)
        assert out['value'] == 1.0
        assert [r['label'] for r in out['breakdown']] == ['一张画']

    def test_no_work_kind_means_all_kinds(self):
        """留空 = 不限类型。

        🔴 别默认成「只数某一种」—— 默认值一变，所有既有「留下件数」的读数
           会跟着变，而且是静默变（数字仍落在合理区间）。
        """
        start, end, _ = _week(timezone.localdate())
        day = start + dt.timedelta(days=1)
        _mk('一张画', day, kind='drawing')
        _mk('一篇文章', day, kind='article')

        assert works_count(_FakeMetric(), start, end)['value'] == 2.0
        assert works_count(_FakeMetric(where={}), start, end)['value'] == 2.0

    def test_unknown_work_kind_raises(self):
        """🔴 类型名配错**必须报错**，绝不能返 0。

        返 0 的话，「真的没画」和「类型名拼错了」在页面上是同一个 `0`，
        而 `0` 是一条**结论**（这月一张都没画）—— 不能由一个笔误冒充。
        """
        start, end, _ = _week(timezone.localdate())
        with pytest.raises(ValueError, match='未知的作品类型'):
            works_count(_FakeMetric(where={'work_kind': 'drwaing'}), start, end)

    def test_no_stale_rule(self):
        """🔴 「这周一件都没留」不是数据源过期 —— 给它 stale 会与 `empty` 打架。"""
        assert STALE_RULES['works_count'] is None


class TestTemplateSwitch:

    def test_output_count_now_reads_works(self):
        t = tpl.TEMPLATE_BY_KEY['output_count']
        assert t['source_config'] == {'kind': 'works_count'}
        assert t['unit'] == '件'
        assert t['name'] == '留下件数'

    def test_content_output_now_reads_works(self):
        t = tpl.TEMPLATE_BY_KEY['content_output']
        assert t['source_config'] == {'kind': 'works_count'}
        assert t['unit'] == '件'

    def test_template_keys_unchanged(self):
        """🔴 `key` 不改 —— 它是 `Metric.template_key` 的指向，改了关系就断。"""
        assert 'output_count' in tpl.TEMPLATE_BY_KEY
        assert 'content_output' in tpl.TEMPLATE_BY_KEY

    def test_no_template_still_reads_diary_for_output(self):
        """周/月两条「留下件数」都不再走日记流（口径只有一把尺子）。"""
        for key in ('output_count', 'content_output'):
            assert tpl.TEMPLATE_BY_KEY[key]['source_config']['kind'] != 'diary_migu_count'


def _week(ref):
    """ISO 周 `[周一, 下周一)`。"""
    mon = ref - dt.timedelta(days=ref.weekday())
    iso = mon.isocalendar()
    return mon, mon + dt.timedelta(days=7), f'{iso[0]}-W{iso[1]:02d}'
