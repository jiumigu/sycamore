"""月度加班台账 → 逐日工作时间记录：生成层 + 落库命令（v3.60.8）

两道防线：
1. **纯函数层**（工作日历、分钟分摊、三情形摊派）—— 不碰 DB，跑得快，钉死规则；
2. **命令层**（干跑不写 / 字段口径 / 幂等）—— 用临时 xlsx 走真流程。

⚠️ 幂等之所以重要：这批记录是**推定值**，一旦重复写入，
「加班合计」会静默翻倍而界面上看不出差别。
"""
import io
import zipfile
from datetime import date, datetime, timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.overtime_recon import (
    ALL_LEAVE,
    BATCH_DEFAULT,
    FULL_LEAVE,
    GRAN,
    build_plan,
    candidates_of,
    plan_month,
    read_monthly,
    restdays_of,
    split_minutes,
    spread,
    workdays_of,
)

# ════════════════════════════════════════════════════════════════════════════
# 最小 xlsx 生成器（与 test_worklog_import 同一套路：手写 zip + XML）
# ════════════════════════════════════════════════════════════════════════════
_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def _cell_xml(col: str, row: int, val) -> str:
    ref = f'{col}{row}'
    if val is None or val == '':
        return ''
    if isinstance(val, (int, float)):
        return f'<c r="{ref}"><v>{val}</v></c>'
    esc = str(val).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{esc}</t></is></c>'


def make_ledger_xlsx(path, pairs) -> str:
    """造一份只含 Sheet1（A=YYYY-M，B=加班小时）的最小 xlsx"""
    rows = [['月份', '加班小时']] + [[k, v] for k, v in pairs]
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                   '</Types>')
        z.writestr('_rels/.rels',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{_RNS}/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        z.writestr('xl/workbook.xml',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   f'<workbook xmlns="{_NS}" xmlns:r="{_RNS}"><sheets>'
                   '<sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{_RNS}/worksheet" Target="worksheets/sheet1.xml"/>'
                   '</Relationships>')
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               f'<worksheet xmlns="{_NS}"><sheetData>']
        for rn, cells in enumerate(rows, start=1):
            xml.append(f'<row r="{rn}">')
            for ci, val in enumerate(cells):
                xml.append(_cell_xml(chr(ord('A') + ci), rn, val))
            xml.append('</row>')
        xml.append('</sheetData></worksheet>')
        z.writestr('xl/worksheets/sheet1.xml', ''.join(xml))
    return str(path)


# ════════════════════════════════════════════════════════════════════════════
# 纯函数：工作日历
# ════════════════════════════════════════════════════════════════════════════
class TestWorkCalendar:
    def test_holiday_is_not_workday(self):
        """国庆 10-01~10-07 不排班"""
        wd = workdays_of(2021, 10)
        for d in range(1, 8):
            assert date(2021, 10, d) not in wd

    def test_makeup_saturday_is_workday(self):
        """调休补班日（周六 2021-10-09）按工作日算，且不再是休息日"""
        assert date(2021, 10, 9) in workdays_of(2021, 10)
        assert date(2021, 10, 9) not in restdays_of(2021, 10)

    def test_full_leave_removed_from_workdays(self):
        """整天请假的日子不算工作日"""
        assert date(2022, 1, 28) not in workdays_of(2022, 1)

    def test_candidates_exclude_every_kind_of_leave(self):
        """全天假 / 半天假 / 计时假 一律移出加班候选"""
        cand = candidates_of(2022, 9)
        assert date(2022, 9, 9) not in cand        # 全天假
        assert date(2022, 9, 13) not in cand       # 半天假
        assert date(2022, 9, 22) not in cand       # 计时假
        # 半天假仍然是「工作日」（要出记录），只是不参与加班
        assert date(2022, 9, 13) in workdays_of(2022, 9)


# ════════════════════════════════════════════════════════════════════════════
# 纯函数：分摊工具
# ════════════════════════════════════════════════════════════════════════════
class TestSplitTools:
    def test_split_exact_and_multiple_of_granularity(self):
        parts = split_minutes(5430, 23)
        assert sum(parts) == 5430, '总量必须精确'
        assert all(p % GRAN == 0 for p in parts), '每份都是 5 分钟的倍数'

    def test_split_rejects_non_multiple(self):
        with pytest.raises(AssertionError):
            split_minutes(1234, 5)

    def test_spread_is_even_not_at_edges(self):
        idx = spread(22, 3)
        assert len(idx) == 3
        assert idx == sorted(idx)
        assert idx[0] >= 2 and idx[-1] <= 19, '不集中在月初/月末'


