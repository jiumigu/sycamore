"""实时计时（Timer）—— 开始 / 停止 / 丢弃 / 运行中查询

重点钉住四条：
1. 停止后必须写出**字段完整**的 TemporalTask（时长 + 日历字段 + 来源标记 + TaskMeta 建档）；
2. 太短（<30s）不入账，且返回原因（不能假装成功）；
3. 超长（>4h）必须用户确认；**自动收尾时超长一律不入账**（防一夜没停写出 24 小时脏数据）；
4. 同一时刻只有一条 running。

⚠️ 会话的开始时间都用「距今 N 分钟」构造，不写死日期 —— 写死会在几周后静默失效。
"""
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.temporal.models import TaskMeta, TemporalTask, TimerSession


URL = '/api/temporal/timer'


def _post(path: str, data: dict):
    return APIClient().post(f'{URL}/{path}/', data, format='json')


def _get(path: str):
    return APIClient().get(f'{URL}/{path}/')


def _running_started(minutes_ago: int, name: str = '写代码') -> TimerSession:
    """直接造一条 running 会话，绕过 HTTP —— 用来模拟「已经跑了一段时间」。"""
    return TimerSession.objects.create(
        task_name=name,
        start_time=timezone.now() - timedelta(minutes=minutes_ago),
        status='running',
    )


@pytest.mark.django_db
class TestStart:
    def test_start_creates_running_session(self):
        r = _post('start', {'task_name': '  写代码  '})
        assert r.status_code == 200, r.content
        body = r.json()
        assert body['session']['status'] == 'running'
        # 任务名去首尾空格后落库
        assert body['session']['task_name'] == '写代码'
        assert body['prev'] is None
        assert TimerSession.objects.filter(status='running').count() == 1

    def test_blank_task_name_rejected(self):
        """必填校验在后端也在 —— 不能只靠前端禁用按钮。"""
        r = _post('start', {'task_name': '   '})
        assert r.status_code == 400
        assert r.json()['code'] == 'invalid'
        assert TimerSession.objects.count() == 0

    def test_running_reports_server_elapsed(self):
        """已流逝时长由后端算：前端拿它当锚点，不拿本地时钟减开始时刻。"""
        _running_started(minutes_ago=125)
        body = _get('running').json()
        assert body['session'] is not None
        # 125 分钟 = 7500 秒，留 10 秒容差给测试执行耗时
        assert 7500 <= body['elapsed_seconds'] <= 7520
        assert body['min_seconds'] == 30
        assert body['long_seconds'] == 4 * 3600

    def test_running_is_null_when_idle(self):
        body = _get('running').json()
        assert body['session'] is None
        assert body['elapsed_seconds'] == 0

    def test_start_auto_closes_previous(self):
        """点新任务 → 上一个自动收尾并入账；同一时刻只剩一个新的 running。"""
        prev = _running_started(minutes_ago=60, name='写作')

        body = _post('start', {'task_name': '写代码'}).json()

        assert body['prev']['outcome'] == 'saved'
        assert body['prev']['task_name'] == '写作'
        prev.refresh_from_db()
        assert prev.status == 'done'
        assert prev.task_id is not None
        assert TimerSession.objects.filter(status='running').count() == 1
        assert TemporalTask.objects.filter(task_name='写作').count() == 1


