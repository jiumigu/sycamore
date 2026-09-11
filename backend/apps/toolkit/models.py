from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Quote(models.Model):
    """摘录馆"""

    LANGUAGE_CHOICES = [
        ('中文', '🇨🇳 中文'), ('英语', '🇬🇧 英语'), ('日语', '🇯🇵 日语'),
        ('德语', '🇩🇪 德语'), ('法语', '🇫🇷 法语'), ('韩语', '🇰🇷 韩语'),
        ('其他', '🌐 其他'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    content = models.TextField(verbose_name='内容')
    author = models.CharField(max_length=200, blank=True, default='', verbose_name='作者/出处')
    language = models.CharField(max_length=20, default='中文', choices=LANGUAGE_CHOICES, verbose_name='语言')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='分类')
    is_paragraph = models.BooleanField(default=False, verbose_name='是否段落')
    short_title = models.CharField(max_length=100, blank=True, default='', verbose_name='缩减标题')
    source = models.CharField(max_length=200, blank=True, default='', verbose_name='来源')
    tags = models.CharField(max_length=500, blank=True, default='', verbose_name='标签')
    is_favorite = models.BooleanField(default=False, verbose_name='收藏')
    review_count = models.IntegerField(default=0, verbose_name='回顾次数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_quote'
        ordering = ['-created_at']
        verbose_name = '摘录'

    def __str__(self):
        return self.content[:50]

    def save(self, *args, **kwargs):
        if self.is_paragraph and not self.short_title:
            self.short_title = self.content[:50] + ('...' if len(self.content) > 50 else '')
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        if self.is_paragraph and self.short_title:
            return self.short_title
        return self.content[:50]


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


class HealthSelfCheck(models.Model):
    """身体健康自查"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    check_date = models.DateField(verbose_name='检查日期')

    # 头部（4项）
    headache = models.CharField(max_length=20, default='无', verbose_name='头痛/偏头痛')
    dizzy = models.CharField(max_length=20, default='无', verbose_name='头晕/眩晕')
    hairloss = models.CharField(max_length=20, default='正常', verbose_name='脱发')
    memory = models.CharField(max_length=20, default='无变化', verbose_name='记忆力变化')

    # 五官（5项）
    vision = models.CharField(max_length=20, default='无', verbose_name='视力模糊/眼干')
    ear = models.CharField(max_length=20, default='无', verbose_name='耳鸣/听力')
    ulcer = models.CharField(max_length=20, default='无', verbose_name='口腔溃疡')
    gum = models.CharField(max_length=20, default='无', verbose_name='牙龈出血')
    allergy = models.CharField(max_length=20, default='无', verbose_name='鼻塞/过敏')

    # 皮肤（3项）
    spots = models.CharField(max_length=20, default='无', verbose_name='新发痣/斑')
    spots_location = models.CharField(max_length=100, blank=True, default='', verbose_name='痣/斑部位')
    rash = models.CharField(max_length=20, default='无', verbose_name='皮疹/瘙痒')
    wound_healing = models.CharField(max_length=20, default='正常', verbose_name='伤口愈合速度')

    # 四肢/肌肉（4项）
    joint = models.CharField(max_length=20, default='无', verbose_name='关节疼痛/僵硬')
    numbness = models.CharField(max_length=20, default='无', verbose_name='手脚发麻')
    muscle = models.CharField(max_length=20, default='无', verbose_name='肌肉酸痛')
    finger_flex = models.CharField(max_length=20, default='正常', verbose_name='手指灵活性')

    # 消化系统（5项）
    appetite = models.CharField(max_length=20, default='正常', verbose_name='食欲')
    bloating = models.CharField(max_length=20, default='无', verbose_name='腹胀/打嗝')
    abdominal_pain = models.CharField(max_length=20, default='无', verbose_name='腹痛')
    reflux = models.CharField(max_length=20, default='无', verbose_name='胃酸反流')
    stool_count = models.IntegerField(null=True, blank=True, verbose_name='大便次数')
    stool_type = models.CharField(max_length=20, default='正常', verbose_name='大便性状')

    # 泌尿系统（2项）
    urination_pain = models.CharField(max_length=20, default='无', verbose_name='尿频/尿急/尿痛')
    nocturia = models.IntegerField(null=True, blank=True, verbose_name='夜尿次数')

    # 睡眠（4项）
    sleep_latency = models.IntegerField(null=True, blank=True, verbose_name='入睡时间(分钟)')
    awakenings = models.IntegerField(null=True, blank=True, verbose_name='夜间醒来次数')
    morning_energy = models.CharField(max_length=20, default='恢复感好', verbose_name='晨起精力')
    snoring = models.CharField(max_length=20, default='无', verbose_name='打鼾')

    # 精力/情绪（4项）
    fatigue = models.CharField(max_length=20, default='无', verbose_name='疲劳感')
    mood = models.CharField(max_length=20, default='偶尔', verbose_name='情绪低落/焦虑')
    afternoon_fatigue = models.CharField(max_length=20, default='偶尔', verbose_name='午后犯困')
    interest_change = models.CharField(max_length=20, default='正常', verbose_name='兴趣变化')

    # 评分和汇总
    health_score = models.IntegerField(default=0, verbose_name='健康分')
    last_score = models.IntegerField(null=True, blank=True, verbose_name='上次分数')
    score_change = models.IntegerField(null=True, blank=True, verbose_name='分数变化')
    alert_items = models.TextField(blank=True, default='', verbose_name='异常项汇总')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_health_self_check'
        ordering = ['-check_date']
        verbose_name = '身体健康自查'

    def __str__(self):
        return f'{self.check_date} 健康分:{self.health_score}'


class FreeSpendingCalculator(models.Model):
    """自由支配额度计算器"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    liquid_assets = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='可支配流动资产(元)')
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='年稳定收入(元)')
    debt = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='固定债务(元)')
    work_years = models.IntegerField(default=20, verbose_name='预计工作年限')
    free_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='计算结果(元/次)')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_free_spending'
        ordering = ['-created_at']
        verbose_name = '自由支配额度计算'

    def __str__(self):
        return f'¥{self.free_amount} ({self.created_at})'


