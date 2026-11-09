"""收件箱批量导入（2026-11-09）

修的三件事各钉一条 —— 它们的共同长相是**不报错、数看着合理**：

① 类别写死 `study`、tags 无条件前缀「备考」⇒ 一次备考导入的工具伪装成通用功能。
② 缺标题 / 日期解析不了的行 `continue` 静默吃掉 ⇒ 「成功 3 失败 2」说不出是哪两行。
③ `failed[]` 前端从不渲染 ⇒ 后端其实报了，用户永远看不到。
"""
import pytest

from apps.inbox.models import InboxItem
from apps.inbox.services import InboxImportService


class TestParseCsvCategory:
    """category 列不再被写死成 `study`。"""

    def test_legal_category_is_respected(self):
        parsed = InboxImportService.parse_csv(
            'content,category\n买电池,待办\n'
        )
        item = parsed['items'][0]
        assert item['category'] == 'todo'
        # 阶段列没写 ⇒ 不进 tags，也不该凭空多一个「备考」
        assert item['tags'] == ''

    def test_unknown_category_falls_back_to_other_and_keeps_as_tag(self):
        """旧模板把备考阶段写在 category 列 ⇒ 当阶段收进 tags，类别落 other。"""
        parsed = InboxImportService.parse_csv(
            'content,category\n精读开发模型,基础期\n'
        )
        item = parsed['items'][0]
        assert item['category'] == 'other'
        assert item['tags'] == '基础期'
        assert '[阶段: 基础期]' not in item['description']   # 没写「阶段」列就不编造备注

    def test_stage_column_goes_to_tags_and_note(self):
        parsed = InboxImportService.parse_csv(
            'content,category,阶段\n精读开发模型,学习,基础期\n'
        )
        item = parsed['items'][0]
        assert item['category'] == 'study'
        assert item['tags'] == '基础期'
        assert '[阶段: 基础期]' in item['description']

    def test_tags_column_is_used_as_is(self):
        # 多标签本身含逗号 ⇒ CSV 里必须加引号（与模板一致）
        parsed = InboxImportService.parse_csv(
            'content,category,tags\n买电池,待办,"生活,采购"\n'
        )
        assert parsed['items'][0]['tags'] == '生活,采购'


class TestParseCsvSkips:
    """被跳过的行必须带行号出来，不能 `continue` 后就没了。"""

    def test_missing_title_is_reported_with_row(self):
        parsed = InboxImportService.parse_csv(
            'content,category\n'
            '买电池,待办\n'
            ',待办\n'
        )
        assert len(parsed['items']) == 1
        assert len(parsed['skipped']) == 1
        assert parsed['skipped'][0]['row'] == 3      # 表头是第 1 行
        assert '标题' in parsed['skipped'][0]['reason']

    def test_bad_date_is_reported_not_silently_none(self):
        parsed = InboxImportService.parse_csv(
            'content,due_date\n买电池,不是日期\n'
        )
        assert parsed['items'] == []
        assert parsed['skipped'][0]['row'] == 2
        assert '不是日期' in parsed['skipped'][0]['reason']


@pytest.mark.django_db
class TestImportItems:
    def test_row_number_survives_to_result(self):
        parsed = InboxImportService.parse_csv('content,category\n买电池,待办\n')
        result = InboxImportService.import_items(1, parsed['items'])
        assert result['success_count'] == 1
        assert result['failed'] == []
        assert InboxItem.objects.get().category == 'todo'
