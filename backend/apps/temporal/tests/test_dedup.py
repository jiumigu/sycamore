"""重复判定 `find_duplicate_task` 的回归守卫（v3.60.29）。

本轮修的是一条**静默缺陷**：判重从「`(task_name, start_time)` 精确相等」改成
「同任务名 + 时段重叠」。两类行为必须**同时**钉住 ——

1. **被 `import_worklog` 规则 A 补全过 `start_time` 的记录仍然认得出**：
   否则重复导入时**静默多插一条**（2026-09-17 实案，多出 9.92h 一条）；
2. **仅仅是相接的分段不算重复**：否则会**吞掉合法记录**，而界面上看不出少了什么
   （2026-01-10「日常家务」两段只重叠 30 秒）。

还有第三条，是**这次修复自己引出来的副作用**，必须一并钉住：
命中的是「已按工作日志校准过」的记录时，**不许拿源数据把校准值覆盖回去** ——
否则重导一次 CSV，被补全的 10h 会被静默打回 9.92h。

推导见 `.workbuddy/memory/TECH-NOTES.md` §64 与 `.workbuddy/memory/2026-10-11.md`。
"""

from datetime import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.temporal.models import TemporalTask
from apps.temporal.services import (
    DUP_OVERLAP_RATIO,
    CSVImportService,
    _overlap_ratio,
    find_duplicate_task,
)


def _aware(text: str) -> datetime:
    return timezone.make_aware(datetime.strptime(text, '%Y-%m-%d %H:%M:%S'))


def _mk(task_name, start, end, duration, notes='', batch='import_orig001'):
    """造一条已有记录（日历字段照 CSV 导入的口径一起填）。"""
    s = _aware(start)
    e = _aware(end) if end else None
    return TemporalTask.objects.create(
        task_name=task_name, task_description='', start_time=s, end_time=e,
        duration_hours=duration, notes=notes, tags=None, task_type=task_name,
        import_batch=batch, year=s.year, mon=f'{s.month:02d}', day=s.day,
        week=s.isocalendar()[1], quarter=(s.month - 1) // 3 + 1,
    )


def _csv(*rows) -> SimpleUploadedFile:
    """按 ATracker 导出列头拼一份 CSV（必需列：任务名称 / 开始时间 / 持续时间（小时））。"""
    head = '任务名称,任务说明,开始时间,结束时间,持续时间（小时）,附注,标签'
    lines = [head] + [','.join(str(c) for c in r) for r in rows]
    return SimpleUploadedFile(
        'atracker.csv', ('\n'.join(lines) + '\n').encode('utf-8'),
        content_type='text/csv',
    )


class TestOverlapRatio:
    """纯函数：口径是「重叠 ÷ 较短一方」，不是「有重叠就算」。"""

    def test_full_overlap_is_one(self):
        a = (_aware('2026-09-17 08:00:00'), _aware('2026-09-17 18:00:00'))
        assert _overlap_ratio(a, a) == 1.0

    def test_disjoint_is_zero(self):
        a = (_aware('2026-09-17 08:00:00'), _aware('2026-09-17 12:00:00'))
        b = (_aware('2026-09-17 13:00:00'), _aware('2026-09-17 18:00:00'))
        assert _overlap_ratio(a, b) == 0.0

    def test_touching_segments_stay_below_threshold(self):
        """2026-01-10「日常家务」的真实形态：相接分段只重叠 30 秒。"""
        a = (_aware('2026-01-10 11:59:00'), _aware('2026-01-10 13:50:30'))
        b = (_aware('2026-01-10 13:50:00'), _aware('2026-01-10 14:10:45'))
        assert 0 < _overlap_ratio(a, b) < DUP_OVERLAP_RATIO

    def test_zero_width_point_inside_is_one(self):
        a = (_aware('2026-09-17 10:00:00'), _aware('2026-09-17 10:00:00'))
        b = (_aware('2026-09-17 08:00:00'), _aware('2026-09-17 18:00:00'))
        assert _overlap_ratio(a, b) == 1.0