class FixedExpense(models.Model):
    """固定开销计算记录"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=200, verbose_name='记录名称')
    items = models.JSONField(default=list, verbose_name='开销项目列表', help_text='[{name, amount, period, icon}]，period 支持 daily/monthly/yearly')
    total_monthly = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='月固定开销')
    total_daily = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='日均固定开销')
    total_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='年固定开销')
    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_fixed_expense'
        ordering = ['-created_at']
        verbose_name = '固定开销计算'

    def __str__(self):
        return f'{self.name or "固定开销"} ¥{self.total_monthly}'


class HourlyWageRecord(models.Model):
    """时薪计算记录"""

    CALC_MODE_CHOICES = [
        ('formal', '🏢 正式职业'),
        ('freelance', '🧑‍💻 自由职业'),
    ]
    FREELANCE_TIME_MODE_CHOICES = [
        ('fixed', '固定时长'),
        ('flexible', '弹性工时'),
    ]

    user_id = models.IntegerField(default=1)
    name = models.CharField(max_length=200, blank=True, default='', verbose_name='记录名称')

    # 计算模式
    calc_mode = models.CharField(
        max_length=20, default='formal', choices=CALC_MODE_CHOICES, verbose_name='计算模式',
    )

    # 正式职业字段
    rest_type = models.CharField(max_length=20, default='双休', verbose_name='休息类型', choices=[
        ('双休', '双休'), ('单休', '单休'), ('大小周', '大小周'), ('不休', '不休'),
    ])
    work_start = models.CharField(max_length=5, default='09:00', verbose_name='上班时间')
    work_end = models.CharField(max_length=5, default='18:00', verbose_name='下班时间')
    lunch_break = models.IntegerField(default=60, verbose_name='午休时长(分钟)')

    # 自由职业字段
    freelance_time_mode = models.CharField(
        max_length=10, default='fixed', choices=FREELANCE_TIME_MODE_CHOICES,
        verbose_name='工时模式',
    )
    freelance_days = models.IntegerField(null=True, blank=True, verbose_name='月工作天数')
    freelance_hours_per_day = models.DecimalField(
        null=True, blank=True, max_digits=3, decimal_places=1, verbose_name='日均工作时长',
    )
    weekly_hours = models.JSONField(default=list, verbose_name='每周各天工作时长')
    freelance_weeks = models.IntegerField(default=4, verbose_name='每月周数')

    # 通用字段
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='月薪(元)')

    # 额外收入来源（工资之外的收入）
    extra_incomes = models.JSONField(default=list, verbose_name='额外收入来源', help_text='[{"name":"公众号","amount":300,"period":"monthly"}]')

    # 通勤
    commute_minutes = models.IntegerField(default=0, verbose_name='单程通勤(分钟)')

    # 计算结果
    work_days_per_month = models.DecimalField(max_digits=5, decimal_places=1, verbose_name='月工作天数')
    work_hours_per_day = models.DecimalField(max_digits=4, decimal_places=1, verbose_name='日工作小时')
    total_hours_per_month = models.DecimalField(max_digits=6, decimal_places=1, verbose_name='月总投入小时')
    hourly_wage = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='时薪(元/时)')

    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'toolkit_hourly_wage'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name or "时薪计算"} ¥{self.hourly_wage}/h'


class ElectricityRecord(models.Model):
    """用电记录"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    record_date = models.DateField(verbose_name='记录日期')
    meter_reading = models.DecimalField(max_digits=10, decimal_places=1, verbose_name='电表读数(度)')

    # 计算结果
    interval_usage = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=1, verbose_name='间隔用电量(度)')
    interval_days = models.IntegerField(null=True, blank=True, verbose_name='间隔天数')
    daily_avg = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=2, verbose_name='日均用电量(度/天)')
    month_usage = models.DecimalField(null=True, blank=True, max_digits=10, decimal_places=1, verbose_name='本月累计用电量(度)')

    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_electricity_record'
        ordering = ['-record_date']
        verbose_name = '用电记录'

    def __str__(self):
        return f'{self.record_date} 读数 {self.meter_reading}度'


