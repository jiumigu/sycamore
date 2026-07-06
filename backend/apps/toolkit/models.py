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


class DecisionLog(models.Model):
    """决策日志"""

    CATEGORY_CHOICES = [
        ('职业', '职业'), ('关系', '关系'), ('财务', '财务'),
        ('健康', '健康'), ('居住', '居住'), ('学习', '学习'),
        ('其他', '其他'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    title = models.CharField(max_length=200, verbose_name='决策标题')
    decision_date = models.DateField(verbose_name='决策日期')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='其他', verbose_name='分类')
    background = models.TextField(verbose_name='背景/情境')
    options = models.JSONField(default=list, verbose_name='选项列表', help_text='[{name, pros, cons}]')
    chosen = models.CharField(max_length=200, verbose_name='最终选择')
    reason = models.TextField(verbose_name='选择理由')
    expected_outcome = models.TextField(verbose_name='预期结果')
    fear_factor = models.IntegerField(default=5, verbose_name='恐惧指数', help_text='1-10')
    actual_outcome = models.TextField(blank=True, default='', verbose_name='实际结果（半年后回顾）')
    was_right = models.BooleanField(null=True, blank=True, verbose_name='决策是否正确')
    learned = models.TextField(blank=True, default='', verbose_name='学到的经验')
    bias_found = models.CharField(max_length=100, blank=True, default='', verbose_name='发现的偏误')
    review_date = models.DateField(null=True, blank=True, verbose_name='回顾日期')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_decision_log'
        ordering = ['-decision_date']
        verbose_name = '决策日志'

    def __str__(self):
        return f'{self.title} ({self.decision_date})'


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


class ReviewRecord(models.Model):
    """复盘记录"""

    REVIEW_TYPES = [
        ('daily', '每日复盘'),
        ('weekly', '周复盘'),
        ('monthly', '月复盘'),
        ('quarterly', '季度复盘'),
        ('life', '人生编舟'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPES, verbose_name='复盘类型')
    review_date = models.DateField(verbose_name='复盘日期')

    # 每日复盘
    daily_status = models.CharField(max_length=50, blank=True, default='', verbose_name='状态')
    daily_people = models.TextField(blank=True, default='', verbose_name='那些人那些事')
    johari_window = models.JSONField(default=dict, blank=True, verbose_name='约哈里窗')
    emotions = models.JSONField(default=dict, blank=True, verbose_name='情绪清单')

    # 周/月复盘
    completed = models.TextField(blank=True, default='', verbose_name='本周/月完成')
    plan_next = models.TextField(blank=True, default='', verbose_name='下周/月计划')
    reflection = models.TextField(blank=True, default='', verbose_name='反思总结')

    # 月复盘专属
    grai = models.JSONField(default=dict, blank=True, verbose_name='GRAI复盘')
    orid = models.JSONField(default=dict, blank=True, verbose_name='ORID复盘')

    # 季度复盘
    nourishing = models.TextField(blank=True, default='', verbose_name='滋养小事')
    draining = models.TextField(blank=True, default='', verbose_name='消耗黑洞')
    fears = models.TextField(blank=True, default='', verbose_name='害怕的事')
    worries = models.TextField(blank=True, default='', verbose_name='烦恼的事')
    envy_target = models.TextField(blank=True, default='', verbose_name='羡慕的对象')
    regret_at_80 = models.TextField(blank=True, default='', verbose_name='80岁遗憾')
    life_paths = models.TextField(blank=True, default='', verbose_name='5年路径推演')

    # 人生编舟
    life_line = models.TextField(blank=True, default='', verbose_name='生命线回顾')
    personal_goals = models.TextField(blank=True, default='', verbose_name='个人目标')
    time_plan = models.TextField(blank=True, default='', verbose_name='四象限规划')
    deep_reflection = models.TextField(blank=True, default='', verbose_name='深度复盘')

    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_review_record'
        ordering = ['-review_date', '-created_at']
        verbose_name = '复盘记录'
        indexes = [
            models.Index(fields=['review_type']),
            models.Index(fields=['review_date']),
        ]

    def __str__(self):
        return f'{self.get_review_type_display()} {self.review_date}'


class LanguageTraining(models.Model):
    """语言训练记录"""

    TRAIN_TYPE_CHOICES = [
        ('granularity', '词汇颗粒度'),
        ('describe', '场景描述'),
        ('material', '语言素材'),
        ('revision', '逼近修订'),
    ]

    user_id = models.IntegerField(default=1, verbose_name='用户ID')
    train_type = models.CharField(max_length=20, choices=TRAIN_TYPE_CHOICES, verbose_name='训练类型')
    train_date = models.DateField(verbose_name='训练日期')

    # 词汇颗粒度
    rough_word = models.CharField(max_length=50, blank=True, default='', verbose_name='粗糙词汇')
    refined_words = models.TextField(blank=True, default='', verbose_name='拆分后的词汇')

    # 场景描述
    summary = models.CharField(max_length=200, blank=True, default='', verbose_name='总结性描述')
    scene = models.TextField(blank=True, default='', verbose_name='场景还原')

    # 语言素材
    source = models.CharField(max_length=200, blank=True, default='', verbose_name='来源')
    quote_text = models.TextField(blank=True, default='', verbose_name='原句')
    why_good = models.TextField(blank=True, default='', verbose_name='为什么觉得好')

    # 逼近修订
    first_draft = models.TextField(blank=True, default='', verbose_name='第一版')
    revisions = models.JSONField(default=list, blank=True, verbose_name='修订过程')
    final_version = models.TextField(blank=True, default='', verbose_name='最终版')

    notes = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'toolkit_language_training'
        ordering = ['-train_date']
        verbose_name = '语言训练记录'
        indexes = [
            models.Index(fields=['train_type']),
            models.Index(fields=['train_date']),
        ]

    def __str__(self):
        return f'{self.get_train_type_display()} {self.train_date}'
