from django.core.exceptions import ValidationError
from django.db import models


class Goal(models.Model):
    """目标模型"""

    CATEGORY_CHOICES = [
        ('year', '年度目标'),
        ('quarter', '季度目标'),
        ('month', '月度目标'),
        ('long-term', '长期目标'),
    ]

    PRIORITY_CHOICES = [
        ('p0', 'P0 - 紧急重要'),
        ('p1', 'P1 - 重要'),
        ('p2', 'P2 - 一般'),
        ('p3', 'P3 - 低优先级'),
    ]

    STATUS_CHOICES = [
        ('planning', '计划中'),
        ('in-progress', '进行中'),
        ('paused', '已暂停'),
        ('completed', '已完成'),
        ('abandoned', '已放弃'),
        ('archived', '已归档'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='目标ID')
    title = models.CharField(max_length=255, verbose_name='目标标题')
    description = models.TextField(blank=True, null=True, verbose_name='目标描述')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name='目标类型')
    tags = models.JSONField(blank=True, null=True, verbose_name='目标标签')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='p2', verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning', verbose_name='状态')
    progress_percentage = models.IntegerField(default=0, editable=False, verbose_name='进度百分比')
    start_date = models.DateField(blank=True, null=True, verbose_name='开始日期')
    deadline = models.DateField(blank=True, null=True, verbose_name='截止日期')
    year = models.IntegerField(blank=True, null=True, verbose_name='年份')
    notes = models.TextField(blank=True, null=True, verbose_name='备注信息')

    # 决策记录
    decision_quality = models.IntegerField(blank=True, null=True, verbose_name='决策质量评分(1-10)')
    mental_models_used = models.CharField(max_length=500, blank=True, null=True, verbose_name='使用的思维模型')
    inversion_check = models.TextField(blank=True, null=True, verbose_name='逆向思考检查')
    first_principles = models.TextField(blank=True, null=True, verbose_name='第一性原理分析')
    circle_check = models.IntegerField(blank=True, null=True, verbose_name='是否在能力圈内')
    happiness_impact = models.IntegerField(blank=True, null=True, verbose_name='幸福影响评分')
    peace_impact = models.IntegerField(blank=True, null=True, verbose_name='内心平静影响评分')

    reward_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='每个里程碑的奖励额度')

    # 里程碑奖励功能
    enable_reward = models.BooleanField(default=False, verbose_name='是否启用里程碑奖励')
    default_reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='默认奖励金额')
    total_reward_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='本目标已发放奖励总额')

    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID（预留）')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'goals_goal'
        verbose_name = '目标'
        verbose_name_plural = '目标'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['year']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
            models.Index(fields=['deadline']),
        ]

    def __str__(self):
        return self.title


class Milestone(models.Model):
    """里程碑模型"""

    STATUS_CHOICES = [
        ('pending', '待开始'),
        ('in-progress', '进行中'),
        ('completed', '已完成'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='里程碑ID')
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='milestones', verbose_name='所属目标')
    title = models.CharField(max_length=255, verbose_name='里程碑标题')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    completed_note = models.TextField(blank=True, null=True, verbose_name='完成备注说明')
    self_review = models.TextField(blank=True, default='', verbose_name='自我批阅')
    description = models.TextField(blank=True, default='', verbose_name='详细描述')
    order_num = models.IntegerField(default=0, verbose_name='排序序号')
    target_date = models.DateField(blank=True, null=True, verbose_name='目标日期')
    target_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name='目标值')
    actual_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name='实际值')

    # 奖励相关
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='里程碑奖励金额')
    reward_synced = models.BooleanField(default=False, verbose_name='奖励是否已同步')
    reward_issued_at = models.DateTimeField(blank=True, null=True, verbose_name='奖励发放时间')
    reward_transaction_id = models.IntegerField(blank=True, null=True, verbose_name='关联的奖励流水ID')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'goals_milestone'
        verbose_name = '里程碑'
        verbose_name_plural = '里程碑'
        ordering = ['order_num', 'id']

    def __str__(self):
        return self.title


