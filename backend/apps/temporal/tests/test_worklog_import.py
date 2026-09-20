"""工作日志 → 牛马工作记录：解析层 + 导入命令（v3.58.7）

两道防线：
1. 纯函数层（加班四代解析、状态分类、工时窗口）——不碰 DB，跑得快、钉死规则；
2. 命令层（干跑/落库/幂等/追加）——用临时 xlsx 走真流程，确认不会重复写、不会误写。
"""
import csv
import zipfile
from datetime import date, datetime, time

import pytest

from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.worklog_parser import (
    WorkLogRow,
    build_plan,
    classify_status,
    is_early_leave,
    is_offday,
    is_overtime,
    is_restday,
    plan_day,
    read_worklog_rows,
    resolve_overtime_end,
    work_window,
)

# ════════════════════════════════════════════════════════════════════════════
# 最小 xlsx 生成器：pytest 环境没有 openpyxl（项目 venv 也不装），
# 手写 zip + XML 造表，正好顺带验证标准库读取路径。
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


def make_xlsx(path, sheets):
    """sheets: [(sheet_name, [[A,B,C,...], ...])]，行 1 是表头"""
    ct = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    wb_sheets, wb_rels = [], []
    for i, (name, _rows) in enumerate(sheets, start=1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        wb_sheets.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
        wb_rels.append(f'<Relationship Id="rId{i}" Type="{_RNS}/worksheet" Target="worksheets/sheet{i}.xml"/>')
    ct.append('</Types>')

    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', ''.join(ct))
        z.writestr('_rels/.rels',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="%s/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>' % _RNS)
        z.writestr('xl/workbook.xml',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   f'<workbook xmlns="{_NS}" xmlns:r="{_RNS}"><sheets>'
                   + ''.join(wb_sheets) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + ''.join(wb_rels) + '</Relationships>')
        for i, (_name, rows) in enumerate(sheets, start=1):
            xml = ['<?xml version="1.0" encoding="UTF-8"?>',
                   f'<worksheet xmlns="{_NS}"><sheetData>']
            for rn, cells in enumerate(rows, start=1):
                xml.append(f'<row r="{rn}">')
                for ci, val in enumerate(cells):
                    col = chr(ord('A') + ci)
                    xml.append(_cell_xml(col, rn, val))
                xml.append('</row>')
            xml.append('</sheetData></worksheet>')
            z.writestr(f'xl/worksheets/sheet{i}.xml', ''.join(xml))


def _serial(y, m, d, hh=0, mm=0):
    """日期 → Excel 序列号"""
    dt = datetime(y, m, d, hh, mm) - datetime(1899, 12, 30)
    return dt.days + dt.seconds / 86400


# ════════════════════════════════════════════════════════════════════════════
# 纯函数
# ════════════════════════════════════════════════════════════════════════════
class TestWorkWindow:
    def test_switch_at_2026_03_02(self):
        assert work_window(date(2026, 2, 27)) == (time(9, 0), time(18, 0))
        assert work_window(date(2026, 3, 1)) == (time(9, 0), time(18, 0))
        assert work_window(date(2026, 3, 2)) == (time(8, 0), time(17, 45))
        assert work_window(date(2026, 9, 17)) == (time(8, 0), time(17, 45))


class TestClassifyStatus:
    @pytest.mark.parametrize('status,expect', [
        ('正常上班', 'include'), ('正常工作', 'include'), ('正常上班【迟到】', 'include'),
        ('加班', 'include'), ('加班【周末】', 'include'), ('加班（法定节假）', 'include'),
        ('加班调休', 'include'), ('实习期单休', 'include'), ('补班', 'include'),
        ('年休假', 'skip'), ('有薪事假', 'skip'), ('病假', 'skip'),
        ('法定节日', 'skip'), ('放假', 'skip'), ('请假', 'skip'), ('三停一休', 'skip'),
    ])
    def test_matrix(self, status, expect):
        assert classify_status(status)[0] == expect

    def test_overtime_beats_exclude_word(self):
        """「加班（法定节假）」含排除词「法定节假」，但加班优先 → 要补"""
        assert classify_status('加班（法定节假）')[0] == 'include'
        assert classify_status('法定节日')[0] == 'skip'

    def test_empty_and_unknown_skipped(self):
        assert classify_status('') == ('skip', '状态为空')
        assert classify_status('工作状态')[0] == 'skip'


class TestOvertimeParsing:
    """四代写法：2023 方括号 / 2024 裸数字 / 2025 起止 / 2026 自然语言"""

    def test_2023_bracket_wins_over_block_hours(self):
        """【加班：17:30~20:00】+ E=2.5h：2.5h 是加班块时长，20:00 才是真实下班时刻"""
        end, mins, src, review, _ = resolve_overtime_end(
            '2.5h', '干活；【加班：17:30~20:00】', '', time(18, 0))
        assert end == time(20, 0) and mins == 120 and not review
        assert '方括号' in src

    def test_2024_bare_number_is_hours(self):
        end, mins, _src, review, _ = resolve_overtime_end('3', '', '', time(18, 0))
        assert end is None and mins == 180 and not review

    def test_2025_range_uses_end_clock(self):
        """2025 的 E 列写的是起止（9:00~22:10）→ 22:10 是下班时刻"""
        end, mins, src, review, _ = resolve_overtime_end('9:00~22:10', '', '', time(18, 0))
        assert end == time(22, 10) and mins == 250 and not review

    def test_2025_range_with_seconds(self):
        end, mins, _, _, _ = resolve_overtime_end('09:19~20:23:01', '', '', time(18, 0))
        assert end == time(20, 23, 1) and mins == 143

    def test_2025_end_before_standard_is_negative_not_wrap(self):
        """18:00 → 17:30 必须算「提前走」，绝不能当加班到次日（+23.5h）"""
        end, mins, _, review, _ = resolve_overtime_end('13:51~17:30', '', '', time(18, 0))
        assert end == time(17, 30) and mins == -30

    def test_2026_natural_language(self):
        for note, expect in [('加班到9点', time(21, 0)), ('加班到7点', time(19, 0)),
                             ('加班到9点10分', time(21, 10)), ('加班到10点50分', time(22, 50))]:
            end, mins, _, review, _ = resolve_overtime_end('', '', note, time(17, 45))
            assert end == expect, note
            assert mins > 0 and not review

    def test_2026_hours_and_half_hour(self):
        assert resolve_overtime_end('', '', '1小时', time(17, 45))[1] == 60
        assert resolve_overtime_end('', '', '半小时', time(17, 45))[1] == 30
        assert resolve_overtime_end('', '', '因为版本升级培训，旁听加班1小时', time(17, 45))[1] == 60

    def test_2026_vague_needs_review(self):
        for note in ('一整天', '1天', '半天'):
            _, mins, _, review, reason = resolve_overtime_end('', '', note, time(17, 45))
            assert review and mins == 0, note

    def test_2026_approximate_hour_flagged(self):
        end, mins, _, review, reason = resolve_overtime_end('', '', '加班到8点多', time(17, 45))
        assert end == time(20, 0) and mins == 135
        assert review and '点多' in reason

    def test_explicit_no_overtime_is_not_review(self):
        _, mins, src, review, _ = resolve_overtime_end('', '', '没加班，因为猴子生日', time(17, 45))
        assert mins == 0 and '没加班' in src and not review

    def test_empty_note_on_overtime_day_needs_review(self):
        _, mins, _, review, reason = resolve_overtime_end('', '', '', time(17, 45))
        assert review and mins == 0 and '都为空' in reason


class TestPlanDay:
    def _row(self, **kw):
        base = dict(sheet='每日记录2025', row_no=9, day=date(2025, 3, 10),
                    content='干活', status='正常上班', dur_raw='', note='')
        base.update(kw)
        return WorkLogRow(**base)
    def test_normal_workday_is_standard_window(self):
        """单条 09:00–18:00 不扣午休（用户 2026-09-18 拍板）"""
        p = plan_day(self._row())
        assert (p.start, p.end, p.duration_hours) == (datetime(2025, 3, 10, 9, 0),
                                                      datetime(2025, 3, 10, 18, 0), 9.0)
        assert not p.needs_review

    def test_2026_new_window(self):
        p = plan_day(self._row(day=date(2026, 3, 9), status='正常工作'))
        assert p.duration_hours == 9.75          # 08:00 → 17:45

    def test_overtime_extends_end(self):
        p = plan_day(self._row(status='加班', dur_raw='2.5h'))
        assert p.end == datetime(2025, 3, 10, 20, 30) and p.duration_hours == 11.5

    def test_offday_uses_table_range_as_full_day(self):
        """周末加班那天没有「标准下班」可延 → 起止直接取表内"""
        p = plan_day(self._row(status='加班【周末】', dur_raw='9h',
                               content='干活；【加班：10:16~19:20】'))
        assert (p.start.strftime('%H:%M'), p.end.strftime('%H:%M')) == ('10:16', '19:20')
        assert p.is_offday and p.duration_hours == pytest.approx(9.07, abs=0.01)

    def test_skipped_statuses_have_no_times(self):
        p = plan_day(self._row(status='年休假'))
        assert p.action == 'skip' and p.start is None and p.skip_reason == '年休假'

    def test_status_without_overtime_but_note_mentions_it_is_flagged(self):
        """实习期单休 +「补班，加班到10点50分」→ 不擅自延长，但标出来"""
        p = plan_day(self._row(status='实习期单休', note='补班，加班到10点50分'))
        assert p.duration_hours == 9.0 and p.needs_review
        assert '备注提到加班' in p.review_reason

    def test_normal_workday_note_mentioning_no_overtime_is_not_flagged(self):
        p = plan_day(self._row(status='正常工作', note='没加班，因为猴子生日'))
        assert not p.needs_review

    def test_build_plan_dedupes_same_day(self):
        rows = [self._row(row_no=2), self._row(row_no=3, status='加班')]
        assert len(build_plan(rows)) == 1


class TestRestdayFallback:
    """规则 B（用户 2026-09-18 第二版拍板）：非工作日族没给时段 → 按标准工时登记，不进待确认。

    实测触发 2 条：2023-11-18 `加班【周末】`（备注「加班是一件很欢乐的事情吗？」）、
    2023-11-24 `加班调休`（备注「调休，但没完全调，一半时间还在工作」）。
    """

    def _row(self, **kw):
        base = dict(sheet='每日记录2025', row_no=9, day=date(2025, 3, 10),
                    content='干活', status='加班', dur_raw='', note='')
        base.update(kw)
        return WorkLogRow(**base)

    @pytest.mark.parametrize('status,expect', [
        ('加班【周末】', True), ('加班（法定节假）', True), ('加班调休', True),
        ('加班', False), ('正常上班', False), ('正常工作', False),
        ('正常上班【迟到】', False), ('实习期单休', False), ('补班', False),
    ])
    def test_is_restday_matrix(self, status, expect):
        assert is_restday(status) is expect

    def test_is_restday_is_superset_of_offday(self):
        """is_offday 只管周末/法定节假（走「全天口径取表内起止」）；
        is_restday 多一个调休（只用于规则 B 的兜底与规则 A 的排除）。"""
        assert is_offday('加班（法定节假）') and is_restday('加班（法定节假）')
        assert not is_offday('加班调休') and is_restday('加班调休')

    def test_offday_without_any_time_falls_back_to_standard_window(self):
        p = plan_day(self._row(status='加班【周末】', note='加班是一件很欢乐的事情吗？'))
        assert not p.needs_review and p.review_reason == ''
        assert (p.start, p.end) == (datetime(2025, 3, 10, 9, 0),
                                    datetime(2025, 3, 10, 18, 0))
        assert p.overtime_source == '非工作日无时段，按标准工时登记'

    def test_swap_leave_without_time_falls_back_to_standard_window(self):
        """调休那一支走的是「非 offday」代码路径，必须显式清掉解析层带出的 review=True"""
        p = plan_day(self._row(status='加班调休', note='调休，但没完全调，一半时间还在工作'))
        assert not p.needs_review and p.review_reason == ''
        assert (p.start, p.end) == (datetime(2025, 3, 10, 9, 0),
                                    datetime(2025, 3, 10, 18, 0))
        assert p.overtime_source == '调休日无时段，按标准工时登记'

    def test_offday_with_hours_still_uses_hours(self):
        """回归：兜底只在「提不出任何时段」时启用，有可解时长仍按上班时刻+时长"""
        p = plan_day(self._row(status='加班【周末】', dur_raw='8h'))
        assert (p.start, p.end) == (datetime(2025, 3, 10, 9, 0),
                                    datetime(2025, 3, 10, 17, 0))
        assert not p.needs_review

    def test_plain_overtime_without_time_still_needs_review(self):
        """规则 B 只覆盖非工作日族；普通「加班」提不出时段仍要人工确认"""
        p = plan_day(self._row(status='加班'))
        assert p.needs_review and '都为空' in p.review_reason

    def test_restday_without_time_uses_2026_window(self):
        p = plan_day(self._row(day=date(2026, 3, 9), status='加班调休'))
        assert (p.start, p.end) == (datetime(2026, 3, 9, 8, 0),
                                    datetime(2026, 3, 9, 17, 45))


class TestEarlyLeaveDetection:
    """备注里写了「提前下班」的日子，结束时刻是实况 → 「补满标准窗口」要放过它

    样板 = 2025-01-25：公司发了提前下班通知，实际记到 16:32，
    补成 18:00 等于把真实记录改成标准工时。
    """

    @pytest.mark.parametrize('note, expect', [
        ('温馨提示：今天手上如果没有紧急工作的小伙伴们，下午4点可以提前下班了。大家工作一年辛苦啦~', True),
        ('今天提前下班', True),
        ('提早下班，回家做饭', True),
        ('我先提前走了', True),
        ('加班到9点', False),
        ('调休，但没完全调，一半时间还在工作', False),
        ('', False),
        (None, False),
    ])
    def test_matrix(self, note, expect):
        assert is_early_leave(note) is expect


# ════════════════════════════════════════════════════════════════════════════
# 读表（结构坑）
# ════════════════════════════════════════════════════════════════════════════
class TestReadWorklogRows:
    def test_column_layouts_and_second_header(self, tmp_path):
        """2023 备注在 G、2024/2025 在 F、2026 在 E；2026 第 3 行是嵌入的第二套表头。"""
        p = tmp_path / 'w.xlsx'
        make_xlsx(p, [
            ('每日记录（2023）', [
                ['月份', '时间日期', '工作内容', '工作状态', '加班|请假时长', '评分', '备注'],
                ['1月', _serial(2023, 1, 3, 9), '内容A', '正常上班', None, 0, '心情A'],
                ['2月', _serial(2023, 2, 1, 9), '内容B', '加班', '2.5h', -2, ''],   # 行2/3
            ]),
            ('每日记录2026', [
                ['y', '   ', '工作内容', '工作状态', '加班|请假时长', '评分', 0],
                ['1月', _serial(2025, 12, 24), '内容C', '正常上班', None, None, None],
                ['月份', '日期', '工作内容', '工作状态', '备注', '文本', None],      # 第 3 行=第二套表头
                ['2026年3月', _serial(2026, 3, 2), '内容D', '正常工作', '键盘很卡'], # 行4
            ]),
            ('Sheet1', [[None]]),
        ])
        rows = read_worklog_rows(str(p))
        # Sheet1 与 2026 的第二套表头都不算：2023 贡献 2 行 + 2026 贡献 2 行
        assert len(rows) == 4
        assert [r.day for r in rows] == [date(2023, 1, 3), date(2023, 2, 1),
                                         date(2025, 12, 24), date(2026, 3, 2)]
        assert rows[0].note == '心情A'             # 2023 → G 列
        assert rows[1].dur_raw == '2.5h'           # 时长列
        assert rows[3].note == '键盘很卡'           # 2026 → E 列（没有时长列）
        assert rows[3].dur_raw == ''

    def test_2024_note_column_is_f(self, tmp_path):
        p = tmp_path / 'w2.xlsx'
        make_xlsx(p, [('每日记录2024', [
            ['   ', '   ', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['1月', _serial(2024, 1, 5), '内容', '加班', '3', '远程1家'],
        ])])
        rows = read_worklog_rows(str(p))
        assert rows[0].note == '远程1家' and rows[0].dur_raw == '3'

    def test_non_date_rows_are_skipped(self, tmp_path):
        """表头损坏也不要紧：B 列不是日期就跳过"""
        p = tmp_path / 'w3.xlsx'
        make_xlsx(p, [('每日记录2025', [
            ['y', '   ', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['1月', '不是日期', '水行', '正常上班', None, ''],
            ['1月', _serial(2025, 2, 3), '内容', '正常上班', None, ''],
        ])])
        rows = read_worklog_rows(str(p))
        assert len(rows) == 1 and rows[0].day == date(2025, 2, 3)


# ════════════════════════════════════════════════════════════════════════════
# 导入命令
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestImportWorklogCommand:
    TASK = '牛马工作'

    def _xlsx(self, tmp_path, name='log.xlsx', extra_rows=()):
        p = tmp_path / name
        make_xlsx(p, [('每日记录2025', [
            ['y', '   ', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['3月', _serial(2025, 3, 10), '周一干活', '正常上班', None, ''],
            ['3月', _serial(2025, 3, 11), '周二干活', '加班', '2.5h', '累'],
            ['3月', _serial(2025, 3, 12), '周三年假', '年休假', None, ''],
            *extra_rows,
        ])])
        return str(p)

    def _run(self, tmp_path, *args):
        from django.core.management import call_command
        return call_command('import_worklog', self._xlsx(tmp_path), *args, verbosity=0)

    def test_dry_run_writes_nothing(self, tmp_path, capsys):
        from django.core.management import call_command
        call_command('import_worklog', self._xlsx(tmp_path), verbosity=0)
        out = capsys.readouterr().out
        assert '干跑' in out and '未写入' in out
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 0

    def test_apply_creates_with_derived_fields(self, tmp_path):
        self._run(tmp_path, '--apply')
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 2   # 年休假不建
        mon = TemporalTask.objects.get(task_name=self.TASK, day=10)
        assert (mon.duration_hours, mon.mon, mon.quarter) == (9.0, '03', 1)
        assert mon.import_batch == 'worklog'
        assert mon.task_description.startswith('[2025-03-10] 周一干活')
        overtime = TemporalTask.objects.get(task_name=self.TASK, day=11)
        assert overtime.end_time.strftime('%H:%M') == '20:30'
        assert overtime.duration_hours == 11.5
        assert overtime.notes == '[2025-03-11] 累'

    def test_apply_creates_task_meta(self, tmp_path):
        TaskMeta.objects.filter(task_name=self.TASK).delete()
        self._run(tmp_path, '--apply')
        assert TaskMeta.objects.filter(task_name=self.TASK).exists()

    def test_rerun_is_idempotent(self, tmp_path):
        """同一份日志跑两次：既不新增、也不重复追加（靠 [YYYY-MM-DD] 标记）"""
        self._run(tmp_path, '--apply')
        first_desc = TemporalTask.objects.get(task_name=self.TASK, day=10).task_description
        self._run(tmp_path, '--apply')
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 2
        assert TemporalTask.objects.get(task_name=self.TASK, day=10).task_description == first_desc

    def test_existing_record_gets_text_appended_not_duplicated(self, tmp_path):
        """当天已有「牛马工作」记录 → 不新增行，只把内容/备注追加过去

        ⚠️ 用**工时完整**（09:00→18:00）的既有记录：碎片记录（如只记下午段）自 v3.58.8 起
        会被规则 A 回补开始时刻，那是另一条路径，见 `TestRuleAExtendFragment`。
        """
        from django.utils import timezone
        existing = TemporalTask.objects.create(
            task_name=self.TASK, task_type=self.TASK,
            start_time=timezone.make_aware(datetime(2025, 3, 10, 9, 0)),
            end_time=timezone.make_aware(datetime(2025, 3, 10, 18, 0)),
            duration_hours=9.0, task_description='原有说明', notes='原有备注',
            year=2025, mon='03', day=10, week=11, quarter=1,
        )
        self._run(tmp_path, '--apply')
        existing.refresh_from_db()
        assert TemporalTask.objects.filter(task_name=self.TASK, day=10).count() == 1
        assert existing.task_description == '原有说明\n[2025-03-10] 周一干活'
        assert existing.notes == '原有备注'          # 当天日志没有备注 → 附注保持原样
        assert existing.duration_hours == 9.0 and existing.end_time.strftime('%H:%M') == '18:00'

    def test_review_rows_are_not_written_by_default(self, tmp_path):
        p = tmp_path / 'r.xlsx'
        make_xlsx(p, [('每日记录2025', [
            ['y', '', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['3月', _serial(2025, 3, 10), '干活', '加班', None, ''],      # 加班但无任何时长信息
        ])])
        from django.core.management import call_command
        call_command('import_worklog', str(p), '--apply', verbosity=0)
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 0
        call_command('import_worklog', str(p), '--apply', '--include-review', verbosity=0)
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 1

    def test_report_csv_written(self, tmp_path):
        out = tmp_path / 'report.csv'
        self._run(tmp_path, '--report', str(out))
        rows = list(csv.DictReader(out.open(encoding='utf-8-sig')))
        assert {r['动作'] for r in rows} == {'新增'}
        assert [r['日期'] for r in rows] == ['2025-03-10', '2025-03-11']

    def test_date_filter(self, tmp_path):
        self._run(tmp_path, '--apply', '--date-from', '2025-03-11', '--date-to', '2025-03-11')
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 1
        assert TemporalTask.objects.get(task_name=self.TASK).day == 11


# ════════════════════════════════════════════════════════════════════════════
# 规则 A：单段碎片回补开始时刻（用户 2026-09-18 拍板，v3.58.8）
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestRuleAExtendFragment:
    """「当天只有一段碎片 + 状态是工作日」→ 把这段**补满当日标准工时窗口**。

    区间口径 `[min(原开始, 标准上班), max(原结束, 标准下班)]`：
    - 只缺开始（典型只记了晚上加班段 `18:00→22:30`）→ `09:00→22:30`；
    - 只缺结束（典型只记了午间 `12:17→12:47`）→ `08:00→17:45`；
    - 两端都没缺 → **一律不动**（这既是幂等键，也是「别乱改已完整记录」的保证）。

    两处豁免：非工作日（周末/法定节假/调休）与备注写明提前下班的日子（`is_early_leave`）。
    ⚠️ 这一条**会改写已有记录的时间字段**，且**不改 `import_batch`**（保留原批次号，
    否则 `DELETE ... WHERE import_batch='worklog'` 会把原始 ATracker 记录一起删掉）。
    """

    TASK = '牛马工作'

    def _existing(self, start, end, duration, *, day=date(2025, 3, 10),
                  batch='import_orig001', desc='原有说明', notes=None):
        from django.utils import timezone
        return TemporalTask.objects.create(
            task_name=self.TASK, task_type=self.TASK,
            start_time=timezone.make_aware(datetime.combine(day, start)),
            end_time=timezone.make_aware(datetime.combine(day, end)),
            duration_hours=duration, task_description=desc, notes=notes,
            import_batch=batch, year=day.year, mon=f'{day.month:02d}', day=day.day,
            week=day.isocalendar()[1], quarter=(day.month - 1) // 3 + 1,
        )

    def _xlsx(self, tmp_path, day=date(2025, 3, 10), status='加班', content='周一干活',
              note='', dur=None):
        p = tmp_path / 'one.xlsx'
        make_xlsx(p, [('每日记录2025', [
            ['y', '', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['3月', _serial(day.year, day.month, day.day), content, status, dur, note],
        ])])
        return str(p)

    def _run(self, tmp_path, *args, **kw):
        from django.core.management import call_command
        call_command('import_worklog', self._xlsx(tmp_path, **kw), *args, verbosity=0)

    def test_start_pulled_back_end_and_batch_kept(self, tmp_path):
        """18:00→22:30 ⇒ 09:00→22:30：结束不动、时长重算、import_batch 保留原批次"""
        obj = self._existing(time(18, 0), time(22, 30), 4.5)
        self._run(tmp_path, '--apply')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'), obj.end_time.strftime('%H:%M')) == ('09:00', '22:30')
        assert obj.duration_hours == 13.5
        assert obj.import_batch == 'import_orig001'          # ⚠️ 不能被改成 worklog
        assert '[2025-03-10] 时段补全：09:00–22:30（原 18:00–22:30' in obj.notes

    def test_content_is_still_appended_alongside_extend(self, tmp_path):
        """补全与「追加文本」是两件事，同一天都要做；附注里追加的备注在前、补全标记在后"""
        obj = self._existing(time(18, 0), time(22, 30), 4.5)
        self._run(tmp_path, '--apply', note='累')
        obj.refresh_from_db()
        notes = obj.notes or ''
        assert '[2025-03-10] 累' in notes and '[2025-03-10] 时段补全' in notes
        assert notes.index('[2025-03-10] 累') < notes.index('[2025-03-10] 时段补全')
        assert obj.task_description == '原有说明\n[2025-03-10] 周一干活'

    def test_calendar_fields_recomputed(self, tmp_path):
        """日历年月周季一并重算——否则年份筛选/月度趋势会按旧值落位"""
        obj = self._existing(time(18, 0), time(22, 30), 4.5,
                             day=date(2025, 12, 31))
        self._run(tmp_path, '--apply', day=date(2025, 12, 31))
        obj.refresh_from_db()
        assert (obj.year, obj.mon, obj.day, obj.quarter) == (2025, '12', 31, 4)

    def test_2026_window_pulls_back_to_0800(self, tmp_path):
        obj = self._existing(time(17, 43), time(18, 59), 1.27, day=date(2026, 8, 19))
        self._run(tmp_path, '--apply', day=date(2026, 8, 19))
        obj.refresh_from_db()
        assert obj.start_time.strftime('%H:%M') == '08:00'
        assert obj.end_time.strftime('%H:%M') == '18:59'

    def test_start_already_early_is_untouched(self, tmp_path):
        """07:50 打的卡：开始已早于标准上班，不往 09:00 拉（否则等于把工时改短）"""
        obj = self._existing(time(7, 50), time(18, 0), 10.17, day=date(2026, 5, 6))
        self._run(tmp_path, '--apply', day=date(2026, 5, 6), status='正常工作')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'), obj.duration_hours) == ('07:50', 10.17)

    def test_end_pulled_forward_when_only_midday_recorded(self, tmp_path):
        """★ 只缺结束：午间碎片 12:17→12:47 ⇒ 08:00→17:45（2026-03-27 真实场景）

        上一版规则 A 只管开始，这种日子补完还是 `08:00→12:47`（下午整段空着）。
        """
        obj = self._existing(time(12, 17), time(12, 47), 0.5, day=date(2026, 3, 27))
        self._run(tmp_path, '--apply', day=date(2026, 3, 27), status='正常工作')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'),
                obj.end_time.strftime('%H:%M')) == ('08:00', '17:45')
        assert obj.duration_hours == 9.75
        assert obj.import_batch == 'import_orig001'          # ⚠️ 仍不能被改成 worklog
        assert '[2026-03-27] 时段补全：08:00–17:45（原 12:17–12:47' in obj.notes

    def test_second_pass_fills_end_left_by_first_pass(self, tmp_path):
        """★ 幂等靠「达标判定」而非附注标记：第一次只补了开始的日子，第二次仍能补上结束

        若幂等键仍是 `[日期] 时段补全` 这个标记，这天会被自己的标记挡住、
        **静默补不上结束**（这正是 v3.58.9 要改掉的东西）。
        """
        obj = self._existing(
            time(9, 0), time(12, 47), 3.78,
            notes='[2025-03-10] 时段补全：09:00–12:47（原 12:17–12:47，按工作日志补全）',
        )
        self._run(tmp_path, '--apply')
        obj.refresh_from_db()
        assert obj.start_time.strftime('%H:%M') == '09:00'   # 已达标的开始端不动
        assert obj.end_time.strftime('%H:%M') == '18:00'     # 缺的结束端补上
        assert obj.duration_hours == 9.0
        assert (obj.notes or '').count('[2025-03-10] 时段补全') == 2   # 旧痕保留 + 新增一行

    def test_early_leave_note_is_spared(self, tmp_path):
        """★ 备注明确写了提前下班 → 结束是**实况**不是记漏，一律不补（2025-01-25 样板）"""
        obj = self._existing(time(8, 56), time(16, 32), 7.6, day=date(2025, 1, 25))
        self._run(tmp_path, '--apply', day=date(2025, 1, 25), status='正常上班',
                  note='温馨提示：今天手上如果没有紧急工作的小伙伴们，下午4点可以提前下班了。'
                       '大家工作一年辛苦啦~')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'),
                obj.end_time.strftime('%H:%M')) == ('08:56', '16:32')
        assert obj.duration_hours == 7.6
        assert '时段补全' not in (obj.notes or '')

    def test_restday_end_before_standard_is_untouched(self, tmp_path):
        """周末单段且结束早于标准下班：按表内实况记，不往 18:00 拉（用户明确选择）"""
        obj = self._existing(time(13, 50), time(17, 30), 3.67, day=date(2025, 10, 19))
        self._run(tmp_path, '--apply', day=date(2025, 10, 19), status='加班【周末】')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'),
                obj.end_time.strftime('%H:%M')) == ('13:50', '17:30')
        assert '时段补全' not in (obj.notes or '')

    def test_multi_fragment_is_untouched(self, tmp_path):
        """当天有多段记录 → 不属于「只有一段碎片」，不动时间"""
        from django.utils import timezone
        self._existing(time(9, 0), time(12, 0), 3.0, notes=None)
        TemporalTask.objects.create(
            task_name=self.TASK, task_type=self.TASK,
            start_time=timezone.make_aware(datetime(2025, 3, 10, 13, 30)),
            end_time=timezone.make_aware(datetime(2025, 3, 10, 18, 12)),
            duration_hours=4.71, task_description='第二段', year=2025, mon='03',
            day=10, week=11, quarter=1,
        )
        self._run(tmp_path, '--apply', status='正常工作')
        rows = TemporalTask.objects.filter(task_name=self.TASK)
        assert sorted(t.start_time.strftime('%H:%M') for t in rows) == ['09:00', '13:30']
        assert not any('时段补全' in (t.notes or '') for t in rows)

    def test_offday_single_fragment_is_untouched(self, tmp_path):
        """周末/法定节假的加班按表内实况记，不往 09:00 拉（用户明确选择）"""
        obj = self._existing(time(13, 24), time(18, 13), 4.81, day=date(2025, 10, 12))
        self._run(tmp_path, '--apply', day=date(2025, 10, 12), status='加班【周末】')
        obj.refresh_from_db()
        assert obj.start_time.strftime('%H:%M') == '13:24'
        assert '[2025-10-12] 时段补全' not in (obj.notes or '')

    def test_extend_is_idempotent(self, tmp_path):
        """重跑：开始时刻不反复位移，附注里也只有一条「时段补全」"""
        obj = self._existing(time(18, 0), time(22, 30), 4.5)
        self._run(tmp_path, '--apply')
        self._run(tmp_path, '--apply')
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'), obj.duration_hours) == ('09:00', 13.5)
        assert (obj.notes or '').count('[2025-03-10] 时段补全') == 1

    def test_extend_runs_even_when_day_already_imported(self, tmp_path):
        """★ 关键：那 95 天早带了 `[日期]` 幂等标记，补全必须**不被它挡住**

        否则第一次导入后这些天永远补不上——补全标记与「已导过」标记是两套。
        """
        obj = self._existing(time(18, 0), time(22, 30), 4.5,
                             desc='原有说明\n[2025-03-10] 周一干活')
        self._run(tmp_path, '--apply')
        obj.refresh_from_db()
        assert obj.start_time.strftime('%H:%M') == '09:00'
        assert obj.duration_hours == 13.5
        assert obj.task_description.count('周一干活') == 1      # 文本没有重复追加

    def test_dry_run_does_not_extend(self, tmp_path):
        obj = self._existing(time(18, 0), time(22, 30), 4.5)
        self._run(tmp_path)                                   # 不带 --apply
        obj.refresh_from_db()
        assert (obj.start_time.strftime('%H:%M'), obj.duration_hours) == ('18:00', 4.5)
        assert '[2025-03-10] 时段补全' not in (obj.notes or '')

    def test_fill_gaps_skips_rule_a_days(self, tmp_path):
        """规则 A 已改写过时间的日子不能再走 --fill-gaps，否则会重复计时"""
        obj = self._existing(time(18, 0), time(22, 30), 4.5)
        self._run(tmp_path, '--apply', '--fill-gaps')
        obj.refresh_from_db()
        assert obj.start_time.strftime('%H:%M') == '09:00'
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 1
        assert not [t for t in TemporalTask.objects.filter(task_name=self.TASK)
                    if '补记' in (t.task_description or '')]

    def test_report_csv_includes_extend_rows(self, tmp_path):
        self._existing(time(18, 0), time(22, 30), 4.5)
        out = tmp_path / 'r.csv'
        self._run(tmp_path, '--report', str(out))
        rows = list(csv.DictReader(out.open(encoding='utf-8-sig')))
        ext = [r for r in rows if r['动作'] == '补全时段']
        assert len(ext) == 1
        assert (ext[0]['日期'], ext[0]['开始'], ext[0]['结束']) == ('2025-03-10', '09:00', '22:30')
        assert '原 18:00→22:30' in ext[0]['加班来源']


@pytest.mark.django_db
class TestFillGaps:
    """`--fill-gaps`：**多段**记录没盖满标准工时时，补一条独立缺口记录。

    ⚠️ v3.58.8 起，「只有一段碎片」的日子改由**规则 A 回补开始时刻**处理（见
    `TestRuleAExtendFragment`），不再走这里——两者互斥，否则会重复计时。
    """

    TASK = '牛马工作'

    def _existing(self, start_h, start_m, end_h, end_m, duration):
        """当天已有的一段记录（多段场景下调用两次）"""
        from django.utils import timezone
        return TemporalTask.objects.create(
            task_name=self.TASK, task_type=self.TASK,
            start_time=timezone.make_aware(datetime(2025, 3, 10, start_h, start_m)),
            end_time=timezone.make_aware(datetime(2025, 3, 10, end_h, end_m)),
            duration_hours=duration, task_description='原有', year=2025, mon='03',
            day=10, week=11, quarter=1,
        )

    def _xlsx(self, tmp_path, status='正常上班'):
        p = tmp_path / 'one.xlsx'
        make_xlsx(p, [('每日记录2025', [
            ['y', '', '工作内容', '工作状态', '加班|请假时长', '备注'],
            ['3月', _serial(2025, 3, 10), '周一干活', status, None, ''],
        ])])
        return str(p)

    def _run(self, tmp_path, *args, **kw):
        from django.core.management import call_command
        call_command('import_worklog', self._xlsx(tmp_path, **kw), *args, verbosity=0)

    def _gap_records(self):
        return [t for t in TemporalTask.objects.filter(task_name=self.TASK)
                if '补记' in (t.task_description or '')]

    def test_segment_gap_is_filled(self, tmp_path):
        """两段记录之间空出的 13:30–14:00 → 补上"""
        self._existing(9, 0, 12, 0, 3.0)
        self._existing(14, 0, 18, 0, 4.0)          # 下午从 14:00 才开始
        self._run(tmp_path, '--apply', '--fill-gaps')
        gaps = self._gap_records()
        assert len(gaps) == 1
        assert (gaps[0].start_time.strftime('%H:%M'),
                gaps[0].end_time.strftime('%H:%M')) == ('13:30', '14:00')
        assert gaps[0].duration_hours == 0.5

    def test_no_gap_when_already_covered(self, tmp_path):
        self._existing(9, 0, 12, 0, 3.0)
        self._existing(13, 30, 18, 0, 4.5)
        self._run(tmp_path, '--apply', '--fill-gaps')
        assert self._gap_records() == []

    def test_flag_off_means_no_gap_records(self, tmp_path):
        self._existing(9, 0, 12, 0, 3.0)
        self._existing(14, 0, 18, 0, 4.0)
        self._run(tmp_path, '--apply')             # 不带 --fill-gaps
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == 2
        assert self._gap_records() == []

    def test_single_evening_fragment_goes_through_rule_a_not_gap(self, tmp_path):
        """只记了 18:00 之后的加班段 → 由规则 A 把**原记录**的开始回补到 09:00，
        而不是再造一条 09:00–18:00 的补记（旧行为，v3.58.8 已改）"""
        obj = self._existing(18, 0, 22, 30, 4.5)
        self._run(tmp_path, '--apply', '--fill-gaps')
        obj.refresh_from_db()
        assert self._gap_records() == []
        assert (obj.start_time.strftime('%H:%M'),
                obj.end_time.strftime('%H:%M'), obj.duration_hours) == ('09:00', '22:30', 13.5)

    def test_offday_is_not_gap_filled(self, tmp_path):
        """周末/法定节假按表内实况记，不补标准工时缺口"""
        self._existing(10, 0, 12, 0, 2.0)
        self._existing(14, 0, 18, 0, 4.0)
        self._run(tmp_path, '--apply', '--fill-gaps', status='加班【周末】')
        assert self._gap_records() == []

    def test_fill_gaps_is_idempotent(self, tmp_path):
        self._existing(9, 0, 12, 0, 3.0)
        self._existing(14, 0, 18, 0, 4.0)
        self._run(tmp_path, '--apply', '--fill-gaps')
        n = TemporalTask.objects.filter(task_name=self.TASK).count()
        self._run(tmp_path, '--apply', '--fill-gaps')
        assert TemporalTask.objects.filter(task_name=self.TASK).count() == n
