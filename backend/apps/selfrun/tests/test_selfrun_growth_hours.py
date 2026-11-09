"""成长计时取数器 `growth_hours`（v3.64.11）

口径：`temporal_task_meta.counts_growth = True` 的任务名，时长合计。

🔴 与「L2 = 深度工作」彻底解耦 —— 这两条用例就是钉这件事的：
   · 深度工作但**没勾** ⇒ 不算；
   · 浅层工作但**勾了** ⇒ 算。
   两边都反向，才说明取数真的只看开关，而不是「碰巧深度工作全勾上了」。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunStage
from apps.selfrun.readers import growth_hours
from apps.temporal.models import TaskMeta, TemporalTask

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


def _meta(name, activity_type, growth):
    return TaskMeta.objects.create(
        task_name=name, activity_type=activity_type, counts_growth=growth,
    )


def _hours(name, hours, days_ago=1):
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    TemporalTask.objects.create(
        task_name=name,
        start_time=timezone.make_aware(dt.datetime.combine(day, dt.time(9, 0))),
        duration_hours=hours, year=day.year, mon=f'{day.month:02d}', day=day.day,
    )


@pytest.fixture
def metric(client):
    """建一个只含「成长小时数」的阶段，返回那条 metric（走模板 ⇒ 顺带钉住模板口径）。"""
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '成长测试阶段',
        'start_date': str(today - dt.timedelta(days=7)),
        'metrics': [{'template_key': 'grow_hours'}],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get().metrics.get(template_key='grow_hours')


def _range(days=7):
    today = timezone.localdate()
    return today - dt.timedelta(days=days), today + dt.timedelta(days=1)


def test_template_uses_growth_reader(metric):
    """模板 `grow_hours` 必须指向 `growth_hours` 取数器。

    🔴 这条是**防回退**的：改回 `temporal_hours + l2=['深度工作']` 不报错，
       只是成长计时悄悄变回「按分类自动算」—— 界面上那个开关就成了摆设。
    """
    assert metric.source_config == {'kind': 'growth_hours'}


def test_counts_flagged_task_even_if_not_deep_work(metric):
    """浅层工作但勾了 ⇒ 算进去。（新分类不进「深度工作」桶也能计入成长）"""
    _meta('投简历', '浅层工作', growth=True)
    _hours('投简历', 2.5)
    out = growth_hours(metric, *_range())
    assert out['value'] == 2.5
    assert [b['label'] for b in out['breakdown']] == ['投简历']


def test_skips_deep_work_task_not_flagged(metric):
    """深度工作但**没勾** ⇒ 不算。（能排除，是这次改口径换来的能力）"""
    _meta('写作', '深度工作', growth=False)
    _hours('写作', 10)
    out = growth_hours(metric, *_range())
    assert out['value'] == 0.0
    assert out['breakdown'] == []


def test_both_directions_in_one_go(metric):
    """两条反向同时成立，才说明口径只看标记、不是「碰巧对上了」。"""
    _meta('写作', '深度工作', growth=False)
    _meta('投简历', '浅层工作', growth=True)
    _hours('写作', 10)
    _hours('投简历', 3)
    out = growth_hours(metric, *_range())
    assert out['value'] == 3.0
    assert [b['label'] for b in out['breakdown']] == ['投简历']
    # 溯源行仍带 L2：读数要能看出「这一行是什么类型」，才能判断勾得对不对
    assert out['breakdown'][0]['l2'] == '浅层工作'


def test_metric_where_is_ignored(metric):
    """`where` 写了什么都不会改变口径 —— 成长计时只有一根轴（那一个开关）。

    留一个可配的 `where` 就等于允许两处定义同一个量；
    真要过滤，用户该去映射编辑器勾/取消勾，而不是偷偷改 KPI 配置。
    """
    metric.source_config = {'kind': 'growth_hours', 'where': {'l2': ['被动消耗']}}
    metric.save(update_fields=['source_config'])

    _meta('投简历', '浅层工作', growth=True)
    _hours('投简历', 3)
    assert growth_hours(metric, *_range())['value'] == 3.0