class Action(models.Model):
    """行为记录模型"""

    id = models.AutoField(primary_key=True, verbose_name='行为ID')
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='actions', verbose_name='所属目标')
    milestone = models.ForeignKey(Milestone, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions', verbose_name='关联里程碑')
    name = models.CharField(max_length=200, verbose_name='行为名称')
    note = models.TextField(blank=True, null=True, verbose_name='备注说明')
    action_date = models.DateField(null=True, blank=True, verbose_name='发生日期')
    completion_log = models.JSONField(blank=True, default=dict, verbose_name='打卡记录')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'goals_action'
        verbose_name = '行为记录'
        verbose_name_plural = '行为记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['goal', 'created_at']),
            models.Index(fields=['goal', 'milestone']),
        ]

    def clean(self):
        if self.milestone and self.milestone.goal_id != self.goal_id:
            raise ValidationError({'milestone': '里程碑必须属于同一个目标'})

    def save(self, *args, **kwargs):
        from datetime import date
        if not self.action_date:
            self.action_date = date.today()
        super().save(*args, **kwargs)


class GoalReview(models.Model):
    """目标回顾模型"""

    REVIEW_TYPES = [
        ('weekly', '周回顾'),
        ('monthly', '月回顾'),
        ('milestone', '里程碑完成时'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='回顾ID')
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='reviews', verbose_name='所属目标')
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES, default='weekly', verbose_name='回顾类型')
    review_date = models.DateField(verbose_name='回顾日期')
    score = models.IntegerField(blank=True, null=True, verbose_name='评分(1-10)')
    what_worked = models.TextField(blank=True, verbose_name='做得好的')
    what_blocked = models.TextField(blank=True, verbose_name='遇到的阻碍')
    next_adjustment = models.TextField(blank=True, verbose_name='下一步调整')
    content = models.TextField(blank=True, verbose_name='回顾内容')
    progress_note = models.TextField(blank=True, null=True, verbose_name='进度说明')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'goals_review'
        verbose_name = '目标回顾'
        verbose_name_plural = '目标回顾'
        ordering = ['-review_date']

    def __str__(self):
        return f'{self.goal.title} - {self.review_date}'


class OutputRecord(models.Model):
    """个人产出记录——用于统计良品率"""

    CATEGORY_CHOICES = [
        ('work', '工作'),
        ('writing', '写作'),
        ('social', '社交'),
        ('study', '学习'),
        ('health', '健康'),
        ('life', '生活'),
        ('other', '其他'),
    ]

    QUALITY_CHOICES = [
        ('good', '良品'),
        ('defective', '不良品'),
        ('waste', '废品'),
    ]

    DIFFICULTY_CHOICES = [(i, str(i)) for i in range(1, 6)]

    FAIL_TYPE_CHOICES = [
        ('cognitive', '认知盲区'),
        ('ability', '能力不足'),
        ('external', '外部因素'),
        ('luck', '运气'),
        ('careless', '粗心'),
        ('other', '其他'),
    ]

    id = models.AutoField(primary_key=True, verbose_name='记录ID')
    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    title = models.CharField(max_length=200, verbose_name='事项名称')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other', verbose_name='类别')
    expected_result = models.TextField(blank=True, verbose_name='预期结果')
    actual_result = models.TextField(blank=True, verbose_name='实际结果')
    quality = models.CharField(max_length=20, choices=QUALITY_CHOICES, verbose_name='质量判定')
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES, default=3, verbose_name='难度', help_text='1=轻车熟路, 5=完全未知')
    fail_reason = models.TextField(blank=True, verbose_name='失败原因（不良品/废品时填写）')
    fail_type = models.CharField(max_length=50, blank=True, choices=FAIL_TYPE_CHOICES, verbose_name='失败类型')
    lesson_learned = models.TextField(blank=True, verbose_name='经验教训')
    occurred_at = models.DateField(blank=True, null=True, verbose_name='发生日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'goals_output_record'
        verbose_name = '产出记录'
        verbose_name_plural = '产出记录'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['quality']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.title