@pytest.mark.django_db
class TestStop:
    def test_stop_writes_complete_temporal_task(self):
        """停止 → 一条字段完整的记录：时长、日历字段、来源、TaskMeta 全部到位。"""
        session = _running_started(minutes_ago=120, name='深度工作')

        r = _post('stop', {'session_id': session.id, 'notes': '改完了展厅'})
        assert r.status_code == 200, r.content
        result = r.json()['result']
        assert result['outcome'] == 'saved'

        task = TemporalTask.objects.get(id=result['task_id'])
        assert task.task_name == '深度工作'
        assert task.notes == '改完了展厅'
        assert task.duration_hours == pytest.approx(2.0, abs=0.02)

        # 日历字段按**开始时刻**派生（跨零点不错日）—— 这里独立算一遍做对账
        local_start = timezone.localtime(task.start_time)
        assert task.year == local_start.year
        assert task.mon == f'{local_start.month:02d}'
        assert task.day == local_start.day
        assert task.week == local_start.isocalendar()[1]
        assert task.quarter == (local_start.month - 1) // 3 + 1

        # 来源标记：serializer 里 import_batch 是 read_only，必须在保存后补写
        assert task.import_batch == 'timer'

        # 新任务名必须进 TaskMeta，否则分类台账/映射编辑器里看不到它
        assert TaskMeta.objects.filter(task_name='深度工作').exists()

        session.refresh_from_db()
        assert session.status == 'done'
        assert session.task_id == task.id

    def test_stop_too_short_is_discarded_and_says_so(self):
        """10 秒的计时不入账 —— 但必须返回 too_short，前端才能提示。"""
        session = TimerSession.objects.create(
            task_name='误触', start_time=timezone.now() - timedelta(seconds=10), status='running',
        )
        r = _post('stop', {'session_id': session.id})
        assert r.status_code == 200, r.content
        assert r.json()['result']['outcome'] == 'too_short'
        assert TemporalTask.objects.count() == 0
        session.refresh_from_db()
        assert session.status == 'discarded'

    def test_stop_over_four_hours_requires_confirmation(self):
        """>4h 先 409，会话保持 running；带 allow_long 才入账。"""
        session = _running_started(minutes_ago=5 * 60, name='忘记停')

        r = _post('stop', {'session_id': session.id})
        assert r.status_code == 409
        assert r.json()['code'] == 'too_long'
        assert TemporalTask.objects.count() == 0
        session.refresh_from_db()
        assert session.status == 'running'

        r2 = _post('stop', {'session_id': session.id, 'allow_long': True})
        assert r2.status_code == 200, r2.content
        assert r2.json()['result']['outcome'] == 'saved'
        assert TemporalTask.objects.filter(task_name='忘记停').count() == 1

    def test_stop_is_idempotent(self):
        """重复点停止不会写出两条记录。"""
        session = _running_started(minutes_ago=45, name='阅读')
        first = _post('stop', {'session_id': session.id}).json()
        second = _post('stop', {'session_id': session.id}).json()

        assert first['result']['outcome'] == 'saved'
        assert second['result']['outcome'] == 'already_closed'
        assert TemporalTask.objects.filter(task_name='阅读').count() == 1

    def test_stop_unknown_session_returns_404(self):
        r = _post('stop', {'session_id': 999999})
        assert r.status_code == 404
        assert r.json()['code'] == 'not_found'

    def test_discard_writes_nothing(self):
        session = _running_started(minutes_ago=90, name='不想记')
        r = _post('discard', {'session_id': session.id})
        assert r.status_code == 200
        assert r.json()['result']['outcome'] == 'discarded'
        assert TemporalTask.objects.count() == 0
        session.refresh_from_db()
        assert session.status == 'discarded'


@pytest.mark.django_db
class TestAutoCloseGuard:
    def test_auto_close_over_four_hours_is_not_saved(self):
        """忘了一夜没停：点新任务时**不**自动写一条 24 小时记录，只回提示。

        这条记录会进月度趋势 / 贡献图 / 平衡轮 / 自运转的时间分配分母，
        静默写进去比少一条严重得多。
        """
        prev = _running_started(minutes_ago=24 * 60, name='忘记停的')

        body = _post('start', {'task_name': '新任务'}).json()

        assert body['prev']['outcome'] == 'too_long_dropped'
        assert body['prev']['elapsed_seconds'] > 4 * 3600
        assert TemporalTask.objects.filter(task_name='忘记停的').count() == 0
        prev.refresh_from_db()
        assert prev.status == 'discarded'
        # 新会话照常开始
        assert TimerSession.objects.filter(status='running', task_name='新任务').count() == 1
