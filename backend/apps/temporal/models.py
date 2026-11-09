from django.db import models
from django.utils import timezone

from .constants import ATTRIBUTION_CHOICES, CATEGORY_CHOICES, DAILY_ROLE_CHOICES


class TemporalTask(models.Model):
    """任务时间记录（映射现有表 temporal_time_atracker_tasks_list）"""

    task_name = models.CharField(max_length=255, verbose_name='任务名称')
    task_description = models.TextField(blank=True, null=True, verbose_name='任务说明')
    start_time = models.DateTimeField(blank=True, null=True, verbose_name='开始时间')
    end_time = models.DateTimeField(blank=True, null=True, verbose_name='结束时间')
    duration = models.TimeField(blank=True, null=True, verbose_name='持续时间')
    duration_hours = models.FloatField(blank=True, null=True, verbose_name='持续小时数')
    notes = models.TextField(blank=True, null=True, verbose_name='附注')
    tags = models.TextField(blank=True, null=True, verbose_name='标签')
    task_type = models.CharField(max_length=100, default='其他', verbose_name='任务类型')
    year = models.IntegerField(blank=True, null=True, verbose_name='年份')
    mon = models.CharField(max_length=10, blank=True, null=True, verbose_name='月份')
    day = models.IntegerField(blank=True, null=True, verbose_name='日期')
    week = models.IntegerField(blank=True, null=True, verbose_name='周数')
    quarter = models.IntegerField(blank=True, null=True, verbose_name='季度')
    category_level1 = models.CharField(
        max_length=50, blank=True, null=True, choices=CATEGORY_CHOICES, verbose_name='一级分类',
    )
    category_level2 = models.CharField(max_length=50, blank=True, null=True, verbose_name='二级分类')
    category_color = models.CharField(max_length=20, blank=True, null=True, verbose_name='分类颜色')
    import_batch = models.CharField(max_length=50, blank=True, null=True, verbose_name='导入批次号')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = False
        db_table = 'temporal_time_atracker_tasks_list'
        verbose_name = '任务时间记录'
        verbose_name_plural = '任务时间记录'
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.task_name} ({self.start_time})'


class OneDayPage(models.Model):
    """每日记录模型（oneday + page 字数统计）"""

    OTYPE_CHOICES = [
        ('MIGU', '迷谷知松'),
        ('HAPPY', '有点开心'),
        ('SAD', '有点闹心'),
        ('DIGITAL', '数字转型'),
        ('SUMMARY', '复盘总结'),
        ('ONEDAY', '普通一日'),
        ('IDEA', '有点想法'),
        ('ACHIEVE', '有点成就'),
    ]

    oid = models.AutoField(primary_key=True, verbose_name='编号')
    years = models.CharField(max_length=25, blank=True, null=True, verbose_name='年度')
    oneday = models.IntegerField(blank=True, null=True, verbose_name='oneday字数')
    page = models.IntegerField(blank=True, null=True, verbose_name='文章字数')
    total = models.IntegerField(blank=True, null=True, verbose_name='总字数')
    title = models.CharField(max_length=255, verbose_name='主题')
    begin_date = models.DateField(default=timezone.localdate, verbose_name='创建日期')
    otype = models.CharField(max_length=50, default='ONEDAY', choices=OTYPE_CHOICES, verbose_name='内容类型')
    update_date = models.DateField(default=timezone.localdate, verbose_name='更新日期')
    flag = models.CharField(max_length=50, blank=True, null=True, verbose_name='标签')
    remark = models.CharField(max_length=255, blank=True, null=True, verbose_name='备注')
    user_id = models.BigIntegerField(blank=True, null=True, verbose_name='预留用户ID')

    class Meta:
        managed = False
        db_table = 'temporal_oneday_page_list'
        verbose_name = '每日记录'
        verbose_name_plural = '每日记录'
        ordering = ['-begin_date']

    def __str__(self):
        return f"{self.title or '无标题'} - {self.begin_date}"

    def save(self, *args, **kwargs):
        if self.begin_date:
            self.years = str(self.begin_date.year)
        self.total = (self.oneday or 0) + (self.page or 0)
        self.update_date = timezone.localdate()
        super().save(*args, **kwargs)


class WeeklyTimeCache(models.Model):
    """周度时间固化统计表"""

    year = models.IntegerField(verbose_name='年份')
    week = models.IntegerField(verbose_name='周次')
    total_hours = models.FloatField(default=0, verbose_name='本周总小时')
    task_count = models.IntegerField(default=0, verbose_name='任务数')
    avg_hours_per_day = models.FloatField(default=0, verbose_name='日均小时')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'temporal_weekly_time_cache'
        db_table_comment = '周度时间缓存：把周工时算完就固化，避免每次都重扫原始表'
        verbose_name = '周度时间固化统计'
        verbose_name_plural = '周度时间固化统计'
        unique_together = ['year', 'week']
        ordering = ['year', 'week']
        indexes = [
            models.Index(fields=['year']),
        ]