# ════════════════════════════════════════════════════════════════════════════
# 纯函数：三情形摊派
# ════════════════════════════════════════════════════════════════════════════
class TestPlanMonth:
    def test_overfull_alternates_three_and_two_half(self):
        """溢出月（2021-12）：一半 3h / 一半 2.5h，且**交错**排"""
        entries, stat = plan_month(2021, 12, 90.5)
        work = sorted([e for e in entries if e.kind == 'work_ot'], key=lambda e: e.day)
        assert len(work) == 23
        assert sum(1 for e in work if e.ot == 180) == 12
        assert sum(1 for e in work if e.ot == 150) == 11
        # 交错（3h→2.5h→3h→2.5h），不是前半 3h 后半 2.5h
        assert [e.ot for e in work[:4]] == [180, 150, 180, 150]
        we = [e for e in entries if e.kind == 'weekend_ot']
        assert len(we) == 3 and all(e.ot == 540 for e in we)
        assert stat.branch == 'overfull'

    def test_overfull_2021_10_remainder_to_weekend(self):
        """17 个候选日：9×3h + 8×2.5h = 47h，余 17h 由 2 个周末日承接"""
        entries, stat = plan_month(2021, 10, 64.0)
        work = [e for e in entries if e.kind == 'work_ot']
        assert len(work) == 17
        assert sum(1 for e in work if e.ot == 180) == 9
        assert sum(1 for e in work if e.ot == 150) == 8
        assert sum(e.ot for e in entries if e.kind == 'weekend_ot') == 17 * 60
        assert stat.weekend_ot_days == 2

    def test_edge_month_stays_all_candidate(self):
        """2022-05（2.79h/天，仅超 2.75h）**不**进溢出分支。

        这是「判定阈值不跟着铺法下调」的判据：若下调，该月会产出 0.5h 的
        周末加班（0.75h 摊到 19 天 = 每天 2.4 分钟，落不成 5 分钟粒度）。
        """
        entries, stat = plan_month(2022, 5, 53.0)
        assert stat.branch == 'all_cand'
        assert not [e for e in entries if e.kind == 'weekend_ot']
        assert all(120 <= e.ot <= 180 for e in entries if e.kind == 'work_ot')

    def test_conservation_across_branches(self):
        """三情形各取一例：每月加班总量必须精确等于台账"""
        cases = [(2020, 4, 24.5), (2021, 12, 90.5), (2022, 5, 53.0), (2022, 12, 2.5)]
        for y, m, h in cases:
            entries, stat = plan_month(y, m, h)
            assert sum(e.ot for e in entries) == round(h * 60), f'{y}-{m} 总量不符'
            assert stat.ok, f'{y}-{m} 核对未过'
            assert sum(p.ot for p in entries if p.kind == 'work_ot') <= len(
                candidates_of(y, m)) * 180

    def test_leave_never_gets_overtime(self):
        """任何请假日都不排加班"""
        for y, m, h in [(2022, 1, 24.5), (2022, 5, 53.0), (2022, 9, 16.5)]:
            entries, _ = plan_month(y, m, h)
            assert not [e for e in entries if e.day in ALL_LEAVE and e.ot > 0], f'{y}-{m}'

    def test_full_leave_has_no_entry(self):
        """整天请假 → 那天根本没有记录（不是记 0 小时）"""
        entries, _ = plan_month(2022, 9, 16.5)
        assert not [e for e in entries if e.day in FULL_LEAVE]

    def test_leave_times(self):
        """半天假记下午 13:30→18:00；计时假从 18:00 往前扣 2.5h"""
        entries, _ = plan_month(2022, 9, 16.5)
        by_day = {e.day: e for e in entries}
        st, en = by_day[date(2022, 9, 13)].times()
        assert (st.strftime('%H:%M'), en.strftime('%H:%M')) == ('13:30', '18:00')
        st, en = by_day[date(2022, 9, 22)].times()
        assert (st.strftime('%H:%M'), en.strftime('%H:%M')) == ('09:00', '15:30')

    def test_normal_workday_window(self):
        """不加班的工作日 = 09:00→18:00（9.0h）"""
        entries, _ = plan_month(2020, 5, 8.5)
        work = [e for e in entries if e.kind == 'work'][0]
        st, en = work.times()
        assert (st.strftime('%H:%M'), en.strftime('%H:%M')) == ('09:00', '18:00')
        assert work.hours == 9.0

    def test_weekend_ot_starts_at_ten(self):
        """周末加班独立一条、10:00 起，不另写 09:00 那条"""
        entries, _ = plan_month(2021, 12, 90.5)
        by_day_we = [e for e in entries if e.kind == 'weekend_ot']
        assert by_day_we, '该月应有周末加班'
        for e in by_day_we:
            st, _ = e.times()
            assert st.strftime('%H:%M') == '10:00'
            # 同日不应再有别的条目
            assert len([x for x in entries if x.day == e.day]) == 1


