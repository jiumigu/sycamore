/**
 * 「这个页面在跑旧代码」—— 自证（唯一实现）
 *
 * 🔴 为什么需要它（2026-10-16 现场）：
 *    dev server 重启**不会**让已经打开的标签页换代码。若热更新的 WebSocket
 *    恰好断了（代理工具、休眠唤醒、长时间挂着的标签页都会），标签页既不重载、
 *    也拿不到新模块 ⇒ **静默停在旧版本**。界面看不出任何异常、控制台一片干净、
 *    用户重试多少次都一样 —— 于是「已修好的 bug」会以「还是不行」的样子回来。
 *    项目历史里同类症状（§97、§104）已经出现过三次，**每次都无法从界面分辨**。
 *
 * 🔴 为什么**不走**热更新通道：探针的职责就是覆盖「WS 已经断了」这个场景。
 *    若它自己依赖 WS，等于拿坏掉的尺子去量坏掉的尺子。
 *    所以这里走**普通 HTTP**：`/build_id.json` + `no-store`。
 *
 * ── 三条必须守住的判据 ──
 *
 * 1. **取不到 ≠ 有新版本。** 请求失败 / 非 2xx / body 里没有 buildId，一律
 *    **不提示**。把「不知道」说成「有新版本」，会让用户为了一个假警报丢掉
 *    正在填的表单 —— 比漏报更糟。这条与「裸 catch 把『取不到』说成『没有』」
 *    是**镜像错误**，同属静默失败。
 *
 * 2. **比的是「页面加载时」的 ID，不是「上一次探测」的 ID。**
 *    `localId` 是编译期注入的常量，随这个页面活一辈子；只有远端变了才提示，
 *    否则横幅在第一轮之后就永远不会再出现。
 *
 * 3. **横幅必须给出口。** 「立即刷新」是正解；「稍后」让用户先把手上的事做完。
 *    —— 只给入口不给出口（或反过来）都会把人卡住（同项目判据：出口控件不得关闭自己）。
 */

/** 与 `vite.config.ts` 的 `buildIdPlugin` 共用同一条路径：dev 由中间件现给、build 由产物带上 */
const BUILD_ID_PATH = '/build_id.json'

/** 轮询间隔。页面重新可见时会**立刻**补一次，所以这个值只影响「一直开着不动」的页面 */
const POLL_INTERVAL_MS = 30_000

const BANNER_ID = 'sycamore-build-version-banner'

/**
 * 用户点过「稍后」的那个远端 ID。
 *
 * 放在模块级是因为 `showBanner` 是模块级函数（它是**页面级**状态：
 * 「这一版新代码我已经知道了，别烦我」，与探针生命周期同义）。
 * ⚠️ 只对**这一个** ID 生效 —— 远端再更新一次仍要提示，
 *    否则「稍后」会退化成**永久静默**，那就把这条防线自己关了。
 */
let dismissedRemoteId: string | null = null

/** 页面加载时那一次构建的 ID（`vite.config.ts` 的 `define` 在编译期替换成字面量） */
function readLocalBuildId(): string {
  // `typeof` 对未声明的标识符是安全的（返回 'undefined'，不抛 ReferenceError），
  // 所以万一某个入口没经过 vite 注入，这里也只是不启用探针，不会炸页面。
  return typeof __BUILD_ID__ === 'string' ? __BUILD_ID__ : ''
}

/**
 * 启动版本探针。
 *
 * @returns 停止函数（页面生命周期内一般不需要调用）
 */
