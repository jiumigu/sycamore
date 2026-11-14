/**
 * 全国「省级」底图注册
 *
 * `better-echarts-maps/dist/china.js` 导出的不是一个可直接注册的 GeoJSON：
 * 它把 34 个省级单位打成一个数组（`China[0][1]` 才是 `FeatureCollection`），
 * 直接把模块对象丢给 `registerMap` 会让各省边界碎成一片散线。
 *
 * 🔴 这段「取 GeoJSON」的写法原先在 3 个页面里各抄了一遍（心愿 / 推演 / 计划地图），
 *    其中两处还用不同的运算符取兜底（`??` 与 `||`）。一处改、两处不改，
 *    症状是「某个页面的地图忽然多出一堆乱线」，而代码看起来一模一样。统一在这里。
 */
import * as echarts from 'echarts'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'

/** 注册到 ECharts 的地图名（省级） */
export const PROVINCE_MAP_NAME = 'china'

let registered = false

/** 注册全国省级地图（幂等）。返回可传给 `geo.map` 的名字 */
export function registerChinaProvinceMap(): string {
  if (registered) return PROVINCE_MAP_NAME
  const pkg = betterEchartsMaps as unknown as { China?: Array<[string, object]> }
  const geoJson = pkg.China?.[0]?.[1] ?? (betterEchartsMaps as unknown as object)
  echarts.registerMap(PROVINCE_MAP_NAME, geoJson as never)
  registered = true
  return PROVINCE_MAP_NAME
}
