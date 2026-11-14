/**
 * 路线视野：一组经纬度 → 地图中心与缩放
 *
 * 🔴 唯一实现在这里：路线推演页与计划内地图都要「把整条路线框进视野」，
 *    两处各写一份阈值表，迟早一处改了另一处没改（同一事实两把尺子）。
 *
 * ⚠️ 阈值是**经验刻度**，不是地理公式：ECharts 的 `zoom` 与视口像素宽高、
 *    卡片尺寸都有关，同一组点在窄容器里会自动显得更远。
 *    这里只保证「相近的量级给相近的缩放」，不追求把端点顶到画布边缘。
 */

export type LngLat = [number, number]

/** 没有可定位的点时的兜底视野（闽东一带，Sycamore 的默认活动区域） */
const FALLBACK_CENTER: LngLat = [118.3, 25.5]
const FALLBACK_ZOOM = 4

/** 单点也给了坐标（例如只有一站）时不要怼到街区级，留出周边省界 */
const SINGLE_ZOOM = 8

export function fitRouteView(coords: LngLat[]): { center: LngLat; zoom: number } {
  if (coords.length === 0) return { center: FALLBACK_CENTER, zoom: FALLBACK_ZOOM }

  const lngs = coords.map((c) => c[0])
  const lats = coords.map((c) => c[1])
  // 用均值而不是包围盒中点：与老版推演页的取景一致，换实现不换观感
  const center: LngLat = [
    lngs.reduce((s, v) => s + v, 0) / coords.length,
    lats.reduce((s, v) => s + v, 0) / coords.length,
  ]
  if (coords.length === 1) return { center, zoom: SINGLE_ZOOM }

  const maxRange = Math.max(
    Math.max(...lngs) - Math.min(...lngs),
    Math.max(...lats) - Math.min(...lats),
  )
  let zoom = 1.5
  if (maxRange < 0.5) zoom = 15
  else if (maxRange < 2) zoom = 10
  else if (maxRange < 5) zoom = 5
  else if (maxRange < 15) zoom = 3
  return { center, zoom }
}
