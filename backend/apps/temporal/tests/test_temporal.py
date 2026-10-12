"""时间追踪任务 CRUD + 时间区间筛选（CONVERT_TZ 回归）+ oneday stats 列名回归"""
import pytest
from datetime import date, datetime

from apps.temporal.models import TaskMeta, TemporalTask, OneDayPage


@pytest.mark.django_db
class TestTemporalTaskCrud:
    def _create_task(self, start='2026-08-10 10:00:00', name='任务A'):
        return TemporalTask.objects.create(
            task_name=name, start_time=datetime.fromisoformat(start),
            duration_hours=1.5, task_type='工作', notes='备注',
        )

    def test_api_create(self):
        from rest_framework.test import APIClient
        c = APIClient()
        r = c.post('/api/temporal/tasks/', {
            'task_name': '新任务', 'start_time': '2026-08-20 09:00:00',
            'duration_hours': 2, 'task_type': '学习', 'notes': '备注内容',
        }, format='json')
        assert r.status_code == 201
        assert r.data['notes'] == '备注内容'

    def test_api_update_notes(self):
        from rest_framework.test import APIClient
        c = APIClient()
        t = self._create_task()
        r = c.patch(f'/api/temporal/tasks/{t.id}/', {'notes': '改备注'}, format='json')
        assert r.status_code == 200 and r.data['notes'] == '改备注'

    def test_api_delete(self):
        from rest_framework.test import APIClient
        c = APIClient()
        t = self._create_task()
        assert c.delete(f'/api/temporal/tasks/{t.id}/').status_code == 204
        assert TemporalTask.objects.filter(id=t.id).count() == 0

    def test_date_range_filter(self):
        from rest_framework.test import APIClient
        self._create_task('2026-08-01 09:00:00')
        self._create_task('2026-08-20 09:00:00')
        self._create_task('2026-09-01 09:00:00')
        c = APIClient()
        r = c.get('/api/temporal/tasks/?date_from=2026-08-01&date_to=2026-08-31')
        assert r.data['count'] == 2


@pytest.mark.django_db
class TestManualTaskEntry:
    """v3.58.6：任务清单「手工新增 / 编辑」—— 时长由起止时间自动算，日历字段随之派生

    （手工新增不经过 CSV 导入，若不在这里派生 year/mon/day/week/quarter，
    新行会落成 NULL → 年份筛选、月度趋势、完整度分母会静默漏掉它。）
    """

    URL = '/api/temporal/tasks/'

    def test_create_derives_duration_and_calendar_fields(self):
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, {
            'task_name': '[SMOKE]手工补记', 'start_time': '2026-09-18 19:30:00',
            'end_time': '2026-09-18 23:00:00', 'notes': '手工新增',
        }, format='json')
        assert r.status_code == 201, r.data
        t = TemporalTask.objects.get(id=r.data['id'])
        assert t.duration_hours == 3.5                      # 19:30 → 23:00
        assert (t.year, t.mon, t.day) == (2026, '09', 18)
        assert t.week == date(2026, 9, 18).isocalendar()[1]
        assert t.quarter == 3
        assert t.task_type == '[SMOKE]手工补记'      # 与 CSV 导入同一约定（task_type 存任务名）
        assert r.data['duration_display'] == '03:30'

    def test_create_client_cannot_desync_duration(self):
        """起止都给时，调用方传的 duration_hours 被覆盖为「结束 − 开始」"""
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, {
            'task_name': '[SMOKE]防串', 'start_time': '2026-09-18 09:00:00',
            'end_time': '2026-09-18 10:00:00', 'duration_hours': 99,
        }, format='json')
        assert r.status_code == 201, r.data
        assert TemporalTask.objects.get(id=r.data['id']).duration_hours == 1.0

    def test_create_end_not_after_start_rejected(self):
        from rest_framework.test import APIClient
        r = APIClient().post(self.URL, {
            'task_name': '[SMOKE]倒挂', 'start_time': '2026-09-18 23:00:00',
            'end_time': '2026-09-18 22:00:00',
        }, format='json')
        assert r.status_code == 400
        assert 'end_time' in r.data

    def test_update_end_time_recomputes_duration(self):
        from rest_framework.test import APIClient
        t = TemporalTask.objects.create(
            task_name='[SMOKE]改结束', start_time=datetime(2026, 9, 18, 10, 0),
            end_time=datetime(2026, 9, 18, 11, 0), duration_hours=1.0,
        )
        r = APIClient().patch(f'{self.URL}{t.id}/', {'end_time': '2026-09-18 12:30:00'}, format='json')
        assert r.status_code == 200, r.data
        t.refresh_from_db()
        assert t.duration_hours == 2.5
        assert t.mon == '09'                                 # 只改结束时间也不该清掉日历字段

    def test_partial_update_notes_keeps_duration(self):
        """只改备注：不传起止时间 → 时长与日历字段原样保留（不猜、不清空）"""
        from rest_framework.test import APIClient
        t = TemporalTask.objects.create(
            task_name='[SMOKE]只改备注', start_time=datetime(2026, 9, 18, 8, 0),
            duration_hours=1.75, year=2026, mon='09', day=18, week=38, quarter=3,
        )
        r = APIClient().patch(f'{self.URL}{t.id}/', {'notes': '只改备注'}, format='json')
        assert r.status_code == 200 and r.data['notes'] == '只改备注'
        t.refresh_from_db()
        assert t.duration_hours == 1.75 and (t.year, t.mon) == (2026, '09')

    def test_create_new_task_name_lands_in_meta(self):
        """手工新增一个新 task_name → 自动进 TaskMeta（未归类桶），否则映射编辑器看不到它"""
        from rest_framework.test import APIClient
        from apps.temporal.models import TaskMeta
        name = '[SMOKE]全新任务名'
        TaskMeta.objects.filter(task_name=name).delete()
        r = APIClient().post(self.URL, {
            'task_name': name, 'start_time': '2026-09-18 14:00:00', 'end_time': '2026-09-18 15:00:00',
        }, format='json')
        assert r.status_code == 201, r.data
        m = TaskMeta.objects.filter(task_name=name).first()
        assert m is not None and m.activity_type == '未归类'