@pytest.mark.django_db
class TestRewriteStillRecognised:
    """① 被规则 A 补全过 start_time 的记录，仍然要认得出（否则重复）。"""

    def test_start_rewritten_to_0800_still_matches_source_0805(self):
        # 库里这条是规则 A 补全后的：start 已从 08:05 改成 08:00，附注留了原时刻
        _mk('牛马工作', '2026-09-17 08:00:00', '2026-09-17 18:00:00', 10.0,
            notes='[2026-09-17] 时段补全：08:00–18:00（原 08:05–18:00，按工作日志补全）')
        hit = find_duplicate_task(
            '牛马工作', _aware('2026-09-17 08:05:00'), _aware('2026-09-17 18:00:00'), 9.92)
        assert hit is not None, '补全后的记录必须仍然命中（旧精度匹配在这里失效）'
        assert hit.start_time.strftime('%H:%M') == '08:00'

    def test_missing_end_falls_back_to_duration(self):
        """ATracker 导出的「结束时间」列常为空 ⇒ 用时长构造区间。"""
        obj = _mk('牛马工作', '2026-09-17 08:05:00', None, 9.92)
        hit = find_duplicate_task('牛马工作', _aware('2026-09-17 08:05:00'), None, 9.92)
        assert hit is not None and hit.id == obj.id


@pytest.mark.django_db
class TestLegalRecordsNotSwallowed:
    """② 合法记录不能被判成重复。"""

    def test_touching_segments_are_not_duplicates(self):
        _mk('日常家务', '2026-01-10 11:59:00', '2026-01-10 13:50:30', 1.86)
        assert find_duplicate_task(
            '日常家务', _aware('2026-01-10 13:50:00'),
            _aware('2026-01-10 14:10:45'), 0.35) is None

    def test_other_day_is_not_duplicate(self):
        _mk('刷短视频', '2026-09-17 18:03:00', '2026-09-17 19:03:00', 1.0)
        assert find_duplicate_task(
            '刷短视频', _aware('2026-09-18 18:03:00'),
            _aware('2026-09-18 19:03:00'), 1.0) is None

    def test_other_task_name_is_not_duplicate(self):
        _mk('刷短视频', '2026-09-17 18:03:00', '2026-09-17 19:03:00', 1.0)
        assert find_duplicate_task(
            '牛马工作', _aware('2026-09-17 18:03:00'),
            _aware('2026-09-17 19:03:00'), 1.0) is None


@pytest.mark.django_db
class TestCSVReimport:
    """端到端：CSV 导入走的是同一个判重，且不许覆盖已校准的值。"""

    def test_reimport_after_rewrite_neither_inserts_nor_overwrites(self):
        obj = _mk('牛马工作', '2026-09-17 08:00:00', '2026-09-17 18:00:00', 10.0,
                  notes='[2026-09-17] 时段补全：08:00–18:00（原 08:05–18:00，按工作日志补全）')
        before = TemporalTask.objects.count()

        stats = CSVImportService().import_from_csv(
            _csv(('牛马工作', '', '2026-09-17 08:05:00', '2026-09-17 18:00:00', 9.92, '', '')),
            'import_regress001')

        assert TemporalTask.objects.count() == before, '重复导入不许新增记录'
        assert stats['inserted'] == 0
        assert stats['protected'] == 1, '应识别为「已按工作日志校准」并保留'
        obj.refresh_from_db()
        assert obj.duration_hours == 10.0, '校准后的时长不许被打回 9.92'
        assert obj.start_time.strftime('%H:%M') == '08:00'

    def test_identical_row_is_still_skipped(self):
        """值完全一致的老路（skipped）不能退化 —— 否则会把所有命中都当 protected。"""
        _mk('牛马工作', '2026-09-17 09:00:00', '2026-09-17 18:00:00', 9.0)
        stats = CSVImportService().import_from_csv(
            _csv(('牛马工作', '', '2026-09-17 09:00:00', '2026-09-17 18:00:00', 9.0, '', '')),
            'import_regress002')
        assert stats['inserted'] == 0
        assert stats['skipped'] == 1
        assert stats['protected'] == 0
