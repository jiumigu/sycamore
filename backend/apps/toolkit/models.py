from django.db import models


class CityCoordinate(models.Model):
    """中国城市经纬度坐标"""
    name = models.CharField(max_length=100, verbose_name='城市名称')
    full_name = models.CharField(max_length=200, blank=True, default='', verbose_name='全称')
    province = models.CharField(max_length=50, blank=True, default='', verbose_name='所属省份')
    lng = models.FloatField(verbose_name='经度')
    lat = models.FloatField(verbose_name='纬度')
    city_type = models.CharField(max_length=20, default='地级市', verbose_name='类型')
    pinyin = models.CharField(max_length=100, blank=True, default='', verbose_name='拼音')

    class Meta:
        db_table = 'toolkit_city_coordinate'
        ordering = ['province', 'name']
        verbose_name = '城市坐标'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['province']),
        ]

    def __str__(self):
        return f'{self.name} ({self.province})'


class ToolkitDefinition(models.Model):
    tool_key = models.CharField(max_length=100, unique=True, verbose_name='工具标识')
    name = models.CharField(max_length=100, verbose_name='工具名称')
    description = models.TextField(blank=True, default='', verbose_name='工具描述')
    icon = models.CharField(max_length=50, default='🔧', verbose_name='图标')
    category = models.CharField(
        max_length=50, default='other', verbose_name='分类',
        choices=[
            ('image', '图片处理'), ('text', '文本处理'),
            ('file', '文件转换'), ('convert', '格式转换'),
            ('other', '其他'),
        ],
    )
    input_schema = models.JSONField(verbose_name='输入参数定义')
    output_type = models.CharField(
        max_length=50, default='file', verbose_name='输出类型',
        choices=[('file', '文件'), ('text', '文本'), ('json', 'JSON')],
    )
    is_async = models.BooleanField(default=True, verbose_name='是否异步')
    timeout_seconds = models.IntegerField(default=300, verbose_name='超时时间')
    is_enabled = models.BooleanField(default=True, verbose_name='是否启用')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_definition'
        ordering = ['category', 'id']
        verbose_name = '工具定义'
        managed = False

    def __str__(self):
        return f'{self.icon} {self.name}'


