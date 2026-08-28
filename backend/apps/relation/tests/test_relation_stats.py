"""relation 服务 ORM 化回归：overview / 趋势 / 质量计算（CONVERT_TZ 修复验证）"""
import pytest
from datetime import timedelta

from django.utils import timezone

from apps.relation.models import Interaction, Relationship
from apps.relation.services.quality_service import QualityService
from apps.relation.services.stats_service import StatsService


@pytest.mark.django_db
class TestRelationStats:
    def _rel(self, name='朋友', quality='neutral'):
        return Relationship.objects.create(user_id=1, name=name, current_quality=quality, current_status='active', tags='')

    def test_overview_monthly_count_uses_range(self):
        """回归：happened_at__year/month 在 CONVERT_TZ 下失效，改为区间后本月计数正确"""
        rel = self._rel()
        now = timezone.now()
        Interaction.objects.create(relationship=rel, user_id=1, energy_score=5,
                                   happened_at=now - timedelta(days=1))  # 本月
        Interaction.objects.create(relationship=rel, user_id=1, energy_score=3,
                                   happened_at=now - timedelta(days=40))  # 上月
        o = StatsService.get_overview()
        assert o['monthly_interactions'] == 1
        assert o['last_month_interactions'] == 1
        assert o['total_energy'] == 8.0

    def test_quality_distribution(self):
        self._rel(name='滋养', quality='nourishing')
        self._rel(name='中性', quality='neutral')
        dist = {d['quality']: d['count'] for d in StatsService.get_quality_distribution()}
        assert dist['nourishing'] == 1 and dist['neutral'] == 1

    def test_energy_trend_period_format(self):
        rel = self._rel()
        now = timezone.now()
        Interaction.objects.create(relationship=rel, user_id=1, energy_score=5, happened_at=now)
        trend = StatsService.get_energy_trend(user_id=1, months=6)
        assert trend and trend[0]['period'] == now.strftime('%Y-%m')
        assert trend[0]['total_energy'] == 5.0

    def test_due_reminders(self):
        old = self._rel(name='久未联系')
        now = timezone.now()
        Interaction.objects.create(relationship=old, user_id=1, energy_score=1,
                                   happened_at=now - timedelta(days=60))
        fresh = self._rel(name='常联系')
        Interaction.objects.create(relationship=fresh, user_id=1, energy_score=1,
                                   happened_at=now - timedelta(days=1))
        due = StatsService.get_due_reminders()
        names = {d['name'] for d in due}
        assert '久未联系' in names and '常联系' not in names

    def test_quality_service_updates(self):
        rel = self._rel()
        now = timezone.now()
        for i in range(5):
            Interaction.objects.create(relationship=rel, user_id=1, energy_score=8,
                                       happened_at=now - timedelta(days=i))
        q = QualityService.update_relationship_quality(rel.id, 1)
        assert q == 'nourishing'
        rel.refresh_from_db()
        assert rel.current_quality == 'nourishing'


@pytest.mark.django_db
class TestDueRemindersExcludeCoworker:
    def test_coworker_excluded_from_reminders(self):
        """当时身份为同事的关系不进入待跟进提醒"""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient
        now = timezone.now()
        coworker = Relationship.objects.create(user_id=1, name='老同事', current_quality='neutral',
                                               current_status='active', tags='', identity_then='同事')
        friend = Relationship.objects.create(user_id=1, name='老朋友', current_quality='neutral',
                                             current_status='active', tags='', identity_then='同学')
        # 两者都超过 30 天未互动
        Interaction.objects.create(relationship=coworker, user_id=1, energy_score=1,
                                   happened_at=now - timedelta(days=60))
        Interaction.objects.create(relationship=friend, user_id=1, energy_score=1,
                                   happened_at=now - timedelta(days=60))
        c = APIClient()
        r = c.get('/api/relation/stats/due_reminders/')
        names = [x['name'] for x in r.data]
        assert '老朋友' in names
        assert '老同事' not in names
