import logging
import os
import subprocess
from datetime import date, datetime

from django.conf import settings
from django.db.models import Max, Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MenuGroup, MenuPreference, Notification, SystemPreset, UserProfile


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


class SystemPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemPreset
        fields = ['preset_type', 'values', 'updated_at']


class SystemPresetViewSet(viewsets.ReadOnlyModelViewSet):
    """系统预设：标签 / 快捷短语，按 preset_type 存取"""

    permission_classes = [AllowAny]
    queryset = SystemPreset.objects.all()
    serializer_class = SystemPresetSerializer

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """按类型获取预设值，如 ?type=diary_tags"""
        preset_type = request.query_params.get('type', '')
        obj = SystemPreset.objects.filter(preset_type=preset_type).first()
        if not obj:
            return Response({'preset_type': preset_type, 'values': []})
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=['post'])
    def save_by_type(self, request):
        """按类型创建/更新预设，body: {preset_type, values}"""
        preset_type = request.data.get('preset_type', '').strip()
        values = request.data.get('values')

        if preset_type not in dict(SystemPreset.PRESET_TYPE_CHOICES):
            return Response({'error': '无效的预设类型'}, status=400)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            return Response({'error': 'values 必须是字符串列表'}, status=400)

        obj, _ = SystemPreset.objects.update_or_create(
            preset_type=preset_type,
            defaults={'values': values},
        )
        return Response(self.get_serializer(obj).data)


# ========== 菜单管理（动态侧边栏） ==========

DEFAULT_MENU_GROUPS = [
    {'key': 'overview', 'name': '总览', 'sort': 1},
    {'key': 'temporal', 'name': '时间感知', 'sort': 2},
    {'key': 'goals', 'name': '目标与项目', 'sort': 3},
    {'key': 'health', 'name': '身心健康', 'sort': 4},
    {'key': 'nourishment', 'name': '精神滋养', 'sort': 5},
    {'key': 'wealth', 'name': '财富管理', 'sort': 6},
    {'key': 'connection', 'name': '连接与足迹', 'sort': 7},
    {'key': 'tools', 'name': '工具箱', 'sort': 8},
    {'key': 'system', 'name': '系统运维', 'sort': 9},
]


def ensure_default_menu_groups() -> None:
    """首次使用惰性 seed 默认分组（表空时写入）"""
    if MenuGroup.objects.exists():
        return
    MenuGroup.objects.bulk_create([
        MenuGroup(group_key=g['key'], group_name=g['name'], sort_order=g['sort'])
        for g in DEFAULT_MENU_GROUPS
    ])


class MenuPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuPreference
        fields = ['id', 'menu_key', 'is_favorite', 'sort_order', 'updated_at']


class MenuGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuGroup
        fields = ['id', 'group_key', 'group_name', 'sort_order', 'is_visible', 'created_at', 'updated_at']


class MenuPreferenceViewSet(viewsets.ReadOnlyModelViewSet):
    """菜单偏好：常用/归档切换 + 批量更新"""

    permission_classes = [AllowAny]
    queryset = MenuPreference.objects.all()
    serializer_class = MenuPreferenceSerializer

    @action(detail=False, methods=['get'])
    def user_prefs(self, request):
        """获取当前用户菜单偏好"""
        user_id = request.query_params.get('user_id', 1)
        prefs = MenuPreference.objects.filter(user_id=user_id)
        return Response(self.get_serializer(prefs, many=True).data)

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新菜单偏好，body: {updates: [{menu_key, is_favorite, sort_order}]}"""
        updates = request.data.get('updates', [])
        if not isinstance(updates, list):
            return Response({'error': 'updates 必须是列表'}, status=400)
        for u in updates:
            menu_key = u.get('menu_key')
            if not menu_key:
                continue
            MenuPreference.objects.update_or_create(
                menu_key=menu_key,
                defaults={
                    'is_favorite': bool(u.get('is_favorite', True)),
                    'sort_order': int(u.get('sort_order', 0)),
                },
            )
        return Response({'success': True, 'updated': len(updates)})


class MenuGroupViewSet(viewsets.ModelViewSet):
    """菜单分组 CRUD（重命名/排序/新增/删除/显隐）"""

    permission_classes = [AllowAny]
    queryset = MenuGroup.objects.all()
    serializer_class = MenuGroupSerializer

    def list(self, request, *args, **kwargs):
        ensure_default_menu_groups()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        # 新分组默认排在最后
        max_sort = MenuGroup.objects.aggregate(Max('sort_order'))['sort_order__max'] or 0
        serializer.save(sort_order=max_sort + 1)


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
