"""综合进度看板 — 季度工作台（由 services.py 拆分）"""

from __future__ import annotations

from django.db.models import Q

from .progress_aggregator import ProgressAggregator

from ..constants import (
    CONVERSION_RULES,
    MODULE_LIST,
    MODULE_META,
    TRAVEL,
    YEARLY_TARGET,
)

class QuarterlyWorkbenchService:
    """季度决策工作台 —— 生成季度对比报告、洞察与追问"""

    QUARTER_MONTHS = {
        1: (1, 2, 3),
        2: (4, 5, 6),
        3: (7, 8, 9),
        4: (10, 11, 12),
    }

    # ── 工具方法 ───────────────────────────────────────

    @staticmethod
    def _prev_quarter(year: int, quarter: int) -> tuple[int, int]:
        """返回上一个季度的 (year, quarter)"""
        if quarter == 1:
            return year - 1, 4
        return year, quarter - 1

    @staticmethod
    def _quarter_months(quarter: int) -> tuple[int, int, int]:
        return QuarterlyWorkbenchService.QUARTER_MONTHS[quarter]

    @classmethod
    def _quarter_range(cls, year: int, quarter: int) -> tuple[tuple[int, int], tuple[int, int]]:
        """返回季度的月份范围 [(year, month), (year, month)]"""
        months = cls._quarter_months(quarter)
        return (year, months[0]), (year, months[2])

    # ── 单模块季度聚合 ────────────────────────────────

    @classmethod
    def _module_quarter_raw(cls, module: str, year: int, quarter: int) -> float:
        months = cls._quarter_months(quarter)
        total = 0.0
        for m in months:
            total += ProgressAggregator._get_raw_value(module, year, m)
        return total

    @classmethod
    def _module_quarter_points(cls, module: str, year: int, quarter: int) -> float:
        raw = cls._module_quarter_raw(module, year, quarter)
        return ProgressAggregator._raw_to_points(module, raw)

    # ── 公开: 季度报告 ────────────────────────────────

    @classmethod
    def get_quarterly_report(cls, year: int, quarter: int) -> dict:
        """生成季度报告：7 模块聚合 + 与上季度 / 去年同期对比"""
        prev_y, prev_q = cls._prev_quarter(year, quarter)
        last_year_quarter = (year - 1, quarter)

        modules_data = []
        for mod in MODULE_LIST:
            cur = cls._module_quarter_points(mod, year, quarter)
            prev = cls._module_quarter_points(mod, prev_y, prev_q)
            last_year = cls._module_quarter_points(mod, *last_year_quarter)
            meta = MODULE_META[mod]
            rule = CONVERSION_RULES[mod]
            raw = cls._module_quarter_raw(mod, year, quarter)

            qoq_change = ((cur - prev) / prev * 100) if prev > 0 else (100 if cur > 0 else 0)
            yoy_change = ((cur - last_year) / last_year * 100) if last_year > 0 else (100 if cur > 0 else 0)

            modules_data.append({
                'module': mod,
                'label': meta['label'],
                'color': meta['color'],
                'points': round(cur, 2),
                'raw_value': round(raw, 2),
                'unit': rule['unit'],
                'prev_quarter_points': round(prev, 2),
                'qoq_change': round(qoq_change, 1),
                'last_year_points': round(last_year, 2),
                'yoy_change': round(yoy_change, 1),
            })

        total = sum(m['points'] for m in modules_data)
        prev_total = sum(m['prev_quarter_points'] for m in modules_data)
        last_year_total = sum(
            cls._module_quarter_points(mod, *last_year_quarter) for mod in MODULE_LIST
        ) if year - 1 >= 2000 else 0

        quarterly_target = YEARLY_TARGET / 4

        return {
            'year': year,
            'quarter': quarter,
            'label': f'{year}年Q{quarter}',
            'total_points': round(total, 2),
            'quarter_target': round(quarterly_target, 2),
            'target_percent': round(total / quarterly_target * 100, 2) if quarterly_target else 0,
            'prev_quarter_total': round(prev_total, 2),
            'qoq_change': round(
                ((total - prev_total) / prev_total * 100) if prev_total > 0 else (100 if total > 0 else 0), 1
            ),
            'last_year_total': round(last_year_total, 2),
            'yoy_change': round(
                ((total - last_year_total) / last_year_total * 100) if last_year_total > 0 else (100 if total > 0 else 0), 1
            ),
            'modules': modules_data,
        }

    # ── 犹豫中事项查询 ────────────────────────────────

    @staticmethod
    def _hesitating_items() -> list[str]:
        """返回犹豫中事项的内容列表（最多10条）"""
        try:
            from apps.inbox.models import InboxItem
            return list(
                InboxItem.objects.filter(status='hesitating')
                .values_list('content', flat=True)[:10]
            )
        except Exception:
            return []

    # ── 公开: 生成洞察与追问 ──────────────────────────

    @classmethod
    def generate_questions(cls, year: int, quarter: int) -> list[dict]:
        """分析季度数据，生成针对性追问"""
        report = cls.get_quarterly_report(year, quarter)
        questions: list[dict] = []
        qk = 0  # question key counter

        # 1. 整体进度追问
        total = report['total_points']
        target = report['quarter_target']

        if total < target * 0.5:
            qk += 1
            questions.append({
                'question_key': f'overall_behind_{qk}',
                'question_category': 'target_behind',
                'question_text': f'Q{quarter} 只完成了目标的 {report["target_percent"]}%，差距较大。'
                                 f'哪个模块拖后腿最严重？下季度需要砍掉什么来补上？',
                'related_module': '',
            })
        elif total < target * 0.8:
            qk += 1
            questions.append({
                'question_key': f'overall_slightly_behind_{qk}',
                'question_category': 'target_behind',
                'question_text': f'Q{quarter} 完成了 {report["target_percent"]}%，还差一点。'
                                 f'哪些模块还有潜力可以挖掘？',
                'related_module': '',
            })

        # 2. 同比/环比显著变化追问
        for m in report['modules']:
            mod = m['module']
            # 环比显著下降
            if m['qoq_change'] <= -30:
                qk += 1
                questions.append({
                    'question_key': f'drop_qoq_{mod}_{qk}',
                    'question_category': 'drop',
                    'question_text': f'【{m["label"]}】环比暴跌 {abs(m["qoq_change"])}%'
                                    f'（{m["prev_quarter_points"]} → {m["points"]} 点）。'
                                    f'发生了什么？是外部因素还是主动选择？需要调整计划吗？',
                    'related_module': mod,
                })
            # 环比显著上升
            elif m['qoq_change'] >= 50:
                qk += 1
                questions.append({
                    'question_key': f'rise_qoq_{mod}_{qk}',
                    'question_category': 'improve',
                    'question_text': f'【{m["label"]}】环比飙升 {m["qoq_change"]}%'
                                    f'（{m["prev_quarter_points"]} → {m["points"]} 点）。'
                                    f'做对了什么？能否复制到其他模块？',
                    'related_module': mod,
                })
            # 同比显著下降
            if m['yoy_change'] <= -30:
                qk += 1
                questions.append({
                    'question_key': f'drop_yoy_{mod}_{qk}',
                    'question_category': 'drop',
                    'question_text': f'【{m["label"]}】同比去年同期下降 {abs(m["yoy_change"])}%'
                                    f'（去年 {m["last_year_points"]} → 今年 {m["points"]} 点）。'
                                    f'这个趋势值得关注，需要制定挽回计划吗？',
                    'related_module': mod,
                })

            # 最低分模块
            if m['points'] <= 1.0 and mod != TRAVEL:  # 旅行可能天然低频
                qk += 1
                questions.append({
                    'question_key': f'low_performer_{mod}_{qk}',
                    'question_category': 'low_performer',
                    'question_text': f'【{m["label"]}】本季度仅 {m["points"]} 点，几乎为零投入。'
                                     f'是暂时搁置还是已经放弃了这个维度？如果是放弃，需要从目标中移除吗？',
                    'related_module': mod,
                })

        # 3. 极端波动追问（找出变化最大的模块）
        changes = [(m['module'], m['label'], abs(m['qoq_change'])) for m in report['modules']]
        changes.sort(key=lambda x: x[2], reverse=True)
        if changes and changes[0][2] > 20:
            top_mod, top_label, top_change = changes[0]
            qk += 1
            questions.append({
                'question_key': f'biggest_swing_{qk}',
                'question_category': 'general',
                'question_text': f'Q{quarter} 变化最大的维度是「{top_label}」（波动 {top_change}%）。'
                                 f'如果只能做一件事来改善下个季度的整体进度，你会做什么？',
                'related_module': top_mod,
            })

        # 4. 年度进度预测
        ytd_ratio = cls._ytd_progress(year, quarter)
        if ytd_ratio < 0.5:
            qk += 1
            questions.append({
                'question_key': f'year_progress_{qk}',
                'question_category': 'target_behind',
                'question_text': f'已经过去 {quarter}/4 年，但只完成了全年目标的 {round(ytd_ratio * 100, 1)}%。'
                                 f'剩下的时间需要加倍投入。最重要的 1-2 个冲刺目标是什么？',
                'related_module': '',
            })

        # 5. 犹豫中事项追问
        hesitating_items = cls._hesitating_items()
        if hesitating_items:
            qk += 1
            names = '、'.join(f'「{item}」' for item in hesitating_items[:3])
            extra = f'还有 {len(hesitating_items) - 3} 件类似事项' if len(hesitating_items) > 3 else ''
            questions.append({
                'question_key': f'hesitating_{qk}',
                'question_category': 'general',
                'question_text': f'你有 {len(hesitating_items)} 件一直想做但不敢开始的事：{names}{extra}。'
                                 f'这些事你真的做不到，还是只是害怕？如果去掉对结果的担忧，你最想先开始哪一件？',
                'related_module': 'inbox',
            })

        # 如果没有明显问题，给一个正面追问
        if not questions:
            qk += 1
            questions.append({
                'question_key': f'all_good_{qk}',
                'question_category': 'general',
                'question_text': f'Q{quarter} 各项指标总体平稳。回顾这三个月，最让你有成就感的是什么？'
                                 f'下季度有什么新计划？',
                'related_module': '',
            })

        return questions

    @classmethod
    def _ytd_progress(cls, year: int, current_quarter: int) -> float:
        """计算年初到本季度结束的累计进度占全年目标的比例"""
        months_up_to = []
        for q in range(1, current_quarter + 1):
            months_up_to.extend(cls._quarter_months(q))
        total = 0.0
        for mod in MODULE_LIST:
            for m in months_up_to:
                total += ProgressAggregator._raw_to_points(mod, ProgressAggregator._get_raw_value(mod, year, m))
        return total / YEARLY_TARGET if YEARLY_TARGET else 0

    # ── 问答持久化 ────────────────────────────────────

    @classmethod
    def get_answers(cls, year: int, quarter: int) -> list[dict]:
        from ..models import QuarterlyAnswer
        qs = QuarterlyAnswer.objects.filter(year=year, quarter=quarter).order_by('created_at')
        return [
            {
                'id': a.id,
                'question_key': a.question_key,
                'question_text': a.question_text,
                'question_category': a.question_category,
                'answer_text': a.answer_text,
                'related_module': a.related_module,
                'action_taken': a.action_taken,
                'updated_at': a.updated_at.isoformat() if a.updated_at else '',
            }
            for a in qs
        ]

    @classmethod
    def save_answer(cls, year: int, quarter: int, question_key: str, answer_text: str,
                    action_taken: bool = False) -> dict:
        from ..models import QuarterlyAnswer
        obj, created = QuarterlyAnswer.objects.update_or_create(
            year=year,
            quarter=quarter,
            question_key=question_key,
            defaults={
                'answer_text': answer_text,
                'action_taken': action_taken,
            },
        )
        return {'id': obj.id, 'status': 'created' if created else 'updated'}

    @classmethod
    def get_insights(cls, year: int, quarter: int) -> list[dict]:
        """生成简洁的洞察摘要"""
        report = cls.get_quarterly_report(year, quarter)
        insights: list[dict] = []

        total = report['total_points']
        target = report['quarter_target']

        # 整体评估
        if total >= target:
            insights.append({
                'type': 'success',
                'icon': '🎯',
                'message': f'达标！Q{quarter} 完成 {total} 点，达到目标的 {report["target_percent"]}%',
            })
        elif total >= target * 0.8:
            insights.append({
                'type': 'warning',
                'icon': '⚠️',
                'message': f'接近达标：Q{quarter} 完成 {total} 点（目标的 {report["target_percent"]}%），还差 {round(target - total, 1)} 点',
            })
        else:
            insights.append({
                'type': 'danger',
                'icon': '🔻',
                'message': f'未达标：Q{quarter} 仅完成 {total} 点（目标的 {report["target_percent"]}%），差距 {round(target - total, 1)} 点',
            })

        # 环比趋势
        qoq = report['qoq_change']
        if qoq > 10:
            insights.append({
                'type': 'success',
                'icon': '📈',
                'message': f'环比上季度增长 {qoq}%，整体趋势向好',
            })
        elif qoq < -10:
            insights.append({
                'type': 'danger',
                'icon': '📉',
                'message': f'环比上季度下降 {abs(qoq)}%，需关注下滑趋势',
            })
        else:
            insights.append({
                'type': 'info',
                'icon': '➡️',
                'message': f'环比基本持平（{qoq}%），稳定性不错',
            })

        # 最佳/最差模块
        sorted_modules = sorted(report['modules'], key=lambda m: m['qoq_change'], reverse=True)
        if sorted_modules:
            best = sorted_modules[0]
            worst = sorted_modules[-1]
            if best['qoq_change'] > 0:
                insights.append({
                    'type': 'success',
                    'icon': '🏆',
                    'message': f'最佳表现：{best["label"]}（环比+{best["qoq_change"]}%，'
                               f'得分 {best["points"]}）',
                })
            if worst['qoq_change'] < 0:
                insights.append({
                    'type': 'danger',
                    'icon': '🐌',
                    'message': f'最需关注：{worst["label"]}（环比{worst["qoq_change"]}%，'
                               f'得分 {worst["points"]}）',
                })

        return insights
