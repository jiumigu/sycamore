"""自我运转 · 测试公用 fixture

🔴 为什么需要这个文件：**测试库里 `selfrun_template` 是空的**。
   `pytest.ini` 用 `--reuse-db --no-migrations`，Django 直接按 model 建表；
   而那 9 条内置模板的 seed 写在**数据迁移** `0002` 里 ⇒ 迁移不跑、seed 也就不跑。
   ⇒ 用例若依赖「模板能兜底」（比如只传 `template_key` 而不传 `goal_value`），
     就会看到 `source_config = {}` ⇒ 抛 `未知的取数器 None`。
     **那不是代码错，是环境里少了起点数据**（与 conftest 补镜像 DDL 同一个道理）。

⚠️ 每个用例都会重建这张表的数据（`db` fixture 给的是事务回滚），所以
   `create` 不需要 `get_or_create`。
"""
import pytest

from apps.selfrun.models import SelfRunTemplate
from apps.selfrun.templates import KPI_TEMPLATES


@pytest.fixture(autouse=True)
def _seed_builtin_templates(db):
    """把 `templates.KPI_TEMPLATES` 那 9 条种进测试库（**autouse**）。

    自动生效，是为了让「只传 template_key」的既有用例继续成立 ——
    否则每加一条模板相关的用例都要记得声明它，漏了就是一条**看着像代码错**的失败。
    """
    for t in KPI_TEMPLATES:
        SelfRunTemplate.objects.create(
            key=t['key'],
            name=t['name'],
            period_type=t['period_type'],
            unit=t['unit'],
            direction=t['direction'],
            goal_value=t['goal_value'],
            floor_value=t['floor_value'],
            goal_why=t['goal_why'],
            floor_why=t['floor_why'],
            agg=t['agg'],
            source_kind=t['source_kind'],
            source_config=t['source_config'],
            sort_order=t['sort_order'],
        )
