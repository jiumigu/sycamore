"""展厅 · 四张 managed 表

## 展厅是什么

> 一个可被访客（潜在客户）走进去看的「策展空间」。

它**不是**仪表盘（给自己看）、**不是**简历（只有证据层）、
**不是**个人主页（只有一面）、**不是**全量数据（策展不是仓库）。

## 核心叙事：能力 → 案例 → 产品

一个品牌、两个馆：

- **能力馆（主）**：卖服务（自媒体 / AI 工作流搭建），证据层最重；
- **作品馆（辅）**：卖产品（钩织 / 刺绣），是「能力的活证据」。

信任逻辑一句话：**我自己在用，所以可信。** 能力馆说「我帮你搭」，
作品馆说「你看，我自己搭的就在这」——两个馆互相作证，而不是互相稀释。

## 核心边界：数据引用、叙事手写

> Sycamore 说数据，展厅说故事。数据从 Sycamore 里「选」（引用），
> 叙事在策展层「写」（手写）。

| 层 | 来源 | 引用 / 手写 |
|---|---|---|
| 品牌层 | 无 | 纯手写 |
| 能力馆 · 案例 | 一期手写，预留 `source_module` / `source_id` 二期引用 | 手写为主 |
| 能力馆 · 技能 | 无 | 纯手写 |
| 作品馆 · 作品 | **引用 `works.Work`（只选不另建清单）** | 引用 + 手写导语 |
"""
from django.db import models


class ShowroomProfile(models.Model):
    """展厅品牌层（单例，纯手写）。

    ⚠️ 单例只在**编辑**接口用 `get_solo()`（get_or_create）；
       预览是只读接口，用 `.first()` 兜底，绝不因读而落库
       （项目铁律：只读接口别 `get_or_create`）。
    """

    ip_name = models.CharField(max_length=50, default='', verbose_name='IP 名')
    tagline = models.CharField(max_length=100, default='', verbose_name='一句话定位')
    positioning = models.CharField(max_length=200, default='', verbose_name='定位（副标）')
    bio = models.TextField(default='', verbose_name='自我介绍')

    email = models.EmailField(blank=True, default='', verbose_name='邮箱')
    wechat = models.CharField(max_length=50, blank=True, default='', verbose_name='微信号')
    other_contact = models.TextField(blank=True, default='', verbose_name='其他联系方式')

    updated_at = models.DateTimeField(auto_now=True, verbose_name='改于')

    class Meta:
        db_table = 'showroom_profile'
        db_table_comment = '展厅品牌层：单例，IP / 定位 / 联系方式，纯手写'
        verbose_name = '展厅品牌'
        verbose_name_plural = '展厅品牌'

    def __str__(self):
        return self.ip_name or '展厅品牌'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ShowroomCase(models.Model):
    """能力馆 · 案例（手写为主，预留引用）。

    ⚠️ `source_module` / `source_id` 一期留空 —— 二期接入里程碑 / 汇总等
       真实事件时用；它们只是「从哪来」的引用，案例文案始终是策展者手写的叙事。
    """

    title = models.CharField(max_length=200, verbose_name='案例标题')
    client = models.CharField(max_length=100, blank=True, default='', verbose_name='客户 / 对象')
    time_label = models.CharField(max_length=50, blank=True, default='', verbose_name='时间（自由文本）')
    problem = models.TextField(default='', verbose_name='解决了什么问题')
    result = models.TextField(default='', verbose_name='成果')
    skill_tags = models.JSONField(default=list, verbose_name='用到的技能')
    # 展示媒体：[{type: 'image'|'video', url}] —— 图片/视频是案例的「证据」。
    # ⚠️ 放展厅侧而非 works：作品库自身一期不展示图，将来要展示再上提为 Work 字段。
    media = models.JSONField(default=list, verbose_name='展示媒体')

    source_module = models.CharField(max_length=50, blank=True, default='', verbose_name='来源模块')
    source_id = models.IntegerField(null=True, blank=True, verbose_name='来源 ID')

    is_visible = models.BooleanField(default=True, verbose_name='是否展示')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建於')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='改于')

    class Meta:
        db_table = 'showroom_case'
        db_table_comment = '能力馆案例：解决了什么问题、成果，手写为主，预留来源引用'
        ordering = ['sort_order', '-created_at']
        verbose_name = '案例'
        verbose_name_plural = '案例'

    def __str__(self):
        return self.title


class ShowroomSkill(models.Model):
    """能力馆 · 技能（纯手写）。"""

    name = models.CharField(max_length=50, verbose_name='技能名称')
    level = models.CharField(
        max_length=20, choices=[
            ('expert', '精通'),
            ('proficient', '熟练'),
            ('familiar', '了解'),
        ], default='proficient', verbose_name='熟练度',
    )
    is_visible = models.BooleanField(default=True, verbose_name='是否展示')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'showroom_skill'
        db_table_comment = '能力馆技能清单，纯手写'
        ordering = ['sort_order', 'name']
        verbose_name = '技能'
        verbose_name_plural = '技能'

    def __str__(self):
        return self.name


class ShowroomWork(models.Model):
    """作品馆 · 作品（引用作品库 + 手写一句导语）。

    只「选」不「另建清单」：作品库 `works.Work` 是「值得留」的唯一真源。
    `title_snapshot` 借鉴 `WorkCapture` 的快照哲学 —— 源作品被删后
    （`SET_NULL` 不悬空），仍能靠快照显示「当时策展的是哪件」。
    """

    work = models.ForeignKey(
        'works.Work', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='showroom_entries', verbose_name='作品',
    )
    title_snapshot = models.CharField(max_length=120, blank=True, default='', verbose_name='当时作品名快照')
    curator_note = models.TextField(blank=True, default='', verbose_name='策展导语（手写）')
    # 展示媒体：[{type: 'image'|'video', url}] —— 手作的可信度靠「看得见」。
    media = models.JSONField(default=list, verbose_name='展示媒体')

    is_visible = models.BooleanField(default=True, verbose_name='是否展示')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建於')

    class Meta:
        db_table = 'showroom_work'
        db_table_comment = '作品馆：从作品库 Work 里挑出的、能证明能力的那几件，引用 + 手写导语'
        ordering = ['sort_order', '-created_at']
        verbose_name = '馆藏作品'
        verbose_name_plural = '馆藏作品'

    def __str__(self):
        return self.title_snapshot or (self.work.name if self.work_id else '馆藏作品')
