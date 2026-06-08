from datetime import date

from django.db import models


class Book(models.Model):
    """书籍阅读记录"""

    BTYPE_CHOICES = [
        ('基础学科', '基础学科'),
        ('哲学智慧', '哲学智慧'),
        ('心理健康', '心理健康'),
        ('财富创造', '财富创造'),
        ('幸福科学', '幸福科学'),
        ('认知提升类', '认知提升类'),
        ('技能工具类', '技能工具类'),
        ('文学滋养类', '文学滋养类'),
        ('休闲放松类', '休闲放松类'),
        ('个人成长类', '个人成长类'),
        ('能量消耗类', '能量消耗类'),
    ]

    STATUS_CHOICES = [
        ('计划阅读', '计划阅读'),
        ('在读', '在读'),
        ('精读', '精读'),
        ('通读', '通读'),
        ('消遣', '消遣'),
        ('弃读', '弃读'),
        ('已完成', '已完成'),
        ('待重读', '待重读'),
    ]

    RECOMMEND_CHOICES = [
        (0, '禁止阅读'),
        (1, '不推荐'),
        (2, '一般'),
        (3, '推荐'),
        (4, '宝藏'),
        (5, '人生必读'),
    ]

    READING_DEPTH_CHOICES = [
        (1, '速读浏览'),
        (2, '重点阅读'),
        (3, '精读细品'),
        (4, '反复研读'),
        (5, '践行内化'),
    ]

    bid = models.AutoField(primary_key=True, verbose_name='编号')
    years = models.CharField(max_length=25, blank=True, null=True, verbose_name='年度')
    btitle = models.CharField(max_length=255, blank=True, null=True, verbose_name='书名标题')
    author = models.CharField(max_length=255, blank=True, null=True, verbose_name='作者')
    original_title = models.CharField(max_length=255, blank=True, null=True, verbose_name='原著书名')
    btype = models.CharField(max_length=50, choices=BTYPE_CHOICES, blank=True, null=True, verbose_name='书籍类型')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, blank=True, null=True, verbose_name='状态')
    recommend = models.IntegerField(choices=RECOMMEND_CHOICES, default=0, verbose_name='推荐指数')
    reading_depth = models.IntegerField(choices=READING_DEPTH_CHOICES, blank=True, null=True, default=3, verbose_name='阅读深度')
    readDate = models.DateField(blank=True, null=True, verbose_name='阅读日期')
    created_at = models.DateField(default=date.today, db_column='createDate', verbose_name='创建日期')
    updated_at = models.DateField(auto_now=True, db_column='updateDate', verbose_name='更新日期')
    tags = models.CharField(max_length=500, blank=True, null=True, verbose_name='标签')
    abandon_reason = models.TextField(blank=True, null=True, verbose_name='弃读原因')
    closedop = models.TextField(blank=True, null=True, verbose_name='读后感')
    openop = models.TextField(blank=True, null=True, verbose_name='打开书时的观点和期待')
    action_item = models.TextField(blank=True, default='', verbose_name='行动项',
        help_text='读完这本书后决定做的一件事')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID（预留）')

    class Meta:
        db_table = 'book_read_list'
        ordering = ['-readDate']
        verbose_name = '书籍阅读记录'
        verbose_name_plural = '书籍阅读记录'

    @property
    def is_finished(self):
        return self.status == '已完成'

    @property
    def is_abandoned(self):
        return self.status == '弃读'

    def __str__(self):
        return f'{self.btitle} - {self.author}'