class ActivityGroup(models.Model):
    """[已弃用 v3.57.0] 旧的「自建聚合分组」层。

    L1 语义订正为「归因（成长/关系/维持/谋生/流失）」后此层取消。
    表 `temporal_activity_group` 保留不删（历史数据零损失），代码侧不再读写。
    """

    name = models.CharField(max_length=50, unique=True, verbose_name='分组名(L1)')
    color = models.CharField(max_length=7, blank=True, null=True, verbose_name='主题色')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_system = models.BooleanField(default=False, verbose_name='系统预设')
    note = models.TextField(blank=True, null=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'temporal_activity_group'
        db_table_comment = '[已弃用 v3.57.0] 旧的自建聚合分组层：代码侧不再读写，表保留不删'
        verbose_name = '时间分组'
        verbose_name_plural = '时间分组'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class TaskMeta(models.Model):
    """三层分类映射：L3 task_name → L2 活动类型 / L1 归因

    注：`group` 字段为旧「聚合分组」遗留（已弃用），保留列不删，代码不再读写。
    """

    task_name = models.CharField(max_length=255, unique=True, verbose_name='任务名(L0)')
    group = models.ForeignKey(
        ActivityGroup, null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='所属L1分组',
    )
    activity_type = models.CharField(max_length=50, verbose_name='活动类型(L2)')
    default_attribution = models.CharField(
        max_length=10, blank=True, null=True,
        choices=ATTRIBUTION_CHOICES, verbose_name='默认归因(L3)',
    )
    is_system = models.BooleanField(default=False, verbose_name='系统预设')
    # 🔴 「成长计时」的**唯一依据**：勾了才计入每周状态的成长小时数。
    #    此前口径是隐式的「L2 活动类型 = 深度工作」，藏在 KPI 的 `source_config.where` 里 ——
    #    界面上看不见、也没法把别的分类拉进来。改成显式标记后：
    #      · 迁移 `0017` 已把当时 L2=深度工作 的任务名回填为 True（数字不变）；
    #      · 之后改 L2 **不再**自动改变成长计时（一把尺子，改分类不再暗改口径）。
    counts_growth = models.BooleanField(
        default=False, verbose_name='计入成长计时',
        help_text='勾选后，该任务名下的时长进入每周状态的「成长小时数」',
    )
    # 🔴 「今天的三条线」的**唯一依据**（v3.64.12 起）：标了角色才进对应那条线。
    #    空白 = 不参与；值域见 `constants.DAILY_ROLE_CHOICES`，阈值见 `DAILY_GUARD_LINES`。
    #    口径放在标记上而不写死任务名：否则改名后护栏会静默变成「未记录」，
    #    且看不出是改名导致的（症状与「成长计时」当年那条隐式口径一模一样）。
    #    ⚠️ v3.64.13 起只有「夜间睡眠 / 午睡」用这一列；「流失」直接读 L1 归因
    #       （玩游戏 / 刷短视频 / 看小说 本来就归流失），不需要再标一遍。
    daily_role = models.CharField(
        max_length=20, blank=True, default='', choices=DAILY_ROLE_CHOICES,
        verbose_name='日常护栏角色',
        help_text='标了才计入「今天的三条线」：夜间睡眠按醒来那一刻归属日期，午睡按开始时刻（流失不看这列）',
    )
    note = models.TextField(blank=True, null=True, verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'temporal_task_meta'
        db_table_comment = '活动类型映射：任务名 → 活动类型 / 归因；库里那行才是真源，代码常量只是种子'
        verbose_name = '活动类型映射'
        verbose_name_plural = '活动类型映射'
        # 显式写 name=：不再受 Django 自动命名规则变化影响（6.0 曾去掉升序 `+` 前缀位）。
        # group 字段虽已弃用（代码不再读写、列保留不删），但其索引是外键约束的刚需——
        # 在保留 group_id 列的前提下删掉也会被 InnoDB/Django 立即重建，故一并保留。
        indexes = [
            models.Index(fields=['activity_type'], name='temporal_ta_activit_b06509_idx'),
            models.Index(fields=['group'], name='temporal_ta_group_i_78a288_idx'),
        ]

    def __str__(self):
        return f'{self.task_name} → {self.activity_type}'


class TimerSession(models.Model):
    """实时计时会话（本表 managed，运行态落在这里）。

    🔴 为什么不把「正在计时」直接写进 `TemporalTask`：
       `TemporalTask` 是 `managed=False` 的外部表（`temporal_time_atracker_tasks_list`），
       ① 不能给它加列；② end_time / duration_hours 为空的半截记录会进统计口径。
       所以运行态单独存本表，**停止时才写一条真正的 `TemporalTask`**。

    🔴 `task_id` 用裸整数而不是 ForeignKey：
       目标表是外部表、主键类型由它的建表 DDL 决定，加 FK 约束有类型不匹配的风险。
       这里只是「记住这条会话写进了哪条记录」，不参与跨表聚合，裸 id 足够。
    """

    STATUS_CHOICES = [
        ('running', '计时中'),
        ('done', '已入账'),
        ('discarded', '已丢弃'),
    ]

    task_name = models.CharField(max_length=255, verbose_name='任务名称')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(blank=True, null=True, verbose_name='结束时间')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='running', verbose_name='状态',
    )
    task_id = models.IntegerField(blank=True, null=True, verbose_name='写入的时间记录ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'temporal_timer_session'
        db_table_comment = '实时计时会话：运行态在此，停止时才写入时间记录'
        verbose_name = '计时会话'
        verbose_name_plural = '计时会话'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='temporal_timer_status_idx'),
        ]

    def __str__(self):
        return f'{self.task_name} ({self.status})'
