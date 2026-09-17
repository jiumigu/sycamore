/**
 * 全国「地级市」底图
 *
 * better-echarts-maps 只直接提供省级地图（`china.js` → `China`），但它的
 * `china-provinces.js` 实际是**按省打包的地级市 GeoJSON**（38 份，含 `-contour`
 * 描边副本）。这里把各省的要素合并成一张全国地级市地图，供旅行足迹做城市级热力。
 *
 * 合计 493 个可着色区域：地级市 + 自治州/地区/盟 + 直辖市下辖区县 + 省直辖县级市。
 * 全国范围内**区域名唯一**，可直接用名称做数据匹配。
 */
import * as echarts from 'echarts'
import betterEchartsMapsProvinces from 'better-echarts-maps/dist/china-provinces.js'
import betterEchartsMaps from 'better-echarts-maps/dist/china.js'

/** 注册到 ECharts 的地图名 */
export const CITY_MAP_NAME = 'china-cities'

/** 行政区划后缀（长的优先，避免「地区」只剥掉「区」） */
const SUFFIXES = ['地区', '市', '州', '盟', '县', '区']

/**
 * 旧称别名（数据里的现行名 → 地图上的区域名）
 * 地图数据停留在早年的区划版本，撤地设市/改名后的名称对不上，逐个兜底。
 */
const LEGACY_ALIAS: Record<string, string> = {
  克孜勒苏州: '克孜勒苏柯州',
  襄阳市: '襄樊市',
  桃园市: '桃园县',
  兴安盟盟: '兴安盟',
  锡林郭勒盟盟: '锡林郭勒盟',
  阿拉善盟盟: '阿拉善盟',
}

type GeoFeature = { properties?: { name?: string }; geometry?: { type?: string; coordinates?: unknown } }
type GeoJSON = { type: string; name: string; features: GeoFeature[] }

let geoJson: GeoJSON | null = null
let regionNames: Set<string> | null = null
let registered = false

function buildGeoJson(): GeoJSON {
  const pkg = betterEchartsMapsProvinces as unknown as {
    ChinaProvinces?: Array<[string, { features?: GeoFeature[] }]>
  }
  const features: GeoFeature[] = []
  ;(pkg.ChinaProvinces || []).forEach(([key, geo]) => {
    if (key.endsWith('-contour')) return // 描边副本，跳过
    ;(geo?.features || []).forEach((f) => features.push(f))
  })
  return { type: 'FeatureCollection', name: CITY_MAP_NAME, features }
}

/** 注册全国地级市地图（幂等），返回地图上的区域名集合 */
export function registerChinaCitiesMap(): Set<string> {
  if (!geoJson) geoJson = buildGeoJson()
  if (!registered) {
    echarts.registerMap(CITY_MAP_NAME, geoJson as never)
    registered = true
  }
  if (!regionNames) {
    regionNames = new Set(
      geoJson.features.map((f) => f.properties?.name || '').filter(Boolean)
    )
  }
  return regionNames
}

function stripSuffix(name: string): string {
  for (const s of SUFFIXES) {
    if (name.endsWith(s)) return name.slice(0, -s.length)
  }
  return name
}

/**
 * 把后端返回的地级市名对齐到地图区域名
 *
 * 容错顺序：精确匹配 → 去后缀后补各种后缀（「毕节市」↔地图「毕节地区」）→ 旧称别名。
 * 对齐失败返回 null，调用方应丢弃该条（ECharts 对未知区域名会静默忽略）。
 */
export function resolveRegionName(name: string): string | null {
  const set = registerChinaCitiesMap()
  if (!name) return null
  if (set.has(name)) return name

  const base = stripSuffix(name)
  const candidates = [base, ...SUFFIXES.map((s) => base + s), LEGACY_ALIAS[name]]
  for (const cand of candidates) {
    if (cand && set.has(cand)) return cand
  }
  return null
}

/**
 * 省级边界环（用于叠加在地级市底图上，让省界可见）
 *
 * 地级市底图只有市内边界时，整片未到访区域是一块灰色，看不出省的分界。
 * `china.js` 的省级边界（34 个省级单位，合计约 2600 个点）足够轻，
 * 交给 `lines` 系列以 polyline 形式画在最上层即可。
 */
let provinceRingsCache: number[][][] | null = null

export function getProvinceBorderRings(): number[][][] {
  if (provinceRingsCache) return provinceRingsCache

  const pkg = betterEchartsMaps as unknown as { China?: Array<[string, { features?: GeoFeature[] }]> }
  const rings: number[][][] = []
  ;(pkg.China || []).forEach(([, geo]) => {
    ;(geo?.features || []).forEach((f) => {
      const geom = f.geometry
      if (!geom?.coordinates) return
      if (geom.type === 'Polygon') {
        ;(geom.coordinates as number[][][]).forEach((ring) => rings.push(ring))
      } else {
        ;(geom.coordinates as number[][][][]).forEach((poly) => poly.forEach((ring) => rings.push(ring)))
      }
    })
  })
  provinceRingsCache = rings
  return rings
}
