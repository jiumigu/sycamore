"""赎回期迁移 · 前后对数（**只读**，不写任何表）

## 为什么要有它

v3.64.20 把「三年赎回期」从「一个模块」搬成「自我运转下的一个长阶段」。
搬动的不是代码，是**同一批数字的出处** —— 而这种搬家最容易出的错是
「数变了，但没人说得清是搬错了还是口径本来就错」。

所以迁移前后各跑一次，`diff` 两份输出：**必须逐字相同**。

## 用法

    # ① 迁移前（此时 redemption_period 还在）
    cd backend && ../.venv/bin/python ledger_crosscheck.py > /tmp/ledger_before.json

    # ② 备份数据库 → 执行 migrate
    cd backend && ../.venv/bin/python manage.py migrate

    # ③ 迁移后
    cd backend && ../.venv/bin/python ledger_crosscheck.py > /tmp/ledger_after.json

    diff /tmp/ledger_before.json /tmp/ledger_after.json

`diff` 无输出 = 闸门通过。有任何一行不同，先别往下走（别删 `db_backups/`）。

⚠️ 只读：脚本只 SELECT。窗口与本金两个输入优先从 `redemption_period` 取；
   那张表被删之后自动回落到长阶段的 `ledger_config`。
"""
import json
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sycamore.settings.development')
django.setup()

from django.db import connection  # noqa: E402
from django.db.models import Sum  # noqa: E402
from django.db.utils import OperationalError, ProgrammingError  # noqa: E402

from apps.redemption import services as rs  # noqa: E402


def _table_exists(name):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = %s",
            [name],
        )
        return cur.fetchone()[0] > 0


def _inputs():
    """返回 `(start, end, principal, 来源)`。

    先看旧表（迁移前），再看长阶段（迁移后）—— 两个都读不到就报错退出，
    **不许**兜一个默认窗口：默认窗口会让「算出来的数」看着正常但压根不是这段路。
    """
    if _table_exists('redemption_period'):
        with connection.cursor() as cur:
            cur.execute(
                'SELECT start_date, end_date, pool_principal '
                'FROM redemption_period ORDER BY id LIMIT 1'
            )
            row = cur.fetchone()
        if row:
            return row[0], row[1], float(row[2] or 0), 'redemption_period'

    from apps.selfrun.models import SelfRunStage

    stage = (
        SelfRunStage.objects
        .filter(parent__isnull=True, name='三年赎回期')
        .order_by('id')
        .first()
    )
    if stage is None:
        stage = (
            SelfRunStage.objects
            .filter(parent__isnull=True, metrics__isnull=True)
            .order_by('id')
            .first()
        )
    if stage is None:
        print('找不到窗口来源：既没有 redemption_period，也没有长阶段。', file=sys.stderr)
        sys.exit(2)
    principal = float((stage.ledger_config or {}).get('pool_principal') or 0)
    return stage.start_date, stage.end_date, principal, f'stage#{stage.id}'


def main():
    start, end, principal, source = _inputs()

    injected, inject_ids = 0.0, []
    if _table_exists('selfrun_pool_inject'):
        from apps.selfrun.readers import pool_inject_totals

        # v3.64.26：注入改成「标记账单」，金额从账单读、并按同一区间夹窗口
        injected, inject_ids = pool_inject_totals(start, end)

    try:
        pool = rs.compute_pool_balance(
            principal, start, end, injected, exclude_bill_ids=inject_ids,
        )
        avg_daily = rs.compute_avg_daily_self_net(start, end)
        support_until, support_reason = rs.compute_support_until(pool['balance'], avg_daily)
        time_block = rs.compute_time_attribution(start, end)
        money = {
            'pool': {
                **pool,
                'avg_daily': avg_daily,
                'support_until': support_until,
                'support_zero_reason': support_reason,
            },
            'tier': rs.compute_tier_stats(start, end),
            'unit_cost': rs.compute_unit_cost(
                start, end, pool['self_expense'] - pool['self_income'],
            ),
        }
    except (OperationalError, ProgrammingError) as exc:
        print(f'读表失败：{exc}', file=sys.stderr)
        sys.exit(3)

    out = {
        'source': source,
        'window': {'start': start.isoformat(), 'end': end.isoformat()},
        'principal': principal,
        'time': time_block,
        'money': money,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str))


if __name__ == '__main__':
    main()
