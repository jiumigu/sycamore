from datetime import datetime

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth, TruncDate

from .models import FoodRecord


class FoodService:
    """美食记录业务逻辑"""

    @staticmethod
    def get_stats(user_id: int = 1) -> dict:
        """获取美食统计"""
        qs = FoodRecord.objects.filter(user_id=user_id)
        today = datetime.now().date()
        month_start = today.replace(day=1)

        stats = qs.aggregate(
            total_records=Count('id'),
            total_cities=Count('city', distinct=True),
            avg_rating=Avg('rating'),
            want_visit_again_count=Count('id', filter=Q(want_visit_again=True)),
        )

        # 最爱分类
        fav = (
            qs.values('category')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
            .first()
        )

        # 本月新增
        this_month = qs.filter(eat_date__gte=month_start).count()

        return {
            'total_records': stats['total_records'] or 0,
            'total_cities': stats['total_cities'] or 0,
            'favorite_category': fav['category'] if fav else None,
            'favorite_category_count': fav['cnt'] if fav else 0,
            'avg_rating': round(float(stats['avg_rating'] or 0), 1),
            'want_visit_again_count': stats['want_visit_again_count'] or 0,
            'this_month_count': this_month,
        }

    @staticmethod
    def get_locations(user_id: int = 1) -> list:
        """获取去过的地方"""
        return list(
            FoodRecord.objects
            .filter(user_id=user_id)
            .values('province', 'city')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    @staticmethod
    def get_map_data(user_id: int = 1) -> list:
        """获取地图展示数据（按省份聚合）"""
        qs = FoodRecord.objects.filter(user_id=user_id)
        provinces = (
            qs.values('province')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        result = []
        for p in provinces:
            cities = list(
                qs.filter(province=p['province'])
                .values('city')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            result.append({
                'province': p['province'],
                'count': p['count'],
                'cities': cities,
            })
        return result

    @staticmethod
    def get_tags(user_id: int = 1) -> list:
        """获取常用标签"""
        tags = (
            FoodRecord.objects
            .filter(user_id=user_id)
            .exclude(Q(tags__isnull=True) | Q(tags=''))
            .values('tags')
        )
        tag_counts: dict[str, int] = {}
        for t in tags:
            for tag in t['tags'].split(','):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return [
            {'name': k, 'count': v}
            for k, v in sorted(tag_counts.items(), key=lambda x: -x[1])
        ]

    @staticmethod
    def get_monthly_trend(year: int, user_id: int = 1) -> list:
        """获取月度趋势"""
        monthly = (
            FoodRecord.objects
            .filter(user_id=user_id, eat_date__year=year)
            .annotate(month=TruncMonth('eat_date'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        return [{'month': m['month'].month, 'count': m['count']} for m in monthly]

    @staticmethod
    def get_category_distribution(user_id: int = 1) -> list:
        """获取分类分布"""
        return list(
            FoodRecord.objects
            .filter(user_id=user_id)
            .values('category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

    @staticmethod
    def get_taste_distribution(user_id: int = 1) -> list:
        """获取美味等级分布"""
        return list(
            FoodRecord.objects
            .filter(user_id=user_id)
            .values('taste_level')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
