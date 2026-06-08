from django.db import models

from .constants import FILE_CATEGORY_CHOICES


class DamsFileResource(models.Model):
    """文件资源"""

    name = models.CharField(max_length=500, verbose_name='文件名')
    path = models.TextField(verbose_name='完整路径')
    storage_location = models.CharField(
        max_length=200, blank=True, default='', verbose_name='存储位置',
    )
    file_category = models.CharField(
        max_length=50, blank=True, default='', choices=FILE_CATEGORY_CHOICES,
        verbose_name='文件分类',
    )
    file_size_mb = models.FloatField(default=0, verbose_name='文件大小(MB)')
    access_count = models.IntegerField(default=0, verbose_name='访问次数')
    last_accessed_at = models.DateTimeField(blank=True, null=True, verbose_name='最后访问时间')
    folder_depth = models.IntegerField(default=0, verbose_name='文件夹深度')
    parent_folder = models.CharField(
        max_length=500, blank=True, default='', verbose_name='父文件夹',
    )
    is_duplicate = models.BooleanField(default=False, verbose_name='是否重复')
    is_organized = models.BooleanField(default=False, verbose_name='是否已整理')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'dams_file_resource'
        verbose_name = '文件资源'
        verbose_name_plural = '文件资源'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name


class DamsAccessLog(models.Model):
    """文件访问日志"""

    file = models.ForeignKey(
        DamsFileResource, on_delete=models.CASCADE, related_name='access_logs',
        db_column='file_id', verbose_name='关联文件',
    )
    accessed_at = models.DateTimeField(verbose_name='访问时间')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        managed = True
        db_table = 'dams_access_log'
        verbose_name = '访问日志'
        verbose_name_plural = '访问日志'
        ordering = ['-accessed_at']

    def __str__(self):
        return f'{self.file.name} @ {self.accessed_at}'
