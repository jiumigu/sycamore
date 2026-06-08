import os
import subprocess
from datetime import date, datetime

from django.conf import settings
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, UserProfile


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
        fields = ['user_id', 'privacy_mode']


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