@pytest.mark.django_db
class TestBuildTimeFields:
    """v3.58.6 抽出的公共派生函数：CSV 导入与手工录入共用一套口径"""

    def test_date_only_no_duration(self):
        from apps.temporal.services import build_time_fields
        f = build_time_fields(datetime(2026, 1, 5, 8, 0))
        assert f == {'year': 2026, 'mon': '01', 'day': 5, 'week': 2, 'quarter': 1}
        assert 'duration_hours' not in f        # 不传 end → 不碰时长（导入走 ATracker 自带值）

    def test_with_end_derives_duration(self):
        from apps.temporal.services import build_time_fields
        f = build_time_fields(datetime(2026, 1, 5, 8, 0), datetime(2026, 1, 5, 9, 30))
        assert f['duration_hours'] == 1.5

    def test_quarter_boundaries(self):
        from apps.temporal.services import build_time_fields
        assert build_time_fields(datetime(2026, 3, 31, 1, 0))['quarter'] == 1
        assert build_time_fields(datetime(2026, 4, 1, 1, 0))['quarter'] == 2
        assert build_time_fields(datetime(2026, 12, 31, 1, 0))['quarter'] == 4


@pytest.mark.django_db
class TestOneDayStats:
    def test_stats_no_500_and_counts(self):
        """回归：beginDate 列重命名后 stats 不再 500"""
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='第一篇', begin_date=date(2026, 8, 1), oneday=100, page=50, total=150, years='2026')
        OneDayPage.objects.create(title='第二篇', begin_date=date(2026, 8, 2), oneday=200, page=100, total=300, years='2026')
        c = APIClient()
        r = c.get('/api/temporal/oneday/stats/')
        assert r.status_code == 200
        assert r.data['total_count'] == 2
        assert r.data['total_words'] == 450
        assert len(r.data['month_stats']) >= 1


@pytest.mark.django_db
class TestOneDayFlagFilter:
    def test_flag_substring_filter(self):
        """flag 多标签（逗号分隔）子串检索：flag=待回顾 应命中 '待回顾,美食'"""
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='需要回顾', begin_date=date(2026, 8, 22), flag='待回顾,美食')
        OneDayPage.objects.create(title='普通', begin_date=date(2026, 8, 23), flag=None)
        OneDayPage.objects.create(title='其他标签', begin_date=date(2026, 8, 24), flag='思考')
        c = APIClient()
        r = c.get('/api/temporal/oneday/?flag=待回顾')
        rows = r.data.get('results') or r.data
        titles = [x['title'] for x in rows]
        assert '需要回顾' in titles, titles
        assert '普通' not in titles and '其他标签' not in titles, titles

    def test_no_flag_param_returns_all(self):
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='A', begin_date=date(2026, 8, 22), flag='待回顾')
        OneDayPage.objects.create(title='B', begin_date=date(2026, 8, 23), flag=None)
        c = APIClient()
        rows = c.get('/api/temporal/oneday/').data.get('results') or []
        # list 会经 DailyLogAutoService 自动生成今日默认日记，因此 >= 2 且含 A/B
        titles = [x['title'] for x in rows]
        assert len(rows) >= 2
        assert 'A' in titles and 'B' in titles


