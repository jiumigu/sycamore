import logging
import os
import subprocess
from datetime import date, datetime

from django.conf import settings
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, UserProfile


logger = logging.getLogger(__name__)


class DatabaseBackupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        backup_dir = os.path.join(settings.BASE_DIR, 'media', 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'sycamore_backup_{timestamp}.sql'
        filepath = os.path.join(backup_dir, filename)

        try:
            db_settings = settings.DATABASES['default']
            cmd = [
                'mysqldump',
                f'--host={db_settings["HOST"]}',
                f'--user={db_settings["USER"]}',
                f'--password={db_settings["PASSWORD"]}',
                db_settings['NAME'],
                '--result-file=' + filepath,
                '--single-transaction',
                '--routines',
                '--triggers',
            ]
            subprocess.run(cmd, check=True)

            return Response({
                'success': True,
                'filename': filename,
                'path': filepath,
                'size': os.path.getsize(filepath),
            })
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=500)

    def get(self, request):
        """获取备份历史列表"""
        backup_dir = os.path.join(settings.BASE_DIR, 'media', 'backups')
        if not os.path.exists(backup_dir):
            return Response([])

        backups = []
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.sql'):
                path = os.path.join(backup_dir, f)
                backups.append({
                    'filename': f,
                    'size': os.path.getsize(path),
                    'created_at': datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                })
        return Response(backups[:10])


class QuickRecordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        content = request.data.get('content', '').strip()
        module = request.data.get('module', 'temporal')

        if not content:
            return Response({'error': '内容不能为空'}, status=400)

        if module == 'temporal':
            from apps.temporal.models import OneDayPage
            OneDayPage.objects.create(
                title=content,
                begin_date=date.today(),
                otype='ONEDAY',
            )
        elif module == 'sugar':
            from apps.sugar.models import SugarRecord
            SugarRecord.objects.create(
                title=content,
                time=date.today(),
                category='other',
                level_of_happiness=5.0,
            )
        elif module == 'goals':
            from apps.inbox.models import InboxItem
            InboxItem.objects.create(
                content=content,
                category='todo',
                status='pending',
                source='manual',
            )

        return Response({'success': True, 'message': '记录成功'})


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    queryset = Notification.objects.all()
    ordering = ['-created_at']

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = Notification.objects.filter(is_read=False).count()
        return Response({'count': count})


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['user_id', 'privacy_mode', 'logseq_path']


class ProfileView(APIView):
    """用户配置（单用户系统，固定 user_id=1）"""

    permission_classes = [AllowAny]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user_id=1)
        return Response(UserProfileSerializer(profile).data)

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user_id=1)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class GlobalSearchView(APIView):
    """全局搜索 — 跨模块检索，按模块分组"""

    permission_classes = [AllowAny]

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query or len(query) < 2:
            return Response({'results': []})

        results = []

        # 1. 摘录馆
        try:
            from apps.toolkit.models import Quote
            for q in Quote.objects.filter(
                Q(content__icontains=query) |
                Q(short_title__icontains=query) |
                Q(tags__icontains=query) |
                Q(author__icontains=query)
            )[:5]:
                results.append({
                    'module': 'quote', 'module_name': '📖 摘录馆',
                    'id': q.id, 'title': q.short_title or q.content[:50],
                    'content': q.content[:100], 'date': q.created_at.strftime('%Y-%m-%d'),
                })
        except Exception as e:
            logger.warning('全局搜索模块「摘录馆」失败: %s', e)

        # 2. 日记流
        try:
            from apps.temporal.models import OneDayPage
            for d in OneDayPage.objects.filter(
                Q(title__icontains=query) | Q(remark__icontains=query)
            )[:5]:
                results.append({
                    'module': 'diary', 'module_name': '📝 日记流',
                    'id': d.oid, 'title': d.title or '无标题',
                    'content': (d.remark or '')[:100], 'date': d.begin_date.isoformat(),
                })
        except Exception as e:
            logger.warning('全局搜索模块「日记流」失败: %s', e)

        # 3. 小确幸
        try:
            from apps.sugar.models import SugarRecord
            for s in SugarRecord.objects.filter(
                Q(title__icontains=query) | Q(joy_type__icontains=query)
            )[:5]:
                results.append({
                    'module': 'sugar', 'module_name': '🍰 小确幸',
                    'id': s.s_id, 'title': s.title[:50],
                    'content': s.title[:100], 'date': s.time.isoformat(),
                })
        except Exception as e:
            logger.warning('全局搜索模块「小确幸」失败: %s', e)

        # 4. 好东西档案馆
        try:
            from apps.treasure.models import GoodThing
            for t in GoodThing.objects.filter(
                Q(name__icontains=query) |
                Q(why_good__icontains=query) |
                Q(avoid_reason__icontains=query) |
                Q(tags__icontains=query)
            )[:5]:
                results.append({
                    'module': 'treasure', 'module_name': '💎 好东西',
                    'id': t.id, 'title': t.name,
                    'content': (t.why_good or t.avoid_reason or '')[:100],
                    'date': t.created_at.strftime('%Y-%m-%d'),
                })
        except Exception as e:
            logger.warning('全局搜索模块「好东西」失败: %s', e)

        # 5. 复盘记录
        try:
            from apps.toolkit.models import ReviewRecord
            for r in ReviewRecord.objects.filter(
                Q(notes__icontains=query) |
                Q(completed__icontains=query) |
                Q(reflection__icontains=query) |
                Q(nourishing__icontains=query) |
                Q(draining__icontains=query) |
                Q(fears__icontains=query) |
                Q(life_line__icontains=query) |
                Q(deep_reflection__icontains=query)
            )[:5]:
                results.append({
                    'module': 'review', 'module_name': '🧭 复盘',
                    'id': r.id,
                    'title': f'{r.get_review_type_display()} - {r.review_date}',
                    'content': (r.notes or r.reflection or '')[:100],
                    'date': r.review_date.isoformat(),
                })
        except Exception as e:
            logger.warning('全局搜索模块「复盘」失败: %s', e)

        # 按模块分组
        grouped = {}
        for r in results:
            group_key = r['module']
            if group_key not in grouped:
                grouped[group_key] = {'module_name': r['module_name'], 'items': []}
            grouped[group_key]['items'].append(r)

        return Response({
            'query': query,
            'total': len(results),
            'groups': list(grouped.values()),
        })
