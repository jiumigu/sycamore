"""实时计时（Timer）—— 手工补录之外的另一个写入入口。

设计要点（每条都对应一个踩过的坑）：

1. 🔴 **绝不 `TemporalTask.objects.create(...)`**。
   时间记录的派生字段（`duration_hours` / `year` / `mon` / `day` / `week` / `quarter`）
   唯一实现是 `TemporalTaskSerializer.validate` → `build_time_fields`；
   新任务名的 `TaskMeta` 建档唯一实现是 `_ensure_task_meta`。
   绕过 serializer 就会得到「记录写进去了、但统计里漏了它」的行 —— 全程不报错。

2. 🔴 **`import_batch` 在 serializer 里是 `read_only`**（防前端篡改来源）。
   所以来源标记在 `serializer.save()` **之后**补写，不是放进 payload —— 放进去会被静默忽略。

3. 🔴 **忘记停止的兜底**：点新任务会自动收掉上一个。如果上一个跑了超过
   `LONG_SECONDS`（4 小时），**不自动入账**，只把会话标成 `discarded` 并回一个提示。
   宁可少一条（用户可手工补录），也不静默写入一条 24 小时脏数据 ——
   它会进月度趋势、贡献图、平衡轮、自运转的时间分配分母。

4. 🔴 **太短的会话不入账但要说出来**：`< MIN_SECONDS`（30 秒）返回 `too_short`，
   前端必须提示「太短，没有记录」。假装保存成功 = 静默失败。

5. 🔴 **已流逝时长由后端算**（`elapsed_of`）：前端只用它当锚点。
"""

from django.utils import timezone

from .models import TemporalTask, TimerSession
from .serializers import TemporalTaskSerializer
from .services import _ensure_task_meta

# 太短不入账：避免误触产生一堆 3 秒记录
MIN_SECONDS = 30
# 超过这个时长（4 小时）必须用户确认才入账
LONG_SECONDS = 4 * 3600
# 来源标记：区分「实时计时」与 CSV 导入 / 手工补录
IMPORT_BATCH = 'timer'


class TimerError(Exception):
    """计时业务错误（带机器可读 code，前端按 code 分支，不解析文案）。"""

    code = 'timer_error'
    status_code = 400

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra


class TimerInvalid(TimerError):
    code = 'invalid'


class TimerNotFound(TimerError):
    code = 'not_found'
    status_code = 404


class TimerTooLong(TimerError):
    """会话超过 4 小时且未确认 —— 由前端弹「这条要记多久」。"""

    code = 'too_long'
    status_code = 409

    def __init__(self, elapsed_seconds: int):
        super().__init__(
            '这条计时已超过 4 小时，请确认是否入账',
            elapsed_seconds=elapsed_seconds,
            long_seconds=LONG_SECONDS,
        )


def elapsed_of(session: TimerSession | None, now=None) -> int:
    """会话已流逝秒数（running 时算到此刻，已结束的用 end_time）。"""
    if session is None:
        return 0
    end = session.end_time or (now or timezone.now())
    return max(0, int((end - session.start_time).total_seconds()))


def get_running() -> TimerSession | None:
    """当前运行中的会话。库是唯一真源 —— 刷新页面/换设备都靠它。"""
    return TimerSession.objects.filter(status='running').order_by('-start_time').first()


def start(task_name: str) -> tuple[TimerSession, dict | None]:
    """开始计时。返回 (新会话, 上一个会话的收尾结果或 None)。

    上一个会话的收尾走同一套规则（见 `_finalize`），只是 `reason='auto'`：
    超 4 小时的一律不入账。
    """
    name = (task_name or '').strip()
    if not name:
        raise TimerInvalid('请填写任务名称')

    now = timezone.now()
    prev_info = None
    prev = get_running()
    if prev is not None:
        prev_info = _finalize(prev, now, notes=prev.notes, reason='auto')

    session = TimerSession.objects.create(
        task_name=name[:255],
        start_time=now,
        status='running',
    )
    return session, prev_info