@pytest.mark.django_db
class TestContribEndpoints:
    def test_task_contrib(self):
        from datetime import date
        from rest_framework.test import APIClient
        TemporalTask.objects.create(task_name='T1', start_time=datetime.fromisoformat('2026-08-01 09:00:00'), duration_hours=2.5)
        TemporalTask.objects.create(task_name='T2', start_time=datetime.fromisoformat('2026-08-01 14:00:00'), duration_hours=1.5)
        TemporalTask.objects.create(task_name='T3', start_time=datetime.fromisoformat('2026-08-02 09:00:00'), duration_hours=3)
        d = APIClient().get('/api/temporal/tasks/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == '2026-08-01')
        assert day1['value'] == 4.0
        assert d['min_year'] == 2026 and d['summary']['total_days'] == 2

    def test_oneday_contrib(self):
        from datetime import date
        from rest_framework.test import APIClient
        OneDayPage.objects.create(title='D1', begin_date=date(2026, 8, 1), oneday=100, page=50)
        OneDayPage.objects.create(title='D2', begin_date=date(2026, 8, 1), oneday=200, page=0)
        d = APIClient().get('/api/temporal/oneday/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == '2026-08-01')
        assert day1['value'] == 350.0  # total = oneday + page

    def test_bill_contrib_net_value(self):
        from datetime import datetime
        from rest_framework.test import APIClient
        from apps.wealth.models import WealthBillList
        now = datetime.now()
        WealthBillList.objects.create(transaction_type='收入', date=now, amount=1000, user_id=1, created_at=now, updated_at=now)
        WealthBillList.objects.create(transaction_type='支出', date=now, amount=300, user_id=1, created_at=now, updated_at=now)
        d = APIClient().get('/api/wealth/bills/contrib/').data
        day1 = next(x for x in d['data'] if x['date'] == now.strftime('%Y-%m-%d'))
        assert day1['value'] == 700.0  # 收入-支出净值

    def test_health_contrib(self):
        from datetime import datetime
        from rest_framework.test import APIClient
        from apps.health.models import HealthRecord
        HealthRecord.objects.create(time=datetime.now(), total=8000, htype=1)
        d = APIClient().get('/api/health/records/contrib/').data
        assert d['summary']['total_days'] >= 1


@pytest.mark.django_db
class TestContribExcludesSleep:
    """v3.60.27：睡眠类任务**不计入**「时间贡献图」

    病根：「休息睡眠」的 L2 = 主动休息 ⇒ 归因 = 维持。一天 8h 睡眠会成为当天**最大**
    归因，而热力图默认口径就是「主导归因」⇒ 几乎天天一片「维持」色，
    真正想看的结构（成长 / 谋生 / 关系）全被压掉。

    ⚠️ 边界：**只剔贡献图**（含点格子的当天明细）。时间统计页的总时长 / 完整度 /
    旭日图 / 月度趋势 / 168h 结构**照旧包含**睡眠 —— 那是「一天到底怎么花的」全量口径。
    本类最后一条用例专门钉住这条边界，防止将来有人把过滤顺手提到公共取数里。
    """

    CONTRIB = '/api/temporal/tasks/contrib/'
    DETAIL = '/api/temporal/tasks/daily_detail/'
    STATS = '/api/temporal/tasks/stats/'

    def _seed(self):
        """2026-08-01 共 13h / 3 条：休息睡眠 8h（维持）+ 阅读思考 4h（成长）+ 牛马工作 1h（谋生）

        剔掉睡眠后应为 5h / 2 条，主导归因「成长」（4h > 谋生 1h）。
        """
        for name, at, attr in [
            ('休息睡眠', '主动休息', '维持'),
            ('阅读思考', '深度工作', '成长'),
            ('牛马工作', '浅层工作', '谋生'),
        ]:
            TaskMeta.objects.create(task_name=name, activity_type=at, default_attribution=attr)
        for name, hour, dur in [('休息睡眠', 0, 8), ('阅读思考', 10, 4), ('牛马工作', 14, 1)]:
            TemporalTask.objects.create(
                task_name=name,
                start_time=datetime.fromisoformat(f'2026-08-01 {hour:02d}:00:00'),
                duration_hours=dur,
                year=2026, mon='08', day=1,
            )

    def _contrib(self, metric='hours'):
        from rest_framework.test import APIClient
        return APIClient().get(self.CONTRIB, {'metric': metric}).data

    def _day(self, body, iso='2026-08-01'):
        return next(x for x in body['data'] if x['date'] == iso)

    def test_hours_metric_excludes_sleep(self):
        """小时口径：8h 睡眠不能算进那天（否则每天 +8h，峰值与总量一起虚高）"""
        self._seed()
        assert self._day(self._contrib('hours'))['value'] == 5.0      # 4 + 1，不含 8

    def test_record_count_metric_excludes_sleep(self):
        """记录数口径：睡眠那条也不该占一笔"""
        self._seed()
        assert self._day(self._contrib('record_count'))['value'] == 2

    def test_sleep_never_becomes_dominant_attr(self):
        """🔴 本轮核心：8h「维持」不能再当那天的主导归因"""
        self._seed()
        day = self._day(self._contrib('dominant_attr'))
        assert day['attr'] == '成长'            # 剔掉睡眠后：成长 4h > 谋生 1h
        assert day['breakdown']['维持'] == 0     # 「维持」桶里一点都不剩

    def test_other_metrics_are_not_collateral_damage(self):
        """剔睡眠**只**动睡眠：成长 / 牛马工作两个口径照旧精确"""
        self._seed()
        assert self._day(self._contrib('toward'))['value'] == 4.0     # 成长小时
        assert self._day(self._contrib('work'))['value'] == 1.0       # 牛马工作

    def test_nap_is_excluded_too(self):
        """名单是**两个**：只剔「休息睡眠」的话午睡会继续定色

        （实测开发库 2026-10-07 / 10-09 两天的主导归因就是被午睡顶成「维持」的。）
        """
        self._seed()
        TaskMeta.objects.create(task_name='午睡', activity_type='主动休息', default_attribution='维持')
        TemporalTask.objects.create(
            task_name='午睡', start_time=datetime.fromisoformat('2026-08-01 13:00:00'),
            duration_hours=2, year=2026, mon='08', day=1,
        )
        # 那天变成 15h / 4 条；两个睡眠任务都被剔 ⇒ 仍应是 5h / 2 条
        assert self._day(self._contrib('hours'))['value'] == 5.0
        assert self._day(self._contrib('record_count'))['value'] == 2

    def test_a_day_with_only_sleep_drops_out_of_the_graph(self):
        """只有睡眠的天会**整格消失**（前端渲染成空白格、不可点）

        语义是「那天没有可分析的活动」。这不是 bug —— 钉住它，
        防止将来有人当成「数据丢了」去改回来。
        """
        TaskMeta.objects.create(task_name='休息睡眠', activity_type='主动休息', default_attribution='维持')
        TemporalTask.objects.create(
            task_name='休息睡眠', start_time=datetime.fromisoformat('2026-08-03 00:00:00'),
            duration_hours=8, year=2026, mon='08', day=3,
        )
        assert all(x['date'] != '2026-08-03' for x in self._contrib('hours')['data'])

    def test_daily_detail_scope_contrib_excludes_sleep(self):
        """点格子弹的明细：不带 scope = 当天全部（通用口径）；scope=contrib = 与热力图同口径

        ⚠️ 默认**不**过滤是故意的：这是通用明细接口，将来别处复用时不该莫名少几行
        （「少行且不报错」正是本项目反复防的那类静默失败）。
        """
        self._seed()
        from rest_framework.test import APIClient
        c = APIClient()
        full = c.get(self.DETAIL, {'date': '2026-08-01'}).data
        assert len(full['items']) == 3 and full['total'] == 13.0
        scoped = c.get(self.DETAIL, {'date': '2026-08-01', 'scope': 'contrib'}).data
        assert len(scoped['items']) == 2 and scoped['total'] == 5.0
        assert all(i['task_name'] != '休息睡眠' for i in scoped['items'])

    def test_exclusion_list_is_pinned(self):
        """名单内容钉死 —— 改任务名 / 新增同类睡眠任务时，这条会失败并提醒同步 constants

        名单是「按任务名」的口径，天生带着「改名之后静默漏掉」的风险；
        这条用例是那个风险的唯一警报器（没有它，漏掉是无声的）。
        """
        from apps.temporal.constants import CONTRIB_EXCLUDED_TASK_NAMES
        assert CONTRIB_EXCLUDED_TASK_NAMES == {'休息睡眠', '午睡'}

    def test_time_stats_page_still_counts_sleep(self):
        """🔴 边界钉子：**只剔贡献图**，时间统计页的总时长照旧含睡眠

        那页是「一天到底怎么花的」的全量口径。把过滤提到那里等于改变了
        「已记录 / 总时间」的含义 —— 而完整度分母本来就是 16h「清醒时段」，
        真要动它是一次独立的、需要重新想清楚的口径决策，不在本轮。
        """
        self._seed()
        from rest_framework.test import APIClient
        ov = APIClient().get(self.STATS, {'year': 2026}).data
        assert ov['total_hours'] == 13.0        # 8 + 4 + 1，含睡眠