export function startBuildVersionWatch(): () => void {
  const localId = readLocalBuildId()

  if (!localId) {
    // 判断不了「我是谁」就没法判断新旧 —— **明说原因，不静默**（同项目判据：取不到要下发原因）
    console.info('[版本探针] 未取到本地构建 ID（__BUILD_ID__ 未注入），本次不启用')
    return () => {}
  }

  let stopped = false
  let inFlight = false

  async function probe(): Promise<void> {
    if (stopped || inFlight) return
    inFlight = true
    try {
      const res = await fetch(`${BUILD_ID_PATH}?t=${Date.now()}`, {
        // 双保险：服务端已回 `no-store`，这里再声明一次，
        // 免得反向代理/CDN 把这份「必须最新」的答案缓存住
        cache: 'no-store',
        credentials: 'same-origin',
      })
      if (!res.ok) return // 服务端不认这个路径 ⇒ 当作「不知道」，不提示（判据 1）
      const data = (await res.json()) as { buildId?: unknown } | null
      const remoteId = typeof data?.buildId === 'string' ? data.buildId : ''
      if (!remoteId) return // 同上：拿不到 ≠ 有新版本
      if (remoteId === localId) return // 判据 2：跟「页面加载时」比
      showBanner(localId, remoteId)
    } catch {
      // 判据 1：网络错误 / 解析失败 ⇒ **什么都不做**。
      // 这里刻意**不打日志** —— 30s 一次的轮询会把控制台刷满，
      // 而控制台刷屏本身就会掩盖真正要看的报错。
    } finally {
      inFlight = false
    }
  }

  const timer = window.setInterval(() => void probe(), POLL_INTERVAL_MS)

  // 用户切回标签页，就是「他正在看这个页面」的时刻 —— 等下一次 30s 轮询太慢，
  // 他可能十秒内就去点了那个「没反应」的按钮。
  function onVisibilityChange(): void {
    if (document.visibilityState === 'visible') void probe()
  }
  document.addEventListener('visibilitychange', onVisibilityChange)

  // 手动出口：控制台敲 `__sycamoreBuildCheck()` 立刻查一次。
  // 给「我怀疑这个页面是旧的」提供一个**当场可行**的取证手段，不必等 30 秒。
  const scope = window as unknown as Record<string, unknown>
  scope.__sycamoreBuildCheck = probe

  return () => {
    stopped = true
    window.clearInterval(timer)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    delete scope.__sycamoreBuildCheck
  }
}

function showBanner(localId: string, remoteId: string): void {
  if (remoteId === dismissedRemoteId) return // 判据 3 的另一半：点过「稍后」就别再烦他
  if (document.getElementById(BANNER_ID)) return

  const bar = document.createElement('div')
  bar.id = BANNER_ID
  bar.setAttribute('role', 'status')
  bar.style.cssText = [
    'position:fixed',
    'top:0',
    'left:0',
    'right:0',
    'z-index:99999', // 高于 Element Plus 的弹窗层（2000+），否则会被 dialog 盖住
    'display:flex',
    'align-items:center',
    'gap:12px',
    'padding:10px 16px',
    'background:#409eff',
    'color:#fff',
    'font-size:14px',
    'line-height:1.5',
    'box-shadow:0 2px 8px rgba(0,0,0,.15)',
  ].join(';')

  const text = document.createElement('span')
  text.textContent = '这个页面在运行旧版本代码 —— 部分操作可能没有反应。刷新后即恢复。'
  text.style.cssText = 'flex:1 1 auto'

  // 版本号对用户没用，对排障有用 —— 所以留着，但用小字弱化，不抢主文案
  const ids = document.createElement('code')
  ids.textContent = `${localId} → ${remoteId}`
  ids.style.cssText = 'font-size:12px;opacity:.75;white-space:nowrap'

  const later = document.createElement('button')
  later.type = 'button'
  later.textContent = '稍后'
  later.style.cssText = [
    'cursor:pointer',
    'border:1px solid rgba(255,255,255,.6)',
    'background:transparent',
    'color:#fff',
    'border-radius:4px',
    'padding:4px 12px',
    'font-size:13px',
  ].join(';')
  later.onclick = () => {
    dismissedRemoteId = remoteId
    bar.remove()
  }

  const reload = document.createElement('button')
  reload.type = 'button'
  reload.textContent = '立即刷新'
  reload.style.cssText = [
    'cursor:pointer',
    'border:1px solid #fff',
    'background:#fff',
    'color:#409eff',
    'border-radius:4px',
    'padding:4px 12px',
    'font-size:13px',
    'font-weight:600',
  ].join(';')
  reload.onclick = () => window.location.reload()

  bar.append(text, ids, later, reload)
  document.body.appendChild(bar)

  // 自证：让「探针发现了什么」留在控制台里，便于事后回溯
  console.info('[版本探针] 页面在跑旧代码：本地 %s / 服务端 %s', localId, remoteId)
}