# ════════════════════════════════════════════════════════════════════════════
# 读台账 + 全量计划
# ════════════════════════════════════════════════════════════════════════════
class TestBuildPlan:
    def test_reads_ledger_and_verifies_every_month(self, tmp_path):
        path = make_ledger_xlsx(tmp_path / 'ledger.xlsx',
                                [('2021-10', 64.0), ('2021-11', 83.0), ('2021-12', 90.5)])
        assert read_monthly(path) == [
            (date(2021, 10, 1), 64.0), (date(2021, 11, 1), 83.0), (date(2021, 12, 1), 90.5)]

        entries, stats = build_plan(path, date(2021, 10, 1), date(2021, 12, 31))
        assert len(stats) == 3 and all(s.ok for s in stats)
        assert sum(e.ot for e in entries) == round((64 + 83 + 90.5) * 60)

    def test_range_filter(self, tmp_path):
        path = make_ledger_xlsx(tmp_path / 'ledger.xlsx',
                                [('2021-10', 64.0), ('2021-12', 90.5)])
        _, stats = build_plan(path, date(2021, 12, 1), date(2021, 12, 31))
        assert [(s.year, s.month) for s in stats] == [(2021, 12)]


# ════════════════════════════════════════════════════════════════════════════
# 命令层（碰 DB，逐个类带标记）
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestReconstructCommand:
    PAIRS = (('2020-05', 8.5), ('2021-12', 90.5))

    def _ledger(self, tmp_path):
        return make_ledger_xlsx(tmp_path / 'ledger.xlsx', list(self.PAIRS))

    def test_dry_run_writes_nothing(self, tmp_path):
        out = io.StringIO()
        call_command('reconstruct_worktime', self._ledger(tmp_path), stdout=out)
        assert TemporalTask.objects.filter(import_batch=BATCH_DEFAULT).count() == 0
        assert '[干跑]' in out.getvalue()
        assert '33/33' not in out.getvalue()          # 只处理了两个月的台账
        assert '月度核对 = 2/2' in out.getvalue()

    def test_apply_then_rerun_is_idempotent(self, tmp_path):
        path = self._ledger(tmp_path)
        expect, _ = build_plan(path, date(2020, 5, 1), date(2021, 12, 31))
        n_expected = len(expect)

        call_command('reconstruct_worktime', path, '--apply', stdout=io.StringIO())
        qs = TemporalTask.objects.filter(import_batch=BATCH_DEFAULT)
        assert qs.count() == n_expected
        first_ids = sorted(qs.values_list('id', flat=True))

        # 重跑：一条都不新增（推定的工时绝不能静默翻倍）
        out2 = io.StringIO()
        call_command('reconstruct_worktime', path, '--apply', stdout=out2)
        assert TemporalTask.objects.filter(import_batch=BATCH_DEFAULT).count() == n_expected
        assert sorted(qs.values_list('id', flat=True)) == first_ids
        assert '跳过重复' in out2.getvalue()

    def test_field_conventions(self, tmp_path):
        call_command('reconstruct_worktime', self._ledger(tmp_path), '--apply',
                     stdout=io.StringIO())
        # 取一条「正常上班」记录核对口径（不硬编码具体日期：
        # 2020-05-01 是劳动节假期，当月第一个工作日是 05-06）
        obj = (TemporalTask.objects
               .filter(import_batch=BATCH_DEFAULT, task_description__contains='正常上班')
               .order_by('start_time').first())
        assert obj is not None
        assert obj.task_name == '牛马工作'
        assert obj.task_type == '牛马工作'
        assert obj.notes == '', '与既有记录一致：空串而非 NULL'
        assert obj.duration is None, '与既有记录一致：留 NULL'
        assert obj.tags is None
        assert obj.import_batch == BATCH_DEFAULT
        assert (obj.year, obj.mon, obj.quarter) == (2020, '05', 2)
        assert obj.day == obj.start_time.day
        assert obj.duration_hours == 9.0
        assert obj.start_time.strftime('%H:%M') == '09:00'
        assert obj.end_time.strftime('%H:%M') == '18:00'
        assert '月度台账反推' in obj.task_description

    def test_does_not_touch_existing_records(self, tmp_path):
        """只新增，绝不改写已有记录（哪怕落在同一区间、同一天）"""
        TemporalTask.objects.create(
            task_name='牛马工作', task_description='[2020-05-06] 原有记录',
            start_time='2020-05-06T09:00:00+08:00', end_time='2020-05-06T18:00:00+08:00',
            duration_hours=9.0, notes='原有备注', task_type='牛马工作',
            import_batch='worklog')

        call_command('reconstruct_worktime', self._ledger(tmp_path), '--apply',
                     stdout=io.StringIO())

        after = TemporalTask.objects.get(import_batch='worklog')
        assert after.task_description == '[2020-05-06] 原有记录'
        assert after.notes == '原有备注'
        # 当天仍按计划生成了自己的记录，两条并存
        # （幂等键带 import_batch，别的来源的记录不影响本批次生成）
        lo = timezone.make_aware(datetime(2020, 5, 6))
        assert TemporalTask.objects.filter(
            task_name='牛马工作', start_time__gte=lo,
            start_time__lt=lo + timedelta(days=1)).count() == 2