class DecisionTracker(models.Model):
    """决策追踪器——决策前的长期观察（倾向/理由持续采样，到期汇总）"""

    STATUS_CHOICES = [
        ('观察中', '观察中'),
        ('已到期', '已到期'),
        ('已决策', '已决策'),
        ('已归档', '已归档'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    topic = models.CharField(max_length=200, verbose_name='决策主题')
    background = models.TextField(blank=True, default='', verbose_name='决策背景')
    start_date = models.DateField(verbose_name='观察开始日期')
    end_date = models.DateField(verbose_name='观察结束日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='观察中', verbose_name='状态')
    final_decision = models.CharField(max_length=50, blank=True, default='', verbose_name='最终决定')
    decision_date = models.DateField(null=True, blank=True, verbose_name='决定日期')
    review_note = models.TextField(blank=True, default='', verbose_name='事后回看（决策后 30 天补填）')
    lean_options = models.JSONField(
        null=True, blank=True,
        verbose_name='自定义倾向选项',
        help_text='字符串数组（2–6 项），如 ["想现在买","再等等","不买"]；留空用默认三项（想继续/不想继续/不确定）',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolkit_decision_tracker'
        ordering = ['-created_at']
        verbose_name = '决策追踪'

    def __str__(self):
        return f'{self.topic}（{self.status}）'

    @property
    def is_custom_lean(self) -> bool:
        return bool(self.lean_options)

    def tendency_options(self) -> list[tuple[str, str]]:
        """本追踪可用的倾向选项 [(key, label)]——自定义选项 key=label（记录直接存文字）"""
        if self.lean_options:
            return [(str(s), str(s)) for s in self.lean_options]
        return [('continue', '想继续'), ('quit', '不想继续'), ('uncertain', '不确定')]


class DecisionRecord(models.Model):
    """决策日常记录——单次倾向采样（倾向选项由所属追踪的 lean_options 决定）"""

    INTENSITY_CHOICES = [
        (1, '很弱'),
        (2, '弱'),
        (3, '中'),
        (4, '强'),
        (5, '很强'),
    ]

    tracker = models.ForeignKey(
        DecisionTracker, on_delete=models.CASCADE, related_name='records', verbose_name='所属决策',
    )
    record_date = models.DateField(verbose_name='记录日期')
    tendency = models.CharField(
        max_length=50,
        verbose_name='倾向',
        help_text='默认追踪存 continue/quit/uncertain；自定义倾向选项的追踪直接存选项文字',
    )
    reason = models.TextField(blank=True, default='', verbose_name='具体理由')
    intensity = models.PositiveSmallIntegerField(
        default=3,
        choices=INTENSITY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='情绪强度',
        help_text='1–5，数值越大越强烈（旧版「低/中/高」已分别映射为 2/3/4）',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_decision_record'
        ordering = ['-record_date', '-id']
        verbose_name = '决策记录'
        indexes = [
            models.Index(fields=['tracker', 'record_date']),
        ]

    def __str__(self):
        return f'{self.record_date} {self.get_tendency_display()}'


class AskScene(models.Model):
    """AI 问答库·业务场景容器——区分不同业务场景（工作/备考/写作…），场景下聚合主题与多轮对话"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    name = models.CharField(max_length=100, unique=True, verbose_name='场景名称')
    description = models.TextField(blank=True, default='', verbose_name='场景说明')
    sort = models.IntegerField(default=0, verbose_name='排序（小在前）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolkit_ask_scene'
        ordering = ['sort', 'id']
        verbose_name = 'AI 问答场景'

    def __str__(self):
        return self.name


class AskTopic(models.Model):
    """AI 问答库·主题——聚合同一问题（多 AI / 多会话 / 多次追问）的全部回答"""

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    scene = models.ForeignKey(
        AskScene, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='topics', verbose_name='所属业务场景',
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name='主题标题')
    question = models.TextField(verbose_name='完整提问（prompt 原文）')
    background = models.TextField(blank=True, default='', verbose_name='提问背景')
    tags = models.JSONField(default=list, blank=True, verbose_name='标签列表（来自系统预设 ask_tags）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'toolkit_ask_topic'
        ordering = ['-created_at']
        verbose_name = 'AI 问答主题'

    def __str__(self):
        return self.title or self.question[:30]


class AskAnswer(models.Model):
    """AI 问答库·回答——某一 AI 在某一对话会话中的一次回答；可被追问形成多轮链"""

    VERDICT_CHOICES = [
        ('采纳', '采纳'),
        ('备用', '备用'),
        ('不采用', '不采用'),
    ]

    topic = models.ForeignKey(
        AskTopic, on_delete=models.CASCADE, related_name='answers', verbose_name='所属主题',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='followups', verbose_name='追问自哪条回答（首轮为空）',
    )
    question = models.TextField(blank=True, default='', verbose_name='本轮提问（追问文本；首轮留空沿用主题 question）')
    ai = models.CharField(max_length=50, verbose_name='回答的 AI 对象')
    session = models.CharField(max_length=100, blank=True, default='', verbose_name='对话会话背景')
    answer = models.TextField(verbose_name='回答全文')
    asked_at = models.DateTimeField(verbose_name='提问时间')
    verdict = models.CharField(max_length=10, blank=True, default='', choices=VERDICT_CHOICES, verbose_name='采纳标记')
    note = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_ask_answer'
        ordering = ['-asked_at', '-id']
        verbose_name = 'AI 回答记录'
        indexes = [
            models.Index(fields=['topic', 'asked_at']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f'{self.ai}@{self.asked_at:%Y-%m-%d}'