def stop(session_id: int, notes: str = '', allow_long: bool = False) -> tuple[TimerSession, dict]:
    """停止并（按规则）入账。已结束的会话原样返回，不重复写记录。"""
    session = TimerSession.objects.filter(id=session_id).first()
    if session is None:
        raise TimerNotFound('计时会话不存在')

    if session.status != 'running':
        return session, {
            'outcome': 'already_closed',
            'status': session.status,
            'task_id': session.task_id,
            'elapsed_seconds': elapsed_of(session),
        }

    now = timezone.now()
    elapsed = elapsed_of(session, now)
    if elapsed > LONG_SECONDS and not allow_long:
        raise TimerTooLong(elapsed)

    return session, _finalize(session, now, notes=notes, reason='manual')


def discard(session_id: int) -> tuple[TimerSession, dict]:
    """丢弃：结束会话但不写时间记录。"""
    session = TimerSession.objects.filter(id=session_id).first()
    if session is None:
        raise TimerNotFound('计时会话不存在')

    if session.status != 'running':
        return session, {
            'outcome': 'already_closed',
            'status': session.status,
            'task_id': session.task_id,
            'elapsed_seconds': elapsed_of(session),
        }

    now = timezone.now()
    elapsed = elapsed_of(session, now)
    session.end_time = now
    session.status = 'discarded'
    session.save(update_fields=['end_time', 'status', 'updated_at'])
    return session, {'outcome': 'discarded', 'elapsed_seconds': elapsed}


def _finalize(
    session: TimerSession, now, notes: str, reason: str,
) -> dict:
    """收掉一个 running 会话：按规则决定「入账 / 太短丢弃 / 超长挂起丢弃」。

    reason:
      - `manual`：用户点停止（超长已在 stop() 里拦过）
      - `auto`：用户点了新任务，自动收尾 —— **超长一律不入账**
    """
    elapsed = elapsed_of(session, now)
    session.end_time = now
    session.notes = notes or ''

    if elapsed < MIN_SECONDS:
        session.status = 'discarded'
        session.save(update_fields=['end_time', 'notes', 'status', 'updated_at'])
        return {
            'outcome': 'too_short',
            'task_name': session.task_name,
            'elapsed_seconds': elapsed,
            'min_seconds': MIN_SECONDS,
        }

    # 自动收尾 + 超长 ⇒ 不入账。这条记录极可能是一夜没停的误操作，
    # 写进去会让当天的时长统计整体失真。
    if reason == 'auto' and elapsed > LONG_SECONDS:
        session.status = 'discarded'
        session.save(update_fields=['end_time', 'notes', 'status', 'updated_at'])
        return {
            'outcome': 'too_long_dropped',
            'task_name': session.task_name,
            'elapsed_seconds': elapsed,
            'long_seconds': LONG_SECONDS,
        }

    task = _write_task(session, notes)
    session.status = 'done'
    session.task_id = task.id
    session.save(update_fields=['end_time', 'notes', 'status', 'task_id', 'updated_at'])
    return {
        'outcome': 'saved',
        'task_name': session.task_name,
        'task_id': task.id,
        'elapsed_seconds': elapsed,
        'duration_hours': task.duration_hours,
    }


def _write_task(session: TimerSession, notes: str) -> TemporalTask:
    """把会话写成一条时间记录 —— 唯一正确路径。"""
    assert session.end_time is not None, '会话未结束不能入账'

    # 传本地时间串（与手工新增、CSV 导入同一表示）：DRF 按 settings.TIME_ZONE
    # 解释成 aware datetime，跨零点不会错日。
    payload = {
        'task_name': session.task_name,
        'start_time': timezone.localtime(session.start_time).strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': timezone.localtime(session.end_time).strftime('%Y-%m-%d %H:%M:%S'),
        'notes': notes or '',
    }
    serializer = TemporalTaskSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    task = serializer.save()

    # `import_batch` 是 serializer 的 read_only 字段（防前端伪造来源），
    # 放进 payload 会被静默忽略 —— 必须在保存之后补写。
    task.import_batch = IMPORT_BATCH
    task.save(update_fields=['import_batch'])

    # 新任务名要进 TaskMeta，否则分类台账 / 映射编辑器里看不到它
    _ensure_task_meta([task.task_name])
    return task