class ToolkitExecution(models.Model):
    tool = models.ForeignKey(
        ToolkitDefinition, on_delete=models.CASCADE,
        db_column='tool_id', verbose_name='工具',
    )
    task_id = models.CharField(max_length=100, blank=True, default='', verbose_name='任务ID')
    input_params = models.JSONField(verbose_name='输入参数')
    output_result = models.TextField(blank=True, default='', verbose_name='输出结果')
    output_file = models.CharField(max_length=500, blank=True, default='', verbose_name='输出文件路径')
    status = models.CharField(
        max_length=20, default='pending', verbose_name='状态',
        choices=[
            ('pending', '等待中'), ('running', '执行中'),
            ('success', '成功'), ('failed', '失败'),
            ('cancelled', '已取消'),
        ],
    )
    progress = models.IntegerField(default=0, verbose_name='进度百分比')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    execution_time_ms = models.IntegerField(blank=True, null=True, verbose_name='执行耗时')
    user_id = models.IntegerField(verbose_name='用户ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='完成时间')

    class Meta:
        db_table = 'toolkit_execution'
        ordering = ['-created_at']
        verbose_name = '工具执行记录'
        managed = False

    def __str__(self):
        return f'{self.tool.name} #{self.id} [{self.status}]'

    def update_progress(self, value):
        self.progress = value
        self.save(update_fields=['progress'])


class TravelRoutePreset(models.Model):
    """旅行路线预设"""
    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    name = models.CharField(max_length=200, verbose_name='路线名称')
    origin = models.CharField(max_length=100, verbose_name='出发地')
    destinations = models.JSONField(default=list, verbose_name='目的地列表')
    description = models.TextField(blank=True, default='', verbose_name='路线描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolkit_travel_route_preset'
        ordering = ['-created_at']
        verbose_name = '旅行路线预设'

    def __str__(self):
        return self.name


class EnvironmentAudit(models.Model):
    """环境校准记录"""
    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    environment_name = models.CharField(max_length=200, verbose_name='环境名称')
    audit_date = models.DateField(verbose_name='校准日期')

    # 六条特征评分（1-5分）
    allow_learning = models.IntegerField(default=0, verbose_name='允许说不知道')
    system_valued = models.IntegerField(default=0, verbose_name='系统能力被珍视')
    signal_over_noise = models.IntegerField(default=0, verbose_name='信号大于噪音')
    body_heard = models.IntegerField(default=0, verbose_name='身体能被听见')
    people_share = models.IntegerField(default=0, verbose_name='高手愿意分享')
    output_echoes = models.IntegerField(default=0, verbose_name='输出有回路')

    total_score = models.IntegerField(default=0, verbose_name='总分')
    verdict = models.CharField(max_length=20, verbose_name='判定')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_environment_audit'
        ordering = ['-audit_date']
        verbose_name = '环境校准记录'

    def __str__(self):
        return f'{self.environment_name} ({self.total_score}/30)'


class CareerEnergyAudit(models.Model):
    """职业能量审计"""
    user_id = models.IntegerField(default=1, verbose_name='用户ID（预留）')
    audit_date = models.DateField(verbose_name='审计日期')

    # 工作内容本身（7项）-5~+5
    task_clarity = models.IntegerField(default=0, verbose_name='任务清晰度', help_text='-5=每天等人给活, +5=知道自己要做什么')
    skill_match = models.IntegerField(default=0, verbose_name='技能匹配度', help_text='-5=总被说半吊子, +5=在能力范围内')
    autonomy = models.IntegerField(default=0, verbose_name='自主决策权', help_text='-5=每个细节要请示, +5=能自己决定')
    achievement = models.IntegerField(default=0, verbose_name='成就感', help_text='-5=做完也没感觉, +5=完成一件事的感觉')
    learning = models.IntegerField(default=0, verbose_name='学习机会', help_text='-5=重复劳动, +5=能学到新东西')
    workload = models.IntegerField(default=0, verbose_name='工作量合理性', help_text='-5=天天加班, +5=工作时间内完成')
    visibility = models.IntegerField(default=0, verbose_name='结果可见性', help_text='-5=不知道有什么用, +5=能看到产出')

    # 环境与人（8项）-5~+5
    communication = models.IntegerField(default=0, verbose_name='沟通效率', help_text='-5=反复解释被误解, +5=一句话说清楚')
    transparency = models.IntegerField(default=0, verbose_name='信息透明度', help_text='-5=突然被告知, +5=变更有通知')
    respect = models.IntegerField(default=0, verbose_name='被尊重程度', help_text='-5=被敷衍啧唉, +5=意见被认真对待')
    feedback_quality = models.IntegerField(default=0, verbose_name='反馈质量', help_text='-5=你是不是不懂, +5=指向具体问题')
    process_smooth = models.IntegerField(default=0, verbose_name='流程顺畅度', help_text='-5=处处受阻, +5=需求不被卡')
    commute = models.IntegerField(default=0, verbose_name='通勤体验', help_text='-5=消耗巨大, +5=轻松到达')
    physical_env = models.IntegerField(default=0, verbose_name='物理环境', help_text='-5=不舒适, +5=舒适')
    colleague_relation = models.IntegerField(default=0, verbose_name='同事关系', help_text='-5=需要防备, +5=相处融洽')

    # 成长与未来（5项）-5~+5
    skill_growth = models.IntegerField(default=0, verbose_name='技能成长', help_text='-5=原地踏步, +5=在提升')
    vision_expand = models.IntegerField(default=0, verbose_name='视野拓展', help_text='-5=信息茧房, +5=接触新思维')
    resume_value = models.IntegerField(default=0, verbose_name='履历增值', help_text='-5=纯粹耗时间, +5=对未来有帮助')
    income_satisfy = models.IntegerField(default=0, verbose_name='收入满意度', help_text='-5=觉得不值, +5=匹配付出')
    direction = models.IntegerField(default=0, verbose_name='方向感', help_text='-5=迷茫, +5=知道往哪走')

    # 身体与情绪（6项）
    morning_feeling = models.IntegerField(default=3, verbose_name='早起感受', help_text='1=期待, 5=恐惧')
    sunday_anxiety = models.IntegerField(default=3, verbose_name='周日焦虑', help_text='1=完全放松, 5=极度焦虑')
    after_work_state = models.IntegerField(default=3, verbose_name='下班后状态', help_text='1=还有精力, 5=瘫倒不想动')
    sleep_quality = models.IntegerField(default=3, verbose_name='睡眠质量', help_text='1=倒头就睡, 5=失眠早醒')
    body_signals = models.CharField(max_length=200, blank=True, default='', verbose_name='身体信号')
    emotion_stability = models.IntegerField(default=3, verbose_name='情绪波动', help_text='1=情绪稳定, 5=经常失控')

    # 综合
    total_score = models.IntegerField(default=0, verbose_name='总分', help_text='范围-130~+130')
    work_score = models.IntegerField(default=0, verbose_name='工作内容得分')
    env_score = models.IntegerField(default=0, verbose_name='环境与人得分')
    growth_score = models.IntegerField(default=0, verbose_name='成长与未来得分')
    body_score = models.IntegerField(default=0, verbose_name='身体与情绪得分')
    decision = models.CharField(max_length=20, default='待观察', verbose_name='判定')
    advice = models.TextField(blank=True, default='', verbose_name='建议')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    next_review_date = models.DateField(null=True, blank=True, verbose_name='下次审计日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_career_energy_audit'
        ordering = ['-audit_date']
        verbose_name = '职业能量审计记录'

    def __str__(self):
        return f'职业能量 {self.audit_date} ({self.total_score}分)'
