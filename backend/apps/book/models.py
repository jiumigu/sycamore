from datetime import date

from django.db import models


class Book(models.Model):
    """书籍阅读记录

    🔴 `status` 只说「这本书在流程的哪一步」，**不说读得多细** ——
       读法归 `reading_depth`。v3.64.79 之前这两件事混在一个字段里：
       `精读 / 通读 / 消遣` 是读法，`计划阅读 / 在读 / 已完成 / 弃读` 是阶段，
       八项并排在一个下拉里，于是「在读」这个词同时指三种东西。

    🔴 状态值是**英文 key**（写库、跨 app 判断都用它），label 是给人看的中文。
       别的模块一律用下面这 6 个类常量，**不许再写中文字面量** ——
       v3.64.79 之前 `summary` 里那两处 `status='已完成'` 就是这么漏掉的，
       漏了不报错，只是那天的「读完的书」静默变成 0。
    """

    # ── 状态（6 个，一个维度：生命周期） ───────────────────────
    STATUS_TO_READ = 'to_read'        # 待读
    STATUS_READING = 'reading'        # 在读
    STATUS_REREADING = 'rereading'    # 在读二刷
    STATUS_FINISHED = 'finished'      # 已读完
    STATUS_SHELVED = 'shelved'        # 搁置（暂停但没弃，可恢复）
    STATUS_ABANDONED = 'abandoned'    # 弃读

    STATUS_CHOICES = [
        (STATUS_TO_READ, '待读'),
        (STATUS_READING, '在读'),
        (STATUS_REREADING, '在读二刷'),
        (STATUS_FINISHED, '已读完'),
        (STATUS_SHELVED, '搁置'),
        (STATUS_ABANDONED, '弃读'),
    ]

    # 「正在读」= 在读 + 二刷。二刷也是正在读，只数 `reading` 会让二刷的书
    # 在统计里凭空消失（两份 map、只改了一份，页面上下两块各自看着都合理）。
    STATUS_ACTIVE = (STATUS_READING, STATUS_REREADING)

    # 「可以选来读」= 待读 + 在读 + 二刷 + 搁置（v3.64.81）。
    # 🔴 已读完**不在**这里：一本书读完了就没有「接下来读这本」这回事，
    #    要二刷得先把状态改成「在读二刷」。弃读同理 —— 那是已经决定不读的书。
    # 🔴 搁置**在**这里：它的定义就是「暂停但没弃，能捡回来」，捡回来的动作
    #    正是「换书」；选中后会被升成「在读」（见 `ReadingFocusService.switch`）。
    # ⚠️ 这份元组是换书候选的**唯一口径**。v3.64.80 之前它压根不存在 ——
    #    弹窗拿的是整张书单按更新时间截 20 条，于是 93 本「已读完」全躺在
    #    「接下来读哪本」里，看着像可以再读一遍。
    STATUS_SELECTABLE = (STATUS_TO_READ, STATUS_READING, STATUS_REREADING, STATUS_SHELVED)

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
    created_at = models.DateField(default=date.today, verbose_name='创建日期')
    updated_at = models.DateField(auto_now=True, verbose_name='更新日期')
    tags = models.CharField(max_length=500, blank=True, null=True, verbose_name='标签')
    abandon_reason = models.TextField(blank=True, null=True, verbose_name='弃读原因')
    closedop = models.TextField(blank=True, null=True, verbose_name='读后感')
    openop = models.TextField(blank=True, null=True, verbose_name='打开书时的观点和期待')
    action_item = models.TextField(blank=True, default='', verbose_name='行动项',
        help_text='读完这本书后决定做的一件事')
    user_id = models.IntegerField(blank=True, null=True, verbose_name='用户ID（预留）')

    class Meta:
        db_table = 'book_read_list'
        db_table_comment = '书籍阅读记录：一张表承载待读 / 在读 / 读完 / 搁置 / 弃读；读法看 reading_depth；列名多为旧式命名（bid / btype / openop / closedop）'
        ordering = ['-readDate']
        verbose_name = '书籍阅读记录'
        verbose_name_plural = '书籍阅读记录'

    @property
    def is_finished(self):
        return self.status == self.STATUS_FINISHED

    @property
    def is_abandoned(self):
        return self.status == self.STATUS_ABANDONED

    def __str__(self):
        return f'{self.btitle} - {self.author}'


class ReadingFocus(models.Model):
    """当前在读的那一本：全库只有一行（pk=1）。

    🔴 这是「现在读哪本」的唯一真源。`Book.status` 说的是这本书走到哪一步
       （读法 / 已读 / 弃读），不是「现在读哪本」—— 两件事，两个字段，
       不互相推导、不自动同步。

    🔴 单行由**唯一写入口**保证（`ReadingFocusService.switch` 里
       `update_or_create(pk=1)`），不靠数据库约束：MySQL 没有条件唯一索引。
       测试里钉「连续换书两次，表里仍 1 行」。

    ⚠️ `book` 用 `SET_NULL`：书被删时指针自动失效、页面提示「去选一本」，
       而不是让删书操作直接 500。
    """

    book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name='当前这本',
    )
    started_on = models.DateField(null=True, blank=True, verbose_name='从哪天开始')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='换于')

    class Meta:
        db_table = 'book_reading_focus'
        db_table_comment = '当前在读指针：全库一行；换书必须给旧书结论（已完成 / 弃读 / 放回）'
        verbose_name = '当前在读'
        verbose_name_plural = '当前在读'

    def __str__(self):
        return f'当前在读：{self.book_id}'
